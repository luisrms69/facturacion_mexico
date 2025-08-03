"""
Utilidades para Facturación Fiscal México
Funciones puente para acceso a datos fiscales sin duplicación
"""

import frappe


def get_invoice_uuid(sales_invoice_name):
	"""
	Obtener UUID fiscal desde Factura Fiscal Mexico vía referencia.
	Reemplaza el campo duplicado fm_uuid_fiscal en Sales Invoice.

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		str|None: UUID fiscal si existe, None si no hay documento fiscal asociado
	"""
	try:
		# Obtener referencia al documento fiscal
		fiscal_doc_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")

		if not fiscal_doc_name:
			return None

		# Obtener UUID desde Factura Fiscal Mexico
		uuid = frappe.db.get_value("Factura Fiscal Mexico", fiscal_doc_name, "uuid")

		return uuid

	except Exception as e:
		frappe.log_error(
			f"Error obteniendo UUID fiscal para {sales_invoice_name}: {e!s}", "Get Invoice UUID Error"
		)
		return None


def get_invoice_fiscal_data(sales_invoice_name):
	"""
	Obtener datos fiscales completos desde Factura Fiscal Mexico.
	Preparado para extensión futura con serie, folio, totales, etc.

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		dict: Datos fiscales o dict vacío si no existe
	"""
	try:
		# Obtener referencia al documento fiscal
		fiscal_doc_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")

		if not fiscal_doc_name:
			return {}

		# Obtener datos fiscales completos
		fiscal_data = frappe.db.get_value(
			"Factura Fiscal Mexico",
			fiscal_doc_name,
			["uuid", "serie", "folio", "total_fiscal", "fm_fiscal_status", "facturapi_id", "fecha_timbrado"],
			as_dict=True,
		)

		return fiscal_data or {}

	except Exception as e:
		frappe.log_error(
			f"Error obteniendo datos fiscales para {sales_invoice_name}: {e!s}",
			"Get Invoice Fiscal Data Error",
		)
		return {}


def has_fiscal_document(sales_invoice_name):
	"""
	Verificar si Sales Invoice tiene documento fiscal asociado.

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		bool: True si tiene documento fiscal, False en caso contrario
	"""
	try:
		fiscal_doc_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")

		return bool(fiscal_doc_name)

	except Exception:
		return False


def is_invoice_stamped(sales_invoice_name):
	"""
	Verificar si la factura está timbrada fiscalmente.
	Reemplaza verificación de fm_uuid_fiscal.

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		bool: True si está timbrada, False en caso contrario
	"""
	try:
		fiscal_data = get_invoice_fiscal_data(sales_invoice_name)

		# Verificar que tenga UUID y estado Timbrada
		return fiscal_data.get("uuid") and fiscal_data.get("fm_fiscal_status") == "Timbrada"

	except Exception:
		return False
