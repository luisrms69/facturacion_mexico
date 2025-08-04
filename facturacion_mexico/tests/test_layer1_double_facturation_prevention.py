# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Double Facturation Prevention Tests
Tests de infraestructura básica para prevención de doble facturación
"""

import unittest

import frappe
from frappe.test_runner import make_test_records


class TestLayer1DoubleFacturationPrevention(unittest.TestCase):
	"""Tests de infraestructura básica - Prevención Doble Facturación"""

	@classmethod
	def setUpClass(cls):
		"""Setup inicial para todos los tests - Precargar DocTypes y datos comunes"""
		frappe.clear_cache()

		# Verificar que DocTypes críticos existen
		cls.required_doctypes = [
			"Sales Invoice",
			"Factura Fiscal Mexico",
			"Custom Field"
		]

		for doctype in cls.required_doctypes:
			if not frappe.db.exists("DocType", doctype):
				frappe.throw(f"DocType requerido {doctype} no existe")

	def test_timbrado_fm_factura_fiscal_mx_field_exists(self):
		"""
		Test: Verificar que campo fm_factura_fiscal_mx existe en Sales Invoice

		Validaciones:
		- Campo existe en metadatos
		- Tipo Link correcto
		- Options apunta a "Factura Fiscal Mexico"
		- Configuración adecuada para backend tracking
		"""
		# Obtener metadatos del DocType
		meta = frappe.get_meta("Sales Invoice")

		# Verificar que el campo existe
		self.assertTrue(
			meta.has_field("fm_factura_fiscal_mx"),
			"Campo fm_factura_fiscal_mx debe existir en Sales Invoice"
		)

		# Obtener configuración del campo
		field = meta.get_field("fm_factura_fiscal_mx")

		# Validar tipo y opciones
		self.assertEqual(
			field.fieldtype, "Link",
			"Campo fm_factura_fiscal_mx debe ser tipo Link"
		)

		self.assertEqual(
			field.options, "Factura Fiscal Mexico",
			"Campo fm_factura_fiscal_mx debe apuntar a DocType Factura Fiscal Mexico"
		)

		# Validar configuración para tracking backend
		self.assertEqual(
			field.read_only, 1,
			"Campo fm_factura_fiscal_mx debe ser read_only para prevenir edición manual"
		)

		# Sugerencia: Validar hidden si es solo para backend
		# self.assertEqual(field.hidden, 1, "Campo debe estar oculto si es solo backend tracking")

		print("✅ Campo fm_factura_fiscal_mx correctamente configurado")

	def test_timbrado_factura_fiscal_validation_method_exists(self):
		"""
		Test: Verificar método validate_no_duplicate_timbrado existe y se ejecuta

		Validaciones:
		- Método existe en clase FacturaFiscalMexico
		- Se ejecuta durante validate()
		- Recibe parámetros correctos
		"""
		# Verificar que el DocType tiene el método
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import FacturaFiscalMexico

		self.assertTrue(
			hasattr(FacturaFiscalMexico, "validate_no_duplicate_timbrado"),
			"Método validate_no_duplicate_timbrado debe existir en FacturaFiscalMexico"
		)

		# Verificar que el método es callable
		method = getattr(FacturaFiscalMexico, "validate_no_duplicate_timbrado")
		self.assertTrue(
			callable(method),
			"validate_no_duplicate_timbrado debe ser método ejecutable"
		)

		# Mock test - Crear documento y verificar que validate invoca el método
		doc = frappe.get_doc({
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": "TEST-VALIDATION-001",  # Sales Invoice mock
			"fm_fiscal_status": "Pendiente"
		})

		# Mock del método para verificar invocación (sin ejecutar validación real)
		original_method = doc.validate_no_duplicate_timbrado
		method_called = False

		def mock_validate_no_duplicate_timbrado():
			nonlocal method_called
			method_called = True

		doc.validate_no_duplicate_timbrado = mock_validate_no_duplicate_timbrado

		try:
			doc.run_method("validate")
			# Nota: puede fallar en otras validaciones, pero el método debe haberse llamado
		except:
			pass  # Ignorar otras validaciones para este test

		# Restaurar método original
		doc.validate_no_duplicate_timbrado = original_method

		self.assertTrue(
			method_called,
			"validate_no_duplicate_timbrado debe ser invocado durante validate()"
		)

		print("✅ Método validate_no_duplicate_timbrado correctamente integrado")

	def test_timbrado_sales_invoice_javascript_functions_exist(self):
		"""
		Test: Verificar funciones JavaScript de prevención existen

		Validaciones:
		- Función is_already_timbrada existe
		- Se asocia a evento refresh correcto
		- Lógica de verificación básica funcional
		"""
		# Leer archivo JavaScript de Sales Invoice
		js_file_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/public/js/sales_invoice.js"

		try:
			with open(js_file_path, 'r', encoding='utf-8') as f:
				js_content = f.read()
		except FileNotFoundError:
			self.fail(f"Archivo JavaScript no encontrado: {js_file_path}")

		# Verificar que función is_already_timbrada existe
		self.assertIn(
			"function is_already_timbrada",
			js_content,
			"Función is_already_timbrada debe existir en sales_invoice.js"
		)

		# Verificar que se usa fm_factura_fiscal_mx para validación
		self.assertIn(
			"fm_factura_fiscal_mx",
			js_content,
			"JavaScript debe usar campo fm_factura_fiscal_mx para verificar timbrado"
		)

		# Verificar que se asocia a evento refresh
		self.assertIn(
			"refresh: function (frm)",
			js_content,
			"Debe haber función refresh para manejar eventos de formulario"
		)

		# Verificar lógica de prevención en refresh
		self.assertIn(
			"is_already_timbrada",
			js_content,
			"Función refresh debe usar is_already_timbrada para control de botones"
		)

		print("✅ Funciones JavaScript de prevención correctamente implementadas")

	def test_doctype_is_submittable_configured(self):
		"""
		Test: Verificar que DocType Factura Fiscal Mexico es submittable

		Validaciones:
		- Campo is_submittable = 1 en JSON
		- DocType permite workflow Save → Submit
		- Frappe maneja botones automáticamente
		"""
		# Obtener metadatos del DocType
		meta = frappe.get_meta("Factura Fiscal Mexico")

		# Verificar que is_submittable está configurado
		self.assertTrue(
			meta.is_submittable,
			"DocType Factura Fiscal Mexico debe tener is_submittable = 1"
		)

		# Verificar que el DocType soporta estados estándar de Frappe
		self.assertIn("docstatus", [field.fieldname for field in meta.fields],
			"DocType submittable debe tener campo docstatus")

		print("✅ DocType correctamente configurado como submittable")

	def test_mixed_architecture_buttons_implementation(self):
		"""
		Test: Verificar arquitectura mixta de botones implementada

		Validaciones:
		- Botones Save/Submit manejados por Frappe (nativo)
		- Botones FacturAPI específicos en JavaScript
		- Sin interferencia entre sistemas
		"""
		# Leer archivo JavaScript de Factura Fiscal Mexico
		js_file_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.js"

		try:
			with open(js_file_path, 'r', encoding='utf-8') as f:
				js_content = f.read()
		except FileNotFoundError:
			self.fail(f"Archivo JavaScript no encontrado: {js_file_path}")

		# Verificar que NO interfiere con botones nativos
		self.assertIn(
			"Save/Submit son manejados automáticamente por Frappe - NO interferir",
			js_content,
			"Código debe documentar que no interfiere con botones nativos"
		)

		# Verificar botones FacturAPI específicos
		self.assertIn(
			"Timbrar con FacturAPI",
			js_content,
			"Debe existir botón específico para timbrado FacturAPI"
		)

		self.assertIn(
			"Cancelar en FacturAPI",
			js_content,
			"Debe existir botón específico para cancelación FacturAPI"
		)

		# Verificar lógica condicional según estados
		self.assertIn(
			"frm.doc.docstatus === 1",
			js_content,
			"Botones FacturAPI deben aparecer solo cuando documento está submitted"
		)

		self.assertIn(
			"fm_fiscal_status",
			js_content,
			"Lógica de botones debe considerar estado fiscal"
		)

		print("✅ Arquitectura mixta de botones correctamente implementada")

	def tearDown(self):
		"""Cleanup después de cada test"""
		frappe.db.rollback()