"""
Utilities for Facturacion Fiscal Mexico
Bridge functions for fiscal data access without duplication.
"""

import frappe

from facturacion_mexico.config.fiscal_states_config import FiscalStates


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
		fiscal_doc_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")

		if not fiscal_doc_name:
			return None

		return frappe.db.get_value("Factura Fiscal Mexico", fiscal_doc_name, "fm_uuid")

	except Exception as e:
		frappe.log_error(
			f"Error obteniendo UUID fiscal para {sales_invoice_name}: {e!s}", "Get Invoice UUID Error"
		)
		return None


# Estados en los que el CFDI sigue existiendo y su folio es VIGENTE.
# PENDIENTE_CANCELACION: cancelación en curso pero aún no aceptada → el CFDI sigue vivo.
_FOLIO_VIGENTE_STATES = {FiscalStates.TIMBRADO, FiscalStates.PENDIENTE_CANCELACION}


def sincronizar_folio_fiscal(sales_invoice_name):
	"""Sincroniza Sales Invoice.fm_folio_fiscal con el FOLIO consecutivo del CFDI VIGENTE.

	Folio = el consecutivo del CFDI (`FFM.folio`), el que usa el cliente. NO es el UUID/timbre.
	Cache de solo lectura para reportes de Cuentas por Cobrar. La fuente fiscal sigue siendo
	Factura Fiscal Mexico; este campo es una proyección, no autoritativo. No usa FacturAPI:
	solo lee campos internos ya persistidos.

	Idempotente: recomputa desde el estado actual y escribe el folio vigente o lo limpia.
	Vigente = la FFM ligada (SI.fm_factura_fiscal_mx) tiene folio y su status está en
	{TIMBRADO, PENDIENTE_CANCELACION}. Si no hay FFM vigente ligada, el campo queda vacío.

	Se escribe con update_modified=False: una proyección de cache no debe alterar el timestamp
	de auditoría de la Sales Invoice (importante también para el backfill masivo).

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		str: El folio escrito, o "" si se limpió.
	"""
	try:
		folio = ""
		ffm_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")
		if ffm_name:
			row = frappe.db.get_value("Factura Fiscal Mexico", ffm_name, ["status", "folio"], as_dict=True)
			if row and row.status in _FOLIO_VIGENTE_STATES and str(row.folio or "").strip():
				folio = str(row.folio).strip()

		# Escribir solo si cambia (idempotencia, evita writes innecesarios)
		current = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_folio_fiscal") or ""
		if current != folio:
			frappe.db.set_value(
				"Sales Invoice", sales_invoice_name, "fm_folio_fiscal", folio, update_modified=False
			)

		return folio

	except Exception as e:
		frappe.log_error(
			f"Error sincronizando folio fiscal para {sales_invoice_name}: {e!s}",
			"Sincronizar Folio Fiscal Error",
		)
		return ""


def get_invoice_fiscal_data(sales_invoice_name):
	"""
	Obtener datos fiscales completos desde Factura Fiscal Mexico.

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		dict: Datos fiscales o dict vacío si no existe
	"""
	try:
		fiscal_doc_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")

		if not fiscal_doc_name:
			return {}

		fiscal_data = frappe.db.get_value(
			"Factura Fiscal Mexico",
			fiscal_doc_name,
			["fm_uuid", "serie", "folio", "total_fiscal", "status", "facturapi_id", "fecha_timbrado"],
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

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		bool: True si está timbrada, False en caso contrario
	"""
	try:
		fiscal_data = get_invoice_fiscal_data(sales_invoice_name)
		return bool(fiscal_data.get("fm_uuid") and fiscal_data.get("status") == FiscalStates.TIMBRADO)

	except Exception:
		return False
