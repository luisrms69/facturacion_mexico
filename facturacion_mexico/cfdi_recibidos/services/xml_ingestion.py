"""
XMLIngestionService — carga, valida y persiste CFDIs recibidos.

Responsabilidades:
- Calcular SHA256 del XML
- Parsear con CFDIRecibidoParser
- Detectar duplicados por UUID
- Validar receiver_rfc contra company.tax_id
- Validar cfdi_type soportado (solo "I" — leído de sat.constants)
- Crear CFDI Recibido con conceptos y XML adjunto
- Resolver proveedor por Supplier.tax_id

Pipeline termina en proveedor. Clasificación y PI son hitos posteriores.
"""

import hashlib

import frappe
from frappe import _
from frappe.utils.file_manager import save_file

from facturacion_mexico.cfdi_recibidos.parsers.cfdi_recibido_parser import CFDIRecibidoParser
from facturacion_mexico.cfdi_recibidos.services.status_manager import (
	compute_stage,
	get_next_action,
	get_stage_message,
)
from facturacion_mexico.cfdi_recibidos.services.supplier_resolver import (
	generate_missing_suppliers as _generate_suppliers,
)
from facturacion_mexico.cfdi_recibidos.services.supplier_resolver import (
	resolve_supplier as _resolve_supplier,
)
from facturacion_mexico.sat.constants import TIPO_COMPROBANTE

# Tipos CFDI aceptados para el flujo de compras recibidas
_TIPOS_COMPRA = {"I"}


def ingest_xml(xml_bytes: bytes, company: str, file_name: str = "cfdi.xml") -> dict:
	"""
	Procesa un XML CFDI recibido y lo persiste como CFDI Recibido.

	Pipeline: parseo → validación RFC → validación tipo → inserción → resolver proveedor.
	Clasificación de conceptos y generación de PI son hitos posteriores.

	Retorna dict con:
	    status              — "XML inválido" | "duplicado" | "No aplicable" |
	                          "Falta proveedor" | "Proveedor encontrado"
	    cfdi_recibido       — nombre del doc creado (None si no se creó)
	    uuid                — UUID extraído (None si error antes del parseo)
	    supplier_rfc        — RFC del emisor del XML
	    supplier_found      — True si se asignó Supplier existente
	    candidato_generar_proveedor — True si es candidato para acción futura
	    message             — descripción del resultado
	    next_action         — acción sugerida al usuario
	"""
	if not xml_bytes:
		return _result("XML inválido", None, None, None, False, False, "XML vacío", None)

	xml_hash = _sha256(xml_bytes)

	# Paso 1: parsear
	try:
		parser = CFDIRecibidoParser(xml_bytes)
		data = parser.parse()
	except Exception as e:
		return _result("XML inválido", None, None, None, False, False, str(e), None)

	uuid = data.get("uuid", "")
	supplier_rfc = data.get("supplier_rfc", "")

	# Paso 2: detectar duplicado por UUID
	if uuid:
		existing_name = frappe.db.get_value("CFDI Recibido", {"uuid": uuid}, "name")
		if existing_name:
			return _result(
				"duplicado",
				existing_name,
				uuid,
				supplier_rfc,
				False,
				False,
				f"UUID ya existe: {existing_name}",
				None,
			)

	# Paso 3: validar receiver_rfc contra company — sin doc si no coincide
	company_rfc = frappe.db.get_value("Company", company, "tax_id") or ""
	receiver_rfc = data.get("receiver_rfc", "")
	if not (company_rfc and receiver_rfc.upper() == company_rfc.upper()):
		msg = _("El receptor del CFDI ({0}) no corresponde al RFC de la empresa ({1}).").format(
			receiver_rfc, company_rfc or "sin RFC configurado"
		)
		return _result("XML inválido", None, uuid, supplier_rfc, False, False, msg, None)

	# Paso 4: validar tipo CFDI
	cfdi_type = data.get("cfdi_type", "")
	if cfdi_type not in _TIPOS_COMPRA:
		tipo_label = TIPO_COMPROBANTE.get(cfdi_type, cfdi_type)
		doc = _crear_doc(company, xml_hash, data, "No aplicable")
		doc.error_message = _("Tipo CFDI '{0}' ({1}) no es aplicable a este flujo.").format(
			cfdi_type, tipo_label
		)
		doc.save(ignore_permissions=True)
		_adjuntar_xml(doc, xml_bytes, file_name)
		return _result(
			"No aplicable",
			doc.name,
			uuid,
			supplier_rfc,
			False,
			False,
			_("Tipo {0} no aplicable al flujo de compras").format(cfdi_type),
			None,
		)

	# Paso 5: crear CFDI Recibido
	doc = _crear_doc(company, xml_hash, data, "Falta proveedor")
	_adjuntar_xml(doc, xml_bytes, file_name)

	# Paso 6: resolver proveedor existente por RFC
	_resolve_supplier(doc.name)
	doc.reload()

	# Paso 7: auto-crear proveedor si no se encontró uno existente
	supplier_created = False
	if doc.status == "Falta proveedor":
		gen = _generate_suppliers([doc.name])
		if gen.get("creados", 0) > 0:
			supplier_created = True
			doc.reload()

	# Avanzar al estado completo del pipeline cuando hay supplier asignado
	if doc.supplier:
		next_stage = compute_stage(doc)
		if doc.status != next_stage:
			doc.db_set("status", next_stage)
			doc.reload()

	stage = doc.status
	supplier_found = bool(doc.supplier)
	candidato = stage == "Falta proveedor"

	if supplier_created:
		message = _("Proveedor nuevo creado automáticamente — revísalo y complétalo")
	else:
		message = get_stage_message(stage)

	supplier_name = ""
	if doc.supplier:
		supplier_name = frappe.db.get_value("Supplier", doc.supplier, "supplier_name") or doc.supplier

	return _result(
		stage,
		doc.name,
		uuid,
		supplier_rfc,
		supplier_found,
		candidato,
		message,
		get_next_action(stage),
		supplier_created=supplier_created,
		supplier=doc.supplier or "",
		supplier_name=supplier_name,
	)


