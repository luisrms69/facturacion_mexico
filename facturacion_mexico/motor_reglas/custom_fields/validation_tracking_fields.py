"""
Validation Tracking Fields - Sprint 4 Semana 2
Custom Fields para tracking de validación de reglas en documentos
"""

import frappe

from facturacion_mexico.setup.custom_fields.field_manager import FieldManager


def setup_validation_tracking_fields():
	"""Configurar custom fields para tracking de validaciones de reglas."""
	field_manager = FieldManager()

	# Custom Fields genéricos para todos los DocTypes que usan reglas
	generic_validation_fields = [
		{
			"doctype": ["Sales Invoice", "Payment Entry", "Customer", "EReceipt MX", "Factura Global MX"],
			"fieldname": "fm_validation_rules_applied",
			"label": "Reglas de Validación Aplicadas",
			"fieldtype": "Long Text",
			"read_only": 1,
			"hidden": 1,
			"description": "JSON con reglas de validación aplicadas y resultados",
		},
		{
			"doctype": ["Sales Invoice", "Payment Entry", "Customer", "EReceipt MX", "Factura Global MX"],
			"fieldname": "fm_validation_timestamp",
			"label": "Última Validación",
			"fieldtype": "Datetime",
			"read_only": 1,
			"hidden": 1,
			"description": "Timestamp de última validación de reglas",
		},
		{
			"doctype": ["Sales Invoice", "Payment Entry", "Customer", "EReceipt MX", "Factura Global MX"],
			"fieldname": "fm_validation_status",
			"label": "Estado de Validación",
			"fieldtype": "Select",
			"options": "Pending\nPassed\nFailed\nWarnings",
			"default": "Pending",
			"read_only": 1,
			"hidden": 1,
			"description": "Estado de validación de reglas fiscales",
		},
	]

	# Custom Fields específicos para Sales Invoice
	sales_invoice_fields = [
		{
			"doctype": "Sales Invoice",
			"fieldname": "fm_included_in_global",
			"label": "Incluido en Factura Global",
			"fieldtype": "Check",
			"read_only": 1,
			"insert_after": "fm_validation_status",
			"section_break": {
				"fieldname": "fm_factura_global_section",
				"label": "Información Factura Global",
				"fieldtype": "Section Break",
				"insert_after": "fm_validation_status",
				"collapsible": 1,
			},
		},
		{
			"doctype": "Sales Invoice",
			"fieldname": "fm_global_invoice",
			"label": "Factura Global",
			"fieldtype": "Link",
			"options": "Factura Global MX",
			"read_only": 1,
			"insert_after": "fm_included_in_global",
		},
		{
			"doctype": "Sales Invoice",
			"fieldname": "fm_global_invoice_date",
			"label": "Fecha de Inclusión",
			"fieldtype": "Date",
			"read_only": 1,
			"insert_after": "fm_global_invoice",
		},
	]

	# Custom Fields para EReceipt MX (actualizar existentes)
	ereceipt_fields = [
		{
			"doctype": "EReceipt MX",
			"fieldname": "fm_rules_validation_count",
			"label": "Validaciones Ejecutadas",
			"fieldtype": "Int",
			"read_only": 1,
			"default": 0,
			"insert_after": "fm_validation_status",
		},
		{
			"doctype": "EReceipt MX",
			"fieldname": "fm_last_validation_result",
			"label": "Último Resultado",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "fm_rules_validation_count",
		},
	]

	try:
		# Instalar campos genéricos
		for field_config in generic_validation_fields:
			doctypes = field_config.pop("doctype")
			for doctype in doctypes:
				field_config_copy = field_config.copy()
				field_config_copy["doctype"] = doctype
				field_manager.create_custom_field(**field_config_copy)

		# Instalar campos de Sales Invoice
		for field_config in sales_invoice_fields:
			# Crear section break si está definido
			if "section_break" in field_config:
				section_config = field_config.pop("section_break")
				field_manager.create_custom_field(**section_config)

			field_manager.create_custom_field(**field_config)

		# Instalar campos de EReceipt MX
		for field_config in ereceipt_fields:
			field_manager.create_custom_field(**field_config)

		frappe.db.commit()
		return {"success": True, "message": "Custom fields para motor de reglas creados exitosamente"}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(f"Error creating validation tracking fields: {e}")
		return {"success": False, "error": str(e)}


