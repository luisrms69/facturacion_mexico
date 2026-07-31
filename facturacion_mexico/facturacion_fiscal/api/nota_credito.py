"""Acción de negocio para Notas de Crédito por descuento/bonificación (Issue #137).

UX: en una Credit Note (Sales Invoice Return) en borrador, el operador ejecuta
"Aplicar como Descuento / Bonificación". El sistema **conserva el Item original** (ERPNext exige que
el item_code exista en la factura origen) y expresa el descuento por descripción
('Descuento - <descripción original>') + cuenta de descuentos configurada por empresa como
income_account. El operador NO selecciona cuentas ni códigos SAT. Tras el Submit, la Factura Fiscal
Mexico detecta la cuenta y clasifica la nota como descuento (TipoRelación 01, UsoCFDI G02, MetodoPago
PUE, FormaPago 15). La ClaveProdServ del CFDI sigue siendo la del Item/línea original.
"""

import frappe
from frappe import _

from facturacion_mexico.facturacion_fiscal.utils import (
	apply_descuento_to_lines,
	credit_note_lines_use_discount_account,
	get_cuenta_descuentos,
)


def _discount_accounting_enabled() -> bool:
	"""True si ERPNext tiene activa la contabilidad de descuentos (Selling Settings)."""
	return bool(frappe.db.get_single_value("Selling Settings", "enable_discount_accounting"))


def preparar_como_descuento(doc) -> dict:
	"""Preparar la Credit Note (borrador) como descuento/bonificación (sin cambiar el Item).

	Guards mínimos (servidor):
	  - Return con factura de origen (return_against);
	  - en borrador;
	  - contabilidad de descuentos de ERPNext DESHABILITADA (ver nota abajo);
	  - cuenta de descuentos configurada para la empresa.
	"""
	if not doc.get("is_return") or not doc.get("return_against"):
		frappe.throw(_("Esta acción solo aplica a notas de crédito con factura de origen (return_against)."))
	if doc.get("docstatus", 0) != 0:
		frappe.throw(_("Solo se puede aplicar mientras la nota de crédito está en borrador."))

	# Precondición operativa (ADR 0025): 'Enable Discount Accounting' de ERPNext debe estar OFF.
	# Con ON y líneas que heredan discount_amount del origen, ERPNext activa su mecanismo nativo
	# (exige discount_account por línea) e invierte/infla el asiento de la nota. Nuestro mecanismo
	# usa cuenta_descuentos como income_account, NO discount_account. No se apaga el setting global
	# automáticamente (afectaría otros procesos): se bloquea antes de tocar la nota.
	if _discount_accounting_enabled():
		frappe.throw(
			_(
				"La contabilidad de descuentos de ERPNext (Selling Settings → 'Enable Discount "
				"Accounting') debe estar DESHABILITADA para emitir notas de crédito por descuento de "
				"Facturación México. Deshabilítela y vuelva a intentar. No se modificó la nota."
			),
			title=_("Enable Discount Accounting Activo"),
		)

	cuenta = get_cuenta_descuentos(doc.get("company"))
	if not cuenta:
		frappe.throw(
			_(
				"No hay 'Cuenta de Descuentos y Bonificaciones' configurada para la empresa {0}. "
				"Configúrela en Facturacion Mexico Company Settings antes de aplicar el descuento."
			).format(doc.get("company")),
			title=_("Cuenta de Descuentos No Configurada"),
		)

	# Un descuento/bonificación NO es devolución física → no debe mover inventario.
	# make_return_doc copió update_stock del origen; aquí se fuerza a 0.
	# Reversible: el valor correcto de una devolución es return_against.update_stock, así que un
	# futuro revert a "Devolución de mercancía" lo restaura desde el origen (determinista, 0 o 1).
	if doc.get("update_stock"):
		doc.update_stock = 0

	lineas = apply_descuento_to_lines(doc, cuenta)
	doc.save()
	return {"ok": True, "lineas": lineas}


@frappe.whitelist()
def aplicar_como_descuento(sales_invoice: str) -> dict:
	"""Punto de entrada desde la UI (botón en Sales Invoice Return en borrador).

	No devuelve el nombre de la cuenta: el usuario final nunca debe ver la cuenta técnica.
	"""
	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	return preparar_como_descuento(doc)


def preparar_reversion_a_devolucion(doc) -> dict:
	"""Revertir una nota preparada como descuento de vuelta a "Devolución de mercancía" (motivo 03).

	Restaura EXACTAMENTE desde el origen (sin adivinar cuentas): por cada línea usa su vínculo
	`sales_invoice_item` (poblado por make_return_doc) para leer el renglón de la factura de origen y
	restaurar `income_account` y `description`; restaura `update_stock` desde `return_against`.

	Guards mínimos (servidor):
	  - Return con factura de origen (return_against);
	  - en borrador (tras Submit no se revierte: aplica cancelación SAT).

	Si CUALQUIER línea no tiene vínculo exacto con su renglón de origen, se BLOQUEA sin modificar la
	nota y se listan las líneas afectadas (no se inventan cuentas contables).
	"""
	if not doc.get("is_return") or not doc.get("return_against"):
		frappe.throw(_("Esta acción solo aplica a notas de crédito con factura de origen (return_against)."))
	if doc.get("docstatus", 0) != 0:
		frappe.throw(_("Solo se puede revertir mientras la nota de crédito está en borrador."))

	origen = frappe.get_doc("Sales Invoice", doc.get("return_against"))
	origen_rows = {r.name: r for r in (origen.get("items") or [])}

	# Validación previa (sin mutación): cada línea debe mapearse EXACTAMENTE a su renglón de origen.
	faltantes = [
		row
		for row in (doc.get("items") or [])
		if not row.get("sales_invoice_item") or row.get("sales_invoice_item") not in origen_rows
	]
	if faltantes:
		detalle = ", ".join(
			_("línea {0} ({1})").format(row.get("idx"), row.get("item_code")) for row in faltantes
		)
		frappe.throw(
			_(
				"No se puede revertir a devolución: estas líneas no tienen un vínculo exacto con su "
				"renglón de la factura de origen, así que no es posible restaurar su cuenta contable sin "
				"adivinar. No se modificó la nota. Líneas: {0}."
			).format(detalle),
			title=_("Reversión No Segura"),
		)

	# Restaurar income_account y description desde el origen (exacto).
	n = 0
	for row in doc.get("items") or []:
		origen_row = origen_rows[row.get("sales_invoice_item")]
		row.income_account = origen_row.income_account
		row.description = origen_row.description
		n += 1

	# Restaurar update_stock desde el origen (cierra la reversibilidad del punto 1).
	doc.update_stock = origen.update_stock

	doc.save()
	return {"ok": True, "lineas": n}


@frappe.whitelist()
def revertir_a_devolucion(sales_invoice: str) -> dict:
	"""Punto de entrada desde la UI (botón inverso en Sales Invoice Return en borrador)."""
	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	return preparar_reversion_a_devolucion(doc)


@frappe.whitelist()
def estado_nota_descuento(sales_invoice: str) -> dict:
	"""Estado de la nota para decidir qué botón mostrar en la UI.

	Se basa en el estado CONTABLE real (income_account de todas las líneas == cuenta de descuentos
	configurada), no en la descripción (editable). Devuelve:
	  - cuenta_configurada: hay cuenta de descuentos para la empresa;
	  - es_descuento: la nota ya está preparada como descuento.
	"""
	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	cuenta = get_cuenta_descuentos(doc.get("company"))
	return {
		"cuenta_configurada": bool(cuenta),
		"es_descuento": credit_note_lines_use_discount_account(doc, cuenta),
	}
