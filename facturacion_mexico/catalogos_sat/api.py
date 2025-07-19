from typing import Any

import frappe
from frappe import _


@frappe.whitelist()
def get_uso_cfdi_for_customer(customer_name: str) -> list[dict[str, Any]]:
	"""
	Obtener usos CFDI válidos para un cliente específico.

	Args:
	        customer_name: Nombre del cliente

	Returns:
	        Lista de usos CFDI válidos según el tipo de cliente
	"""
	try:
		# Obtener datos del cliente
		customer = frappe.get_doc("Customer", customer_name)

		# Determinar si es persona física o moral basado en RFC
		es_persona_fisica = _is_persona_fisica(customer.rfc) if customer.rfc else True

		# Filtros base para catálogos activos
		filters = {"vigencia_hasta": [">=", frappe.utils.today()]}

		# Agregar filtro según tipo de persona
		if es_persona_fisica:
			filters["aplica_fisica"] = 1
		else:
			filters["aplica_moral"] = 1

		# Obtener usos CFDI válidos
		usos_cfdi = frappe.get_all(
			"Uso CFDI SAT",
			filters=filters,
			fields=["name", "code", "description", "aplica_fisica", "aplica_moral"],
			order_by="code",
		)

		# Si el cliente tiene uso por defecto, marcarlo
		if customer.uso_cfdi_default:
			for uso in usos_cfdi:
				if uso.name == customer.uso_cfdi_default:
					uso["is_default"] = True
					break

		return usos_cfdi

	except Exception as e:
		frappe.logger().error(f"Error obteniendo usos CFDI para cliente {customer_name}: {e!s}")
		frappe.throw(_("Error al obtener usos CFDI válidos:") + str(e))

	return []


@frappe.whitelist()
def get_regimen_fiscal_for_customer(customer_name: str) -> list[dict[str, Any]]:
	"""
	Obtener regímenes fiscales válidos para un cliente específico.

	Args:
	        customer_name: Nombre del cliente

	Returns:
	        Lista de regímenes fiscales válidos según el tipo de cliente
	"""
	try:
		# Obtener datos del cliente
		customer = frappe.get_doc("Customer", customer_name)

		# Determinar si es persona física o moral basado en RFC
		es_persona_fisica = _is_persona_fisica(customer.rfc) if customer.rfc else True

		# Filtros base para catálogos activos
		filters = {"vigencia_hasta": [">=", frappe.utils.today()]}

		# Agregar filtro según tipo de persona
		if es_persona_fisica:
			filters["aplica_fisica"] = 1
		else:
			filters["aplica_moral"] = 1

		# Obtener regímenes fiscales válidos
		regimenes_fiscales = frappe.get_all(
			"Regimen Fiscal SAT",
			filters=filters,
			fields=["name", "code", "description", "aplica_fisica", "aplica_moral"],
			order_by="code",
		)

		# Si el cliente tiene régimen por defecto, marcarlo
		if customer.regimen_fiscal:
			for regimen in regimenes_fiscales:
				if regimen.name == customer.regimen_fiscal:
					regimen["is_default"] = True
					break

		return regimenes_fiscales

	except Exception as e:
		frappe.logger().error(f"Error obteniendo regímenes fiscales para cliente {customer_name}: {e!s}")
		frappe.throw(_("Error al obtener regímenes fiscales válidos:") + str(e))

	return []


@frappe.whitelist()
def sync_sat_catalogs():
	"""
	Sincronizar catálogos SAT (tarea programada).

	Nota: Por ahora mantiene catálogos estáticos ya que son estables.
	En futuras versiones se puede implementar sync desde SAT.
	"""
	try:
		# Verificar que existan catálogos básicos
		catalogs_to_verify = [
			("Uso CFDI SAT", "G01"),
			("Regimen Fiscal SAT", "601"),
			("Forma Pago SAT", "01"),
			("Metodo Pago SAT", "PUE"),
		]

		missing_catalogs = []

		for doctype, sample_code in catalogs_to_verify:
			if not frappe.db.exists(doctype, sample_code):
				missing_catalogs.append(doctype)

		if missing_catalogs:
			frappe.logger().warning(f"Catálogos SAT faltantes: {missing_catalogs}")
			# Crear catálogos básicos si faltan
			_create_basic_catalogs()

		# Log de sincronización exitosa
		frappe.logger().info("Sincronización de catálogos SAT completada")

		return {
			"success": True,
			"message": "Catálogos SAT sincronizados exitosamente",
			"missing_catalogs": missing_catalogs,
		}

	except Exception as e:
		frappe.logger().error(f"Error sincronizando catálogos SAT: {e!s}")
		return {"success": False, "message": f"Error en sincronización: {e!s}"}