def remove_validation_tracking_fields():
	"""Remover custom fields de tracking de validaciones."""
	field_manager = FieldManager()

	# Lista de todos los campos a remover
	fields_to_remove = [
		# Campos genéricos
		("Sales Invoice", "fm_validation_rules_applied"),
		("Sales Invoice", "fm_validation_timestamp"),
		("Sales Invoice", "fm_validation_status"),
		("Payment Entry", "fm_validation_rules_applied"),
		("Payment Entry", "fm_validation_timestamp"),
		("Payment Entry", "fm_validation_status"),
		("Customer", "fm_validation_rules_applied"),
		("Customer", "fm_validation_timestamp"),
		("Customer", "fm_validation_status"),
		("EReceipt MX", "fm_validation_rules_applied"),
		("EReceipt MX", "fm_validation_timestamp"),
		("EReceipt MX", "fm_validation_status"),
		("Factura Global MX", "fm_validation_rules_applied"),
		("Factura Global MX", "fm_validation_timestamp"),
		("Factura Global MX", "fm_validation_status"),
		# Campos específicos Sales Invoice
		("Sales Invoice", "fm_included_in_global"),
		("Sales Invoice", "fm_global_invoice"),
		("Sales Invoice", "fm_global_invoice_date"),
		("Sales Invoice", "fm_factura_global_section"),
		# Campos específicos EReceipt MX
		("EReceipt MX", "fm_rules_validation_count"),
		("EReceipt MX", "fm_last_validation_result"),
	]

	try:
		for doctype, fieldname in fields_to_remove:
			try:
				field_manager.remove_custom_field(doctype, fieldname)
			except Exception as field_error:
				# Log individual field errors but continue
				frappe.log_error(f"Error removing field {fieldname} from {doctype}: {field_error}")

		frappe.db.commit()
		return {"success": True, "message": "Custom fields de motor de reglas removidos exitosamente"}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(f"Error removing validation tracking fields: {e}")
		return {"success": False, "error": str(e)}


# Funciones helper para working con validation tracking
def update_validation_status(doctype, document_name, status, rules_applied=None):
	"""Actualizar estado de validación en documento."""
	try:
		update_fields = {
			"fm_validation_status": status,
			"fm_validation_timestamp": frappe.utils.now_datetime(),
		}

		if rules_applied:
			import json

			update_fields["fm_validation_rules_applied"] = json.dumps(rules_applied, indent=2, default=str)

		frappe.db.set_value(doctype, document_name, update_fields, update_modified=False)

		return True

	except Exception as e:
		frappe.log_error(f"Error updating validation status: {e}")
		return False


def get_validation_history(doctype, document_name):
	"""Obtener historial de validaciones de un documento."""
	try:
		doc_data = frappe.db.get_value(
			doctype,
			document_name,
			["fm_validation_status", "fm_validation_timestamp", "fm_validation_rules_applied"],
			as_dict=True,
		)

		if not doc_data:
			return {"success": False, "error": "Document not found"}

		# Parsear reglas aplicadas si existe
		rules_applied = None
		if doc_data.get("fm_validation_rules_applied"):
			try:
				import json

				rules_applied = json.loads(doc_data["fm_validation_rules_applied"])
			except (json.JSONDecodeError, KeyError):
				rules_applied = None

		return {
			"success": True,
			"validation_status": doc_data.get("fm_validation_status"),
			"last_validation": doc_data.get("fm_validation_timestamp"),
			"rules_applied": rules_applied,
			"document": {"doctype": doctype, "name": document_name},
		}

	except Exception as e:
		return {"success": False, "error": str(e)}


def clear_validation_data(doctype, document_name):
	"""Limpiar datos de validación de un documento."""
	try:
		update_fields = {
			"fm_validation_status": "Pending",
			"fm_validation_timestamp": None,
			"fm_validation_rules_applied": None,
		}

		frappe.db.set_value(doctype, document_name, update_fields, update_modified=False)

		return True

	except Exception as e:
		frappe.log_error(f"Error clearing validation data: {e}")
		return False
