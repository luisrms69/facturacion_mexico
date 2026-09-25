"""Ruteo contable de ventas extranjeras → ``Sales Invoice Item.income_account``.

Aplica, para receptores extranjeros, la cuenta única configurable
``Configuracion Fiscal Mexico.cuenta_ingreso_venta_extranjera``. Las ventas
nacionales conservan íntegra la resolución nativa de ERPNext (Item → Item Group →
Brand → Company): este módulo NO toca ``income_account`` en ese caso.

Patrón two-phase (necesario para evitar contaminación de ``Item Default``):
``SellingController.validate`` llama ``set_default_income_account_for_item`` y, si una
línea lleva un ``income_account`` distinto al default de la empresa, lo persiste en el
``Item Default`` del artículo. Por eso:

* Fase 1 — ``before_validate`` (antes del controller): se blanquea ``income_account``
  de las líneas de una venta extranjera, para que el controller resuelva nativo
  y NO contamine el maestro.
* Fase 2 — ``validate`` (después del controller): se reaplica la cuenta extranjera a
  las líneas. En submit, si la operación es extranjera y la cuenta falta o es inválida,
  se bloquea (fail-closed).

Precedencia de la cuenta de la línea: **cuenta de descuentos > routing extranjero >
defaults nativos**. Una nota de crédito por descuento/bonificación marca sus líneas con
``income_account = cuenta_descuentos`` (ver ``facturacion_fiscal.utils``); esas líneas
NO se blanquean ni se reemplazan por la cuenta extranjera —de lo contrario se rompería
la detección de Motivo/TipoRelación 01—. El routing extranjero solo toca líneas que no
son de descuento; si TODAS son de descuento, no hay nada que rutear (ni fail-closed).

Se ejecuta igual en UI, API, ``insert()`` y en el importador ``cfdi_emitidos`` (que
dispara los mismos doc_events), sin lógica paralela.
"""

import frappe
from frappe import _

from facturacion_mexico.facturacion_fiscal.utils import get_cuenta_descuentos
from facturacion_mexico.ventas_extranjeras.clasificacion import (
	EXTRANJERA,
	clasificar_territorialidad,
)

# Flag de request para no reclasificar dos veces el mismo documento en un save.
_FLAG_TERRITORIALIDAD = "fm_territorialidad"


def _territorialidad(doc) -> str:
	"""Clasificar una vez por save y cachear en flags del documento."""
	cached = getattr(doc.flags, _FLAG_TERRITORIALIDAD, None)
	if cached:
		return cached
	tipo = clasificar_territorialidad(doc)
	setattr(doc.flags, _FLAG_TERRITORIALIDAD, tipo)
	return tipo


def get_cuenta_ingreso_extranjera(company: str) -> str | None:
	"""Cuenta de ingreso extranjera configurada para la empresa (o None)."""
	if not company:
		return None
	name = frappe.db.get_value("Configuracion Fiscal Mexico", {"company": company}, "name")
	if not name:
		return None
	return frappe.db.get_value("Configuracion Fiscal Mexico", name, "cuenta_ingreso_venta_extranjera") or None


def _cuenta_valida(cuenta: str, company: str) -> bool:
	"""La cuenta existe, es de la empresa, es Income, no es grupo y no está deshabilitada."""
	data = frappe.db.get_value(
		"Account", cuenta, ["root_type", "company", "is_group", "disabled"], as_dict=True
	)
	if not data:
		return False
	return bool(
		data.company == company and data.root_type == "Income" and not data.is_group and not data.disabled
	)


def _es_linea_descuento(row, cuenta_descuentos) -> bool:
	"""True si la línea está contabilizada contra la cuenta de descuentos configurada."""
	return bool(cuenta_descuentos) and row.get("income_account") == cuenta_descuentos


def before_validate(doc, method=None):
	"""Fase 1: para ventas extranjeras, blanquear ``income_account`` de las líneas.

	Así el controller resuelve nativo y ``set_default_income_account_for_item`` no
	escribe la cuenta extranjera en el ``Item Default`` del artículo. Las líneas de
	descuento (income_account == cuenta_descuentos) se preservan intactas.
	"""
	if _territorialidad(doc) != EXTRANJERA:
		return
	cuenta_desc = get_cuenta_descuentos(doc.get("company"))
	for row in doc.get("items") or []:
		if _es_linea_descuento(row, cuenta_desc):
			continue
		row.income_account = None


def validate(doc, method=None):
	"""Fase 2: reaplicar la cuenta extranjera tras el controller + fail-closed en submit."""
	if _territorialidad(doc) != EXTRANJERA:
		# Nacional / indeterminado: NO tocar income_account (resolución nativa ERPNext).
		return

	company = doc.get("company")
	cuenta_desc = get_cuenta_descuentos(company)
	# Solo se rutean líneas que NO son de descuento (cuenta_descuentos tiene precedencia).
	target_rows = [r for r in (doc.get("items") or []) if not _es_linea_descuento(r, cuenta_desc)]
	if not target_rows:
		# NC de descuento extranjera: cuenta_descuentos manda; nada que rutear ni bloquear.
		return

	cuenta = get_cuenta_ingreso_extranjera(company)
	enviando = getattr(doc, "docstatus", 0) == 1

	if not cuenta:
		if enviando:
			frappe.throw(
				_(
					"Venta extranjera: configure la <b>Cuenta de Ingreso — Venta Extranjera</b> "
					"en <b>Configuracion Fiscal Mexico</b> de la empresa {0} antes de enviar/timbrar."
				).format(company)
			)
		# Borrador permitido: no se aplica cuenta (queda resolución nativa hasta configurar).
		return

	if not _cuenta_valida(cuenta, company):
		if enviando:
			frappe.throw(
				_(
					"Venta extranjera: la cuenta de ingreso configurada {0} es inválida "
					"(empresa/tipo/estado). Corrija <b>Configuracion Fiscal Mexico</b>."
				).format(cuenta)
			)
		# Borrador: no aplicar una cuenta inválida.
		return

	for row in target_rows:
		row.income_account = cuenta
