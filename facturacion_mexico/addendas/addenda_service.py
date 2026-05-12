"""
AddendaService — Motor neutral para addendas CFDI (Issue #129, Fase 2).

Responsabilidades:
  - Resolver si una Sales Invoice requiere addenda
  - Validar configuración (tipo existe y activo)
  - Validar datos obligatorios por tipo
  - Renderizar XML de addenda
  - Devolver formato listo para FacturAPI: {addenda_xml, namespaces, metadata}

NO acoplado a FacturAPI directamente.
NO registra hooks.
NO activa Sales Invoice.validate ni on_submit.
Usado por _prepare_facturapi_data() (pre-timbrado) en Fase 4.

Regla crítica: render() retorna None si la SI no requiere addenda.
El llamador SOLO agrega payload["addenda"] y payload["namespaces"] si render() != None.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint


class AddendaService:
	"""Motor neutral para preparar addendas CFDI para pre-timbrado FacturAPI."""

	def is_required(self, sales_invoice_doc) -> bool:
		"""¿Esta SI requiere addenda?"""
		return cint(sales_invoice_doc.get("fm_addenda_required")) == 1

	def get_addenda_type_name(self, sales_invoice_doc) -> str | None:
		"""Tipo de addenda configurado en la SI."""
		return sales_invoice_doc.get("fm_addenda_type") or None

	def validate_config(self, sales_invoice_doc) -> None:
		"""Validar que hay tipo configurado y está activo. frappe.throw si falla."""
		if not self.is_required(sales_invoice_doc):
			return

		addenda_type = self.get_addenda_type_name(sales_invoice_doc)
		if not addenda_type:
			frappe.throw(
				_(
					"La factura requiere addenda pero no tiene tipo de addenda configurado "
					"(campo fm_addenda_type vacío)."
				)
			)

		if not frappe.db.exists("Addenda Type", addenda_type):
			frappe.throw(_("Tipo de addenda '{0}' no existe.").format(addenda_type))

		addenda_type_doc = frappe.get_cached_doc("Addenda Type", addenda_type)
		if not addenda_type_doc.is_active:
			frappe.throw(_("Tipo de addenda '{0}' no está activo.").format(addenda_type))

		if not addenda_type_doc.xml_template:
			frappe.throw(_("Tipo de addenda '{0}' no tiene template XML configurado.").format(addenda_type))

	def validate_required_data(self, sales_invoice_doc, addenda_values: dict) -> None:
		"""Validar que los campos obligatorios del tipo tienen valor. frappe.throw si faltan."""
		if not self.is_required(sales_invoice_doc):
			return

		addenda_type = self.get_addenda_type_name(sales_invoice_doc)
		if not addenda_type:
			return

		try:
			addenda_type_doc = frappe.get_cached_doc("Addenda Type", addenda_type)
		except frappe.DoesNotExistError:
			return

		missing = []
		for fd in addenda_type_doc.field_definitions or []:
			if fd.is_mandatory and not addenda_values.get(fd.field_name):
				missing.append(fd.field_label or fd.field_name)

		if missing:
			frappe.throw(
				_("La addenda tipo '{0}' requiere los siguientes datos que faltan: {1}").format(
					addenda_type, ", ".join(missing)
				)
			)

	def render(
		self,
		sales_invoice_doc,
		addenda_values: dict | None = None,
	) -> dict | None:
		"""Renderizar addenda para incluir en payload FacturAPI.

		Returns:
		    None — si la SI no requiere addenda (NO incluir campo en payload)
		    dict — si requiere addenda:
		        {
		            "addenda_xml": str,           # XML string listo para FacturAPI
		            "namespaces": [               # formato FacturAPI
		                {"prefix": str, "uri": str}
		            ],
		            "metadata": {
		                "addenda_type": str,
		                "namespace_uri": str,
		                "namespace_prefix": str,
		            },
		            "errors": [],
		        }

		Raises:
		    frappe.ValidationError — si requiere addenda pero hay error de config o datos
		"""
		if not self.is_required(sales_invoice_doc):
			return None

		addenda_type = self.get_addenda_type_name(sales_invoice_doc)

		# Validar configuración completa
		self.validate_config(sales_invoice_doc)

		# Resolver valores de addenda
		if addenda_values is None:
			addenda_values = self._get_default_values(sales_invoice_doc)

		# Validar datos obligatorios
		self.validate_required_data(sales_invoice_doc, addenda_values)

		# Generar XML usando AddendaGenerator existente
		from facturacion_mexico.addendas.generic_addenda_generator import AddendaGenerator

		generator = AddendaGenerator(addenda_type)

		invoice_data = (
			sales_invoice_doc.as_dict() if hasattr(sales_invoice_doc, "as_dict") else dict(sales_invoice_doc)
		)
		result = generator.generate(invoice_data, addenda_values)

		if not result.get("success"):
			errors = result.get("validation_errors") or [
				result.get("message", "Error desconocido en generación de addenda")
			]
			frappe.throw(
				_("Error generando addenda tipo '{0}': {1}").format(
					addenda_type, "; ".join(str(e) for e in errors)
				)
			)

		addenda_xml = result["xml_content"]

		# Obtener namespace del DocType Addenda Type
		addenda_type_doc = frappe.get_cached_doc("Addenda Type", addenda_type)
		namespace_uri = addenda_type_doc.namespace or ""
		namespace_prefix = self._derive_prefix(addenda_type)

		# Formato FacturAPI: array de {prefix, uri} — solo si hay namespace
		namespaces = []
		if namespace_uri:
			namespaces = [{"prefix": namespace_prefix, "uri": namespace_uri}]

		return {
			"addenda_xml": addenda_xml,
			"namespaces": namespaces,
			"metadata": {
				"addenda_type": addenda_type,
				"namespace_uri": namespace_uri,
				"namespace_prefix": namespace_prefix,
			},
			"errors": [],
		}

	def _get_default_values(self, sales_invoice_doc) -> dict:
		"""Obtener valores por defecto de addenda desde Customer.fm_addenda_defaults."""
		customer = sales_invoice_doc.get("customer")
		if not customer:
			return {}

		addenda_type = self.get_addenda_type_name(sales_invoice_doc)
		if not addenda_type:
			return {}

		from facturacion_mexico.addendas.generic_addenda_generator import get_customer_addenda_defaults

		return get_customer_addenda_defaults(customer, addenda_type)

	def _derive_prefix(self, addenda_type: str) -> str:
		"""Derivar prefix XML válido del nombre del tipo de addenda.

		Ejemplos: "WALMART" → "walmart", "SAP ERP v2" → "saperp", "odoo-1" → "odoo"
		El prefix se usa en payload["namespaces"][0]["prefix"].
		"""
		clean = re.sub(r"[^a-zA-Z0-9]", "", addenda_type.lower())
		return clean[:20] or "addenda"
