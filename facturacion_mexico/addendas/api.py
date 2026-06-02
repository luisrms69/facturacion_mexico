"""
Addendas API — arquitectura nueva (Jinja2 templates + datos desde Customer/Address/Company).
"""

import json

import frappe
from frappe import _

from facturacion_mexico.addendas.validators.xsd_validator import validate_addenda_xml


@frappe.whitelist()
def get_addenda_types():
	"""Obtener tipos de addenda activos."""
	try:
		types = frappe.get_all(
			"Addenda Type",
			filters={"is_active": 1},
			fields=[
				"name",
				"description",
				"version",
				"requires_product_mapping",
				"namespace",
				"documentation_url",
			],
			order_by="name",
		)
		return {"success": True, "data": types, "count": len(types)}
	except Exception as e:
		frappe.log_error(f"Error obteniendo tipos de addenda: {e!s}")
		return {"success": False, "message": str(e), "data": []}


@frappe.whitelist()
def validate_addenda_xml_api(xml_content: str, addenda_type: str):
	"""Validar XML contra XSD."""
	try:
		result = validate_addenda_xml(xml_content, addenda_type)
		return {"success": True, "validation": result}
	except Exception as e:
		frappe.log_error(f"Error validando XML de addenda: {e!s}")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def generate_generic_addenda(sales_invoice: str, addenda_type: str, addenda_values: str | None = None):
	"""Generar addenda usando sistema genérico con Jinja2 templates."""
	try:
		if isinstance(addenda_values, str):
			addenda_values = json.loads(addenda_values)

		from facturacion_mexico.addendas.generic_addenda_generator import generate_addenda_for_invoice

		return generate_addenda_for_invoice(sales_invoice, addenda_type, addenda_values)
	except Exception as e:
		frappe.log_error(f"Error in generate_generic_addenda API: {e!s}", "Generic Addenda API")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_addenda_field_definitions(addenda_type: str):
	"""Obtener definición de campos para un tipo de addenda."""
	try:
		from facturacion_mexico.addendas.generic_addenda_generator import get_addenda_type_fields

		return get_addenda_type_fields(addenda_type)
	except Exception as e:
		frappe.log_error(f"Error in get_addenda_field_definitions API: {e!s}", "Generic Addenda API")
		return {"success": False, "message": str(e), "fields": []}


@frappe.whitelist()
def setup_customer_addenda_auto_detection(customer: str | None = None, apply_changes: bool = False):
	"""Ejecutar auto-detección de addendas para cliente."""
	try:
		from facturacion_mexico.addendas.addenda_auto_detector import (
			apply_auto_detection,
			detect_customer_addenda_requirement,
		)

		if customer:
			detection_result = detect_customer_addenda_requirement(customer)
			if apply_changes and detection_result.get("success"):
				apply_result = apply_auto_detection(customer)
				return {"success": True, "detection_result": detection_result, "apply_result": apply_result}
			return detection_result
		else:
			from facturacion_mexico.addendas.addenda_auto_detector import bulk_auto_detect_customers

			return bulk_auto_detect_customers(limit=50)
	except Exception as e:
		frappe.log_error(f"Error in setup_customer_addenda_auto_detection: {e!s}", "Auto Detection API")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_customer_addenda_info(customer: str):
	"""Obtener información completa de addenda para un cliente."""
	try:
		if not customer:
			return {"success": False, "message": "Customer es requerido"}

		customer_doc = frappe.get_cached_doc("Customer", customer)

		customer_info = {
			"requires_addenda": customer_doc.get("fm_requires_addenda", 0),
			"addenda_type": customer_doc.get("fm_default_addenda_type"),
			"buyer_gln": customer_doc.get("fm_buyer_gln"),
			"seller_gln": customer_doc.get("fm_seller_gln"),
			"seller_id": customer_doc.get("fm_seller_id"),
			"invoice_creator_gln": customer_doc.get("fm_invoice_creator_gln"),
			"dias_credito": customer_doc.get("fm_dias_credito_addenda"),
		}

		return {"success": True, "customer_info": customer_info}
	except Exception as e:
		frappe.log_error(f"Error in get_customer_addenda_info API: {e!s}", "Customer Addenda Info")
		return {"success": False, "message": str(e)}
