"""
Custom Fields para Sales Invoice - Sistema de Addendas
Sprint 3 - Facturación México
"""

from typing import Any

import frappe
from frappe import _
from frappe.utils import now


def create_sales_invoice_addenda_fields():
	"""Crear campos personalizados para Sales Invoice relacionados con addendas."""

	# Definir los campos a agregar
	custom_fields = [
		{
			"fieldname": "fm_addenda_section",
			"fieldtype": "Section Break",
			"label": "Información de Addenda",
			"insert_after": "fm_section_break_cfdi",  # Después de sección CFDI
			"depends_on": "eval:doc.docstatus == 1",
			"collapsible": 1,
		},
		{
			"fieldname": "fm_addenda_required",
			"fieldtype": "Check",
			"label": "Requiere Addenda",
			"insert_after": "fm_addenda_section",
			"read_only": 1,
			"default": 0,
		},
		{
			"fieldname": "fm_addenda_type",
			"fieldtype": "Link",
			"label": "Tipo de Addenda",
			"options": "Addenda Type",
			"insert_after": "fm_addenda_required",
			"read_only": 1,
			"depends_on": "fm_addenda_required",
		},
		{
			"fieldname": "fm_addenda_status",
			"fieldtype": "Select",
			"label": "Estado de Addenda",
			"options": "\nPendiente\nGenerando\nCompletada\nError",
			"insert_after": "fm_addenda_type",
			"read_only": 1,
			"depends_on": "fm_addenda_required",
		},
		{
			"fieldname": "fm_addenda_column_break",
			"fieldtype": "Column Break",
			"insert_after": "fm_addenda_status",
		},
		{
			"fieldname": "fm_addenda_xml",
			"fieldtype": "Code",
			"label": "XML de Addenda",
			"options": "XML",
			"insert_after": "fm_addenda_column_break",
			"read_only": 1,
			"depends_on": "eval:doc.fm_addenda_status == 'Completada'",
		},
		{
			"fieldname": "fm_addenda_errors",
			"fieldtype": "Small Text",
			"label": "Errores de Addenda",
			"insert_after": "fm_addenda_xml",
			"read_only": 1,
			"depends_on": "eval:doc.fm_addenda_status == 'Error'",
		},
		{
			"fieldname": "fm_addenda_generated_date",
			"fieldtype": "Datetime",
			"label": "Fecha Generación Addenda",
			"insert_after": "fm_addenda_errors",
			"read_only": 1,
			"depends_on": "eval:doc.fm_addenda_status == 'Completada'",
		},
	]

	# Crear los custom fields
	for field in custom_fields:
		create_custom_field("Sales Invoice", field)

	print("✅ Custom fields de addenda agregados a Sales Invoice")


def create_customer_addenda_fields():
	"""Crear campos personalizados para Customer relacionados con addendas."""

	custom_fields = [
		{
			"fieldname": "fm_addenda_info_section",
			"fieldtype": "Section Break",
			"label": "Configuración de Addendas",
			"insert_after": "more_info",  # Después de información adicional
			"collapsible": 1,
		},
		{
			"fieldname": "fm_requires_addenda",
			"fieldtype": "Check",
			"label": "Requiere Addenda",
			"insert_after": "fm_addenda_info_section",
			"default": 0,
		},
		{
			"fieldname": "fm_default_addenda_type",
			"fieldtype": "Link",
			"label": "Tipo de Addenda Por Defecto",
			"options": "Addenda Type",
			"insert_after": "fm_requires_addenda",
			"depends_on": "fm_requires_addenda",
		},
	]

	# Crear los custom fields
	for field in custom_fields:
		create_custom_field("Customer", field)

	print("✅ Custom fields de addenda agregados a Customer")


def create_custom_field(doctype: str, field_config: dict):
	"""Crear un custom field específico."""
	try:
		# Verificar si el campo ya existe
		existing = frappe.get_all(
			"Custom Field", filters={"dt": doctype, "fieldname": field_config["fieldname"]}, limit=1
		)

		if existing:
			print(f"⚠️  Campo {field_config['fieldname']} ya existe en {doctype}")
			return

		# Crear el custom field
		custom_field = frappe.new_doc("Custom Field")
		custom_field.dt = doctype
		custom_field.fieldname = field_config["fieldname"]
		custom_field.fieldtype = field_config["fieldtype"]
		custom_field.label = field_config.get("label", "")
		custom_field.insert_after = field_config.get("insert_after")
		custom_field.options = field_config.get("options", "")
		custom_field.read_only = field_config.get("read_only", 0)
		custom_field.default = field_config.get("default", "")
		custom_field.depends_on = field_config.get("depends_on", "")
		custom_field.collapsible = field_config.get("collapsible", 0)
		custom_field.description = field_config.get("description", "")

		custom_field.insert()

		print(f"✅ Campo {field_config['fieldname']} creado en {doctype}")

	except Exception as e:
		print(f"❌ Error creando campo {field_config['fieldname']} en {doctype}: {e!s}")


def remove_sales_invoice_addenda_fields():
	"""Remover campos personalizados de Sales Invoice."""
	field_names = [
		"fm_addenda_section",
		"fm_addenda_required",
		"fm_addenda_type",
		"fm_addenda_status",
		"fm_addenda_column_break",
		"fm_addenda_xml",
		"fm_addenda_errors",
		"fm_addenda_generated_date",
	]

	remove_custom_fields("Sales Invoice", field_names)


