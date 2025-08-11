import frappe

def run():
    """
    Pre-seeding para CI - Ejecutar ANTES del test runner.

    Crea todas las dependencias que el runner necesita ANTES de cargar test_records.json.
    Idempotente: se puede ejecutar múltiples veces sin conflictos.
    """
    print("🌱 CI Pre-seeding iniciado...")

    # 1. Crear Warehouse Types básicos
    _create_warehouse_types()

    # 2. Crear _Test Company
    _create_test_company()

    # 3. Crear estructura de cuentas Tax
    _create_tax_accounts()

    # 4. Crear Item Tax Templates
    _create_item_tax_templates()

    # 5. Crear masters básicos ERPNext
    _create_basic_masters()

    frappe.db.commit()
    print("✅ CI Pre-seeding completado")

def _create_warehouse_types():
    """Crear Warehouse Types requeridos por ERPNext."""
    warehouse_types = ["Stores", "Work In Progress", "Finished Goods", "Transit"]

    for wh_type in warehouse_types:
        if not frappe.db.exists("Warehouse Type", wh_type):
            frappe.get_doc({
                "doctype": "Warehouse Type",
                "name": wh_type,
            }).insert(ignore_permissions=True, ignore_if_duplicate=True)

    print(f"✅ Warehouse Types creados: {warehouse_types}")

def _create_test_company():
    """Crear _Test Company con configuración estándar ERPNext."""
    if not frappe.db.exists("Company", "_Test Company"):
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "_Test Company",
            "abbr": "_TC",
            "default_currency": "INR",
            "country": "India"
        })
        company.insert(ignore_permissions=True)
        print("✅ _Test Company creado")
    else:
        print("ℹ️  _Test Company ya existe")

def _create_tax_accounts():
    """Crear estructura de cuentas Tax requeridas por Item Tax Templates."""
    accounts = [
        # Cuenta padre grupo
        {
            "name": "Current Liabilities - _TC",
            "account_name": "Current Liabilities",
            "company": "_Test Company",
            "is_group": 1,
            "root_type": "Liability"
        },
        # Cuenta Tax padre grupo
        {
            "name": "Duties and Taxes - _TC",
            "account_name": "Duties and Taxes",
            "company": "_Test Company",
            "parent_account": "Current Liabilities - _TC",
            "is_group": 1,
            "root_type": "Liability"
        },
        # Cuenta Tax específica
        {
            "name": "_Test Account Excise Duty - _TC",
            "account_name": "_Test Account Excise Duty",
            "company": "_Test Company",
            "parent_account": "Duties and Taxes - _TC",
            "is_group": 0,
            "account_type": "Tax",
            "root_type": "Liability",
            "account_currency": "INR"
        }
    ]

    for account_data in accounts:
        if not frappe.db.exists("Account", account_data["name"]):
            try:
                frappe.get_doc(account_data).insert(ignore_permissions=True)
                print(f"✅ Account creado: {account_data['name']}")
            except Exception as e:
                # Skip si parent account no existe aún
                print(f"⚠️  Saltando {account_data['name']}: {e}")
                continue

def _create_item_tax_templates():
    """Crear Item Tax Templates que los tests requieren."""
    templates = [
        {"name": "_Test Account Excise Duty @ 10 - _TC", "rate": 10},
        {"name": "_Test Account Excise Duty @ 12 - _TC", "rate": 12},
        {"name": "_Test Account Excise Duty @ 15 - _TC", "rate": 15},
        {"name": "_Test Account Excise Duty @ 20 - _TC", "rate": 20},
        {"name": "_Test Item Tax Template 1 - _TC", "rate": 10}
    ]

    tax_account = "_Test Account Excise Duty - _TC"

    # Verificar que la cuenta Tax existe
    if not frappe.db.exists("Account", tax_account):
        print(f"⚠️  Tax account {tax_account} no existe, saltando templates")
        return

    for template in templates:
        if not frappe.db.exists("Item Tax Template", template["name"]):
            try:
                frappe.get_doc({
                    "doctype": "Item Tax Template",
                    "name": template["name"],
                    "title": template["name"],
                    "company": "_Test Company",
                    "taxes": [{"tax_type": tax_account, "tax_rate": template["rate"]}]
                }).insert(ignore_permissions=True, ignore_if_duplicate=True)
                print(f"✅ Item Tax Template creado: {template['name']}")
            except Exception as e:
                print(f"⚠️  Error creando template {template['name']}: {e}")

def _create_basic_masters():
    """Crear masters básicos que ERPNext tests requieren."""

    # UOMs básicos
    uoms = ["Unit", "Nos", "Box", "Kg"]
    for uom in uoms:
        if not frappe.db.exists("UOM", uom):
            frappe.get_doc({
                "doctype": "UOM",
                "uom_name": uom,
            }).insert(ignore_permissions=True, ignore_if_duplicate=True)
    print(f"✅ UOMs creados: {uoms}")

    # Customer Groups
    customer_groups = [
        {"name": "All Customer Groups", "parent": None, "is_group": 1},
        {"name": "Individual", "parent": "All Customer Groups", "is_group": 0},
        {"name": "Commercial", "parent": "All Customer Groups", "is_group": 0}
    ]

    for group in customer_groups:
        if not frappe.db.exists("Customer Group", group["name"]):
            doc_data = {
                "doctype": "Customer Group",
                "customer_group_name": group["name"],
                "is_group": group["is_group"]
            }
            if group["parent"]:
                doc_data["parent_customer_group"] = group["parent"]

            frappe.get_doc(doc_data).insert(ignore_permissions=True, ignore_if_duplicate=True)

    print("✅ Customer Groups creados")

    # Supplier Groups
    supplier_groups = [
        {"name": "All Supplier Groups", "parent": None, "is_group": 1},
        {"name": "Services", "parent": "All Supplier Groups", "is_group": 0},
        {"name": "Hardware", "parent": "All Supplier Groups", "is_group": 0}
    ]

    for group in supplier_groups:
        if not frappe.db.exists("Supplier Group", group["name"]):
            doc_data = {
                "doctype": "Supplier Group",
                "supplier_group_name": group["name"],
                "is_group": group["is_group"]
            }
            if group["parent"]:
                doc_data["parent_supplier_group"] = group["parent"]

            frappe.get_doc(doc_data).insert(ignore_permissions=True, ignore_if_duplicate=True)

    print("✅ Supplier Groups creados")

if __name__ == "__main__":
    run()