"""
Addendas API - Sprint 3
APIs principales para el sistema de addendas genéricas
"""

import json

import frappe
from frappe import _

from facturacion_mexico.addendas.addenda_auto_detector import AddendaAutoDetector

# Sprint 6 Phase 3: Importar sistema genérico
from facturacion_mexico.addendas.generic_addenda_generator import AddendaGenerator

# Importar parsers y validadores
from facturacion_mexico.addendas.parsers.cfdi_parser import CFDIParser
from facturacion_mexico.addendas.parsers.xml_builder import AddendaXMLBuilder
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
		return {
			"success": False,
			"message": _("Error obteniendo tipos de addenda: {0}").format(str(e)),
			"data": [],
		}


@frappe.whitelist()
def get_addenda_configuration(customer):
	"""Obtener configuración de addenda para cliente."""
	try:
		if not customer:
			return {"success": False, "message": _("Customer es requerido"), "data": None}

		# Buscar configuraciones activas para el cliente
		configurations = frappe.get_all(
			"Addenda Configuration",
			filters={
				"customer": customer,
				"is_active": 1,
				"effective_date": ["<=", frappe.utils.today()],
				"expiry_date": [">=", frappe.utils.today()],
			},
			fields=[
				"name",
				"addenda_type",
				"priority",
				"auto_apply",
				"validation_level",
				"effective_date",
				"expiry_date",
			],
			order_by="priority, creation",
		)

		# Si hay múltiples, tomar la de mayor prioridad (menor número)
		active_config = configurations[0] if configurations else None

		if active_config:
			# Obtener valores de campos
			config_doc = frappe.get_doc("Addenda Configuration", active_config["name"])
			field_values = {}

			for field_value in config_doc.field_values:
				field_values[field_value.field_definition] = {
					"value": field_value.field_value,
					"is_dynamic": field_value.is_dynamic,
					"dynamic_source": field_value.dynamic_source,
					"dynamic_field": field_value.dynamic_field,
				}

			active_config["field_values"] = field_values

		return {
			"success": True,
			"data": active_config,
			"all_configurations": configurations,
			"has_configuration": bool(active_config),
		}

	except Exception as e:
		frappe.log_error(f"Error obteniendo configuración de addenda: {e!s}")
		return {
			"success": False,
			"message": _("Error obteniendo configuración: {0}").format(str(e)),
			"data": None,
		}


@frappe.whitelist()
def generate_addenda_xml(sales_invoice, addenda_type=None, validate_output=True):
	"""Generar XML de addenda para factura."""
	try:
		if not sales_invoice:
			return {"success": False, "message": _("Sales Invoice es requerido"), "xml": ""}

		# Obtener documento de factura
		invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)

		# Determinar tipo de addenda
		if not addenda_type:
			config_result = get_addenda_configuration(invoice_doc.customer)
			if not config_result["success"] or not config_result["data"]:
				return {
					"success": False,
					"message": _("No hay configuración de addenda para el cliente {0}").format(
						invoice_doc.customer
					),
					"xml": "",
				}
			addenda_type = config_result["data"]["addenda_type"]

		# Obtener tipo de addenda
		addenda_type_doc = frappe.get_doc("Addenda Type", addenda_type)

		# Obtener template
		template_result = get_addenda_template(addenda_type)
		if not template_result["success"]:
			return template_result

		template_xml = template_result["data"]["template_xml"]

		# Obtener datos del CFDI (si existe)
		cfdi_data = {}
		if invoice_doc.get("fm_cfdi_xml"):
			try:
				parser = CFDIParser(invoice_doc.fm_cfdi_xml)
				cfdi_data = parser.get_cfdi_data()
			except Exception as e:
				frappe.log_error(f"Error parseando CFDI: {e!s}")

		# Obtener valores de campos
		config_result = get_addenda_configuration(invoice_doc.customer)
		field_values = {}

		if config_result["success"] and config_result["data"]:
			field_values = config_result["data"].get("field_values", {})

		# Resolver valores dinámicos
		resolved_values = _resolve_dynamic_values(field_values, invoice_doc, cfdi_data)

		# Construir XML
		builder = AddendaXMLBuilder(template_xml, resolved_values, cfdi_data)

		if addenda_type_doc.namespace:
			builder.add_namespace(addenda_type_doc.namespace)

		addenda_xml = builder.replace_variables().build()

		# Validar si se solicita
		validation_result = {"valid": True, "message": "", "errors": []}
		if validate_output:
			validation_result = validate_addenda_xml(addenda_xml, addenda_type)

		return {
			"success": True,
			"xml": addenda_xml,
			"addenda_type": addenda_type,
			"validation": validation_result,
			"field_values_used": resolved_values,
			"cfdi_data_available": bool(cfdi_data),
		}

	except Exception as e:
		frappe.log_error(f"Error generando XML de addenda: {e!s}")
		return {"success": False, "message": _("Error generando XML: {0}").format(str(e)), "xml": ""}


