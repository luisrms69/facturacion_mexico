import frappe
from frappe import _
from frappe.utils import now_datetime


def after_install():
	"""Ejecutar después de instalar la app."""
	frappe.logger().info("Starting Facturacion Mexico installation...")
	create_initial_configuration()
	create_basic_sat_catalogs()  # PRIMERO: crear catálogos SAT
	create_custom_fields_for_erpnext()  # SEGUNDO: crear custom fields que referencian catálogos
	frappe.logger().info("Facturacion Mexico installation completed successfully.")
	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure installation process completes successfully


def create_initial_configuration():
	"""Crear configuración inicial de Facturación México."""
	if not frappe.db.exists("Facturacion Mexico Settings", "Facturacion Mexico Settings"):
		settings = frappe.new_doc("Facturacion Mexico Settings")
		settings.sandbox_mode = 1
		settings.timeout = 30
		settings.auto_generate_ereceipts = 1
		settings.send_email_default = 0
		settings.download_files_default = 1
		settings.save()
		frappe.msgprint(_("Configuración inicial de Facturación México creada"))


def create_custom_fields_for_erpnext():
	"""Crear custom fields en DocTypes de ERPNext."""
	from facturacion_mexico.facturacion_fiscal.custom_fields import create_all_custom_fields

	create_all_custom_fields()


def create_basic_sat_catalogs():
	"""Crear catálogos básicos SAT."""

	# Crear algunos registros básicos de Uso CFDI
	basic_uso_cfdi = [
		{"code": "G01", "description": "Adquisición de mercancías", "aplica_fisica": 1, "aplica_moral": 1},
		{
			"code": "G02",
			"description": "Devoluciones, descuentos o bonificaciones",
			"aplica_fisica": 1,
			"aplica_moral": 1,
		},
		{"code": "G03", "description": "Gastos en general", "aplica_fisica": 1, "aplica_moral": 1},
		{"code": "P01", "description": "Por definir", "aplica_fisica": 1, "aplica_moral": 1},
	]

	for uso in basic_uso_cfdi:
		if not frappe.db.exists("Uso CFDI SAT", uso["code"]):
			doc = frappe.new_doc("Uso CFDI SAT")
			doc.update(uso)
			doc.save()

	# Crear algunos registros básicos de Régimen Fiscal
	basic_regimen_fiscal = [
		{
			"code": "601",
			"description": "General de Ley Personas Morales",
			"aplica_fisica": 0,
			"aplica_moral": 1,
		},
		{
			"code": "603",
			"description": "Personas Morales con Fines no Lucrativos",
			"aplica_fisica": 0,
			"aplica_moral": 1,
		},
		{
			"code": "605",
			"description": "Sueldos y Salarios e Ingresos Asimilados a Salarios",
			"aplica_fisica": 1,
			"aplica_moral": 0,
		},
		{
			"code": "612",
			"description": "Personas Físicas con Actividades Empresariales y Profesionales",
			"aplica_fisica": 1,
			"aplica_moral": 0,
		},
	]

	for regimen in basic_regimen_fiscal:
		if not frappe.db.exists("Regimen Fiscal SAT", regimen["code"]):
			doc = frappe.new_doc("Regimen Fiscal SAT")
			doc.update(regimen)
			doc.save()

	frappe.msgprint(_("Catálogos básicos SAT creados"))


def before_tests():
	"""
	Configuración pre-tests para facturacion_mexico.

	Crea warehouse types básicos que ERPNext necesita para testing,
	específicamente "Transit" que causa el error LinkValidationError.
	Establece contexto de testing siguiendo patrón condominium_management.
	"""
	frappe.clear_cache()

	# Establecer flag de testing siguiendo patrón condominium_management
	frappe.flags.in_test = True

	# Crear warehouse types básicos antes de que test runner inicie
	_create_basic_warehouse_types()

	# Setup básico de ERPNext si no existe - PRIMERO crear Company
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	year = now_datetime().year

	if not frappe.get_list("Company"):
		try:
			setup_complete(
				{
					"currency": "MXN",
					"full_name": "Administrator",
					"company_name": "Facturacion Mexico Test LLC",
					"timezone": "America/Mexico_City",
					"company_abbr": "FMT",
					"industry": "Services",
					"country": "Mexico",
					"fy_start_date": f"{year}-01-01",
					"fy_end_date": f"{year}-12-31",
					"company_tagline": "Testing Company",
					"chart_of_accounts": "Standard",
				}
			)
		except Exception as e:
			print(f"Warning: setup_complete failed: {e}")
			_create_minimal_company()

	# DESPUÉS de crear Company, asegurar que registros básicos existen
	_ensure_basic_erpnext_records()

	# Crear cuentas contables básicas de ERPNext para testing
	_create_basic_erpnext_accounts()

	# Crear tax categories básicas para testing
	_create_basic_tax_categories()

	# Crear cost centers básicos para testing
	_create_basic_cost_centers()

	# Crear item tax templates básicos para testing
	_create_basic_item_tax_templates()

	# Setup roles - usar ERPNext si disponible
	try:
		from erpnext.setup.utils import enable_all_roles_and_domains

		enable_all_roles_and_domains()
	except (ImportError, Exception) as e:
		print(f"Warning: enable_all_roles_and_domains failed: {e}")
		_setup_basic_roles_frappe_only()

	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure test setup completes successfully