def remove_customer_addenda_fields():
	"""Remover campos personalizados de Customer."""
	field_names = ["fm_addenda_info_section", "fm_requires_addenda", "fm_default_addenda_type"]

	remove_custom_fields("Customer", field_names)


def remove_custom_fields(doctype: str, field_names: list[str]):
	"""Remover una lista de custom fields."""
	for field_name in field_names:
		try:
			# Buscar el custom field
			custom_fields = frappe.get_all("Custom Field", filters={"dt": doctype, "fieldname": field_name})

			# Eliminar si existe
			for cf in custom_fields:
				frappe.delete_doc("Custom Field", cf.name)
				print(f"✅ Campo {field_name} removido de {doctype}")

		except Exception as e:
			print(f"❌ Error removiendo campo {field_name} de {doctype}: {e!s}")


def update_addenda_status(sales_invoice: str, status: str, addenda_xml: str = "", errors: str = ""):
	"""Actualizar estado de addenda en Sales Invoice."""
	try:
		# Actualizar directamente en la base de datos para evitar validaciones
		update_data = {"fm_addenda_status": status, "modified": now(), "modified_by": frappe.session.user}

		if status == "Completada" and addenda_xml:
			update_data.update(
				{"fm_addenda_xml": addenda_xml, "fm_addenda_generated_date": now(), "fm_addenda_errors": ""}
			)
		elif status == "Error" and errors:
			update_data.update(
				{"fm_addenda_errors": errors, "fm_addenda_xml": "", "fm_addenda_generated_date": ""}
			)

		frappe.db.set_value("Sales Invoice", sales_invoice, update_data)
		frappe.db.commit()

	except Exception as e:
		frappe.log_error(f"Error actualizando estado de addenda: {e!s}")


def check_addenda_requirement(sales_invoice_doc):
	"""Verificar si la factura requiere addenda y actualizar campos."""
	try:
		# Verificar configuración del cliente
		from facturacion_mexico.addendas.api import get_addenda_requirements

		requirements = get_addenda_requirements(sales_invoice_doc.customer)

		if requirements.get("requires_addenda"):
			config = requirements.get("configuration")

			# Actualizar campos de addenda
			frappe.db.set_value(
				"Sales Invoice",
				sales_invoice_doc.name,
				{
					"fm_addenda_required": 1,
					"fm_addenda_type": config.get("addenda_type"),
					"fm_addenda_status": "Pendiente" if config.get("auto_apply") else "",
				},
			)
		else:
			# Limpiar campos si no requiere addenda
			frappe.db.set_value(
				"Sales Invoice",
				sales_invoice_doc.name,
				{"fm_addenda_required": 0, "fm_addenda_type": "", "fm_addenda_status": ""},
			)

		frappe.db.commit()

	except Exception as e:
		frappe.log_error(f"Error verificando requerimiento de addenda: {e!s}")


def auto_generate_addenda(sales_invoice_doc):
	"""Generar automáticamente addenda si está configurado."""
	try:
		# Solo si está configurado para auto-aplicar
		if not sales_invoice_doc.get("fm_addenda_required"):
			return

		# Verificar que esté en estado pendiente
		if sales_invoice_doc.get("fm_addenda_status") != "Pendiente":
			return

		# Actualizar estado a generando
		update_addenda_status(sales_invoice_doc.name, "Generando")

		# Generar addenda
		from facturacion_mexico.addendas.api import generate_addenda_xml

		result = generate_addenda_xml(sales_invoice_doc.name, validate_output=True)

		if result.get("success"):
			# Addenda generada exitosamente
			update_addenda_status(sales_invoice_doc.name, "Completada", addenda_xml=result.get("xml", ""))

			# Insertar en CFDI si está disponible
			if sales_invoice_doc.get("fm_cfdi_xml") and result.get("xml"):
				try:
					from facturacion_mexico.addendas.parsers.cfdi_parser import CFDIParser

					parser = CFDIParser(sales_invoice_doc.fm_cfdi_xml)
					modified_cfdi = parser.insert_addenda(result["xml"])

					# Actualizar CFDI con addenda
					frappe.db.set_value(
						"Sales Invoice", sales_invoice_doc.name, {"fm_cfdi_xml": modified_cfdi}
					)

				except Exception as e:
					frappe.log_error(f"Error insertando addenda en CFDI: {e!s}")
		else:
			# Error generando addenda
			update_addenda_status(
				sales_invoice_doc.name, "Error", errors=result.get("message", "Error desconocido")
			)

	except Exception as e:
		frappe.log_error(f"Error en generación automática de addenda: {e!s}")
		update_addenda_status(sales_invoice_doc.name, "Error", errors=str(e))


# Funciones para instalar/desinstalar
def install_addenda_custom_fields():
	"""Instalar todos los custom fields de addendas."""
	print("🔧 Instalando custom fields de addendas...")

	create_sales_invoice_addenda_fields()
	create_customer_addenda_fields()

	# Limpiar cache
	frappe.clear_cache()

	print("✅ Custom fields de addendas instalados correctamente")


def uninstall_addenda_custom_fields():
	"""Desinstalar todos los custom fields de addendas."""
	print("🧹 Removiendo custom fields de addendas...")

	remove_sales_invoice_addenda_fields()
	remove_customer_addenda_fields()

	# Limpiar cache
	frappe.clear_cache()

	print("✅ Custom fields de addendas removidos correctamente")


if __name__ == "__main__":
	# Para testing/debugging
	install_addenda_custom_fields()
