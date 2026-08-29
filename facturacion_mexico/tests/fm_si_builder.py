"""Infraestructura de tests — builder de Sales Invoice reales con cuentas cableadas.

NO es código productivo: vive solo en la suite. Resuelve cuentas reales de una company
de prueba con plan de cuentas completo (`_Test Company`) para que `insert()` + `submit()`
no fallen con «Income Account None cannot be same as Debit To None» cuando el site usa como
default una company sin plan de cuentas (p. ej. la mínima "Test PCV Company").

Reutilizable por:
  - tests que necesitan una Sales Invoice real submitted (RC-A: re-facturación, check PPD);
  - tests de clasificación de notas de crédito (#223), que requieren una SI de origen
    submitted y su Sales Invoice Return persistida.
"""

import frappe

# Company canónica de ERPNext con plan de cuentas completo en el site de tests.
TEST_COMPANY = "_Test Company"


def resolve_test_accounts(company: str = TEST_COMPANY) -> tuple[str, str]:
	"""Devuelve `(debit_to, income_account)` reales de la company de prueba.

	`debit_to` prefiere la cuenta «Debtors» (Receivable canónica); `income_account`
	prefiere una cuenta «Sales» de tipo Income. Ambos con fallback al primer registro
	del tipo correspondiente para no acoplarse a un nombre exacto.
	"""
	debit_to = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Receivable", "is_group": 0, "name": ["like", "%Debtors%"]},
		"name",
	) or frappe.db.get_value(
		"Account", {"company": company, "account_type": "Receivable", "is_group": 0}, "name"
	)
	income_account = frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Income", "is_group": 0, "name": ["like", "Sales -%"]},
		"name",
	) or frappe.db.get_value("Account", {"company": company, "root_type": "Income", "is_group": 0}, "name")
	return debit_to, income_account


def _resolve_cost_center(company: str, cost_center: str | None) -> str | None:
	if cost_center:
		return cost_center
	return frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")


def make_submitted_si(
	*,
	customer: str,
	item_code: str,
	company: str = TEST_COMPANY,
	cost_center: str | None = None,
	qty: float = 1,
	rate: float = 1000,
	currency: str | None = None,
	do_submit: bool = True,
	item_overrides: dict | None = None,
	si_overrides: dict | None = None,
):
	"""Crea una Sales Invoice real con `debit_to`, `income_account` y `cost_center`
	cableados a cuentas reales de `company`, la inserta y (por defecto) la envía.

	Devuelve el documento (`frappe.model.document.Document`).
	"""
	debit_to, income_account = resolve_test_accounts(company)
	cc = _resolve_cost_center(company, cost_center)

	si = frappe.new_doc("Sales Invoice")
	si.company = company
	si.customer = customer
	si.debit_to = debit_to
	if cc:
		si.cost_center = cc
	si.currency = currency or frappe.db.get_value("Company", company, "default_currency")
	si.conversion_rate = 1.0
	if si_overrides:
		for k, v in si_overrides.items():
			setattr(si, k, v)

	line = {
		"item_code": item_code,
		"qty": qty,
		"rate": rate,
		"income_account": income_account,
		"cost_center": cc,
	}
	if item_overrides:
		line.update(item_overrides)
	si.append("items", line)

	si.insert(ignore_permissions=True)
	if do_submit:
		si.submit()
	return si
