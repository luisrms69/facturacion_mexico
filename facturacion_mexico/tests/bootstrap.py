import frappe

def _create_basic_warehouse_types():
    """Crear tipos de warehouse básicos que Company necesita.

    Evita el error 'Could not find Warehouse Type: Transit'.
    """
    warehouse_types = ["Stores", "Work In Progress", "Finished Goods", "Transit"]

    for wh_type in warehouse_types:
        if not frappe.db.exists("Warehouse Type", wh_type):
            frappe.get_doc({
                "doctype": "Warehouse Type",
                "name": wh_type,
            }).insert(ignore_permissions=True)

def _create_basic_erpnext_accounts():
    """Crear cuentas contables básicas de ERPNext requeridas para testing.

    Crea específicamente _Test Account Excise Duty - _TC con account_type="Tax".
    """
    companies = frappe.get_all("Company", filters={"abbr": "_TC"}, fields=["name", "abbr"], limit=1)

    if not companies:
        return

    company_name = companies[0].name
    company_abbr = companies[0].abbr

    # Cuentas básicas requeridas - especialmente Tax account
    basic_accounts = [
        ["_Test Bank", "Bank Accounts", 0, "Bank", None],
        ["_Test Cash", "Cash In Hand", 0, "Cash", None],
        ["_Test Receivable", "Current Assets", 0, "Receivable", None],
        ["_Test Payable", "Current Liabilities", 0, "Payable", None],
        ["_Test Account Excise Duty", "Current Assets", 0, "Tax", None],  # CRÍTICO: Tax account
    ]

    for account_name, parent_account, is_group, account_type, currency in basic_accounts:
        full_account_name = f"{account_name} - {company_abbr}"
        parent_account_name = f"{parent_account} - {company_abbr}"

        if frappe.db.exists("Account", full_account_name):
            continue

        if not frappe.db.exists("Account", parent_account_name):
            continue

        try:
            account_doc = {
                "doctype": "Account",
                "account_name": account_name,
                "parent_account": parent_account_name,
                "company": company_name,
                "is_group": is_group,
            }

            if account_type:
                account_doc["account_type"] = account_type

            if currency:
                account_doc["account_currency"] = currency

            frappe.get_doc(account_doc).insert(ignore_permissions=True)
        except Exception:
            pass  # Continue with other accounts

def _create_basic_cost_centers():
    """Crear cost centers básicos requeridos para testing."""
    companies = frappe.get_all("Company", filters={"abbr": "_TC"}, fields=["name", "abbr"], limit=1)

    if not companies:
        return

    company_name = companies[0].name
    company_abbr = companies[0].abbr

    cost_centers = ["_Test Cost Center", "_Test Cost Center 2"]

    for cost_center_base_name in cost_centers:
        cost_center_name = f"{cost_center_base_name} - {company_abbr}"

        if frappe.db.exists("Cost Center", cost_center_name):
            continue

        try:
            frappe.get_doc({
                "doctype": "Cost Center",
                "cost_center_name": cost_center_base_name,
                "company": company_name,
                "is_group": 0,
                "parent_cost_center": f"{company_name} - {company_abbr}",
            }).insert(ignore_permissions=True)
        except Exception:
            pass  # Continue with other cost centers

def ensure_test_deps():
    _create_basic_warehouse_types()
    _ensure_erpnext_baseline_company_inr()
    _create_basic_erpnext_accounts()
    _create_basic_cost_centers()
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
    # Buscar específicamente la cuenta Tax que creamos
    acc = frappe.db.get_value("Account",
        {"company": "_Test Company", "account_type": "Tax"}, "name"
    )
    if not acc:
        # Fallback: buscar la cuenta específica que creamos
        acc = "_Test Account Excise Duty - _TC"
        if frappe.db.exists("Account", acc):
            return acc
        # Último fallback: cualquier cuenta de la compañía
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