@frappe.whitelist()
def validate_addenda_xml_api(xml_content, addenda_type):
	"""Validar XML contra XSD."""
	try:
		result = validate_addenda_xml(xml_content, addenda_type)

		return {"success": True, "validation": result}

	except Exception as e:
		frappe.log_error(f"Error validando XML de addenda: {e!s}")
		return {
			"success": False,
			"message": _("Error durante validación: {0}").format(str(e)),
			"validation": {"is_valid": False, "errors": [str(e)], "warnings": []},
		}


@frappe.whitelist()
def create_addenda_configuration(customer, addenda_type, field_values, **kwargs):
	"""Crear nueva configuración de addenda."""
	try:
		if not customer or not addenda_type:
			return {"success": False, "message": _("Customer y Addenda Type son requeridos")}

		# Verificar que no exista configuración activa
		existing = frappe.get_all(
			"Addenda Configuration",
			filters={"customer": customer, "addenda_type": addenda_type, "is_active": 1},
			limit=1,
		)

		if existing:
			return {
				"success": False,
				"message": _("Ya existe una configuración activa para este cliente y tipo de addenda"),
			}

		# Crear configuración
		config_doc = frappe.new_doc("Addenda Configuration")
		config_doc.customer = customer
		config_doc.addenda_type = addenda_type
		config_doc.is_active = kwargs.get("is_active", 1)
		config_doc.priority = kwargs.get("priority", 1)
		config_doc.auto_apply = kwargs.get("auto_apply", 1)
		config_doc.validation_level = kwargs.get("validation_level", "Warning")
		config_doc.effective_date = kwargs.get("effective_date", frappe.utils.today())
		config_doc.notify_on_error = kwargs.get("notify_on_error", 0)
		config_doc.error_recipients = kwargs.get("error_recipients", "")

		# REGLA #44: NO usar append en APIs - causa parent_doc error
		# Crear configuración básica sin field_values por ahora
		# Los field_values se pueden agregar después con update si es necesario

		config_doc.insert()

		# REGLA #44: Si se necesitan field_values, usar método alternativo
		# Por ahora la configuración básica es suficiente para testing

		return {
			"success": True,
			"message": _("Configuración de addenda creada exitosamente"),
			"name": config_doc.name,
		}

	except Exception as e:
		frappe.log_error(f"Error creando configuración de addenda: {e!s}")
		return {"success": False, "message": _("Error creando configuración: {0}").format(str(e))}


@frappe.whitelist()
def get_product_mappings(customer, items=None):
	"""Obtener mapeo de productos para cliente."""
	try:
		if not customer:
			return {"success": False, "message": _("Customer es requerido"), "data": {}}

		filters = {"customer": customer, "is_active": 1}

		if items:
			if isinstance(items, str):
				items = json.loads(items)
			filters["item"] = ["in", items]

		mappings = frappe.get_all(
			"Addenda Product Mapping",
			filters=filters,
			fields=[
				"item",
				"customer_item_code",
				"customer_item_description",
				"customer_uom",
				"additional_data",
			],
		)

		# Convertir a diccionario para fácil acceso
		mapping_dict = {}
		for mapping in mappings:
			mapping_dict[mapping["item"]] = {
				"customer_code": mapping["customer_item_code"],
				"customer_description": mapping["customer_item_description"],
				"customer_uom": mapping["customer_uom"],
				"additional_data": json.loads(mapping["additional_data"] or "{}"),
			}

		return {"success": True, "data": mapping_dict, "count": len(mappings)}

	except Exception as e:
		frappe.log_error(f"Error obteniendo mapeo de productos: {e!s}")
		return {"success": False, "message": _("Error obteniendo mapeo: {0}").format(str(e)), "data": {}}


