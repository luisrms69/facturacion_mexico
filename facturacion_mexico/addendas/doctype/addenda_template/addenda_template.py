"""
Addenda Template DocType - Sprint 3
Template XML para tipos de addenda
"""

import xml.dom.minidom
from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document
from lxml import etree


class AddendaTemplate(Document):
	"""DocType para templates XML de addendas."""

	def validate(self):
		"""Validaciones del template."""
		self.validate_xml_template()
		self.validate_default_template()
		self.set_audit_fields()

	def validate_xml_template(self):
		"""Validar que el template XML sea válido."""
		if not self.template_xml:
			frappe.throw(_("Template XML es requerido"))

		try:
			# Verificar que sea XML válido usando parsing seguro
			from facturacion_mexico.utils.secure_xml import secure_parse_xml

			secure_parse_xml(self.template_xml, parser_type="lxml")

			# Verificar que tenga variables válidas
			self.validate_template_variables()

		except etree.XMLSyntaxError as e:
			frappe.throw(_("Template XML inválido: {0}").format(str(e)))
		except Exception as e:
			frappe.throw(_("Error validando template: {0}").format(str(e)))

	def validate_template_variables(self):
		"""Validar variables en el template."""
		import re

		# Buscar variables {{ variable }}
		variables = re.findall(r"\{\{([^}]+)\}\}", self.template_xml)

		if not variables:
			frappe.msgprint(_("Template no contiene variables dinámicas"), indicator="orange")
			return

		# Verificar variables válidas
		for var in variables:
			var = var.strip()

			# Variables básicas permitidas
			valid_patterns = [
				r"^[a-zA-Z_][a-zA-Z0-9_]*$",  # Variable simple
				r"^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$",  # Variable con punto
				r"^[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\)$",  # Función
			]

			if not any(re.match(pattern, var) for pattern in valid_patterns):
				frappe.msgprint(_("Variable posiblemente inválida: {0}").format(var), indicator="orange")

	def validate_default_template(self):
		"""Validar que solo haya un template por defecto por tipo."""
		if self.is_default:
			existing = frappe.get_all(
				"Addenda Template",
				filters={"addenda_type": self.addenda_type, "is_default": 1, "name": ["!=", self.name]},
				limit=1,
			)

			if existing:
				frappe.throw(
					_("Ya existe un template por defecto para el tipo {0}").format(self.addenda_type)
				)

	def set_audit_fields(self):
		"""Establecer campos de auditoría."""
		if self.is_new():
			self.created_by = frappe.session.user
			self.created_date = frappe.utils.now()

		self.modified_by = frappe.session.user
		self.modified_date = frappe.utils.now()

	def get_template_variables(self) -> list[str]:
		"""Obtener lista de variables en el template."""
		import re

		variables = re.findall(r"\{\{([^}]+)\}\}", self.template_xml)
		return [var.strip() for var in variables]

	def preview_template(self, sample_data: dict | None = None) -> str:
		"""Generar preview del template con datos de muestra."""
		if not sample_data:
			sample_data = self.get_sample_data()

		try:
			from facturacion_mexico.addendas.parsers.xml_builder import AddendaXMLBuilder

			builder = AddendaXMLBuilder(self.template_xml, sample_data)
			preview = builder.replace_variables().build()

			# Formatear para mejor visualización
			dom = xml.dom.minidom.parseString(preview)
			return dom.toprettyxml(indent="  ")

		except Exception as e:
			return _("Error generando preview: {0}").format(str(e))

	def get_sample_data(self) -> dict:
		"""Generar datos de muestra para el template."""
		variables = self.get_template_variables()
		sample_data = {}

		for var in variables:
			# Generar valor de muestra basado en el nombre de la variable
			if any(keyword in var.lower() for keyword in ["fecha", "date"]):
				sample_data[var] = "2025-07-20"
			elif any(keyword in var.lower() for keyword in ["monto", "amount", "total"]):
				sample_data[var] = "1000.00"
			elif any(keyword in var.lower() for keyword in ["codigo", "code"]):
				sample_data[var] = "ABC123"
			elif any(keyword in var.lower() for keyword in ["folio", "numero"]):
				sample_data[var] = "12345"
			else:
				sample_data[var] = f"Valor_{var}"

		return sample_data

	def validate_against_xsd(self, sample_data: dict | None = None) -> dict:
		"""Validar template contra XSD del tipo de addenda."""
		try:
			# Obtener tipo de addenda
			addenda_type_doc = frappe.get_doc("Addenda Type", self.addenda_type)

			if not addenda_type_doc.xsd_schema:
				return {"valid": True, "message": _("No hay esquema XSD para validar"), "errors": []}

			# Generar XML con datos de muestra
			test_xml = self.preview_template(sample_data)

			# Validar contra XSD
			from facturacion_mexico.addendas.validators.xsd_validator import XSDValidator

			validator = XSDValidator(addenda_type_doc.xsd_schema)
			is_valid, errors, warnings = validator.validate_with_details(test_xml)

			return {
				"valid": is_valid,
				"message": _("Validación completada"),
				"errors": errors,
				"warnings": warnings,
			}

		except Exception as e:
			return {
				"valid": False,
				"message": _("Error durante validación: {0}").format(str(e)),
				"errors": [str(e)],
			}

	def clone_template(self, new_name: str, new_version: str) -> str:
		"""Clonar template con nuevo nombre y versión."""
		new_doc = frappe.copy_doc(self)
		new_doc.template_name = new_name
		new_doc.version = new_version
		new_doc.is_default = 0  # El clon no puede ser por defecto
		new_doc.insert()

		return new_doc.name

	def get_usage_stats(self) -> dict:
		"""Obtener estadísticas de uso del template."""
		try:
			# Contar configuraciones que usan este template
			configurations = frappe.get_all(
				"Addenda Configuration",
				filters={"addenda_type": self.addenda_type},
				fields=["name", "customer"],
			)

			# Contar facturas recientes que podrían usar este template
			recent_invoices = frappe.get_all(
				"Sales Invoice",
				filters={
					"docstatus": 1,
					"posting_date": [">", frappe.utils.add_days(frappe.utils.today(), -30)],
				},
				limit=1000,
			)

			return {
				"configurations_count": len(configurations),
				"recent_invoices": len(recent_invoices),
				"template_age_days": frappe.utils.date_diff(frappe.utils.today(), self.created_date),
			}

		except Exception as e:
			frappe.log_error(f"Error obteniendo estadísticas de template: {e!s}")
			return {"configurations_count": 0, "recent_invoices": 0, "template_age_days": 0}

	@staticmethod
	def create_sample_template(addenda_type: str, template_name: str = "Template Básico") -> str:
		"""Crear template de muestra para un tipo de addenda."""
		# Template XML básico
		basic_template = """<?xml version="1.0" encoding="UTF-8"?>
<addenda>
	<informacionGeneral>
		<fechaEmision>{{ cfdi_fecha }}</fechaEmision>
		<folioFiscal>{{ cfdi_uuid }}</folioFiscal>
		<montoTotal>{{ cfdi_total }}</montoTotal>
	</informacionGeneral>
	<proveedor>
		<rfc>{{ emisor_rfc }}</rfc>
		<razonSocial>{{ emisor_nombre }}</razonSocial>
	</proveedor>
	<cliente>
		<rfc>{{ receptor_rfc }}</rfc>
		<razonSocial>{{ receptor_nombre }}</razonSocial>
	</cliente>
	<conceptos>
		{% for concepto in conceptos %}
		<concepto>
			<descripcion>{{ concepto.descripcion }}</descripcion>
			<cantidad>{{ concepto.cantidad }}</cantidad>
			<valorUnitario>{{ concepto.valor_unitario }}</valorUnitario>
			<importe>{{ concepto.importe }}</importe>
		</concepto>
		{% endfor %}
	</conceptos>
</addenda>"""

		# Crear documento
		doc = frappe.new_doc("Addenda Template")
		doc.addenda_type = addenda_type
		doc.template_name = template_name
		doc.version = "1.0"
		doc.description = f"Template básico para {addenda_type}"
		doc.template_xml = basic_template
		doc.is_default = 1
		doc.insert()

		return doc.name


# Métodos para hooks
def on_doctype_update():
	"""Ejecutar cuando se actualiza el DocType."""
	frappe.db.add_index("Addenda Template", ["addenda_type", "is_default"])


def get_permission_query_conditions(user):
	"""Condiciones de permisos para consultas."""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	# Los usuarios solo pueden ver templates de tipos de addenda activos
	return """(`tabAddenda Template`.`addenda_type` in (
		select name from `tabAddenda Type` where is_active = 1
	))"""


def has_permission(doc, user):
	"""Verificar permisos específicos del documento."""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	# Verificar que el tipo de addenda esté activo
	try:
		addenda_type_doc = frappe.get_doc("Addenda Type", doc.addenda_type)
		return addenda_type_doc.is_active
	except Exception:
		return False
