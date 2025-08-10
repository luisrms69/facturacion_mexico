import frappe

def ensure_test_deps():
    _ensure_erpnext_baseline_company_inr()
    _ensure_item_tax_template("_Test Account Excise Duty @ 10 - _TC", 10)
    _ensure_item_tax_template("_Test Account Excise Duty @ 12 - _TC", 12)

def _ensure_erpnext_baseline_company_inr():
    # Crea la _Test Company en INR si no existe (o si existe mal configurada, la repara)
    from erpnext.tests.utils import create_test_company
    if not frappe.db.exists("Company", "_Test Company"):
        create_test_company()  # crea _Test Company con abbr _TC y baseline esperado (INR)

    # Si alguien cambió la moneda, normalízala a INR para el runner
    company = frappe.get_doc("Company", "_Test Company")
    if company.default_currency != "INR":
        company.default_currency = "INR"
        company.save()

        # Asegurar que cuentas de la _Test Company estén en INR (evita mismatch de Party Account)
        frappe.db.sql("""
            UPDATE `tabAccount`
               SET account_currency = 'INR'
             WHERE company = '_Test Company'
               AND (account_currency IS NULL OR account_currency <> 'INR')
        """)

        # Ajusta Price Lists de prueba si existen
        frappe.db.sql("""
            UPDATE `tabPrice List`
               SET currency = 'INR'
             WHERE selling = 1 OR buying = 1
        """)

        frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure ERPNext baseline test company normalization

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