"""
Setup de Payment Terms estándar para facturacion_mexico.

ensure_default_payment_terms()
    Crea los Payment Terms y Payment Terms Templates FM estándar si no existen.
    Idempotente: puede ejecutarse múltiples veces sin duplicar ni sobrescribir.
    Se llama desde after_install. Para sitios existentes, ejecutar manualmente:
        bench --site <site> execute facturacion_mexico.setup.payment_terms.ensure_default_payment_terms
"""

import frappe

_PAYMENT_TERMS = [
	{"name": "FM Pago de contado", "credit_days": 0},
	{"name": "FM Pago a 15 días", "credit_days": 15},
	{"name": "FM Pago a 30 días", "credit_days": 30},
	{"name": "FM Pago a 60 días", "credit_days": 60},
	{"name": "FM Pago a 90 días", "credit_days": 90},
]


def ensure_default_payment_terms():
	"""Crea Payment Terms y Payment Terms Templates FM estándar si no existen."""
	for pt in _PAYMENT_TERMS:
		_ensure_payment_term(pt["name"], pt["credit_days"])

	for pt in _PAYMENT_TERMS:
		_ensure_payment_terms_template(pt["name"])

	frappe.db.commit()  # nosemgrep: frappe-manual-commit


def _ensure_payment_term(name: str, credit_days: int):
	if frappe.db.exists("Payment Term", name):
		return
	doc = frappe.new_doc("Payment Term")
	doc.payment_term_name = name
	doc.invoice_portion = 100
	doc.due_date_based_on = "Day(s) after invoice date"
	doc.credit_days = credit_days
	doc.insert(ignore_permissions=True)


def _ensure_payment_terms_template(name: str):
	if frappe.db.exists("Payment Terms Template", name):
		return
	doc = frappe.new_doc("Payment Terms Template")
	doc.template_name = name
	doc.append(
		"terms",
		{
			"payment_term": name,
			"invoice_portion": 100,
			"credit_days_based_on": "Day(s) after invoice date",
			"credit_days": _credit_days_for(name),
		},
	)
	doc.insert(ignore_permissions=True)


def _credit_days_for(name: str) -> int:
	for pt in _PAYMENT_TERMS:
		if pt["name"] == name:
			return pt["credit_days"]
	return 0
