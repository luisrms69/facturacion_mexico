"""
Fase 3 Issue #129 — Propagación de configuración de addenda Customer → Sales Invoice.

Reglas:
- Propagar Customer.fm_requires_addenda → SI.fm_addenda_required
  solo si fm_addenda_required está en 0 (default/vacío).
- Propagar Customer.fm_default_addenda_type → SI.fm_addenda_type
  solo si fm_addenda_type está vacío.
- No bloquear guardado de draft.
- No generar XML.
- No llamar AddendaService.render().
"""

import frappe
from frappe.utils import cint


def propagate_addenda_from_customer(doc, method=None):
	"""Hook Sales Invoice.validate — propaga flags de addenda desde Customer.

	Las notas de crédito (is_return=1) se excluyen: la addenda en facturas de
	devolución no es práctica estándar y requiere configuración explícita.
	"""
	if not doc.customer:
		return

	# Return invoices (notas de crédito) do not inherit addenda from customer
	if cint(doc.get("is_return")):
		return

	customer_requires = cint(frappe.db.get_value("Customer", doc.customer, "fm_requires_addenda") or 0)
	customer_type = frappe.db.get_value("Customer", doc.customer, "fm_default_addenda_type") or ""

	# fm_addenda_required: propagar desde Customer solo si SI aún no lo tiene activo
	if not cint(doc.get("fm_addenda_required")) and customer_requires:
		doc.fm_addenda_required = 1

	# fm_addenda_type: propagar desde Customer solo si SI no tiene tipo configurado
	if not doc.get("fm_addenda_type") and customer_type:
		doc.fm_addenda_type = customer_type
