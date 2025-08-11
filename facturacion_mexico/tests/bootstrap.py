import frappe
import json
import os

def ensure_test_deps():
    """
    Bootstrap estático según recomendación del experto - Opción B.

    Carga fixtures estáticos desde JSON para evitar whack-a-mole infinito.
    Solo hace frappe.get_doc(data).insert(ignore_if_duplicate=True).
    """
    _load_static_fixtures()
    _normalize_currency_if_needed()

def _load_static_fixtures():
    """Cargar todos los fixtures estáticos desde JSON."""

    # Cargar Item Tax Templates
    _load_json_fixtures("item_tax_template.json")

    # Cargar Accounts (Tax hierarchy)
    _load_json_fixtures("account.json")

def _load_json_fixtures(filename):
    """Cargar fixtures desde archivo JSON."""
    fixtures_path = os.path.join(
        frappe.get_app_path("facturacion_mexico"),
        "tests", "test_records", filename
    )

    if not os.path.exists(fixtures_path):
        return

    with open(fixtures_path, 'r', encoding='utf-8') as f:
        fixtures = json.load(f)

    for data in fixtures:
        try:
            # Verificar si ya existe
            if frappe.db.exists(data["doctype"], data["name"]):
                continue

            # Crear documento
            doc = frappe.get_doc(data)
            doc.insert(ignore_permissions=True, ignore_if_duplicate=True)

        except Exception as e:
            # Log pero continuar con otros fixtures
            print(f"Warning: Failed to create {data['doctype']} {data['name']}: {e}")
            continue

def _normalize_currency_if_needed():
    """Normalizar currency solo si es necesario."""
    if frappe.db.exists("Company", "_Test Company"):
        company = frappe.get_doc("Company", "_Test Company")
        if company.default_currency != "INR":
            company.default_currency = "INR"
            company.save()

            # Alinear accounts a INR para evitar mismatches
            frappe.db.sql("""
                UPDATE `tabAccount`
                SET account_currency = %s
                WHERE company = %s
                AND (account_currency IS NULL OR account_currency <> %s)
            """, ("INR", "_Test Company", "INR"))

            frappe.db.commit()