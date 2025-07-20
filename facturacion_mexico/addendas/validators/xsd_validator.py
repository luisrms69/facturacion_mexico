"""
XSD Validator - Sprint 3
Validador de XML contra esquemas XSD para addendas
"""

import io
from typing import Optional

import frappe
from frappe import _
from lxml import etree

from facturacion_mexico.utils.secure_xml import secure_parse_xml, validate_xml_size


class XSDValidator:
	"""Validador de XML contra esquemas XSD."""

	def __init__(self, xsd_schema: str):
		"""
		Inicializar con esquema XSD.

		Args:
			xsd_schema (str): Contenido del esquema XSD
		"""
		self.xsd_schema = xsd_schema
		self.schema = None
		self.errors = []
		self.warnings = []
		self._parse_schema()

	def _parse_schema(self):
		"""Parsear y compilar el esquema XSD."""
		try:
			# Parsear esquema XSD
			schema_doc = secure_parse_xml(self.xsd_schema, parser_type="lxml")
			self.schema = etree.XMLSchema(schema_doc)

		except etree.XMLSchemaParseError as e:
			self.errors.append(f"Error en esquema XSD: {e!s}")
			self.schema = None
		except etree.XMLSyntaxError as e:
			self.errors.append(f"XML sintácticamente incorrecto en esquema: {e!s}")
			self.schema = None
		except Exception as e:
			self.errors.append(f"Error inesperado parseando esquema: {e!s}")
			self.schema = None

	def validate(self, xml_content: str) -> bool:
		"""
		Validar XML contra el esquema.

		Args:
			xml_content (str): Contenido XML a validar

		Returns:
			bool: True si es válido, False si no
		"""
		self.errors.clear()
		self.warnings.clear()

		if not self.schema:
			self.errors.append("No hay esquema XSD válido para validación")
			return False

		try:
			# Parsear XML
			xml_doc = secure_parse_xml(xml_content, parser_type="lxml")

			# Validar contra esquema
			is_valid = self.schema.validate(xml_doc)

			if not is_valid:
				# Recopilar errores de validación
				for error in self.schema.error_log:
					self.errors.append(f"Línea {error.line}: {error.message}")

			return is_valid

		except etree.XMLSyntaxError as e:
			self.errors.append(f"XML sintácticamente incorrecto: {e!s}")
			return False
		except Exception as e:
			self.errors.append(f"Error durante validación: {e!s}")
			return False

	def validate_with_details(self, xml_content: str) -> tuple[bool, list[str], list[str]]:
		"""
		Validar XML y retornar detalles completos.

		Args:
			xml_content (str): Contenido XML a validar

		Returns:
			Tuple[bool, List[str], List[str]]: (is_valid, errors, warnings)
		"""
		is_valid = self.validate(xml_content)
		return is_valid, self.errors.copy(), self.warnings.copy()

	def get_errors(self) -> list[str]:
		"""Obtener lista de errores de la última validación."""
		return self.errors.copy()

	def get_warnings(self) -> list[str]:
		"""Obtener lista de advertencias de la última validación."""
		return self.warnings.copy()

	def get_error_summary(self) -> str:
		"""Obtener resumen de errores como string."""
		if not self.errors:
			return ""

		return "; ".join(self.errors)

	def validate_multiple_files(self, xml_files: list[str]) -> list[dict]:
		"""
		Validar múltiples archivos XML.

		Args:
			xml_files (List[str]): Lista de contenidos XML

		Returns:
			List[dict]: Lista de resultados de validación
		"""
		results = []

		for i, xml_content in enumerate(xml_files):
			is_valid, errors, warnings = self.validate_with_details(xml_content)

			results.append(
				{
					"file_index": i,
					"is_valid": is_valid,
					"errors": errors,
					"warnings": warnings,
					"error_count": len(errors),
					"warning_count": len(warnings),
				}
			)

		return results

	def get_schema_info(self) -> dict:
		"""Obtener información sobre el esquema XSD."""
		if not self.schema:
			return {"valid": False, "error": "No hay esquema válido"}

		try:
			# Información básica del esquema
			schema_doc = secure_parse_xml(self.xsd_schema, parser_type="lxml")

			info = {
				"valid": True,
				"target_namespace": schema_doc.get("targetNamespace", ""),
				"element_form_default": schema_doc.get("elementFormDefault", "unqualified"),
				"attribute_form_default": schema_doc.get("attributeFormDefault", "unqualified"),
				"version": schema_doc.get("version", ""),
				"elements": [],
				"complex_types": [],
				"simple_types": [],
			}

			# Extraer elementos definidos
			elements = schema_doc.xpath("//xs:element", namespaces={"xs": "http://www.w3.org/2001/XMLSchema"})
			for element in elements:
				name = element.get("name")
				if name:
					info["elements"].append(
						{
							"name": name,
							"type": element.get("type", ""),
							"min_occurs": element.get("minOccurs", "1"),
							"max_occurs": element.get("maxOccurs", "1"),
						}
					)

			# Extraer tipos complejos
			complex_types = schema_doc.xpath(
				"//xs:complexType", namespaces={"xs": "http://www.w3.org/2001/XMLSchema"}
			)
			for complex_type in complex_types:
				name = complex_type.get("name")
				if name:
					info["complex_types"].append(name)

			# Extraer tipos simples
			simple_types = schema_doc.xpath(
				"//xs:simpleType", namespaces={"xs": "http://www.w3.org/2001/XMLSchema"}
			)
			for simple_type in simple_types:
				name = simple_type.get("name")
				if name:
					info["simple_types"].append(name)

			return info

		except Exception as e:
			return {"valid": False, "error": f"Error extrayendo información: {e!s}"}

	def suggest_fixes(self, xml_content: str) -> list[str]:
		"""
		Sugerir correcciones para errores de validación.

		Args:
			xml_content (str): Contenido XML con errores

		Returns:
			List[str]: Lista de sugerencias
		"""
		suggestions = []

		if not self.validate(xml_content):
			for error in self.errors:
				suggestion = self._analyze_error_and_suggest(error)
				if suggestion:
					suggestions.append(suggestion)

		return suggestions

	def _analyze_error_and_suggest(self, error: str) -> str | None:
		"""Analizar error y sugerir corrección."""
		error_lower = error.lower()

		# Errores comunes y sugerencias basados en los mensajes reales de lxml
		if "is not a valid value of the atomic type" in error_lower:
			if "xs:date" in error_lower:
				return "Corregir formato de fecha. Use formato ISO: YYYY-MM-DD (ej: 2025-07-20)"
			elif "xs:decimal" in error_lower or "xs:number" in error_lower:
				return "Corregir formato numérico. Use formato decimal (ej: 1000.00)"
			elif "xs:int" in error_lower or "xs:integer" in error_lower:
				return "Corregir formato de número entero (ej: 123)"
			else:
				return "Verificar que el valor cumple con las restricciones del tipo de dato"

		if "missing child element" in error_lower and "expected is" in error_lower:
			# Extraer el elemento faltante del mensaje
			import re

			match = re.search(r"Expected is.*?\{[^}]*\}([^)]*)", error)
			if match:
				missing_element = match.group(1).strip()
				return f"Agregar elemento obligatorio faltante: <{missing_element}>"
			else:
				return "Agregar elementos obligatorios que faltan según el esquema"

		if "element" in error_lower and "not expected" in error_lower:
			return "Verificar que todos los elementos estén en el orden correcto según el esquema"

		if "namespace" in error_lower:
			return "Verificar que los namespaces estén declarados correctamente"

		if "attribute" in error_lower and ("required" in error_lower or "missing" in error_lower):
			return "Agregar atributos obligatorios que faltan"

		# Fallback genérico
		return "Revisar la estructura del XML contra el esquema XSD"

	def create_validation_report(self, xml_content: str, include_schema_info: bool = False) -> dict:
		"""
		Crear reporte completo de validación.

		Args:
			xml_content (str): Contenido XML a validar
			include_schema_info (bool): Incluir información del esquema

		Returns:
			dict: Reporte completo
		"""
		is_valid, errors, warnings = self.validate_with_details(xml_content)

		report = {
			"timestamp": frappe.utils.now(),
			"is_valid": is_valid,
			"errors": errors,
			"warnings": warnings,
			"error_count": len(errors),
			"warning_count": len(warnings),
			"suggestions": self.suggest_fixes(xml_content) if not is_valid else [],
		}

		if include_schema_info:
			report["schema_info"] = self.get_schema_info()

		return report

	@staticmethod
	def validate_xml_against_xsd(xml_content: str, xsd_content: str) -> dict:
		"""
		Método estático para validación rápida.

		Args:
			xml_content (str): Contenido XML
			xsd_content (str): Contenido XSD

		Returns:
			dict: Resultado de validación
		"""
		try:
			validator = XSDValidator(xsd_content)
			return validator.create_validation_report(xml_content)
		except Exception as e:
			return {
				"timestamp": frappe.utils.now(),
				"is_valid": False,
				"errors": [f"Error durante validación: {e!s}"],
				"warnings": [],
				"error_count": 1,
				"warning_count": 0,
				"suggestions": [],
			}

	def is_schema_valid(self) -> bool:
		"""Verificar si el esquema XSD es válido."""
		return self.schema is not None

	def get_schema_validation_errors(self) -> list[str]:
		"""Obtener errores de validación del esquema."""
		return self.errors if not self.schema else []