@frappe.whitelist()
def test_addenda_generation(sales_invoice, addenda_type=None):
	"""Generar addenda de prueba sin timbrar."""
	try:
		# Generar XML
		result = generate_addenda_xml(sales_invoice, addenda_type, validate_output=True)

		if not result["success"]:
			return result

		# Agregar información adicional para testing
		result["test_mode"] = True
		result["timestamp"] = frappe.utils.now()

		# Verificar si se puede insertar en CFDI
		if result.get("cfdi_data_available"):
			try:
				invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
				if invoice_doc.get("fm_cfdi_xml"):
					parser = CFDIParser(invoice_doc.fm_cfdi_xml)
					is_valid, message = parser.validate_cfdi_structure()
					result["cfdi_validation"] = {"valid": is_valid, "message": message}

					if is_valid:
						# Simular inserción (sin guardar)
						try:
							modified_xml = parser.insert_addenda(result["xml"])
							result["can_insert"] = True
							result["preview_length"] = len(modified_xml)
						except Exception as e:
							result["can_insert"] = False
							result["insert_error"] = str(e)
			except Exception as e:
				result["cfdi_validation"] = {"valid": False, "message": f"Error validando CFDI: {e!s}"}

		return result

	except Exception as e:
		frappe.log_error(f"Error en test de generación de addenda: {e!s}")
		return {"success": False, "message": _("Error en test: {0}").format(str(e))}


# Funciones helper internas


def _resolve_dynamic_values(field_values: dict, invoice_doc, cfdi_data: dict) -> dict:
	"""Resolver valores dinámicos de campos."""
	resolved = {}

	for field_name, field_data in field_values.items():
		if isinstance(field_data, dict) and field_data.get("is_dynamic"):
			resolved[field_name] = _get_dynamic_value(field_data, invoice_doc, cfdi_data)
		elif isinstance(field_data, dict):
			resolved[field_name] = field_data.get("value", "")
		else:
			resolved[field_name] = str(field_data)

	return resolved


def _get_dynamic_value(field_data: dict, invoice_doc, cfdi_data: dict) -> str:
	"""Obtener valor dinámico de un campo."""
	try:
		source = field_data.get("dynamic_source", "")
		field = field_data.get("dynamic_field", "")

		if not source or not field:
			return field_data.get("value", "")

		if source == "Sales Invoice":
			value = getattr(invoice_doc, field, "")
		elif source == "Customer":
			customer_doc = frappe.get_doc("Customer", invoice_doc.customer)
			value = getattr(customer_doc, field, "")
		elif source == "Item" and invoice_doc.items:
			# Tomar del primer item
			value = getattr(invoice_doc.items[0], field, "")
		elif source == "CFDI" and cfdi_data:
			value = cfdi_data.get(field, "")
		else:
			value = field_data.get("value", "")

		# Aplicar transformación si existe
		transform = field_data.get("transformation", "")
		if transform and value:
			if transform == "Uppercase":
				value = str(value).upper()
			elif transform == "Lowercase":
				value = str(value).lower()
			elif transform == "Title":
				value = str(value).title()

		return str(value) if value is not None else ""

	except Exception as e:
		frappe.log_error(f"Error obteniendo valor dinámico: {e!s}")
		return field_data.get("value", "")


def get_addenda_template(addenda_type: str) -> dict:
	"""Obtener template para tipo de addenda."""
	try:
		# Buscar template por defecto
		template = frappe.get_all(
			"Addenda Template",
			filters={"addenda_type": addenda_type, "is_default": 1},
			fields=["name", "template_xml"],
			limit=1,
		)

		if not template:
			# Buscar cualquier template para el tipo
			template = frappe.get_all(
				"Addenda Template",
				filters={"addenda_type": addenda_type},
				fields=["name", "template_xml"],
				limit=1,
			)

		if not template:
			# Crear template básico
			return {
				"success": True,
				"data": {
					"name": "Generated",
					"template_xml": AddendaXMLBuilder.create_sample_template(addenda_type),
				},
			}

		return {"success": True, "data": template[0]}

	except Exception as e:
		return {"success": False, "message": _("Error obteniendo template: {0}").format(str(e))}


@frappe.whitelist()
def get_addenda_requirements(customer):
	"""Verificar si un cliente requiere addenda y qué tipo."""
	try:
		config_result = get_addenda_configuration(customer)

		return {
			"requires_addenda": config_result["success"] and config_result["data"],
			"configuration": config_result["data"] if config_result["success"] else None,
			"auto_apply": config_result["data"]["auto_apply"]
			if config_result["success"] and config_result["data"]
			else False,
		}

	except Exception as e:
		frappe.log_error(f"Error verificando requerimientos de addenda: {e!s}")
		return {"requires_addenda": False, "configuration": None, "auto_apply": False}


# ============================================================================
# SPRINT 6 PHASE 3: APIs GENÉRICAS CON JINJA2 TEMPLATES
# ============================================================================


