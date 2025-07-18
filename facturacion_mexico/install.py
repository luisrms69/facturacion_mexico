import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import now_datetime


def after_install():
	"""Ejecutar después de instalar la app."""
	create_initial_configuration()
	create_basic_sat_catalogs()  # PRIMERO: crear catálogos SAT
	create_custom_fields_for_erpnext()  # SEGUNDO: crear custom fields que referencian catálogos
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
	"""
	frappe.clear_cache()

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
