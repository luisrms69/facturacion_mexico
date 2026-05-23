"""
XMLIngestionService — carga, valida y persiste CFDIs recibidos.

Responsabilidades:
- Calcular SHA256 del XML
- Parsear con CFDIRecibidoParser
- Detectar duplicados por UUID
- Validar receiver_rfc contra company.tax_id
- Crear CFDI Recibido con conceptos y XML adjunto
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils.file_manager import save_file

from facturacion_mexico.cfdi_recibidos.parsers.cfdi_recibido_parser import CFDIRecibidoParser


def ingest_xml(xml_bytes: bytes, company: str, file_name: str = "cfdi.xml") -> dict:
	"""
	Procesa un XML CFDI recibido y lo persiste como CFDI Recibido.

	Retorna dict con:
	    status: "ok" | "duplicado" | "error"
	    cfdi_recibido: nombre del doc creado (o None si duplicado/error sin doc)
	    uuid: UUID extraído (o None si error antes del parseo)
	    message: descripción del resultado
	"""
	if not xml_bytes:
		return _result("error", None, None, "XML vacío")

	xml_hash = _sha256(xml_bytes)

	# Paso 1: parsear
	try:
		parser = CFDIRecibidoParser(xml_bytes)
		data = parser.parse()
	except Exception as e:
		return _result("error", None, None, str(e))

	uuid = data.get("uuid", "")

	# Paso 2: detectar duplicado por UUID
	if uuid:
		existing = frappe.db.get_value("CFDI Recibido", {"uuid": uuid}, "name")
		if existing:
			return _result("duplicado", existing, uuid, f"UUID ya existe: {existing}")

	# Paso 3: validar receiver_rfc contra company
	company_rfc = frappe.db.get_value("Company", company, "tax_id") or ""
	receiver_rfc = data.get("receiver_rfc", "")
	rfc_matches = company_rfc and receiver_rfc.upper() == company_rfc.upper()

	# Paso 4: crear CFDI Recibido
	doc = frappe.new_doc("CFDI Recibido")
	doc.company = company
	doc.xml_hash = xml_hash

	# Poblar campos del parseo
	_populate_fields(doc, data)

	if not rfc_matches:
		doc.status = "Error"
		doc.error_message = _("El receptor del CFDI ({0}) no corresponde al RFC de la empresa ({1}).").format(
			receiver_rfc, company_rfc or "sin RFC configurado"
		)
	else:
		doc.status = "Parseado"

	# Crear child rows de conceptos
	for c in data.get("conceptos", []):
		doc.append("conceptos", c)

	doc.insert(ignore_permissions=True)

	# Paso 5: adjuntar XML original
	file_doc = save_file(
		fname=file_name,
		content=xml_bytes,
		dt="CFDI Recibido",
		dn=doc.name,
		is_private=True,
	)
	doc.db_set("xml_file", file_doc.file_url)

	status = "ok" if rfc_matches else "error"
	message = "CFDI procesado correctamente" if rfc_matches else doc.error_message
	return _result(status, doc.name, uuid, message)


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


def _result(status: str, cfdi_recibido: str | None, uuid: str | None, message: str) -> dict:
	return {
		"status": status,
		"cfdi_recibido": cfdi_recibido,
		"uuid": uuid,
		"message": message,
	}