def _create_basic_warehouse_types():
	"""
	Crear tipos de warehouse básicos que Company necesita.

	Evita el error 'Could not find Warehouse Type: Transit'.
	"""
	warehouse_types = ["Stores", "Work In Progress", "Finished Goods", "Transit"]

	for wh_type in warehouse_types:
		if not frappe.db.exists("Warehouse Type", wh_type):
			frappe.get_doc(
				{
					"doctype": "Warehouse Type",
					"name": wh_type,
				}
			).insert(ignore_permissions=True)
			print(f"✅ Created Warehouse Type: {wh_type}")


def _ensure_basic_erpnext_records():
	"""
	Asegurar que registros básicos requeridos por ERPNext existen.

	NOTA: Esta función debe ejecutarse DESPUÉS de crear Company.
	"""
	# Obtener la primera company disponible
	companies = frappe.get_all("Company", fields=["name"], limit=1)
	company_name = companies[0].name if companies else None

	# Department - crear "All Departments" como grupo principal
	if not frappe.db.exists("Department", "All Departments"):
		department_doc = {
			"doctype": "Department",
			"department_name": "All Departments",
			"is_group": 1,
		}

		# Solo agregar company si existe una
		if company_name:
			department_doc["company"] = company_name

		frappe.get_doc(department_doc).insert(ignore_permissions=True, ignore_if_duplicate=True)
		print(
			f"✅ Created root department: All Departments{' with company: ' + company_name if company_name else ''}"
		)


def _create_minimal_company():
	"""
	Crear Company mínima como fallback cuando setup_complete falla.
	"""
	if not frappe.db.exists("Company", "Facturacion Mexico Test LLC"):
		# Asegurar que warehouse types existen primero
		_create_basic_warehouse_types()

		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "Facturacion Mexico Test LLC",
				"abbr": "FMT",
				"default_currency": "MXN",
				"country": "Mexico",
			}
		)
		company.insert(ignore_permissions=True)
		print("✅ Created minimal company: Facturacion Mexico Test LLC")


def _setup_basic_roles_frappe_only():
	"""
	Setup roles básicos usando solo funciones de Frappe Framework.
	"""
	if frappe.db.exists("User", "Administrator"):
		user = frappe.get_doc("User", "Administrator")
		required_roles = ["System Manager", "Desk User"]

		for role in required_roles:
			if not any(r.role == role for r in user.roles):
				user.append("roles", {"role": role})

		user.save(ignore_permissions=True)
		print("✅ Setup basic roles for Administrator")


def _create_basic_erpnext_accounts():
	"""
	Crear cuentas contables básicas de ERPNext requeridas para testing.

	Basado en erpnext/accounts/doctype/account/test_account.py _make_test_records().
	Evita el error 'Could not find Account: _Test Payable USD - _TC'.
	"""
	# Obtener las companies de testing específicas que necesitan cuentas
	for company_abbr_search in ["_TC", "_TC1", "TCP1"]:
		companies = frappe.get_all(
			"Company", filters={"abbr": company_abbr_search}, fields=["name", "abbr"], limit=1
		)

		if not companies:
			continue

		company_name = companies[0].name
		company_abbr = companies[0].abbr

		_create_accounts_for_company(company_name, company_abbr)


