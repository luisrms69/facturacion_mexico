"""
Utilidades para manejo mejorado de errores - Resolución de CodeQL
Patrones seguros para manejo de excepciones específicas
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, Optional, Union

import frappe


class AddendaException(Exception):
	"""Excepción base para el módulo de addendas."""

	def __init__(self, message: str, error_code: str | None = None, details: dict | None = None):
		super().__init__(message)
		self.error_code = error_code
		self.details = details or {}


class XMLParsingError(AddendaException):
	"""Error específico de parsing XML."""

	pass


class ValidationError(AddendaException):
	"""Error específico de validación."""

	pass


class ConfigurationError(AddendaException):
	"""Error específico de configuración."""

	pass


def safe_execute(
	func: Callable,
	*args,
	default_return: Any = None,
	log_errors: bool = True,
	allowed_exceptions: tuple = (),
	**kwargs,
) -> Any:
	"""
	Ejecutar función de forma segura con manejo específico de errores.

	Args:
		func: Función a ejecutar
		*args: Argumentos posicionales
		default_return: Valor por defecto si hay error
		log_errors: Si loggear errores
		allowed_exceptions: Tupla de excepciones permitidas que se re-lanzan
		**kwargs: Argumentos nombrados

	Returns:
		Resultado de la función o default_return
	"""
	try:
		return func(*args, **kwargs)
	except allowed_exceptions:
		# Re-lanzar excepciones permitidas
		raise
	except (ValueError, TypeError, KeyError) as e:
		if log_errors:
			frappe.log_error(f"Error de validación en {func.__name__}: {e!s}", "Safe Execute")
		return default_return
	except OSError as e:
		if log_errors:
			frappe.log_error(f"Error de E/S en {func.__name__}: {e!s}", "Safe Execute")
		return default_return
	except Exception as e:
		if log_errors:
			frappe.log_error(f"Error inesperado en {func.__name__}: {e!s}", "Safe Execute")
		return default_return


def handle_xml_errors(default_return: Any = None, log_prefix: str = "XML Error"):
	"""
	Decorador para manejo específico de errores XML.

	Args:
		default_return: Valor por defecto si hay error
		log_prefix: Prefijo para logging
	"""

	def decorator(func):
		@wraps(func)
		def wrapper(*args, **kwargs):
			try:
				return func(*args, **kwargs)
			except (ET.ParseError, etree.XMLSyntaxError) as e:
				frappe.log_error(f"{log_prefix} - XML Parse Error: {e!s}", f"{func.__name__}")
				return default_return
			except (UnicodeDecodeError, UnicodeError) as e:
				frappe.log_error(f"{log_prefix} - Encoding Error: {e!s}", f"{func.__name__}")
				return default_return
			except (ValueError, TypeError) as e:
				frappe.log_error(f"{log_prefix} - Value Error: {e!s}", f"{func.__name__}")
				return default_return
			except Exception as e:
				frappe.log_error(f"{log_prefix} - Unexpected Error: {e!s}", f"{func.__name__}")
				return default_return

		return wrapper

	return decorator


def handle_database_errors(default_return: Any = None, log_prefix: str = "Database Error"):
	"""
	Decorador para manejo específico de errores de base de datos.

	Args:
		default_return: Valor por defecto si hay error
		log_prefix: Prefijo para logging
	"""

	def decorator(func):
		@wraps(func)
		def wrapper(*args, **kwargs):
			try:
				return func(*args, **kwargs)
			except frappe.DoesNotExistError as e:
				frappe.log_error(f"{log_prefix} - Record Not Found: {e!s}", f"{func.__name__}")
				return default_return
			except frappe.DuplicateEntryError as e:
				frappe.log_error(f"{log_prefix} - Duplicate Entry: {e!s}", f"{func.__name__}")
				return default_return
			except frappe.PermissionError as e:
				frappe.log_error(f"{log_prefix} - Permission Error: {e!s}", f"{func.__name__}")
				return default_return
			except Exception as e:
				frappe.log_error(f"{log_prefix} - Database Error: {e!s}", f"{func.__name__}")
				return default_return

		return wrapper

	return decorator


def handle_api_errors(default_return: Any = None, log_prefix: str = "API Error"):
	"""
	Decorador para manejo específico de errores de API.

	Args:
		default_return: Valor por defecto si hay error
		log_prefix: Prefijo para logging
	"""

	def decorator(func):
		@wraps(func)
		def wrapper(*args, **kwargs):
			try:
				return func(*args, **kwargs)
			except (ConnectionError, TimeoutError) as e:
				frappe.log_error(f"{log_prefix} - Connection Error: {e!s}", f"{func.__name__}")
				return default_return
			except (ValueError, KeyError) as e:
				frappe.log_error(f"{log_prefix} - Data Error: {e!s}", f"{func.__name__}")
				return default_return
			except Exception as e:
				frappe.log_error(f"{log_prefix} - API Error: {e!s}", f"{func.__name__}")
				return default_return

		return wrapper

	return decorator


# Imports necesarios
try:
	import xml.etree.ElementTree as ET

	from lxml import etree
except ImportError:
	# Fallback si lxml no está disponible
	ET = None
	etree = None