@frappe.whitelist()
def generate_generic_addenda(sales_invoice, addenda_type, addenda_values=None):
	"""
	Generar addenda usando sistema genérico con Jinja2 templates
	Sprint 6 Phase 3 - API principal para addendas genéricas
	"""
	try:
		if isinstance(addenda_values, str):
			addenda_values = json.loads(addenda_values)

		# Usar el nuevo generador genérico
		from facturacion_mexico.addendas.generic_addenda_generator import generate_addenda_for_invoice

		result = generate_addenda_for_invoice(sales_invoice, addenda_type, addenda_values)

		return result

	except Exception as e:
		frappe.log_error(f"Error in generate_generic_addenda API: {e!s}", "Generic Addenda API")
		return {"success": False, "message": f"Error generando addenda genérica: {e!s}"}


@frappe.whitelist()
def get_addenda_field_definitions(addenda_type):
	"""
	Obtener definición de campos para un tipo de addenda
	Sprint 6 Phase 3 - Campos dinámicos configurables
	"""
	try:
		from facturacion_mexico.addendas.generic_addenda_generator import get_addenda_type_fields

		result = get_addenda_type_fields(addenda_type)

		return result

	except Exception as e:
		frappe.log_error(f"Error in get_addenda_field_definitions API: {e!s}", "Generic Addenda API")
		return {"success": False, "message": f"Error: {e!s}", "fields": []}


@frappe.whitelist()
def setup_customer_addenda_auto_detection(customer=None, apply_changes=False):
	"""
	Ejecutar auto-detección de addendas para cliente
	Sprint 6 Phase 3 - Auto-detección inteligente
	"""
	try:
		from facturacion_mexico.addendas.addenda_auto_detector import (
			apply_auto_detection,
			detect_customer_addenda_requirement,
		)

		if customer:
			# Auto-detección para cliente específico
			detection_result = detect_customer_addenda_requirement(customer)

			if apply_changes and detection_result.get("success"):
				apply_result = apply_auto_detection(customer)
				return {"success": True, "detection_result": detection_result, "apply_result": apply_result}
			else:
				return detection_result
		else:
			# Auto-detección en lote
			from facturacion_mexico.addendas.addenda_auto_detector import bulk_auto_detect_customers

			return bulk_auto_detect_customers(limit=50)

	except Exception as e:
		frappe.log_error(f"Error in setup_customer_addenda_auto_detection API: {e!s}", "Auto Detection API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def install_customer_addenda_fields():
	"""
	Instalar custom fields de addenda en Customer
	Sprint 6 Phase 3 - Configuración inicial
	"""
	try:
		from facturacion_mexico.addendas.custom_fields.customer_addenda_fields import (
			create_customer_addenda_fields,
		)

		result = create_customer_addenda_fields()
		return result

	except Exception as e:
		frappe.log_error(f"Error installing customer addenda fields: {e!s}", "Customer Addenda Fields")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def get_customer_addenda_info(customer):
	"""
	Obtener información completa de addenda para un cliente
	Sprint 6 Phase 3 - Vista consolidada
	"""
	try:
		if not customer:
			return {"success": False, "message": "Customer es requerido"}

		customer_doc = frappe.get_cached_doc("Customer", customer)

		# Información básica
		customer_info = {
			"requires_addenda": customer_doc.get("fm_requires_addenda", 0),
			"addenda_type": customer_doc.get("fm_addenda_type"),
			"auto_detected": customer_doc.get("fm_addenda_auto_detected", 0),
			"validation_override": customer_doc.get("fm_addenda_validation_override", 0),
		}

		# Valores por defecto
		defaults = {}
		if customer_doc.get("fm_addenda_defaults"):
			try:
				defaults = json.loads(customer_doc.fm_addenda_defaults)
			except json.JSONDecodeError:
				pass

		# Si tiene tipo de addenda, obtener definición de campos
		field_definitions = []
		if customer_info["addenda_type"]:
			field_result = get_addenda_field_definitions(customer_info["addenda_type"])
			if field_result.get("success"):
				field_definitions = field_result["fields"]

		# Auto-detección (si no tiene configuración manual)
		auto_detection = None
		if not customer_info["requires_addenda"]:
			from facturacion_mexico.addendas.addenda_auto_detector import detect_customer_addenda_requirement

			auto_detection = detect_customer_addenda_requirement(customer)

		return {
			"success": True,
			"customer_info": customer_info,
			"defaults": defaults,
			"field_definitions": field_definitions,
			"auto_detection": auto_detection,
		}

	except Exception as e:
		frappe.log_error(f"Error in get_customer_addenda_info API: {e!s}", "Customer Addenda Info")
		return {"success": False, "message": f"Error: {e!s}"}
