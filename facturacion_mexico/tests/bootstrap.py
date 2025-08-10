import frappe

def ensure_test_deps():
    _ensure_erpnext_baseline_company_inr()
    _ensure_item_tax_template("_Test Account Excise Duty @ 10 - _TC", 10)
    _ensure_item_tax_template("_Test Account Excise Duty @ 12 - _TC", 12)

def _ensure_erpnext_baseline_company_inr():
    # El test que falla busca específicamente "_Test Company" con abbr "_TC"
    # Crear _Test Company si no existe (datos mínimos requeridos)
    if not frappe.db.exists("Company", "_Test Company"):
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "_Test Company",
            "abbr": "_TC",
            "default_currency": "INR",
            "country": "India"
        })
        company.insert(ignore_permissions=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure test company exists before other dependencies

def _pick_any_tax_account_in_inr():
    # El baseline suele traer cuentas en INR; tomamos alguna válida (liability o cualquiera)
    acc = frappe.db.get_value("Account",
        {"company": "_Test Company", "root_type": "Liability"}, "name"
    )
    if not acc:
        acc = frappe.db.get_value("Account", {"company": "_Test Company"}, "name")
    return acc

def _ensure_item_tax_template(name: str, rate_percent: float):
    if frappe.db.exists("Item Tax Template", name):
        return
    tax_account = _pick_any_tax_account_in_inr()
    doc = frappe.get_doc({
        "doctype": "Item Tax Template",
        "title": name,
        "name": name,  # nombre exacto que los tests esperan
        "company": "_Test Company",
        "taxes": [{"tax_type": tax_account, "tax_rate": rate_percent}]
    })
    doc.insert()
    frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure test dependencies are persisted before test execution