def _crear_doc(company: str, xml_hash: str, data: dict, status: str):
	"""Crea e inserta un CFDI Recibido con los datos del parseo."""
	doc = frappe.new_doc("CFDI Recibido")
	doc.company = company
	doc.xml_hash = xml_hash
	doc.status = status
	_populate_fields(doc, data)
	for c in data.get("conceptos", []):
		doc.append("conceptos", c)
	doc.insert(ignore_permissions=True)
	return doc


def _adjuntar_xml(doc, xml_bytes: bytes, file_name: str):
	file_doc = save_file(
		fname=file_name,
		content=xml_bytes,
		dt="CFDI Recibido",
		dn=doc.name,
		is_private=True,
	)
	doc.db_set("xml_file", file_doc.file_url)


def _populate_fields(doc, data: dict) -> None:
	"""Copia los campos del parseo al documento."""
	scalar_fields = [
		"uuid",
		"version",
		"cfdi_type",
		"serie",
		"folio",
		"issue_date",
		"currency",
		"exchange_rate",
		"fm_payment_method_sat",
		"fm_payment_form_sat",
		"uso_cfdi",
		"subtotal",
		"discount",
		"total",
		"total_impuestos_trasladados",
		"total_impuestos_retenidos",
		"impuestos_json",
		"supplier_rfc",
		"supplier_name",
		"supplier_tax_regime",
		"receiver_rfc",
		"receiver_name",
		"fecha_timbrado",
		"rfc_pac",
		"no_certificado_sat",
		"no_certificado_emisor",
	]
	for field in scalar_fields:
		if field in data:
			setattr(doc, field, data[field])


def _sha256(content: bytes) -> str:
	return hashlib.sha256(content).hexdigest()


def _result(
	status: str,
	cfdi_recibido: str | None,
	uuid: str | None,
	supplier_rfc: str | None,
	supplier_found: bool,
	candidato_generar_proveedor: bool,
	message: str,
	next_action: str | None,
	*,
	supplier_created: bool = False,
	supplier: str = "",
	supplier_name: str = "",
) -> dict:
	return {
		"status": status,
		"cfdi_recibido": cfdi_recibido,
		"uuid": uuid,
		"supplier_rfc": supplier_rfc,
		"supplier_found": supplier_found,
		"candidato_generar_proveedor": candidato_generar_proveedor,
		"message": message,
		"next_action": next_action,
		"supplier_created": supplier_created,
		"supplier": supplier,
		"supplier_name": supplier_name,
	}
