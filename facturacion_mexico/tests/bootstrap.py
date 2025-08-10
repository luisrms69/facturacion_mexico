import frappe

def ensure_test_deps():
    _ensure_test_company()
    _ensure_item_tax_template("_Test Account Excise Duty @ 10 - _TC", 10)
    _ensure_item_tax_template("_Test Account Excise Duty @ 12 - _TC", 12)

def _ensure_test_company():
    # Garantiza la compañía de pruebas que usan los tests de ERPNext
    if not frappe.db.exists("Company", "_Test Company"):
        # Crear la compañía de testing manualmente con datos mínimos
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "_Test Company",
            "abbr": "_TC",
            "default_currency": "MXN",
            "country": "Mexico"
        })
        company.insert(ignore_permissions=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure test company exists before other dependencies

def _pick_any_tax_account():
    # Selecciona una cuenta válida para el template; ajusta si quieres algo más específico
    acc = frappe.db.get_value("Account", {"company": "_Test Company", "root_type": "Liability"}, "name")
    if not acc:
        acc = frappe.db.get_value("Account", {"company": "_Test Company"}, "name")
    return acc

def _ensure_item_tax_template(name: str, rate_percent: float):
    if frappe.db.exists("Item Tax Template", name):
        return
    tax_account = _pick_any_tax_account()
    doc = frappe.get_doc({
        "doctype": "Item Tax Template",
        "title": name,          # Para que coincida también en UI
        "name": name,           # Importante: nombre EXACTO que espera el runner
        "company": "_Test Company",
        "taxes": [{
            "tax_type": tax_account,
            "tax_rate": rate_percent  # en %
        }]
    })
    doc.insert()
    frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure test dependencies are persisted before test execution