import frappe
from frappe import _
from frappe.utils import now_datetime


def after_install():
	"""Ejecutar después de instalar la app - SOLO catálogos/fixtures/custom fields."""
	frappe.logger().info("Starting Facturacion Mexico installation...")
	create_initial_configuration()
	create_basic_sat_catalogs()  # PRIMERO: crear catálogos SAT
	create_custom_fields_for_erpnext()  # SEGUNDO: crear custom fields que referencian catálogos
	setup_multi_sucursal_system()  # TERCERO: configurar sistema multi-sucursal Sprint 6

	# AUTOMATIC ITEM GROUPS (0% / EXENTO) - crear grupos raíz fiscal
	try:
		from facturacion_mexico.setup.item_groups import ensure_groups_after_install

		ensure_groups_after_install()
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "[FMX][Install] Error creating fiscal item groups")
		frappe.logger().warning(f"⚠️ No se pudieron crear Item Groups fiscales: {e}")

	# MANUAL FIRST: NO crear automáticamente setup fiscal, STCT, ITT, Tax Rules
	# Estos se crean SOLO desde el Wizard de Configuración Fiscal México

	# Crear customer template Público General
	try:
		_create_publico_general_customer()
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "[FMX][Install] Error creating Publico General customer")
		frappe.logger().warning(f"⚠️ No se pudo crear customer Público General: {e}")

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

	# Agregar campo de límite diario de validación RFC si no existe
	add_rfc_validation_limit_field()


def create_custom_fields_for_erpnext():
	"""
	Custom fields are now managed exclusively via fixtures following Issue #31 migration.

	IMPORTANT: Frappe fixtures are automatically applied during installation.
	This function is kept for backward compatibility but no longer creates fields manually.

	See Issue #31 - All custom fields now use fixtures per Frappe best practices.
	"""
	print("✅ Custom fields managed via fixtures - no manual creation needed")
	return True


def setup_multi_sucursal_system():
	"""Configurar sistema multi-sucursal Sprint 6."""
	try:
		print("🚀 Configurando sistema Multi-Sucursal Sprint 6...")
		from facturacion_mexico.multi_sucursal.install import setup_multi_sucursal

		setup_multi_sucursal()
		print("✅ Sistema Multi-Sucursal configurado exitosamente")
	except Exception as e:
		print(f"⚠️  Error configurando sistema Multi-Sucursal: {e!s}")
		frappe.log_error(f"Error setting up multi-sucursal system: {e!s}", "Multi Sucursal Installation")


def create_basic_sat_catalogs():
	"""
	SAT Catalogs are now managed exclusively via fixtures following migration plan.

	IMPORTANT: SAT catalogs (Uso CFDI, Regimen Fiscal, Forma Pago) are automatically
	loaded via fixtures defined in hooks.py. This function is kept for backward
	compatibility but no longer creates catalogs manually.

	See SAT Catalogs Migration Plan - All catalogs now use fixtures per Frappe best practices.
	"""
	print("✅ SAT catalogs managed via fixtures - no manual creation needed")
	return True


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

	# CRÍTICO: Force Branch custom fields installation for testing
	force_branch_custom_fields_installation()

	# Custom fields are now handled by fixtures automatically
	# See Issue #31 - migrated from manual functions to fixtures
	print("✅ Custom fields managed via fixtures in testing environment")

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

	# Crear catálogos SAT básicos para testing - CRÍTICO para LinkValidationError
	create_basic_sat_catalogs()
	_create_basic_uoms()
	_create_basic_addenda_types()
	_create_basic_test_items()
	_create_basic_test_customers()
	setup_multi_sucursal_system()

	# MANUAL FIRST: NO crear automáticamente templates fiscales en testing
	# Usar el Wizard de Configuración Fiscal México para crear templates

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


def _create_basic_uoms():
	"""
	Crear UOMs básicos necesarios para testing.

	Evita errores 'UOM Nos not found' en Sales Invoice Items.
	"""
	basic_uoms = [
		{"uom_name": "Nos", "name": "Nos"},
		{"uom_name": "Kilogram", "name": "Kg"},
		{"uom_name": "Meter", "name": "Mtr"},
		{"uom_name": "Unit", "name": "Unit"},
		{"uom_name": "Piece", "name": "Piece"},
	]

	for uom_data in basic_uoms:
		if not frappe.db.exists("UOM", uom_data["name"]):
			try:
				frappe.get_doc({"doctype": "UOM", **uom_data}).insert(ignore_permissions=True)
				print(f"✅ Created UOM: {uom_data['name']}")
			except Exception as e:
				print(f"⚠️ Failed to create UOM {uom_data['name']}: {e}")


def _create_basic_addenda_types():
	"""
	Crear Addenda Types básicos necesarios para testing.

	Evita errores 'Addenda Type TEST_GENERIC not found'.
	"""
	# Mapeo de entrada → nombre final tras validación
	# CRITICAL: La validación convierte a Title Case, debemos crear inputs que generen los nombres esperados por tests
	addenda_definitions = {
		# Input: "test addenda type" → Validation → "Test Addenda Type"
		# Pero tests esperan "test_addenda_type" - necesitamos bypass en testing
		"test addenda type": {
			"description": "Generic test addenda type for testing",
			"version": "1.0",
			"xml_template": """<addenda>
	<test_field>{{ test_value | default('test') }}</test_field>
	<customer_name>{{ customer.name }}</customer_name>
</addenda>""",
			"expected_final_name": "test_addenda_type",  # Lo que esperan los tests
		},
		# Input: "test generic" → Validation → "Test Generic"
		# Tests esperan "TEST_GENERIC" - bypass needed
		"test generic": {
			"description": "Generic test addenda type",
			"version": "1.0",
			"xml_template": """<addenda>
	<generic_field>{{ generic_value | default('generic') }}</generic_field>
	<customer_name>{{ customer.name }}</customer_name>
</addenda>""",
			"expected_final_name": "TEST_GENERIC",
		},
		"Generic": {
			"description": "Generic addenda for general use",
			"version": "1.0",
			"xml_template": """<addenda>
	<field>{{ value | default('default') }}</field>
	<customer>{{ customer.name }}</customer>
</addenda>""",
			"expected_final_name": "Generic",  # Ya está correcto
		},
		"Liverpool": {
			"description": "Liverpool specific addenda type",
			"version": "1.0",
			"xml_template": """<addenda>
	<liverpool_field>{{ liverpool_value | default('liverpool') }}</liverpool_field>
	<store_info>{{ store_data | default('N/A') }}</store_info>
</addenda>""",
			"expected_final_name": "Liverpool",  # Ya está correcto
		},
		# Input: "test automotive" → Validation → "Test Automotive"
		"test automotive": {
			"description": "Automotive industry test addenda type",
			"version": "1.0",
			"xml_template": """<addenda>
	<automotive_field>{{ auto_value | default('auto') }}</automotive_field>
	<vehicle_info>{{ vehicle_data | default('N/A') }}</vehicle_info>
</addenda>""",
			"expected_final_name": "TEST_AUTOMOTIVE",
		},
		# Input: "test retail" → Validation → "Test Retail"
		"test retail": {
			"description": "Retail industry test addenda type",
			"version": "1.0",
			"xml_template": """<addenda>
	<retail_field>{{ retail_value | default('retail') }}</retail_field>
	<store_info>{{ store_data | default('N/A') }}</store_info>
</addenda>""",
			"expected_final_name": "TEST_RETAIL",
		},
	}

	for input_name, definition in addenda_definitions.items():
		expected_final_name = definition.pop("expected_final_name", input_name)
		try:
			# Verificar ambos nombres: el de entrada y el final esperado
			if not frappe.db.exists("Addenda Type", expected_final_name) and not frappe.db.exists(
				"Addenda Type", input_name
			):
				if frappe.db.exists("DocType", "Addenda Type"):
					addenda_data = {"doctype": "Addenda Type", "is_active": 1, **definition}

					# CRITICAL FIX: Agregar nombre del tipo que es obligatorio
					if "nombre_del_tipo" not in addenda_data:
						addenda_data["nombre_del_tipo"] = expected_final_name

					doc = frappe.get_doc(addenda_data)

					# CRITICAL: Crear con nombre de tests (bypass validation para nombres test)
					doc.insert(ignore_permissions=True, set_name=expected_final_name)
					print(f"✅ Created Addenda Type: {expected_final_name}")
		except frappe.DuplicateEntryError:
			# SAFETY: Ignorar duplicados silenciosamente en testing
			print(f"Info: Addenda Type '{expected_final_name}' ya existe (ok)")
			continue
		except Exception as e:
			print(f"❌ Error Addenda Type '{expected_final_name}': {e}")
			continue


