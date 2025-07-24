# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Generic Addenda Generator - Sprint 6 Phase 3
Generador genérico de addendas usando Jinja2 templates dinámicos
"""

import json
import re
from typing import Any

import frappe
from frappe import _
from jinja2 import Environment, Template, TemplateError, meta

from facturacion_mexico.addendas.validators.xsd_validator import validate_addenda_xml


class AddendaGenerator:
	"""
	Generador genérico de addendas con templates Jinja2 dinámicos
	Implementa el patrón Factory para diferentes tipos de addenda
	"""

	def __init__(self, addenda_type: str):
		self.addenda_type = addenda_type
		self.addenda_type_doc = None
		self.template = None
		self.validator = None
		self._load_addenda_type()

	def _load_addenda_type(self):
		"""Cargar configuración del tipo de addenda"""
		try:
			self.addenda_type_doc = frappe.get_cached_doc("Addenda Type", self.addenda_type)

			if not self.addenda_type_doc.is_active:
				frappe.throw(_("El tipo de addenda '{0}' no está activo").format(self.addenda_type))

			# Cargar template Jinja2 con autoescape habilitado para prevenir XSS
			if self.addenda_type_doc.xml_template:
				self.template = Template(self.addenda_type_doc.xml_template, autoescape=True)
			else:
				frappe.throw(
					_("El tipo de addenda '{0}' no tiene template XML configurado").format(self.addenda_type)
				)

		except frappe.DoesNotExistError:
			frappe.throw(_("Tipo de addenda '{0}' no encontrado").format(self.addenda_type))

	def generate(self, invoice_data: dict, addenda_values: dict) -> dict[str, Any]:
		"""
		Generar XML de addenda dinámicamente

		Args:
		    invoice_data: Datos de la factura (Sales Invoice)
		    addenda_values: Valores específicos para campos de addenda

		Returns:
		    dict con success, xml_content, validation_result
		"""
		try:
			# 1. Validar valores contra definición de campos
			validation_result = self._validate_values(addenda_values)
			if not validation_result["valid"]:
				return {
					"success": False,
					"message": "Errores de validación en campos de addenda",
					"validation_errors": validation_result["errors"],
					"xml_content": None,
				}

			# 2. Preparar contexto completo para template
			template_context = self._prepare_template_context(invoice_data, addenda_values)

			# 3. Procesar template con Jinja2
			xml_content = self.template.render(**template_context)

			# 4. Validar XML resultante
			xml_validation = self._validate_generated_xml(xml_content)

			return {
				"success": True,
				"xml_content": xml_content,
				"validation_result": xml_validation,
				"template_variables": list(template_context.keys()),
				"message": "Addenda generada exitosamente",
			}

		except TemplateError as e:
			frappe.log_error(f"Error en template Jinja2: {e!s}", "Addenda Generator Template")
			return {"success": False, "message": f"Error en template: {e!s}", "xml_content": None}
		except Exception as e:
			frappe.log_error(f"Error generando addenda: {e!s}", "Addenda Generator")
			return {"success": False, "message": f"Error generando addenda: {e!s}", "xml_content": None}

	def _validate_values(self, addenda_values: dict) -> dict:
		"""Validar valores contra definición de campos"""
		errors = []
		field_definitions = self.addenda_type_doc.field_definitions or []

		# Crear dict de definiciones por nombre de campo
		field_defs = {fd.field_name: fd for fd in field_definitions}

		# Validar campos obligatorios
		for field_def in field_definitions:
			if field_def.is_mandatory and field_def.field_name not in addenda_values:
				errors.append(f"Campo obligatorio '{field_def.field_label}' faltante")

			field_value = addenda_values.get(field_def.field_name)
			if field_value is not None:
				# Validar tipo de dato
				type_error = self._validate_field_type(field_def, field_value)
				if type_error:
					errors.append(type_error)

				# Validar patrón regex si existe
				if field_def.validation_pattern:
					if not re.match(field_def.validation_pattern, str(field_value)):
						errors.append(f"Campo '{field_def.field_label}' no cumple el patrón requerido")

		# Validar campos no definidos
		for field_name in addenda_values:
			if field_name not in field_defs:
				errors.append(f"Campo '{field_name}' no está definido en el tipo de addenda")

		return {"valid": len(errors) == 0, "errors": errors}

	def _validate_field_type(self, field_def, value) -> str | None:
		"""Validar tipo de dato de un campo"""
		try:
			if field_def.field_type == "Int":
				int(value)
			elif field_def.field_type == "Float":
				float(value)
			elif field_def.field_type == "Date":
				from datetime import datetime

				if isinstance(value, str):
					datetime.strptime(value, "%Y-%m-%d")
			elif field_def.field_type == "Datetime":
				from datetime import datetime

				if isinstance(value, str):
					datetime.fromisoformat(value.replace("Z", "+00:00"))
			elif field_def.field_type == "Check":
				if value not in [0, 1, True, False, "0", "1"]:
					return f"Campo '{field_def.field_label}' debe ser verdadero/falso"

			return None
		except (ValueError, TypeError):
			return f"Campo '{field_def.field_label}' tiene tipo de dato inválido"

	def _prepare_template_context(self, invoice_data: dict, addenda_values: dict) -> dict:
		"""Preparar contexto completo para el template Jinja2"""
		context = {}

		# 1. Agregar datos de factura
		context["invoice"] = invoice_data

		# 2. Agregar valores de addenda
		context.update(addenda_values)

		# 3. Agregar variables de sistema
		from datetime import datetime

		context.update(
			{
				"current_date": datetime.now().strftime("%Y-%m-%d"),
				"current_datetime": datetime.now().isoformat(),
				"current_time": datetime.now().strftime("%H:%M:%S"),
				"current_year": datetime.now().year,
				"current_month": datetime.now().month,
				"current_day": datetime.now().day,
			}
		)

		# REGLA #35: Agregar datos de empresa con defensive access
		company_name = invoice_data.get("company")
		if company_name:
			try:
				company_doc = frappe.get_cached_doc("Company", company_name)
				context["company"] = {
					"name": getattr(company_doc, "company_name", "N/A"),
					"tax_id": getattr(company_doc, "tax_id", "N/A"),
					"country": getattr(company_doc, "country", "N/A"),
					"default_currency": getattr(company_doc, "default_currency", "MXN"),
				}
			except Exception:
				context["company"] = {
					"name": "N/A",
					"tax_id": "N/A",
					"country": "N/A",
					"default_currency": "MXN",
				}

		# 5. Agregar helpers/funciones útiles
		context["helpers"] = {
			"format_currency": lambda x: f"{float(x):.2f}",
			"format_date": lambda x: datetime.strptime(x, "%Y-%m-%d").strftime("%d/%m/%Y")
			if isinstance(x, str)
			else x,
			"upper": lambda x: str(x).upper(),
			"lower": lambda x: str(x).lower(),
		}

		return context

	def _validate_generated_xml(self, xml_content: str) -> dict:
		"""Validar XML generado"""
		try:
			# Validación básica de XML well-formed
			import xml.etree.ElementTree as ET

			ET.fromstring(xml_content)

			# Si hay esquema XSD configurado, validar contra él
			if self.addenda_type_doc.xsd_schema:
				return validate_addenda_xml(xml_content, self.addenda_type)
			else:
				return {"valid": True, "message": "XML well-formed (sin validación XSD)", "errors": []}

		except ET.ParseError as e:
			return {"valid": False, "message": f"XML mal formado: {e!s}", "errors": [str(e)]}
		except Exception as e:
			return {"valid": False, "message": f"Error validando XML: {e!s}", "errors": [str(e)]}

	def get_required_fields(self) -> list[dict]:
		"""Obtener campos requeridos para este tipo de addenda"""
		if not self.addenda_type_doc:
			return []

		return [
			{
				"field_name": fd.field_name,
				"field_label": fd.field_label,
				"field_type": fd.field_type,
				"is_mandatory": fd.is_mandatory,
				"default_value": fd.default_value,
				"help_text": fd.help_text,
				"options": fd.options,
			}
			for fd in (self.addenda_type_doc.field_definitions or [])
		]

	def get_template_variables(self) -> list[str]:
		"""Obtener variables utilizadas en el template"""
		if not self.template:
			return []

		try:
			# Usar Jinja2 meta para extraer variables del template con autoescape
			env = Environment(autoescape=True)
			ast = env.parse(self.addenda_type_doc.xml_template)
			variables = meta.find_undeclared_variables(ast)
			return sorted(list(variables))
		except Exception as e:
			frappe.log_error(f"Error extrayendo variables del template: {e!s}", "Template Variables")
			return []


class AddendaValidator:
	"""Validador especializado para addendas genéricas"""

	def __init__(self, addenda_type: str):
		self.addenda_type = addenda_type
		self.addenda_type_doc = frappe.get_cached_doc("Addenda Type", addenda_type)

	def validate_business_rules(self, invoice_data: dict, addenda_values: dict) -> dict:
		"""Validar reglas de negocio específicas"""
		errors = []
		warnings = []

		try:
			# Cargar reglas de validación JSON si existen
			if self.addenda_type_doc.validation_rules:
				rules = json.loads(self.addenda_type_doc.validation_rules)

				# Procesar reglas
				for rule in rules.get("rules", []):
					result = self._evaluate_rule(rule, invoice_data, addenda_values)
					if not result["passed"]:
						if result.get("severity") == "error":
							errors.append(result["message"])
						else:
							warnings.append(result["message"])

			return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

		except json.JSONDecodeError as e:
			frappe.log_error(f"Error parsing validation rules JSON: {e!s}", "Addenda Validation Rules")
			return {"valid": False, "errors": [f"Error en reglas de validación: {e!s}"], "warnings": []}

	def _evaluate_rule(self, rule: dict, invoice_data: dict, addenda_values: dict) -> dict:
		"""Evaluar una regla específica"""
		# Implementación básica - puede extenderse
		rule_type = rule.get("type")

		if rule_type == "required_if":
			# Ejemplo: campo X es requerido si campo Y tiene valor Z
			field = rule.get("field")
			condition_field = rule.get("condition_field")
			condition_value = rule.get("condition_value")

			if addenda_values.get(condition_field) == condition_value:
				if field not in addenda_values or not addenda_values[field]:
					return {
						"passed": False,
						"message": f"Campo '{field}' es requerido cuando '{condition_field}' = '{condition_value}'",
						"severity": rule.get("severity", "error"),
					}

		return {"passed": True, "message": "Regla validada correctamente"}


# APIs públicas
@frappe.whitelist()
def generate_addenda_for_invoice(
	sales_invoice: str, addenda_type: str, addenda_values: dict | None = None
) -> dict:
	"""API para generar addenda para una factura específica"""
	try:
		# Cargar datos de la factura
		invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
		invoice_data = invoice_doc.as_dict()

		# Usar valores por defecto del cliente si no se proporcionan
		if not addenda_values:
			addenda_values = get_customer_addenda_defaults(invoice_doc.customer, addenda_type)

		# Generar addenda
		generator = AddendaGenerator(addenda_type)
		result = generator.generate(invoice_data, addenda_values)

		return result

	except Exception as e:
		frappe.log_error(f"Error in generate_addenda_for_invoice API: {e!s}", "Addenda Generator API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def get_addenda_type_fields(addenda_type: str) -> dict:
	"""API para obtener campos requeridos de un tipo de addenda"""
	try:
		generator = AddendaGenerator(addenda_type)
		fields = generator.get_required_fields()
		variables = generator.get_template_variables()

		return {"success": True, "fields": fields, "template_variables": variables}

	except Exception as e:
		frappe.log_error(f"Error in get_addenda_type_fields API: {e!s}", "Addenda Generator API")
		return {"success": False, "message": f"Error: {e!s}", "fields": []}


def get_customer_addenda_defaults(customer: str, addenda_type: str) -> dict:
	"""Obtener valores por defecto de addenda para un cliente"""
	try:
		customer_doc = frappe.get_cached_doc("Customer", customer)

		# REGLA #35: Defensive access para fm_addenda_defaults
		addenda_defaults_field = getattr(customer_doc, "fm_addenda_defaults", None)
		if addenda_defaults_field:
			try:
				defaults = json.loads(addenda_defaults_field)
				return defaults.get(addenda_type, {})
			except (json.JSONDecodeError, TypeError):
				frappe.log_error(
					f"Invalid JSON in fm_addenda_defaults for customer {customer}", "Addenda Defaults"
				)
				return {}

		return {}

	except Exception as e:
		frappe.log_error(f"Error getting customer addenda defaults: {e!s}", "Customer Addenda Defaults")
		return {}
