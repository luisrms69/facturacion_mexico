"""
Utilidades para parsing seguro de XML - Protección contra XXE
Resuelve vulnerabilidades de seguridad identificadas por CodeQL
"""

import xml.etree.ElementTree as ET
from typing import Union

from lxml import etree


def secure_parse_xml(xml_content: str | bytes, parser_type: str = "lxml") -> etree._Element | ET.Element:
	"""
	Parsear XML de forma segura evitando vulnerabilidades XXE.

	Args:
		xml_content: Contenido XML como string o bytes
		parser_type: "lxml" o "etree" para especificar el parser

	Returns:
		Elemento XML parseado de forma segura

	Raises:
		ValueError: Si el XML es inválido
		Exception: Si hay errores de parsing
	"""
	if not xml_content:
		raise ValueError("Contenido XML vacío")

	# Convertir a bytes si es necesario
	if isinstance(xml_content, str):
		xml_bytes = xml_content.encode("utf-8")
	else:
		xml_bytes = xml_content

	if parser_type == "lxml":
		return _secure_parse_lxml(xml_bytes)
	else:
		return _secure_parse_etree(xml_bytes)


def _secure_parse_lxml(xml_bytes: bytes) -> etree._Element:
	"""Parsear con lxml de forma segura."""
	# Crear parser seguro que previene XXE attacks
	parser = etree.XMLParser(
		# Deshabilitar resolución de entidades externas
		resolve_entities=False,
		# Deshabilitar DTD processing
		no_network=True,
		# Deshabilitar carga de DTD externas
		load_dtd=False,
		# Límites de seguridad
		huge_tree=False,
		# Remover comentarios y processing instructions
		remove_comments=True,
		remove_pis=True,
	)

	try:
		return etree.fromstring(xml_bytes, parser=parser)
	except etree.XMLSyntaxError as e:
		raise ValueError(f"XML inválido: {e!s}") from e
	except Exception as e:
		raise Exception(f"Error parseando XML: {e!s}") from e


def _secure_parse_etree(xml_bytes: bytes) -> ET.Element:
	"""Parsear con ElementTree de forma segura."""
	# ElementTree es más seguro por defecto, pero añadimos validaciones
	try:
		# Verificar que no contenga DTD o entidades externas peligrosas
		xml_str = xml_bytes.decode("utf-8")

		# Buscar patrones potencialmente peligrosos
		dangerous_patterns = [
			"<!DOCTYPE",
			"<!ENTITY",
			"SYSTEM ",
			"PUBLIC ",
			"file://",
			"ftp://",
			"gopher://",
		]

		xml_upper = xml_str.upper()
		for pattern in dangerous_patterns:
			if pattern.upper() in xml_upper:
				raise ValueError(f"XML contiene patrón potencialmente peligroso: {pattern}")

		return ET.fromstring(xml_bytes)

	except ET.ParseError as e:
		raise ValueError(f"XML inválido: {e!s}") from e
	except UnicodeDecodeError as e:
		raise ValueError(f"Encoding XML inválido: {e!s}") from e
	except Exception as e:
		raise Exception(f"Error parseando XML: {e!s}") from e


def validate_xml_size(xml_content: str | bytes, max_size_mb: int = 10) -> bool:
	"""
	Validar que el XML no exceda un tamaño máximo.

	Args:
		xml_content: Contenido XML
		max_size_mb: Tamaño máximo en MB

	Returns:
		True si el tamaño es válido

	Raises:
		ValueError: Si excede el tamaño máximo
	"""
	if isinstance(xml_content, str):
		size_bytes = len(xml_content.encode("utf-8"))
	else:
		size_bytes = len(xml_content)

	max_size_bytes = max_size_mb * 1024 * 1024

	if size_bytes > max_size_bytes:
		raise ValueError(f"XML excede tamaño máximo ({max_size_mb}MB): {size_bytes / 1024 / 1024:.2f}MB")

	return True


def sanitize_xml_string(xml_string: str) -> str:
	"""
	Sanitizar string XML removiendo caracteres potencialmente peligrosos.

	Args:
		xml_string: String XML a sanitizar

	Returns:
		String XML sanitizado
	"""
	if not xml_string:
		return ""

	# Remover caracteres de control excepto tab, newline, carriage return
	sanitized = "".join(char for char in xml_string if ord(char) >= 32 or char in "\t\n\r")

	return sanitized