def _create_accounts_for_company(company_name, company_abbr):
	"""
	Crear cuentas para una company específica.
	"""
	# Cuentas básicas requeridas por ERPNext testing
	# Formato: [account_name, parent_account, is_group, account_type, currency]
	basic_accounts = [
		["_Test Bank", "Bank Accounts", 0, "Bank", None],
		["_Test Bank USD", "Bank Accounts", 0, "Bank", "USD"],
		["_Test Cash", "Cash In Hand", 0, "Cash", None],
		["_Test Receivable", "Current Assets", 0, "Receivable", None],
		["_Test Payable", "Current Liabilities", 0, "Payable", None],
		["_Test Receivable USD", "Current Assets", 0, "Receivable", "USD"],
		["_Test Payable USD", "Current Liabilities", 0, "Payable", "USD"],
		["_Test Account Cost for Goods Sold", "Expenses", 0, None, None],
		["_Test Account Sales", "Direct Income", 0, None, None],
		["_Test Account Excise Duty", "Current Assets", 0, "Tax", None],
	]

	for account_name, parent_account, is_group, account_type, currency in basic_accounts:
		full_account_name = f"{account_name} - {company_abbr}"
		parent_account_name = f"{parent_account} - {company_abbr}"

		# Verificar si la cuenta ya existe
		if frappe.db.exists("Account", full_account_name):
			continue

		# Verificar si la cuenta padre existe
		if not frappe.db.exists("Account", parent_account_name):
			print(
				f"⚠️ Parent account {parent_account_name} not found, skipping {account_name} for {company_abbr}"
			)
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
			print(f"✅ Created account: {full_account_name}")

		except Exception as e:
			print(f"⚠️ Failed to create account {account_name} for {company_abbr}: {e}")


def _create_basic_tax_categories():
	"""
	Crear tax categories básicas requeridas para testing ERPNext.
	"""
	basic_tax_categories = ["_Test Tax Category 1", "_Test Tax Category 2"]

	for tax_category in basic_tax_categories:
		if not frappe.db.exists("Tax Category", tax_category):
			try:
				frappe.get_doc(
					{"doctype": "Tax Category", "title": tax_category, "name": tax_category}
				).insert(ignore_permissions=True)
				print(f"✅ Created tax category: {tax_category}")
			except Exception as e:
				print(f"⚠️ Failed to create tax category {tax_category}: {e}")


def _create_basic_cost_centers():
	"""
	Crear cost centers básicos requeridos para testing ERPNext.
	"""
	# Obtener las companies de testing específicas que necesitan cost centers
	for company_abbr_search in ["_TC", "_TC1", "TCP1"]:
		companies = frappe.get_all(
			"Company", filters={"abbr": company_abbr_search}, fields=["name", "abbr"], limit=1
		)

		if not companies:
			continue

		company_name = companies[0].name
		company_abbr = companies[0].abbr

		# Crear múltiples cost centers requeridos
		cost_centers = ["_Test Cost Center", "_Test Cost Center 2"]

		for cost_center_base_name in cost_centers:
			cost_center_name = f"{cost_center_base_name} - {company_abbr}"

			if not frappe.db.exists("Cost Center", cost_center_name):
				try:
					frappe.get_doc(
						{
							"doctype": "Cost Center",
							"cost_center_name": cost_center_base_name,
							"company": company_name,
							"is_group": 0,
							"parent_cost_center": f"{company_name} - {company_abbr}",
						}
					).insert(ignore_permissions=True)
					print(f"✅ Created cost center: {cost_center_name}")
				except Exception as e:
					print(f"⚠️ Failed to create cost center {cost_center_base_name} for {company_abbr}: {e}")


def _create_basic_item_tax_templates():
	"""
	Crear item tax templates básicos requeridos para testing ERPNext.
	"""
	# Obtener las companies de testing específicas que necesitan tax templates
	for company_abbr_search in ["_TC", "_TC1", "TCP1"]:
		companies = frappe.get_all(
			"Company", filters={"abbr": company_abbr_search}, fields=["name", "abbr"], limit=1
		)

		if not companies:
			continue

		company_name = companies[0].name
		company_abbr = companies[0].abbr

		# Tax templates requeridos
		tax_templates = [
			{"name": f"_Test Account Excise Duty @ 10 - {company_abbr}", "rate": 10},
			{"name": f"_Test Account Excise Duty @ 12 - {company_abbr}", "rate": 12},
		]

		for template in tax_templates:
			template_name = template["name"]

			if not frappe.db.exists("Item Tax Template", template_name):
				try:
					tax_doc = frappe.get_doc(
						{
							"doctype": "Item Tax Template",
							"title": template_name,
							"company": company_name,
							"taxes": [
								{
									"tax_type": f"_Test Account Excise Duty - {company_abbr}",
									"tax_rate": template["rate"],
								}
							],
						}
					)
					tax_doc.insert(ignore_permissions=True)
					print(f"✅ Created item tax template: {template_name}")
				except Exception as e:
					print(f"⚠️ Failed to create item tax template {template_name}: {e}")