def _is_persona_fisica(rfc: str) -> bool:
	"""
	Determinar si un RFC corresponde a persona física o moral.

	Args:
	        rfc: RFC a verificar

	Returns:
	        True si es persona física, False si es moral
	"""
	if not rfc or len(rfc) < 12:
		return True

	# Persona física: 13 caracteres (4 letras + 6 números + 3 caracteres)
	# Persona moral: 12 caracteres (3 letras + 6 números + 3 caracteres)
	return len(rfc.strip()) == 13


def _create_basic_catalogs():
	"""Crear catálogos básicos SAT si no existen."""
	from facturacion_mexico.install import create_basic_sat_catalogs

	create_basic_sat_catalogs()


@frappe.whitelist()
def validate_rfc(rfc: str) -> dict[str, Any]:
	"""
	Validar RFC con dígito verificador.

	Args:
	        rfc: RFC a validar

	Returns:
	        Diccionario con resultado de validación
	"""
	try:
		if not rfc:
			return {"valid": False, "message": "RFC no puede estar vacío"}

		rfc = rfc.strip().upper()

		# Validar longitud
		if len(rfc) not in [12, 13]:
			return {"valid": False, "message": "RFC debe tener 12 o 13 caracteres"}

		# Validar RFCs genéricos
		generic_rfcs = ["XAXX010101000", "XEXX010101000"]
		if rfc in generic_rfcs:
			return {"valid": False, "message": "No se permite RFC genérico"}

		# Validar formato básico
		if not _validate_rfc_format(rfc):
			return {"valid": False, "message": "Formato de RFC inválido"}

		# Validar dígito verificador
		if not _validate_rfc_check_digit(rfc):
			return {"valid": False, "message": "Dígito verificador de RFC inválido"}

		# Determinar tipo de persona
		es_persona_fisica = _is_persona_fisica(rfc)

		return {
			"valid": True,
			"message": "RFC válido",
			"is_persona_fisica": es_persona_fisica,
			"is_persona_moral": not es_persona_fisica,
			"formatted_rfc": rfc,
		}

	except Exception as e:
		frappe.logger().error(f"Error validando RFC {rfc}: {e!s}")
		return {"valid": False, "message": f"Error en validación: {e!s}"}


def _validate_rfc_format(rfc: str) -> bool:
	"""Validar formato básico de RFC."""
	import re

	if len(rfc) == 13:
		# Persona física: 4 letras + 6 dígitos + 3 caracteres
		pattern = r"^[A-Z]{4}[0-9]{6}[A-Z0-9]{3}$"
	else:
		# Persona moral: 3 letras + 6 dígitos + 3 caracteres
		pattern = r"^[A-Z]{3}[0-9]{6}[A-Z0-9]{3}$"

	return bool(re.match(pattern, rfc))


def _validate_rfc_check_digit(rfc: str) -> bool:
	"""
	Validar dígito verificador de RFC.

	Implementación básica del algoritmo de validación del SAT.
	"""
	try:
		# Tabla de valores para el cálculo
		valores = {
			"0": 0,
			"1": 1,
			"2": 2,
			"3": 3,
			"4": 4,
			"5": 5,
			"6": 6,
			"7": 7,
			"8": 8,
			"9": 9,
			"A": 10,
			"B": 11,
			"C": 12,
			"D": 13,
			"E": 14,
			"F": 15,
			"G": 16,
			"H": 17,
			"I": 18,
			"J": 19,
			"K": 20,
			"L": 21,
			"M": 22,
			"N": 23,
			"O": 24,
			"P": 25,
			"Q": 26,
			"R": 27,
			"S": 28,
			"T": 29,
			"U": 30,
			"V": 31,
			"W": 32,
			"X": 33,
			"Y": 34,
			"Z": 35,
		}

		# Extraer dígito verificador
		digito_verificador = rfc[-1]
		rfc_sin_digito = rfc[:-1]

		# Calcular suma ponderada
		suma = 0
		factor = len(rfc_sin_digito) + 1

		for char in rfc_sin_digito:
			if char in valores:
				suma += valores[char] * factor
				factor -= 1

		# Calcular módulo
		modulo = suma % 11

		# Determinar dígito esperado
		if modulo == 0:
			digito_esperado = "0"
		elif modulo == 1:
			digito_esperado = "A"
		else:
			digito_esperado = str(11 - modulo)

		return digito_verificador == digito_esperado

	except Exception as e:
		frappe.logger().error(f"Error validando dígito verificador: {e!s}")
		return False