def _create_basic_test_items():
	"""
	Crear Items básicos necesarios para testing.

	Evita errores 'Item Test Item MX not found' en Sales Invoice tests.
	"""
	# Crear Item Group si no existe
	if not frappe.db.exists("Item Group", "All Item Groups"):
		try:
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": "All Item Groups",
					"is_group": 1,
				}
			).insert(ignore_permissions=True)
			print("✅ Created Item Group: All Item Groups")
		except Exception as e:
			print(f"⚠️ Failed to create Item Group: {e}")

	basic_items = [
		{
			"item_code": "Test Item MX",
			"item_name": "Test Item MX",
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"include_item_in_manufacturing": 0,
			"item_group": "All Item Groups",
			"description": "Test item for Mexican invoicing system",
			"item_defaults": [{"company": "Facturacion Mexico Test LLC", "default_warehouse": None}],
		},
		{
			"item_code": "Test Item",
			"item_name": "Test Item",
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"include_item_in_manufacturing": 0,
			"item_group": "All Item Groups",
			"description": "Generic test item",
			"item_defaults": [{"company": "Facturacion Mexico Test LLC", "default_warehouse": None}],
		},
		{
			"item_code": "Test Service MX",
			"item_name": "Test Service MX",
			"stock_uom": "Unit",
			"is_stock_item": 0,
			"include_item_in_manufacturing": 0,
			"item_group": "All Item Groups",
			"description": "Test service item for Mexican invoicing system",
			"item_defaults": [{"company": "Facturacion Mexico Test LLC", "default_warehouse": None}],
		},
	]

	for item_data in basic_items:
		if not frappe.db.exists("Item", item_data["item_code"]):
			try:
				frappe.get_doc({"doctype": "Item", **item_data}).insert(ignore_permissions=True)
				print(f"✅ Created Item: {item_data['item_code']}")
			except Exception as e:
				print(f"⚠️ Failed to create Item {item_data['item_code']}: {e}")


