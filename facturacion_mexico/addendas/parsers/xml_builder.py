"""
XML Builder - Sprint 3
Constructor dinámico de XML para addendas usando templates
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import frappe
from frappe import _
from lxml import etree


class AddendaXMLBuilder:
	"""Constructor de XML para addendas usando templates dinámicos."""

	def __init__(self, template, field_values, cfdi_data=None):
		"""
		Inicializar con template y valores.

		Args:
			template (str): Template XML con variables {{ }}
			field_values (dict): Valores de campos de la addenda
			cfdi_data (dict): Datos extraídos del CFDI
		"""
		self.template = template
		self.field_values = field_values or {}
		self.cfdi_data = cfdi_data or {}
		self.namespace = None
		self.variables = {}
		self._prepare_variables()

	def _prepare_variables(self):
		"""Preparar diccionario completo de variables."""
		# Combinar todas las fuentes de datos
		self.variables.update(self.cfdi_data)
		self.variables.update(self.field_values)

		# Agregar variables de sistema
		self.variables.update(
			{
				"current_date": datetime.now().strftime("%Y-%m-%d"),
				"current_datetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
				"current_time": datetime.now().strftime("%H:%M:%S"),
				"system_user": frappe.session.user,
				"company": frappe.defaults.get_user_default("Company") or "",
			}
		)

	def add_namespace(self, namespace):
		"""Agregar namespace al XML."""
		self.namespace = namespace
		return self

	def replace_variables(self):
		"""Reemplazar variables {{ }} con valores."""
		try:
			xml_content = self.template

			# Encontrar todas las variables en el template
			variable_pattern = r"\{\{\s*([^}]+)\s*\}\}"
			variables_found = re.findall(variable_pattern, xml_content)

			for var_expression in variables_found:
				var_value = self._resolve_variable(var_expression.strip())
				placeholder = "{{ " + var_expression + " }}"
				xml_content = xml_content.replace(placeholder, str(var_value))

			self.xml_content = xml_content
			return self

		except Exception as e:
			frappe.throw(_("Error reemplazando variables: {0}").format(str(e)))

	def _resolve_variable(self, expression):
		"""Resolver una expresión de variable."""
		try:
			# Variable simple
			if expression in self.variables:
				return self._format_value(self.variables[expression])

			# Variable con formato
			if "|" in expression:
				var_name, format_spec = expression.split("|", 1)
				var_name = var_name.strip()
				format_spec = format_spec.strip()

				if var_name in self.variables:
					return self._apply_format(self.variables[var_name], format_spec)

			# Variable con path (ej: concepto.descripcion)
			if "." in expression:
				return self._resolve_path(expression)

			# Variable con función (ej: sum(conceptos.importe))
			if "(" in expression and ")" in expression:
				return self._resolve_function(expression)

			# Variable no encontrada - retornar placeholder o valor por defecto
			frappe.log_error(f"Variable no encontrada en template: {expression}")
			return f"[{expression}]"

		except Exception as e:
			frappe.log_error(f"Error resolviendo variable '{expression}': {str(e)}")
			return f"[ERROR: {expression}]"

	def _resolve_path(self, path):
		"""Resolver variable con path (ej: concepto.descripcion)."""
		try:
			parts = path.split(".")
			current = self.variables

			for part in parts:
				if isinstance(current, dict) and part in current:
					current = current[part]
				elif isinstance(current, list) and part.isdigit():
					index = int(part)
					if 0 <= index < len(current):
						current = current[index]
					else:
						return ""
				else:
					return ""

			return self._format_value(current)

		except Exception:
			return ""

	def _resolve_function(self, expression):
		"""Resolver función (ej: sum(conceptos.importe), count(conceptos))."""
		try:
			# Extraer nombre de función y argumentos
			func_match = re.match(r"(\w+)\s*\(\s*([^)]*)\s*\)", expression)
			if not func_match:
				return ""

			func_name = func_match.group(1)
			args = func_match.group(2).strip()

			# Funciones disponibles
			if func_name == "sum":
				return self._func_sum(args)
			elif func_name == "count":
				return self._func_count(args)
			elif func_name == "avg":
				return self._func_avg(args)
			elif func_name == "max":
				return self._func_max(args)
			elif func_name == "min":
				return self._func_min(args)
			elif func_name == "first":
				return self._func_first(args)
			elif func_name == "last":
				return self._func_last(args)

			return ""

		except Exception as e:
			frappe.log_error(f"Error resolviendo función '{expression}': {str(e)}")
			return ""

	def _func_sum(self, path):
		"""Función sum: sumar valores de un array."""
		values = self._get_array_values(path)
		return sum(float(v) for v in values if self._is_number(v))

	def _func_count(self, path):
		"""Función count: contar elementos."""
		values = self._get_array_values(path)
		return len(values)

	def _func_avg(self, path):
		"""Función avg: promedio de valores."""
		values = [float(v) for v in self._get_array_values(path) if self._is_number(v)]
		return sum(values) / len(values) if values else 0

	def _func_max(self, path):
		"""Función max: valor máximo."""
		values = [float(v) for v in self._get_array_values(path) if self._is_number(v)]
		return max(values) if values else 0

	def _func_min(self, path):
		"""Función min: valor mínimo."""
		values = [float(v) for v in self._get_array_values(path) if self._is_number(v)]
		return min(values) if values else 0

	def _func_first(self, path):
		"""Función first: primer elemento."""
		values = self._get_array_values(path)
		return values[0] if values else ""

	def _func_last(self, path):
		"""Función last: último elemento."""
		values = self._get_array_values(path)
		return values[-1] if values else ""

	def _get_array_values(self, path):
		"""Obtener valores de un array usando path."""
		try:
			if not path:
				return []

			# Si es un path simple, buscar en variables
			if "." not in path:
				value = self.variables.get(path, [])
				return value if isinstance(value, list) else [value] if value else []

			# Path complejo (ej: conceptos.importe)
			parts = path.split(".")
			array_path = parts[0]
			field_path = ".".join(parts[1:]) if len(parts) > 1 else None

			array_data = self.variables.get(array_path, [])
			if not isinstance(array_data, list):
				return []

			if not field_path:
				return array_data

			# Extraer campo específico de cada elemento
			values = []
			for item in array_data:
				if isinstance(item, dict):
					value = self._resolve_path_in_object(item, field_path)
					if value is not None:
						values.append(value)

			return values

		except Exception:
			return []

	def _resolve_path_in_object(self, obj, path):
		"""Resolver path dentro de un objeto."""
		try:
			parts = path.split(".")
			current = obj

			for part in parts:
				if isinstance(current, dict) and part in current:
					current = current[part]
				else:
					return None

			return current

		except Exception:
			return None

	def _is_number(self, value):
		"""Verificar si un valor es numérico."""
		try:
			float(value)
			return True
		except (ValueError, TypeError):
			return False

	def _apply_format(self, value, format_spec):
		"""Aplicar formato a un valor."""
		try:
			format_spec = format_spec.lower()

			if format_spec == "uppercase":
				return str(value).upper()
			elif format_spec == "lowercase":
				return str(value).lower()
			elif format_spec == "title":
				return str(value).title()
			elif format_spec.startswith("date"):
				return self._format_date(value, format_spec)
			elif format_spec.startswith("number"):
				return self._format_number(value, format_spec)
			elif format_spec.startswith("currency"):
				return self._format_currency(value, format_spec)
			else:
				return str(value)

		except Exception:
			return str(value)

	def _format_date(self, value, format_spec):
		"""Formatear fecha."""
		try:
			# Extraer formato específico si existe
			if ":" in format_spec:
				_, date_format = format_spec.split(":", 1)
			else:
				date_format = "%Y-%m-%d"

			# Convertir valor a datetime si es necesario
			if isinstance(value, str):
				# Intentar varios formatos comunes
				for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"]:
					try:
						dt = datetime.strptime(value, fmt)
						break
					except ValueError:
						continue
				else:
					return str(value)
			elif isinstance(value, datetime):
				dt = value
			else:
				return str(value)

			return dt.strftime(date_format)

		except Exception:
			return str(value)

	def _format_number(self, value, format_spec):
		"""Formatear número."""
		try:
			num = float(value)

			# Extraer especificación de decimales
			if ":" in format_spec:
				_, decimal_spec = format_spec.split(":", 1)
				decimals = int(decimal_spec) if decimal_spec.isdigit() else 2
			else:
				decimals = 2

			return f"{num:.{decimals}f}"

		except Exception:
			return str(value)

	def _format_currency(self, value, format_spec):
		"""Formatear moneda."""
		try:
			num = float(value)

			# Extraer símbolo de moneda
			if ":" in format_spec:
				_, currency_symbol = format_spec.split(":", 1)
			else:
				currency_symbol = "$"

			return f"{currency_symbol}{num:,.2f}"

		except Exception:
			return str(value)

	def _format_value(self, value):
		"""Formatear valor básico."""
		if value is None:
			return ""
		elif isinstance(value, bool):
			return "true" if value else "false"
		elif isinstance(value, (int, float)):
			return str(value)
		else:
			return frappe.utils.escape_html(str(value))

	def build(self):
		"""Construir XML final."""
		try:
			# Reemplazar variables si no se ha hecho
			if not hasattr(self, "xml_content"):
				self.replace_variables()

			# Validar estructura XML
			self.validate_structure()

			# Agregar namespace si se especificó
			if self.namespace:
				self.xml_content = self._add_namespace_to_root()

			return self.xml_content

		except Exception as e:
			frappe.throw(_("Error construyendo XML: {0}").format(str(e)))

	def validate_structure(self):
		"""Validar estructura XML."""
		try:
			ET.fromstring(self.xml_content)
		except ET.ParseError as e:
			frappe.throw(_("XML generado inválido: {0}").format(str(e)))

	def _add_namespace_to_root(self):
		"""Agregar namespace al elemento raíz."""
		try:
			# Parsear XML
			root = ET.fromstring(self.xml_content)

			# Agregar namespace al elemento raíz
			root.set("xmlns", self.namespace)

			# Retornar XML con namespace
			return ET.tostring(root, encoding="unicode")

		except Exception as e:
			frappe.log_error(f"Error agregando namespace: {str(e)}")
			return self.xml_content

	def get_variables_used(self):
		"""Obtener lista de variables usadas en el template."""
		variable_pattern = r"\{\{\s*([^}]+)\s*\}\}"
		return re.findall(variable_pattern, self.template)

	def validate_template(self):
		"""Validar que el template tenga estructura correcta."""
		try:
			# Verificar que tenga variables
			variables = self.get_variables_used()
			if not variables:
				return False, _("Template no contiene variables")

			# Intentar construcción con datos de prueba
			test_values = {var: f"test_{var}" for var in variables}
			test_builder = AddendaXMLBuilder(self.template, test_values)
			test_xml = test_builder.replace_variables().build()

			return True, _("Template válido")

		except Exception as e:
			return False, _("Template inválido: {0}").format(str(e))

	@staticmethod
	def create_sample_template(addenda_type):
		"""Crear template de ejemplo para un tipo de addenda."""
		try:
			# Template básico
			template = """<?xml version="1.0" encoding="UTF-8"?>
<{addenda_type}>
    <DatosGenerales
        fecha="{{ cfdi_fecha }}"
        total="{{ cfdi_total }}"
        uuid="{{ cfdi_uuid }}" />
    <Emisor rfc="{{ emisor_rfc }}" nombre="{{ emisor_nombre }}" />
    <Receptor rfc="{{ receptor_rfc }}" nombre="{{ receptor_nombre }}" />
</{addenda_type}>""".format(addenda_type=addenda_type)

			return template

		except Exception as e:
			frappe.log_error(f"Error creando template de ejemplo: {str(e)}")
			return ""