# Funciones de utilidad para validación
def validate_addenda_xml(xml_content: str, addenda_type: str) -> dict:
	"""
	Validar XML de addenda contra su tipo.

	Args:
		xml_content (str): Contenido XML de la addenda
		addenda_type (str): Nombre del tipo de addenda

	Returns:
		dict: Resultado de validación
	"""
	try:
		# Obtener esquema XSD del tipo de addenda
		addenda_doc = frappe.get_doc("Addenda Type", addenda_type)

		if not addenda_doc.xsd_schema:
			return {
				"is_valid": True,
				"message": _("No hay esquema XSD definido para validación"),
				"errors": [],
				"warnings": [_("Validación XSD omitida - no hay esquema definido")],
			}

		# Validar
		validator = XSDValidator(addenda_doc.xsd_schema)
		report = validator.create_validation_report(xml_content)

		return {
			"is_valid": report["is_valid"],
			"message": _("Validación XSD completada"),
			"errors": report["errors"],
			"warnings": report["warnings"],
			"suggestions": report.get("suggestions", []),
		}

	except frappe.DoesNotExistError:
		return {
			"is_valid": False,
			"message": _("Tipo de addenda no encontrado: {0}").format(addenda_type),
			"errors": [_("Tipo de addenda no existe")],
			"warnings": [],
		}
	except Exception as e:
		frappe.log_error(f"Error validando addenda XML: {e!s}")
		return {
			"is_valid": False,
			"message": _("Error durante validación: {0}").format(str(e)),
			"errors": [str(e)],
			"warnings": [],
		}


@frappe.whitelist()
def validate_xml_against_schema(xml_content, xsd_content):
	"""
	API endpoint para validar XML contra esquema XSD.

	Args:
		xml_content (str): Contenido XML
		xsd_content (str): Contenido XSD

	Returns:
		dict: Resultado de validación
	"""
	try:
		return XSDValidator.validate_xml_against_xsd(xml_content, xsd_content)
	except Exception as e:
		frappe.log_error(f"Error en API de validación XSD: {e!s}")
		return {"is_valid": False, "errors": [str(e)], "warnings": [], "error_count": 1, "warning_count": 0}