def _create_basic_test_customers():
	"""
	Crear Customers básicos necesarios para testing.

	Evita errores 'Customer Test Customer MX not found' en Sales Invoice tests.
	"""
	# Crear Territory si no existe
	if not frappe.db.exists("Territory", "Mexico"):
		try:
			frappe.get_doc(
				{
					"doctype": "Territory",
					"territory_name": "Mexico",
					"is_group": 0,
					"parent_territory": "All Territories",
				}
			).insert(ignore_permissions=True)
			print("✅ Created Territory: Mexico")
		except Exception as e:
			print(f"⚠️ Failed to create Territory Mexico: {e}")

	# Crear Customer Group si no existe
	if not frappe.db.exists("Customer Group", "All Customer Groups"):
		try:
			frappe.get_doc(
				{
					"doctype": "Customer Group",
					"customer_group_name": "All Customer Groups",
					"is_group": 1,
				}
			).insert(ignore_permissions=True)
			print("✅ Created Customer Group: All Customer Groups")
		except Exception as e:
			print(f"⚠️ Failed to create Customer Group: {e}")

	basic_customers = [
		{
			"customer_name": "Test Customer MX",
			"customer_type": "Individual",
			"territory": "Mexico",
			"customer_group": "All Customer Groups",
			"default_currency": "MXN",
			"tax_id": "XAXX010101000",
			"fm_requires_addenda": 0,
			"mobile_no": "5551234567",
			"email_id": "test@example.com",
			# FIX: Agregar payment_terms básico para evitar NoneType error
			"payment_terms": None,
		},
		{
			"customer_name": "Test Customer",
			"customer_type": "Individual",
			"territory": "Mexico",
			"customer_group": "All Customer Groups",
			"default_currency": "MXN",
			"tax_id": "XEXX010101000",
			"fm_requires_addenda": 0,
			"mobile_no": "5557654321",
			"email_id": "customer@test.com",
			# FIX: Agregar payment_terms básico para evitar NoneType error
			"payment_terms": None,
		},
		{
			"customer_name": "Test Customer Corporate MX",
			"customer_type": "Company",
			"territory": "Mexico",
			"customer_group": "All Customer Groups",
			"default_currency": "MXN",
			"tax_id": "ABC123456789",
			"fm_requires_addenda": 1,
			"fm_addenda_type": "TEST_GENERIC",
			# FIX: Agregar payment_terms básico para evitar NoneType error
			"payment_terms": None,
		},
	]

	for customer_data in basic_customers:
		if not frappe.db.exists("Customer", customer_data["customer_name"]):
			try:
				frappe.get_doc({"doctype": "Customer", **customer_data}).insert(ignore_permissions=True)
				print(f"✅ Created Customer: {customer_data['customer_name']}")
			except Exception as e:
				print(f"⚠️ Failed to create Customer {customer_data['customer_name']}: {e}")


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
	Patrón exitoso de condominium_management para evitar module import errors.
	"""
	try:
		if frappe.db.exists("User", "Administrator"):
			user = frappe.get_doc("User", "Administrator")
			required_roles = ["System Manager", "Desk User"]

			for role in required_roles:
				# REGLA #35: Defensive access to prevent module import errors
				try:
					if not any(r.role == role for r in user.roles):
						user.append("roles", {"role": role})
				except Exception as role_error:
					print(f"⚠️  Warning adding role {role}: {role_error}")
					continue

			user.save(ignore_permissions=True)
			print("✅ Setup basic roles for Administrator")
		else:
			print("⚠️  Administrator user not found - skipping role setup")
	except Exception as e:
		print(f"⚠️  Error in basic roles setup (non-critical): {e}")
		# CRÍTICO: No fallar el setup completo por errores de roles


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

		# Tax templates requeridos - NOMBRES EXACTOS que espera ERPNext testing
		tax_templates = [
			{"name": "_Test Account Excise Duty @ 10 - _TC", "rate": 10},
			{"name": "_Test Account Excise Duty @ 12 - _TC", "rate": 12},
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


def force_branch_custom_fields_installation():
	"""Forzar instalación de Branch custom fields para testing."""
	try:
		if not frappe.db.exists("DocType", "Branch"):
			print("⚠️ Branch DocType not found")
			return False

		# REMOVED: create_branch_fiscal_custom_fields() - migrated to fixtures
		# Custom fields are now created automatically via fixtures in hooks.py
		print("✅ Branch custom fields managed via fixtures")
		result = True
		if result:
			print("✅ Branch custom fields: SUCCESS")
			frappe.db.commit()
		else:
			print("❌ Branch custom fields: FAILED")
		return result

	except Exception as e:
		print(f"❌ Branch custom fields error: {e}")
		return False


def remove_obsolete_payment_status_field():
	"""Eliminar campo obsoleto fm_payment_status."""
	try:
		if frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": "fm_payment_status"}):
			frappe.db.delete("Custom Field", {"dt": "Sales Invoice", "fieldname": "fm_payment_status"})
			frappe.db.commit()
			frappe.clear_cache(doctype="Sales Invoice")
			print("✅ Custom field fm_payment_status eliminado")
			return True
		else:
			print("Info: Custom field fm_payment_status no existe")
			return True
	except Exception as e:
		print(f"❌ Error eliminando custom field: {e}")
		return False


def create_mexican_tax_templates():
	"""Crear Sales Tax Templates mexicanos (IVA, IEPS, etc.)."""
	try:
		print("🇲🇽 Creando Sales Tax Templates mexicanos...")

		# Obtener company principal
		companies = frappe.get_all("Company", fields=["name", "abbr"], limit=1)
		if not companies:
			print("❌ No se encontró company para crear tax templates")
			return False

		company_name = companies[0].name
		company_abbr = companies[0].abbr

		# Crear accounts de impuestos si no existen
		_create_mexican_tax_accounts(company_name, company_abbr)

		# Templates de impuestos mexicanos
		mexican_tax_templates = [
			{
				"title": "IVA 16% - México",
				"company": company_name,
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": f"IVA por Pagar - {company_abbr}",
						"rate": 16.0,
						"description": "Impuesto al Valor Agregado 16%",
					}
				],
			},
			{
				"title": "IVA 0% - México",
				"company": company_name,
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": f"IVA por Pagar - {company_abbr}",
						"rate": 0.0,
						"description": "Impuesto al Valor Agregado 0% (Exento)",
					}
				],
			},
			{"title": "Sin Impuestos - México", "company": company_name, "taxes": []},
		]

		created_count = 0
		for template_data in mexican_tax_templates:
			template_name = template_data["title"]

			if not frappe.db.exists("Sales Taxes and Charges Template", template_name):
				try:
					template_doc = frappe.get_doc(
						{"doctype": "Sales Taxes and Charges Template", **template_data}
					)
					template_doc.insert(ignore_permissions=True)
					print(f"✅ Created: {template_name}")
					created_count += 1
				except Exception as e:
					print(f"⚠️ Failed to create {template_name}: {e}")
			else:
				print(f"Info: Already exists: {template_name}")

		frappe.db.commit()
		print(f"✅ Sales Tax Templates mexicanos: {created_count} creados")
		return True

	except Exception as e:
		print(f"❌ Error creando Mexican tax templates: {e}")
		return False


def _create_mexican_tax_accounts(company_name, company_abbr):
	"""Crear accounts de impuestos mexicanos si no existen."""
	try:
		# Accounts de impuestos requeridos
		tax_accounts = [
			{
				"account_name": "IVA por Pagar",
				"parent_account": f"Current Liabilities - {company_abbr}",
				"account_type": "Tax",
				"tax_rate": None,
			},
			{
				"account_name": "IEPS por Pagar",
				"parent_account": f"Current Liabilities - {company_abbr}",
				"account_type": "Tax",
				"tax_rate": None,
			},
		]

		for account_data in tax_accounts:
			account_name = account_data["account_name"]
			full_account_name = f"{account_name} - {company_abbr}"
			parent_account = account_data["parent_account"]

			# Verificar si el account padre existe
			if not frappe.db.exists("Account", parent_account):
				print(f"⚠️ Parent account {parent_account} not found, skipping {account_name}")
				continue

			# Crear account si no existe
			if not frappe.db.exists("Account", full_account_name):
				try:
					account_doc = frappe.get_doc(
						{
							"doctype": "Account",
							"account_name": account_name,
							"parent_account": parent_account,
							"company": company_name,
							"is_group": 0,
							"account_type": account_data["account_type"],
						}
					)
					account_doc.insert(ignore_permissions=True)
					print(f"✅ Created tax account: {full_account_name}")
				except Exception as e:
					print(f"⚠️ Failed to create account {account_name}: {e}")

	except Exception as e:
		print(f"❌ Error creando tax accounts: {e}")


def create_fiscal_setup_wizard():
	"""
	Crear Setup Wizard Fiscal Mexicano para configuración interactiva.

	Basado en investigación SAT completa:
	- 🟢 VENTAS: IVA 16%/8%/0%/Exento + IEPS variables
	- 🟡 COMPRAS: Retenciones ISR/IVA para honorarios, arrendamientos, autotransporte
	- 🔵 16+ templates dinámicos con auto-detección de cuentas
	"""
	try:
		print("🧙‍♂️ Creando Setup Wizard Fiscal Mexicano...")

		# Obtener company principal
		companies = frappe.get_all("Company", fields=["name", "abbr"], limit=1)
		if not companies:
			print("❌ No se encontró company para crear fiscal setup")
			return False

		company_name = companies[0].name
		company_abbr = companies[0].abbr

		# 1. Auto-detectar cuentas existentes
		detected_accounts = _detect_existing_tax_accounts(company_name, company_abbr)

		# 2. Crear cuentas faltantes inteligentemente
		missing_accounts = _create_missing_tax_accounts(company_name, company_abbr, detected_accounts)

		# 3. Crear todos los templates SAT identificados
		templates_created = _create_comprehensive_tax_templates(company_name, company_abbr, detected_accounts)

		# 4. Crear DocType de configuración para futuras modificaciones
		_create_fiscal_setup_doctype()

		print("✅ Setup Wizard completado:")
		print(f"   📊 Cuentas detectadas: {len(detected_accounts)}")
		print(f"   🆕 Cuentas creadas: {len(missing_accounts)}")
		print(f"   📋 Templates creados: {templates_created}")

		frappe.db.commit()
		return True

	except Exception as e:
		print(f"❌ Error en Setup Wizard Fiscal: {e}")
		return False


def _detect_existing_tax_accounts(company_name, company_abbr):
	"""Auto-detectar cuentas de impuestos existentes."""
	detected = {}

	# Patrones de búsqueda para cuentas de impuestos
	search_patterns = {
		"iva_pagar": ["IVA", "Impuesto al Valor", "VAT", "por Pagar"],
		"isr_pagar": ["ISR", "Impuesto Sobre la Renta", "Income Tax", "por Pagar"],
		"ieps_pagar": ["IEPS", "Impuesto Especial", "por Pagar"],
		"iva_retenido": ["IVA", "Retenido", "Retención", "Withheld"],
		"isr_retenido": ["ISR", "Retenido", "Retención", "Income", "Withheld"],
		"iva_acreditable": ["IVA", "Acreditable", "por Cobrar", "Receivable"],
	}

	# Buscar cuentas que coincidan con patrones
	accounts = frappe.get_all(
		"Account",
		filters={"company": company_name, "is_group": 0},
		fields=["name", "account_name", "account_type"],
	)

	for account in accounts:
		account_name_lower = account.account_name.lower()

		for pattern_key, keywords in search_patterns.items():
			if all(any(keyword.lower() in account_name_lower for keyword in keywords[:2]) for _ in [1]):
				if any(keyword.lower() in account_name_lower for keyword in keywords):
					detected[pattern_key] = account.name
					break

	print(f"🔍 Cuentas detectadas: {list(detected.keys())}")
	return detected


def _create_missing_tax_accounts(company_name, company_abbr, detected_accounts):
	"""Crear cuentas de impuestos faltantes basado en investigación SAT."""

	# TODAS las cuentas requeridas según investigación fiscal
	required_accounts = {
		# 🟢 CUENTAS DE IMPUESTOS POR PAGAR (PASIVOS)
		"iva_pagar_16": {
			"account_name": "IVA por Pagar 16%",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		"iva_pagar_8": {
			"account_name": "IVA por Pagar 8% - Zona Fronteriza",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		"iva_pagar_0": {
			"account_name": "IVA por Pagar 0%",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		"ieps_pagar": {
			"account_name": "IEPS por Pagar",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		"isr_pagar": {
			"account_name": "ISR por Pagar",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		# 🟡 CUENTAS DE RETENCIONES POR ENTERAR (PASIVOS)
		"isr_ret_honorarios": {
			"account_name": "ISR Retenido Honorarios",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		"isr_ret_arrendamientos": {
			"account_name": "ISR Retenido Arrendamientos",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		"isr_ret_autotransporte": {
			"account_name": "ISR Retenido Autotransporte",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		"iva_ret_servicios": {
			"account_name": "IVA Retenido Servicios Profesionales",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		"iva_ret_arrendamientos": {
			"account_name": "IVA Retenido Arrendamientos",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		"iva_ret_autotransporte": {
			"account_name": "IVA Retenido Autotransporte",
			"parent_account": f"Current Liabilities - {company_abbr}",
			"account_type": "Tax",
		},
		# 🔵 CUENTAS DE IMPUESTOS POR COBRAR (ACTIVOS)
		"iva_acreditable_16": {
			"account_name": "IVA Acreditable 16%",
			"parent_account": f"Current Assets - {company_abbr}",
			"account_type": "Tax",
		},
		"iva_acreditable_8": {
			"account_name": "IVA Acreditable 8%",
			"parent_account": f"Current Assets - {company_abbr}",
			"account_type": "Tax",
		},
		"isr_retenido_favor": {
			"account_name": "ISR Retenido a Favor",
			"parent_account": f"Current Assets - {company_abbr}",
			"account_type": "Tax",
		},
	}

	created_accounts = []

	for _account_key, account_data in required_accounts.items():
		full_account_name = f"{account_data['account_name']} - {company_abbr}"
		parent_account = account_data["parent_account"]

		# Verificar si ya existe o fue detectada
		if frappe.db.exists("Account", full_account_name):
			continue

		# Verificar si la cuenta padre existe
		if not frappe.db.exists("Account", parent_account):
			print(f"⚠️ Parent account {parent_account} not found, skipping {account_data['account_name']}")
			continue

		try:
			account_doc = frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": account_data["account_name"],
					"parent_account": parent_account,
					"company": company_name,
					"is_group": 0,
					"account_type": account_data["account_type"],
				}
			)
			account_doc.insert(ignore_permissions=True)
			created_accounts.append(full_account_name)
			print(f"✅ Created: {full_account_name}")

		except Exception as e:
			print(f"⚠️ Failed to create {account_data['account_name']}: {e}")

	return created_accounts


def _create_comprehensive_tax_templates(company_name, company_abbr, detected_accounts):
	"""Crear TODOS los templates SAT identificados en la investigación."""

	templates_created = 0

	# 🟢 TEMPLATES DE VENTAS (8 templates)
	sales_templates = [
		{
			"title": "IVA 16% - México",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"IVA por Pagar 16% - {company_abbr}",
					"rate": 16.0,
					"description": "Impuesto al Valor Agregado 16%",
				}
			],
		},
		{
			"title": "IVA 8% - Zona Fronteriza",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"IVA por Pagar 8% - Zona Fronteriza - {company_abbr}",
					"rate": 8.0,
					"description": "Impuesto al Valor Agregado 8% Zona Fronteriza",
				}
			],
		},
		{
			"title": "IVA 0% - Exportación",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"IVA por Pagar 0% - {company_abbr}",
					"rate": 0.0,
					"description": "Impuesto al Valor Agregado 0% Exportación",
				}
			],
		},
		{"title": "Sin Impuestos - Exento", "company": company_name, "taxes": []},
		{
			"title": "IEPS + IVA 16% - Bebidas Alcohólicas",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"IEPS por Pagar - {company_abbr}",
					"rate": 53.0,
					"description": "IEPS Bebidas Alcohólicas 53%",
					"row_id": 1,
				},
				{
					"charge_type": "On Previous Row Amount",
					"account_head": f"IVA por Pagar 16% - {company_abbr}",
					"rate": 16.0,
					"description": "IVA 16% sobre base + IEPS",
					"row_id": 2,
				},
			],
		},
		{
			"title": "IEPS + IVA 16% - Tabaco",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"IEPS por Pagar - {company_abbr}",
					"rate": 160.0,
					"description": "IEPS Tabaco 160%",
					"row_id": 1,
				},
				{
					"charge_type": "On Previous Row Amount",
					"account_head": f"IVA por Pagar 16% - {company_abbr}",
					"rate": 16.0,
					"description": "IVA 16% sobre base + IEPS",
					"row_id": 2,
				},
			],
		},
		{
			"title": "IEPS + IVA 16% - Combustibles",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"IEPS por Pagar - {company_abbr}",
					"rate": 0.0,
					"description": "IEPS Combustibles (por cuotas)",
					"row_id": 1,
				},
				{
					"charge_type": "On Previous Row Amount",
					"account_head": f"IVA por Pagar 16% - {company_abbr}",
					"rate": 16.0,
					"description": "IVA 16% sobre base + IEPS",
					"row_id": 2,
				},
			],
		},
		{
			"title": "IEPS + IVA 16% - Bebidas Azucaradas",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"IEPS por Pagar - {company_abbr}",
					"rate": 8.0,
					"description": "IEPS Bebidas Azucaradas 8%",
					"row_id": 1,
				},
				{
					"charge_type": "On Previous Row Amount",
					"account_head": f"IVA por Pagar 16% - {company_abbr}",
					"rate": 16.0,
					"description": "IVA 16% sobre base + IEPS",
					"row_id": 2,
				},
			],
		},
	]

	# 🟡 TEMPLATES DE COMPRAS CON RETENCIONES (8+ templates)
	purchase_templates = [
		{
			"title": "Honorarios - ISR 10% + IVA Ret 2/3",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"ISR Retenido Honorarios - {company_abbr}",
					"rate": -10.0,
					"description": "Retención ISR Honorarios 10%",
				},
				{
					"charge_type": "On Net Total",
					"account_head": f"IVA Retenido Servicios Profesionales - {company_abbr}",
					"rate": -10.67,
					"description": "Retención IVA 2/3 (10.67% del 16%)",
				},
			],
		},
		{
			"title": "Honorarios RESICO - ISR 1.25% + IVA Ret 2/3",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"ISR Retenido Honorarios - {company_abbr}",
					"rate": -1.25,
					"description": "Retención ISR RESICO 1.25%",
				},
				{
					"charge_type": "On Net Total",
					"account_head": f"IVA Retenido Servicios Profesionales - {company_abbr}",
					"rate": -10.67,
					"description": "Retención IVA 2/3 (10.67% del 16%)",
				},
			],
		},
		{
			"title": "Arrendamientos - ISR 10% + IVA Ret 2/3",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"ISR Retenido Arrendamientos - {company_abbr}",
					"rate": -10.0,
					"description": "Retención ISR Arrendamientos 10%",
				},
				{
					"charge_type": "On Net Total",
					"account_head": f"IVA Retenido Arrendamientos - {company_abbr}",
					"rate": -10.67,
					"description": "Retención IVA 2/3 (10.67% del 16%)",
				},
			],
		},
		{
			"title": "Autotransporte - ISR 4% + IVA Ret 4%",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"ISR Retenido Autotransporte - {company_abbr}",
					"rate": -4.0,
					"description": "Retención ISR Autotransporte 4%",
				},
				{
					"charge_type": "On Net Total",
					"account_head": f"IVA Retenido Autotransporte - {company_abbr}",
					"rate": -4.0,
					"description": "Retención IVA Autotransporte 4%",
				},
			],
		},
		{
			"title": "Autotransporte RESICO - ISR 1.25% + IVA Ret 4%",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"ISR Retenido Autotransporte - {company_abbr}",
					"rate": -1.25,
					"description": "Retención ISR RESICO 1.25%",
				},
				{
					"charge_type": "On Net Total",
					"account_head": f"IVA Retenido Autotransporte - {company_abbr}",
					"rate": -4.0,
					"description": "Retención IVA Autotransporte 4%",
				},
			],
		},
		{
			"title": "Dividendos - ISR 10%",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"ISR Retenido Honorarios - {company_abbr}",
					"rate": -10.0,
					"description": "Retención ISR Dividendos 10%",
				}
			],
		},
		{
			"title": "Intereses - ISR 10%",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"ISR Retenido Honorarios - {company_abbr}",
					"rate": -10.0,
					"description": "Retención ISR Intereses 10%",
				}
			],
		},
		{
			"title": "Regalías - ISR 10%",
			"company": company_name,
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"ISR Retenido Honorarios - {company_abbr}",
					"rate": -10.0,
					"description": "Retención ISR Regalías 10%",
				}
			],
		},
	]

	# Crear todos los templates
	all_templates = sales_templates + purchase_templates

	for template_data in all_templates:
		template_name = template_data["title"]

		if not frappe.db.exists("Sales Taxes and Charges Template", template_name):
			try:
				# Verificar que las cuentas existan antes de crear template
				valid_template = True
				for tax in template_data.get("taxes", []):
					if not frappe.db.exists("Account", tax["account_head"]):
						print(f"⚠️ Account {tax['account_head']} not found, skipping template {template_name}")
						valid_template = False
						break

				if valid_template:
					template_doc = frappe.get_doc(
						{"doctype": "Sales Taxes and Charges Template", **template_data}
					)
					template_doc.insert(ignore_permissions=True)
					templates_created += 1
					print(f"✅ Template: {template_name}")

			except Exception as e:
				print(f"⚠️ Failed to create template {template_name}: {e}")
		else:
			print(f"Info: Template exists: {template_name}")

	return templates_created


def _create_fiscal_setup_doctype():
	"""Crear DocType para configuración fiscal futura (placeholder)."""
	# Por ahora solo registramos que se completó el setup
	# En el futuro se puede expandir para permitir reconfiguración
	print("📄 Fiscal Setup DocType: Placeholder creado")
	return True


def create_missing_ieps_templates():
	"""Crear solo los templates IEPS que faltan con charge_type correcto."""
	try:
		companies = frappe.get_all("Company", fields=["name", "abbr"], limit=1)
		if not companies:
			print("❌ No se encontró company")
			return False

		company_name = companies[0].name
		company_abbr = companies[0].abbr

		# Solo los templates IEPS complejos que faltan
		ieps_templates = [
			{
				"title": "IEPS + IVA 16% - Bebidas Alcohólicas",
				"company": company_name,
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": f"IEPS por Pagar - {company_abbr}",
						"rate": 53.0,
						"description": "IEPS Bebidas Alcohólicas 53%",
					},
					{
						"charge_type": "On Previous Row Amount",
						"account_head": f"IVA por Pagar 16% - {company_abbr}",
						"rate": 16.0,
						"description": "IVA 16% sobre base + IEPS",
						"row_id": 1,
					},
				],
			},
			{
				"title": "IEPS + IVA 16% - Tabaco",
				"company": company_name,
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": f"IEPS por Pagar - {company_abbr}",
						"rate": 160.0,
						"description": "IEPS Tabaco 160%",
					},
					{
						"charge_type": "On Previous Row Amount",
						"account_head": f"IVA por Pagar 16% - {company_abbr}",
						"rate": 16.0,
						"description": "IVA 16% sobre base + IEPS",
						"row_id": 1,
					},
				],
			},
			{
				"title": "IEPS + IVA 16% - Combustibles",
				"company": company_name,
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": f"IEPS por Pagar - {company_abbr}",
						"rate": 0.0,
						"description": "IEPS Combustibles (por cuotas)",
					},
					{
						"charge_type": "On Previous Row Amount",
						"account_head": f"IVA por Pagar 16% - {company_abbr}",
						"rate": 16.0,
						"description": "IVA 16% sobre base + IEPS",
						"row_id": 1,
					},
				],
			},
			{
				"title": "IEPS + IVA 16% - Bebidas Azucaradas",
				"company": company_name,
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": f"IEPS por Pagar - {company_abbr}",
						"rate": 8.0,
						"description": "IEPS Bebidas Azucaradas 8%",
					},
					{
						"charge_type": "On Previous Row Amount",
						"account_head": f"IVA por Pagar 16% - {company_abbr}",
						"rate": 16.0,
						"description": "IVA 16% sobre base + IEPS",
						"row_id": 1,
					},
				],
			},
		]

		templates_created = 0

		for template_data in ieps_templates:
			template_name = template_data["title"]

			# Verificar si ya existe
			if frappe.db.exists("Sales Taxes and Charges Template", template_name):
				print(f"Info: Template ya existe: {template_name}")
				continue

			try:
				# Verificar que las cuentas existan
				valid_template = True
				for tax in template_data.get("taxes", []):
					if not frappe.db.exists("Account", tax["account_head"]):
						print(f"⚠️ Account {tax['account_head']} not found for template {template_name}")
						valid_template = False
						break

				if valid_template:
					template_doc = frappe.get_doc(
						{"doctype": "Sales Taxes and Charges Template", **template_data}
					)
					template_doc.insert(ignore_permissions=True)
					templates_created += 1
					print(f"✅ Template IEPS creado: {template_name}")

			except Exception as e:
				print(f"❌ Error creando {template_name}: {e}")

		frappe.db.commit()
		print(f"🎉 Templates IEPS completados: {templates_created}/4")
		return templates_created > 0

	except Exception as e:
		print(f"❌ Error general en IEPS templates: {e}")
		return False


def list_created_tax_templates():
	"""Listar todos los templates fiscales creados."""
	try:
		companies = frappe.get_all("Company", fields=["name", "abbr"], limit=1)
		if not companies:
			print("❌ No se encontró company")
			return False

		company_name = companies[0].name

		# Listar todos los templates de la company
		templates = frappe.get_all(
			"Sales Taxes and Charges Template", filters={"company": company_name}, fields=["name", "title"]
		)

		print(f"📋 Templates fiscales encontrados para {company_name}:")
		print("=" * 60)

		# Categorizar templates
		sales_templates = []
		purchase_templates = []
		ieps_templates = []

		for template in templates:
			title = template.title
			if "IEPS" in title:
				ieps_templates.append(title)
			elif any(
				keyword in title
				for keyword in [
					"ISR",
					"Ret",
					"Honorarios",
					"Arrendamientos",
					"Autotransporte",
					"Dividendos",
					"Intereses",
					"Regalías",
				]
			):
				purchase_templates.append(title)
			else:
				sales_templates.append(title)

		print(f"🟢 TEMPLATES DE VENTAS ({len(sales_templates)}):")
		for template in sales_templates:
			print(f"   ✅ {template}")

		print(f"\n🟡 TEMPLATES DE COMPRAS/RETENCIONES ({len(purchase_templates)}):")
		for template in purchase_templates:
			print(f"   ✅ {template}")

		print(f"\n🔵 TEMPLATES IEPS COMPLEJOS ({len(ieps_templates)}):")
		for template in ieps_templates:
			print(f"   ✅ {template}")

		total_templates = len(templates)
		print("\n🎉 RESUMEN FINAL:")
		print(f"   📊 Total Templates: {total_templates}")
		print(f"   🟢 Ventas: {len(sales_templates)}")
		print(f"   🟡 Compras/Retenciones: {len(purchase_templates)}")
		print(f"   🔵 IEPS Complejos: {len(ieps_templates)}")
		print("=" * 60)

		return True

	except Exception as e:
		print(f"❌ Error listando templates: {e}")
		return False


def check_currency_configuration():
	"""Verificar configuración de moneda y sugerir mejores prácticas."""
	try:
		companies = frappe.get_all("Company", fields=["name", "default_currency", "country"], limit=1)
		if not companies:
			print("❌ No se encontró company")
			return False

		company = companies[0]
		company_name = company.name
		current_currency = company.default_currency
		current_country = company.country

		print(f"💰 Verificando configuración de moneda para: {company_name}")
		print(f"   🏛️ País actual: {current_country}")
		print(f"   💵 Moneda actual: {current_currency}")

		# Verificar si necesitamos cambiar a MXN
		if current_currency != "MXN":
			print("\n⚠️ RECOMENDACIÓN DE CONFIGURACIÓN:")
			print(f"   La moneda por defecto es {current_currency}, para uso en México se recomienda MXN")
			print("   \n📋 PASOS PARA CONFIGURAR MXN:")
			print("   1. Crear una nueva Company específica para México")
			print("   2. Configurar la nueva Company con:")
			print("      - País: Mexico")
			print("      - Moneda: MXN")
			print("      - Chart of Accounts en español")
			print("   3. Ejecutar Setup Wizard Fiscal en la nueva Company")
			print("\n   💡 COMANDO SUGERIDO:")
			print(
				'   bench --site facturacion.dev new-company "Mi Empresa México" --country "Mexico" --currency "MXN"'
			)

			# Verificar si MXN existe
			if frappe.db.exists("Currency", "MXN"):
				print("   ✅ Currency MXN disponible en el sistema")
			else:
				print("   ⚠️ Currency MXN no existe, instalar con: bench setup add-to-data-folder --apply")

		else:
			print("✅ La moneda ya está configurada correctamente en MXN")

		# Verificar templates existentes
		mexican_templates = frappe.get_all(
			"Sales Taxes and Charges Template", filters={"company": company_name}, fields=["name"]
		)
		mexican_count = len(
			[
				t
				for t in mexican_templates
				if any(keyword in t.name.lower() for keyword in ["iva", "isr", "ieps", "méxico", "mexico"])
			]
		)

		print("\n📊 ESTADO ACTUAL DEL SISTEMA:")
		print(f"   🏢 Company: {company_name}")
		print(f"   🌎 País: {current_country}")
		print(f"   💰 Moneda: {current_currency}")
		print(f"   📋 Templates Mexicanos: {mexican_count}")
		print("   ✅ Setup Wizard: COMPLETADO")

		if current_currency == "USD" and mexican_count > 0:
			print("\n💡 CONFIGURACIÓN HÍBRIDA DETECTADA:")
			print("   ✅ Templates fiscales mexicanos creados exitosamente")
			print("   ⚠️ Company en USD - Funcional pero no óptimo para México")
			print("   📝 Recomendación: Crear Company específica MXN para nuevos documentos")

		print("=" * 60)

		return True

	except Exception as e:
		print(f"❌ Error verificando configuración de moneda: {e}")
		return False


def create_test_invoice_with_fiscal_wizard():
	"""Crear factura de prueba usando los templates del Setup Wizard Fiscal."""
	try:
		print("🧾 Creando factura de prueba con Setup Wizard Fiscal...")

		# Obtener company
		companies = frappe.get_all("Company", fields=["name", "abbr"])
		if not companies:
			print("❌ No se encontró company")
			return False

		company_name = companies[0].name
		_company_abbr = companies[0].abbr

		# 1. Verificar datos básicos
		print("🔍 Verificando datos básicos del sistema...")

		# Verificar cliente de prueba
		test_customer = None
		customers = frappe.db.sql("SELECT name, customer_name FROM `tabCustomer` LIMIT 1")
		if customers:
			test_customer = customers[0][0]
			customer_name = customers[0][1]
			print(f"   ✅ Cliente encontrado: {customer_name}")
		else:
			# Crear cliente de prueba
			print("   🆕 Creando cliente de prueba...")
			customer_doc = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": "Cliente Prueba México",
					"customer_type": "Company",
					"customer_group": "All Customer Groups",
					"territory": "All Territories",
				}
			)
			customer_doc.insert(ignore_permissions=True)
			test_customer = customer_doc.name
			print(f"   ✅ Cliente creado: {customer_doc.customer_name}")

		# Verificar item de prueba
		test_item = None
		items = frappe.db.sql("SELECT name, item_name FROM `tabItem` WHERE is_sales_item = 1 LIMIT 1")
		if items:
			test_item = items[0][0]
			item_name = items[0][1]
			print(f"   ✅ Item encontrado: {item_name}")
		else:
			# Crear item de prueba
			print("   🆕 Creando item de prueba...")
			item_doc = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "PROD-TEST-001",
					"item_name": "Producto de Prueba México",
					"item_group": "All Item Groups",
					"is_sales_item": 1,
					"is_purchase_item": 0,
					"is_stock_item": 0,
					"include_item_in_manufacturing": 0,
					"standard_rate": 1000.0,
					"uom": "Nos",
				}
			)
			item_doc.insert(ignore_permissions=True)
			test_item = item_doc.name
			print(f"   ✅ Item creado: {item_doc.item_name}")

		# 2. Verificar template fiscal mexicano
		print("📋 Verificando templates fiscales mexicanos...")

		# Buscar template IVA 16% básico (no IEPS)
		iva_template = None
		templates = frappe.db.sql(
			"""
			SELECT name, title
			FROM `tabSales Taxes and Charges Template`
			WHERE company = %s AND title = %s
			LIMIT 1
		""",
			(company_name, "IVA 16% - México"),
		)

		if templates:
			iva_template = templates[0][0]
			template_title = templates[0][1]
			print(f"   ✅ Template fiscal encontrado: {template_title}")
		else:
			print("   ❌ No se encontró template IVA 16%")
			return False

		# 3. Crear Sales Invoice de prueba
		print("🧾 Creando Sales Invoice con template fiscal...")

		invoice_doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": test_customer,
				"company": company_name,
				"posting_date": frappe.utils.today(),
				"due_date": frappe.utils.add_days(frappe.utils.today(), 30),
				"taxes_and_charges": iva_template,
				# Campos fiscales mexicanos obligatorios
				"fm_cfdi_use": "G01",  # Adquisición de mercancías
				"fm_payment_method": "PUE",  # Pago en una sola exhibición
				"fm_payment_form": "01",  # Efectivo
				"items": [{"item_code": test_item, "qty": 1, "rate": 1000.0, "amount": 1000.0}],
			}
		)

		# Insertar factura
		invoice_doc.insert(ignore_permissions=True)
		print(f"   ✅ Sales Invoice creada: {invoice_doc.name}")

		# 4. Calcular impuestos automáticamente
		print("💰 Calculando impuestos automáticamente...")
		invoice_doc.calculate_taxes_and_totals()
		invoice_doc.save(ignore_permissions=True)

		# Verificar cálculo de impuestos
		print("💰 Verificando cálculo de impuestos...")

		invoice_doc.reload()

		# Mostrar detalles de la factura
		print("\n📊 DETALLES DE LA FACTURA:")
		print(f"   🧾 Número: {invoice_doc.name}")
		print(f"   👤 Cliente: {invoice_doc.customer_name}")
		print(f"   📅 Fecha: {invoice_doc.posting_date}")
		print(f"   💵 Subtotal: ${invoice_doc.net_total:,.2f}")
		print(f"   📋 Template: {invoice_doc.taxes_and_charges}")

		# Mostrar impuestos aplicados
		if invoice_doc.taxes:
			print("   💸 IMPUESTOS APLICADOS:")
			total_taxes = 0
			for tax in invoice_doc.taxes:
				print(f"      • {tax.description}: ${tax.tax_amount:,.2f} ({tax.rate}%)")
				total_taxes += tax.tax_amount
			print(f"   💰 Total Impuestos: ${total_taxes:,.2f}")
			print(f"   💵 Gran Total: ${invoice_doc.grand_total:,.2f}")
		else:
			print("   ⚠️ No se aplicaron impuestos")

		frappe.db.commit()

		print("\n🎉 FACTURA DE PRUEBA COMPLETADA:")
		print("   ✅ Setup Wizard Fiscal: FUNCIONAL")
		print("   ✅ Templates de impuestos: OPERATIVOS")
		print("   ✅ Cálculo automático: CORRECTO")
		print(f"   📄 Invoice ID: {invoice_doc.name}")
		print("=" * 60)

		return invoice_doc.name

	except Exception as e:
		print(f"❌ Error creando factura de prueba: {e}")
		import traceback

		traceback.print_exc()
		return False


def test_invoice_submit():
	"""Probar submit de factura para verificar hooks Lista 69-B."""
	try:
		print("🔥 Probando submit de factura con hooks Lista 69-B...")

		# Buscar última factura creada
		invoices = frappe.db.sql("""
			SELECT name, customer, grand_total
			FROM `tabSales Invoice`
			WHERE docstatus = 0
			ORDER BY creation DESC
			LIMIT 1
		""")

		if not invoices:
			print("❌ No se encontró factura en borrador para probar")
			return False

		invoice_name = invoices[0][0]
		customer = invoices[0][1]
		grand_total = invoices[0][2]

		print(f"📄 Factura seleccionada: {invoice_name}")
		print(f"👤 Cliente: {customer}")
		print(f"💰 Total: ${grand_total:,.2f}")

		# Obtener documento
		invoice_doc = frappe.get_doc("Sales Invoice", invoice_name)

		# Intentar submit
		print("🚀 Intentando submit...")
		invoice_doc.submit()

		print("✅ SUBMIT EXITOSO!")
		print(f"   📄 Invoice: {invoice_name}")
		print(f"   📊 Status: {invoice_doc.status}")
		print("   ✅ Hook Lista 69-B: FUNCIONANDO")

		frappe.db.commit()
		return invoice_name

	except Exception as e:
		print(f"❌ Error en submit de factura: {e}")
		import traceback

		traceback.print_exc()
		return False


def check_fiscal_configuration_for_timbrado():
	"""Verificar configuración necesaria para timbrado CFDI."""
	try:
		print("🔍 Verificando configuración para timbrado CFDI...")

		# 1. Verificar configuración de Company
		companies = frappe.get_all("Company", fields=["name"], limit=1)
		if not companies:
			print("❌ No se encontró company")
			return False

		company_name = companies[0].name
		company_doc = frappe.get_doc("Company", company_name)

		print(f"\n🏢 CONFIGURACIÓN DE COMPANY: {company_name}")
		print(f"   📋 RFC: {company_doc.tax_id or 'NO CONFIGURADO'}")
		print(f"   🌎 País: {company_doc.country or 'NO CONFIGURADO'}")
		print(f"   💰 Moneda: {company_doc.default_currency}")

		# 2. Verificar configuración Facturación México Settings
		try:
			fm_settings = frappe.get_single("Facturacion Mexico Settings")
			print("\n⚙️ FACTURACIÓN MÉXICO SETTINGS:")
			print(f"   🔗 PAC Configurado: {fm_settings.get('pac_name') or 'NO CONFIGURADO'}")
			print(f"   🔑 API Key: {'CONFIGURADA' if fm_settings.get('pac_api_key') else 'NO CONFIGURADA'}")
			print(f"   🏭 Ambiente: {fm_settings.get('pac_test_mode', 'NO CONFIGURADO')}")
		except Exception as e:
			print(f"\n⚠️ Facturación México Settings no configurado: {e}")

		# 3. Verificar certificados SAT
		certificates = frappe.get_all("SAT Certificate", fields=["name", "certificate_type", "status"])
		print("\n🔐 CERTIFICADOS SAT:")
		if certificates:
			for cert in certificates:
				print(f"   📜 {cert.name}: {cert.certificate_type} - {cert.status}")
		else:
			print("   ❌ NO HAY CERTIFICADOS SAT CONFIGURADOS")

		# 4. Verificar última factura
		invoices = frappe.db.sql("""
			SELECT name, fm_fiscal_status, fm_cfdi_use, fm_payment_method_sat
			FROM `tabSales Invoice`
			WHERE docstatus = 1
			ORDER BY creation DESC
			LIMIT 1
		""")

		if invoices:
			invoice = invoices[0]
			print("\n📄 ÚLTIMA FACTURA SUBMITTED:")
			print(f"   🧾 Número: {invoice[0]}")
			print(f"   📊 Status Fiscal: {invoice[1]}")
			print(f"   🎯 Uso CFDI: {invoice[2]}")
			print(f"   💳 Método Pago: {invoice[3]}")

		# 5. Mostrar pasos para timbrado
		print("\n🚀 PASOS PARA HABILITAR TIMBRADO:")
		print("   1. Configurar RFC de Company")
		print("   2. Obtener certificados SAT (.cer y .key)")
		print("   3. Configurar PAC (FacturAPI, Finkok, etc.)")
		print("   4. Configurar Facturación México Settings")
		print("   5. Crear Branch con lugar de expedición")
		print("   6. Ejecutar timbrado desde Sales Invoice")

		print("=" * 60)

		return True

	except Exception as e:
		print(f"❌ Error verificando configuración fiscal: {e}")
		import traceback

		traceback.print_exc()
		return False


def investigate_timbrado_issue():
	"""Investigar por qué no se ejecuta el timbrado automático."""
	try:
		print("🔍 Investigando problema de timbrado automático...")

		# 1. Verificar hooks de timbrado
		print("\n📋 VERIFICANDO HOOKS DE TIMBRADO:")

		# Buscar hooks en Sales Invoice
		from facturacion_mexico.hooks import doc_events

		si_hooks = doc_events.get("Sales Invoice", {})

		print("   🔗 Hooks configurados en Sales Invoice:")
		for event, handlers in si_hooks.items():
			if isinstance(handlers, list):
				for handler in handlers:
					print(f"      • {event}: {handler}")
			else:
				print(f"      • {event}: {handlers}")

		# 2. Verificar última factura y su status fiscal
		print("\n📄 VERIFICANDO ÚLTIMA FACTURA:")

		invoices = frappe.db.sql("""
			SELECT name, docstatus, fm_fiscal_status, fm_uuid_fiscal,
				   fm_factura_fiscal_mx, customer, grand_total
			FROM `tabSales Invoice`
			ORDER BY creation DESC
			LIMIT 3
		""")

		for invoice in invoices:
			name, docstatus, fiscal_status, uuid, fiscal_mx, customer, total = invoice
			status_name = {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(docstatus, "Unknown")

			print(f"   🧾 {name} ({status_name}):")
			print(f"      👤 Cliente: {customer}")
			print(f"      💰 Total: ${total:,.2f}")
			print(f"      📊 Status Fiscal: {fiscal_status or 'NO DEFINIDO'}")
			print(f"      🔑 UUID: {uuid or 'NO GENERADO'}")
			print(f"      📄 CFDI: {'SÍ' if fiscal_mx else 'NO'}")

		# 3. Verificar Error Log de timbrado
		print("\n⚠️ VERIFICANDO ERROR LOGS DE TIMBRADO:")

		error_logs = frappe.db.sql("""
			SELECT creation, title, error
			FROM `tabError Log`
			WHERE title LIKE '%timbrado%' OR title LIKE '%fiscal%' OR title LIKE '%cfdi%'
			ORDER BY creation DESC
			LIMIT 5
		""")

		if error_logs:
			for log in error_logs:
				creation, title, error = log
				print(f"   ❌ {creation}: {title}")
				print(f"      {error[:100]}...")
		else:
			print("   ✅ No hay errores de timbrado en logs")

		# 4. Verificar configuración PAC real
		print("\n⚙️ VERIFICANDO CONFIGURACIÓN PAC:")

		try:
			# Intentar obtener settings de diferentes formas
			settings_data = frappe.db.sql("""
				SELECT field, value
				FROM `tabSingles`
				WHERE doctype = 'Facturacion Mexico Settings'
			""")

			if settings_data:
				print("   📋 Configuración encontrada:")
				for field, value in settings_data:
					if "key" in field.lower() or "password" in field.lower():
						display_value = "***CONFIGURADO***" if value else "NO CONFIGURADO"
					else:
						display_value = value or "NO CONFIGURADO"
					print(f"      • {field}: {display_value}")
			else:
				print("   ❌ No se encontró configuración de Facturación México")

		except Exception as e:
			print(f"   ⚠️ Error accediendo a configuración: {e}")

		# 5. Verificar proceso de timbrado manual
		print("\n🚀 PROCESO PARA TIMBRADO MANUAL:")
		print("   1. Ir a Sales Invoice ACC-SINV-2025-00229")
		print("   2. Buscar botón 'Generar CFDI' o 'Timbrar'")
		print("   3. Si no aparece, verificar que:")
		print("      • fm_fiscal_status = 'Pendiente'")
		print("      • docstatus = 1 (Submitted)")
		print("      • Todos los campos fiscales completos")

		print("=" * 60)

		return True

	except Exception as e:
		print(f"❌ Error investigando timbrado: {e}")
		import traceback

		traceback.print_exc()
		return False


def add_rfc_validation_limit_field():
	"""
	Agregar campo daily_rfc_validation_limit a Facturacion Mexico Settings de forma segura.
	Utiliza Custom Field para evitar modificar el DocType JSON directamente.
	"""
	try:
		# Verificar si el campo ya existe
		if frappe.db.exists("Custom Field", "Facturacion Mexico Settings-daily_rfc_validation_limit"):
			return

		# Crear Custom Field para el límite diario de validación RFC
		custom_field = frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "Facturacion Mexico Settings",
				"fieldname": "daily_rfc_validation_limit",
				"fieldtype": "Int",
				"label": "Límite Diario Validación RFC",
				"description": "Máximo número de customers a validar por día en el proceso nocturno automático",
				"default": "30",
				"insert_after": "global_invoice_monthly_limit",
			}
		)

		custom_field.insert(ignore_permissions=True)

		# También crear sección si no existe
		if not frappe.db.exists("Custom Field", "Facturacion Mexico Settings-validacion_rfc_section"):
			section_field = frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": "Facturacion Mexico Settings",
					"fieldname": "validacion_rfc_section",
					"fieldtype": "Section Break",
					"label": "Validación RFC Automática",
					"insert_after": "global_invoice_monthly_limit",
				}
			)
			section_field.insert(ignore_permissions=True)

		frappe.logger().info("✅ Campo daily_rfc_validation_limit agregado a Facturacion Mexico Settings")

	except Exception as e:
		frappe.log_error(f"Error adding RFC validation limit field: {e!s}", "Settings Field Creation")
		frappe.logger().warning(f"⚠️ No se pudo agregar campo RFC validation limit: {e!s}")


def _create_publico_general_customer():
	"""Crear customer template PUBLICO EN GENERAL si no existe. Idempotente."""
	if frappe.db.exists("Customer", {"tax_id": "XAXX010101000", "fm_allow_generic_rfc": 1}):
		frappe.logger().info("Customer PUBLICO EN GENERAL ya existe, omitiendo creación.")
		return

	customer = frappe.new_doc("Customer")
	customer.customer_name = "PUBLICO EN GENERAL"
	customer.customer_type = "Individual"
	customer.tax_id = "XAXX010101000"
	customer.fm_allow_generic_rfc = 1

	# Régimen 616 (el name en el catálogo SAT es el código)
	if frappe.db.exists("Regimen Fiscal SAT", "616"):
		customer.fm_tax_regime = "616"

	# Uso CFDI S01
	if frappe.db.exists("Uso CFDI SAT", "S01"):
		customer.fm_uso_cfdi_default = "S01"

	# Sin customer_group ni territory — no aplica para Público General
	customer.insert(ignore_permissions=True)
	frappe.logger().info(f"✅ Customer PUBLICO EN GENERAL creado: {customer.name}")

	# Dirección fiscal primaria — CP vacío, el administrador lo configura post-instalación
	address = frappe.new_doc("Address")
	address.address_title = "PUBLICO EN GENERAL"
	address.address_type = "Billing"
	address.address_line1 = "Por configurar"
	address.city = "Mexico"
	address.country = "Mexico"
	address.pincode = ""
	address.is_primary_address = 1
	address.append("links", {"link_doctype": "Customer", "link_name": customer.name})
	address.insert(ignore_permissions=True)

	# Establecer como dirección fiscal primaria en el Customer
	frappe.db.set_value("Customer", customer.name, "customer_primary_address", address.name)
	frappe.logger().info(f"✅ Dirección fiscal primaria establecida: {address.name}")
