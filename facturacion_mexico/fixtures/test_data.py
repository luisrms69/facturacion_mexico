"""
Fixtures centralizados para testing de facturacion_mexico.

Este módulo contiene todos los datos de prueba necesarios para ejecutar
tests de manera consistente y aislada.
"""

import frappe


def get_test_uso_cfdi_records():
	"""Registros de Uso CFDI SAT para testing."""
	return [
		{
			"doctype": "Uso CFDI SAT",
			"code": "G01",
			"description": "Adquisición de mercancías",
			"aplica_fisica": 1,
			"aplica_moral": 1,
		},
		{
			"doctype": "Uso CFDI SAT",
			"code": "G02",
			"description": "Devoluciones, descuentos o bonificaciones",
			"aplica_fisica": 1,
			"aplica_moral": 1,
		},
		{
			"doctype": "Uso CFDI SAT",
			"code": "G03",
			"description": "Gastos en general",
			"aplica_fisica": 1,
			"aplica_moral": 1,
		},
		{
			"doctype": "Uso CFDI SAT",
			"code": "P01",
			"description": "Por definir",
			"aplica_fisica": 1,
			"aplica_moral": 1,
		},
	]


def get_test_regimen_fiscal_records():
	"""Registros de Régimen Fiscal SAT para testing."""
	return [
		{
			"doctype": "Regimen Fiscal SAT",
			"code": "601",
			"description": "General de Ley Personas Morales",
			"aplica_fisica": 0,
			"aplica_moral": 1,
		},
		{
			"doctype": "Regimen Fiscal SAT",
			"code": "612",
			"description": "Personas Físicas con Actividades Empresariales y Profesionales",
			"aplica_fisica": 1,
			"aplica_moral": 0,
		},
	]


def get_test_customer_record():
	"""Cliente de prueba con configuración fiscal."""
	return {
		"doctype": "Customer",
		"customer_name": "Cliente Test Facturación México",
		"customer_type": "Company",
		"customer_group": "All Customer Groups",
		"territory": "All Territories",
		"fm_rfc": "ABC123456789",
		"fm_regimen_fiscal": "601",
		"fm_uso_cfdi_default": "G03",
	}


def get_test_sales_invoice_record():
	"""Sales Invoice de prueba con campos fiscales México."""
	return {
		"doctype": "Sales Invoice",
		"customer": "Cliente Test Facturación México",
		"posting_date": frappe.utils.today(),
		"due_date": frappe.utils.add_days(frappe.utils.today(), 30),
		"company": "_Test Company",
		"currency": "MXN",
		"fm_cfdi_use": "G03",
		"fm_payment_method_sat": "PUE",
		"items": [
			{
				"item_code": "_Test Item",
				"qty": 1,
				"rate": 100,
				"amount": 100,
			}
		],
	}


def get_test_facturacion_mexico_settings():
	"""Configuración de prueba para Facturación México."""
	return {
		"doctype": "Facturacion Mexico Settings",
		"rfc_emisor": "TEST123456789",
		"lugar_expedicion": "01000",
		"test_api_key": "test_api_key_for_testing",
		"sandbox_mode": 1,
		"timeout": 30,
		"auto_generate_ereceipts": 1,
	}


def create_test_records():
	"""
	Crear todos los registros de prueba necesarios.

	Esta función debe ser llamada en setUpClass() de las clases de test.
	"""
	# Crear registros de catálogos SAT
	for record in get_test_uso_cfdi_records():
		if not frappe.db.exists("Uso CFDI SAT", record["code"]):
			frappe.get_doc(record).insert(ignore_permissions=True)

	for record in get_test_regimen_fiscal_records():
		if not frappe.db.exists("Regimen Fiscal SAT", record["code"]):
			frappe.get_doc(record).insert(ignore_permissions=True)

	# Crear configuración de testing
	settings_data = get_test_facturacion_mexico_settings()
	if not frappe.db.exists("Facturacion Mexico Settings", "Facturacion Mexico Settings"):
		frappe.get_doc(settings_data).insert(ignore_permissions=True)
	else:
		settings = frappe.get_doc("Facturacion Mexico Settings", "Facturacion Mexico Settings")
		settings.update(settings_data)
		settings.save(ignore_permissions=True)

	# Crear cliente de prueba
	customer_data = get_test_customer_record()
	if not frappe.db.exists("Customer", customer_data["customer_name"]):
		frappe.get_doc(customer_data).insert(ignore_permissions=True)

	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist test data across test cases


def cleanup_test_records():
	"""
	Limpiar registros de prueba.

	Esta función debe ser llamada en tearDownClass() de las clases de test.
	"""
	try:
		# Limpiar en orden inverso para evitar errores de dependencias
		if frappe.db.exists("Customer", "Cliente Test Facturación México"):
			frappe.delete_doc("Customer", "Cliente Test Facturación México", force=True)

		# Limpiar catálogos SAT de testing
		test_uso_codes = ["G01", "G02", "G03", "P01"]
		for code in test_uso_codes:
			if frappe.db.exists("Uso CFDI SAT", code):
				frappe.delete_doc("Uso CFDI SAT", code, force=True)

		test_regimen_codes = ["601", "612"]
		for code in test_regimen_codes:
			if frappe.db.exists("Regimen Fiscal SAT", code):
				frappe.delete_doc("Regimen Fiscal SAT", code, force=True)

		frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist test data across test cases
	except Exception as e:
		# No fallar si hay errores en cleanup
		print(f"Warning during test cleanup: {e}")
