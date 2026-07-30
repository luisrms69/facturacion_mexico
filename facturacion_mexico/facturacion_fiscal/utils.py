"""
Utilities for Facturacion Fiscal Mexico
Bridge functions for fiscal data access without duplication.
"""

import frappe

from facturacion_mexico.config.fiscal_states_config import FiscalStates


def get_cuenta_descuentos(company):
	"""Cuenta de ingresos configurada para descuentos/bonificaciones de una empresa.

	Se lee de Facturacion Mexico Company Settings.cuenta_descuentos (config por empresa,
	sin hardcode). Devuelve None si no hay empresa o no está configurada.
	"""
	if not company:
		return None
	return (
		frappe.db.get_value("Facturacion Mexico Company Settings", {"company": company}, "cuenta_descuentos")
		or None
	)


def credit_note_lines_use_discount_account(sales_invoice, cuenta_descuentos) -> bool:
	"""True si TODAS las líneas de ítem de la nota de crédito están contabilizadas contra
	la cuenta de descuentos configurada (income_account por línea).

	Señal de la Opción X: la intención de descuento se expresa nativamente al asignar
	income_account = cuenta configurada ANTES del Submit. Requiere cuenta configurada y ≥1 línea.
	Si alguna línea usa otra cuenta, retorna False (no inferir descuento — punto 8).
	"""
	if not cuenta_descuentos:
		return False
	doc = sales_invoice if hasattr(sales_invoice, "items") else frappe.get_doc("Sales Invoice", sales_invoice)
	items = doc.get("items") or []
	if not items:
		return False
	return all((row.get("income_account") == cuenta_descuentos) for row in items)


# Prefijo de descripción fiscal de una nota de crédito por descuento/bonificación.
DESCRIPCION_DESCUENTO = "Descuento"


def build_descuento_description(origen_desc) -> str:
	"""Descripción fiscal de una línea de descuento: 'Descuento - <descripción de la partida origen>'.

	Criterio del contador: no usar la descripción genérica 'Descuento' cuando exista una partida
	origen identificable. Si no hay descripción origen → 'Descuento'. Idempotente: si el texto ya
	empieza con 'Descuento' no vuelve a prefijar (evita 'Descuento - Descuento - ...').
	"""
	origen = (origen_desc or "").strip()
	if not origen:
		return DESCRIPCION_DESCUENTO
	if origen.lower().startswith(DESCRIPCION_DESCUENTO.lower()):
		return origen
	return f"{DESCRIPCION_DESCUENTO} - {origen}"


def apply_descuento_to_lines(doc, cuenta_descuentos) -> int:
	"""Preparar TODAS las líneas de la nota como descuento/bonificación, SIN cambiar el Item.

	ERPNext exige que el `item_code` de una nota de crédito con `return_against` exista en la factura
	origen (validación core `validate_returned_items`); por eso se **conserva el Item original** y el
	descuento se expresa por descripción + cuenta contable. Por cada línea:
	  - `description`     = 'Descuento - <descripción original>' (idempotente);
	  - `income_account`  = cuenta de descuentos configurada por empresa.

	Se conservan `item_code`, cantidad, precio, UOM e impuestos. La ClaveProdServ SAT
	del CFDI se obtiene normalmente del Item/línea original (item_code intacto). Devuelve el número de
	líneas afectadas. No guarda el documento (lo hace el llamador).
	"""
	n = 0
	for row in doc.get("items") or []:
		# Fuente de la descripción origen: description de la línea o, si está vacía, item_name
		# (mismo fallback que usa el flujo normal en resolve_concepto_description). ERPNext deja
		# description vacío cuando el Item maestro no tiene description, pero item_name sí se llena.
		row.description = build_descuento_description(row.get("description") or row.get("item_name"))
		row.income_account = cuenta_descuentos
		n += 1
	return n


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


def resolver_folio_vigente(sales_invoice_name):
	"""Read-only: folio (FFM.folio) de la SI si su FFM ligada es vigente, o "" si no.

	Vigente = FFM ligada (SI.fm_factura_fiscal_mx) con folio y status en
	{TIMBRADO, PENDIENTE_CANCELACION}. No escribe. Fuente única de la regla de vigencia:
	la reutilizan `sincronizar_folio_fiscal` (flujo en vivo) y el backfill.
	"""
	ffm_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")
	if not ffm_name:
		return ""
	row = frappe.db.get_value("Factura Fiscal Mexico", ffm_name, ["status", "folio"], as_dict=True)
	if row and row.status in _FOLIO_VIGENTE_STATES and str(row.folio or "").strip():
		return str(row.folio).strip()
	return ""


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
		folio = resolver_folio_vigente(sales_invoice_name)

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
