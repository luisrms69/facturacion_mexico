"""
Addendas API - Sprint 3
APIs principales para el sistema de addendas genéricas
"""

import json

import frappe
from frappe import _

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

		# Agregar valores de campos
		if isinstance(field_values, str):
			field_values = json.loads(field_values)

		for field_name, field_data in field_values.items():
			field_value_row = config_doc.append("field_values")
			field_value_row.field_definition = field_name

			if isinstance(field_data, dict):
				field_value_row.field_value = field_data.get("value", "")
				field_value_row.is_dynamic = field_data.get("is_dynamic", 0)
				field_value_row.dynamic_source = field_data.get("dynamic_source", "")
				field_value_row.dynamic_field = field_data.get("dynamic_field", "")
			else:
				field_value_row.field_value = str(field_data)

		config_doc.insert()

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
