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
	get_cuenta_descuentos,
)


def preparar_como_descuento(doc) -> dict:
	"""Preparar la Credit Note (borrador) como descuento/bonificación (sin cambiar el Item).

	Guards mínimos (servidor):
	  - Return con factura de origen (return_against);
	  - en borrador;
	  - cuenta de descuentos configurada para la empresa.
	"""
	if not doc.get("is_return") or not doc.get("return_against"):
		frappe.throw(_("Esta acción solo aplica a notas de crédito con factura de origen (return_against)."))
	if doc.get("docstatus", 0) != 0:
		frappe.throw(_("Solo se puede aplicar mientras la nota de crédito está en borrador."))

	cuenta = get_cuenta_descuentos(doc.get("company"))
	if not cuenta:
		frappe.throw(
			_(
				"No hay 'Cuenta de Descuentos y Bonificaciones' configurada para la empresa {0}. "
				"Configúrela en Facturacion Mexico Company Settings antes de aplicar el descuento."
			).format(doc.get("company")),
			title=_("Cuenta de Descuentos No Configurada"),
		)

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
