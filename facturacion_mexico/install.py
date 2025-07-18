import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


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
