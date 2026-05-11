"""
Reclasificación fiscal de impuestos en Payment Entry.

Patrón comprobado en producción (llantascs.dev — template "002 IVA Cobranza"):

  charge_type          = On Paid Amount
  included_in_paid_amount = 1          → sin Cash/Bank counterpart
  add_deduct_tax       = Add           → para ambas filas
  rate destino         = +rate_neta    → Cr cuenta_destino
  rate origen          = -rate_neta    → Dr cuenta_origen (negativo = reverso)

Fórmula de rate:
  monto_reclasificar = tax_amount * (allocated / grand_total)
  rate = monto_reclasificar / pe.paid_amount * 100

  Esto maneja automáticamente:
  - IVA puro 16%:         rate ≈ 13.793%
  - IVA frontera 8%:      rate ≈ 7.407%
  - Mezcla 16%+0%:        rate = lo que resulte de los montos reales
  - Múltiples facturas:   rate ponderada sobre paid_amount total

GL resultante (sin Cash extra):
  Dr  cuenta_origen   monto_reclasificar
  Cr  cuenta_destino  monto_reclasificar
"""

from dataclasses import dataclass, field
from typing import Optional

import frappe
from frappe.utils import flt

_RECLAS_MARKER = "[RECLAS-MX]"

_DOCTYPES_SOPORTADOS = {
	"Sales Invoice": "Cobro",
	"Purchase Invoice": "Pago",
}


# ---------------------------------------------------------------------------
# Hook principal
# ---------------------------------------------------------------------------


def cargar_impuestos_en_payment_entry(doc, method=None):
	"""Hook validate — carga filas de reclasificación en PE.taxes."""
	_limpiar_filas_reclas(doc)

	paid_amount = flt(doc.paid_amount)
	if paid_amount <= 0:
		return

	grupos = _calcular_grupos_desde_doc(doc)
	if not grupos:
		return

	for (cuenta_origen, cuenta_destino, tipo_op), monto in grupos.items():
		monto = round(flt(monto), 6)
		if monto <= 0:
			continue

		# Rate efectiva: monto a reclasificar como % del paid_amount total
		rate = round(monto / paid_amount * 100, 6)
		calc_amount = round(rate / 100 * paid_amount, 2)
		desc = f"{_RECLAS_MARKER} {tipo_op} | {cuenta_origen} → {cuenta_destino}"

		# Fila destino: rate positivo → Cr cuenta_destino en GL
		doc.append(
			"taxes",
			{
				"charge_type": "On Paid Amount",
				"account_head": cuenta_destino,
				"description": desc,
				"add_deduct_tax": "Add",
				"included_in_paid_amount": 1,
				"rate": rate,
				"tax_amount": calc_amount,
				"base_tax_amount": calc_amount,
			},
		)

		# Fila origen: rate negativo → Dr cuenta_origen en GL
		doc.append(
			"taxes",
			{
				"charge_type": "On Paid Amount",
				"account_head": cuenta_origen,
				"description": desc,
				"add_deduct_tax": "Add",
				"included_in_paid_amount": 1,
				"rate": -rate,
				"tax_amount": -calc_amount,
				"base_tax_amount": -calc_amount,
			},
		)

	# Recalcular para que totals/base_tax_amount queden correctos antes del GL
	doc.apply_taxes()


def generar_reclasificacion_payment_entry(doc, method=None):
	"""Hook on_submit — no-op. ERPNext genera GL desde PE.taxes nativo."""
	pass


def cancelar_reclasificacion_payment_entry(doc, method=None):
	"""Hook on_cancel — no-op. ERPNext reversa GL nativo al cancelar."""
	pass


# ---------------------------------------------------------------------------
# Cálculo de grupos
# ---------------------------------------------------------------------------


def _limpiar_filas_reclas(doc):
	"""Elimina filas de reclasificación previas para recalcular."""
	doc.taxes = [t for t in doc.get("taxes", []) if _RECLAS_MARKER not in (t.description or "")]


def _calcular_grupos_desde_doc(doc) -> dict:
	"""
	Devuelve {(cuenta_origen, cuenta_destino, tipo_op): monto_total}
	con los montos proporcionales reales a reclasificar.
	"""
	grupos: dict = {}
	company = doc.company

	for ref in doc.get("references", []):
		if flt(ref.allocated_amount) <= 0:
			continue

		tipo_operacion = _DOCTYPES_SOPORTADOS.get(ref.reference_doctype)
		if not tipo_operacion:
			continue

		try:
			invoice = frappe.get_doc(ref.reference_doctype, ref.reference_name)
		except Exception:
			continue

		grand_total = flt(invoice.grand_total)
		if not grand_total:
			continue

		proporcion = flt(ref.allocated_amount) / grand_total

		for tax in invoice.get("taxes", []):
			tax_amount = flt(tax.tax_amount)
			if tax_amount == 0:
				continue

			cuenta_destino = frappe.db.get_value(
				"Mapeo Reclasificacion Fiscal Payment Entry",
				{
					"company": company,
					"tipo_operacion": tipo_operacion,
					"cuenta_origen": tax.account_head,
					"activo": 1,
				},
				"cuenta_destino",
			)
			if not cuenta_destino:
				frappe.log_error(
					f"Sin mapeo de reclasificación: {company} / {tipo_operacion} / "
					f"{tax.account_head}. Impuesto no reclasificado en PE {doc.name}.",
					"Reclasificación Fiscal Incompleta",
				)
				continue

			key = (tax.account_head, cuenta_destino, tipo_operacion)
			monto = round(tax_amount * proporcion, 6)
			grupos[key] = grupos.get(key, 0.0) + monto

	return grupos


# ---------------------------------------------------------------------------
# Diagnóstico (solo lectura)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def analizar_payment_entry_whitelisted(payment_entry_name: str) -> dict:
	"""Diagnóstico desde bench console — no modifica nada."""
	pe = frappe.get_doc("Payment Entry", payment_entry_name)
	paid_amount = flt(pe.paid_amount)
	grupos = _calcular_grupos_desde_doc(pe)

	resultado = {
		"payment_entry": pe.name,
		"paid_amount": paid_amount,
		"grupos": [],
	}
	for (origen, destino, tipo), monto in grupos.items():
		rate = round(monto / paid_amount * 100, 6) if paid_amount else 0
		resultado["grupos"].append(
			{
				"cuenta_origen": origen,
				"cuenta_destino": destino,
				"tipo_operacion": tipo,
				"monto_reclasificar": round(monto, 2),
				"rate_efectiva": rate,
			}
		)
	return resultado
