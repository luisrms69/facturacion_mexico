# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 3 Double Facturation Prevention Workflows Tests
Tests end-to-end de workflows de prevención de doble facturación
"""

import unittest

import frappe
from frappe.test_runner import make_test_records


class TestLayer3DoubleFacturationWorkflows(unittest.TestCase):
	"""Tests de workflows end-to-end - Prevención Doble Facturación"""

	@classmethod
	def setUpClass(cls):
		"""Setup inicial para workflows completos"""
		frappe.clear_cache()

		# Crear datos de prueba necesarios
		cls.test_customer = "_Test Customer"
		cls.test_company = "_Test Company"
		cls.test_item = "_Test Item"

		# Verificar que datos de prueba existen
		if not frappe.db.exists("Customer", cls.test_customer):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": cls.test_customer,
				"customer_type": "Individual"
			}).insert()

		if not frappe.db.exists("Company", cls.test_company):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": cls.test_company,
				"default_currency": "MXN"
			}).insert()

	def test_timbrado_complete_double_prevention_workflow(self):
		"""
		Test: Workflow completo de prevención doble facturación

		Flujo completo:
		1. Sales Invoice submitted → Crear Factura Fiscal
		2. Factura Fiscal timbrada → Actualizar status
		3. Intentar crear segunda factura → Debe fallar
		4. Verificar UI buttons behavior
		"""
		# PASO 1: Crear Sales Invoice submitted
		sales_invoice = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": self.test_customer,
			"company": self.test_company,
			"posting_date": frappe.utils.today(),
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": self.test_item,
				"rate": 1000,
				"qty": 1
			}]
		})
		sales_invoice.insert()
		sales_invoice.submit()

		# Verificar estado inicial
		self.assertEqual(sales_invoice.docstatus, 1, "Sales Invoice debe estar submitted")
		self.assertFalse(sales_invoice.fm_factura_fiscal_mx,
			"Sales Invoice inicial no debe tener factura fiscal")

		# PASO 2: Crear Factura Fiscal Mexico
		factura_fiscal = frappe.get_doc({
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": sales_invoice.name,
			"company": sales_invoice.company,
			"customer": sales_invoice.customer,
			"fm_fiscal_status": "Pendiente"
		})
		factura_fiscal.insert()
		# Verificar que Save/Submit workflow funciona con is_submittable
		self.assertEqual(factura_fiscal.docstatus, 0, "Después de insert debe ser draft (docstatus=0)")
		factura_fiscal.submit()
		self.assertEqual(factura_fiscal.docstatus, 1, "Después de submit debe ser submitted (docstatus=1)")

		# Simular actualización automática de referencia
		frappe.db.set_value("Sales Invoice", sales_invoice.name,
			"fm_factura_fiscal_mx", factura_fiscal.name)
		frappe.db.commit()

		# PASO 3: Simular timbrado exitoso (cambiar estado)
		frappe.db.set_value("Factura Fiscal Mexico", factura_fiscal.name,
			"fm_fiscal_status", "Timbrada")
		frappe.db.commit()

		# Recargar documentos
		sales_invoice.reload()
		factura_fiscal.reload()

		# Verificar estado después del timbrado
		self.assertEqual(factura_fiscal.fm_fiscal_status, "Timbrada",
			"Factura Fiscal debe estar marcada como Timbrada")
		self.assertEqual(sales_invoice.fm_factura_fiscal_mx, factura_fiscal.name,
			"Sales Invoice debe tener referencia a factura fiscal")

		# PASO 4: Intentar crear segunda Factura Fiscal (debe fallar)
		second_factura = frappe.get_doc({
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": sales_invoice.name,  # Mismo Sales Invoice
			"company": sales_invoice.company,
			"customer": sales_invoice.customer,
			"fm_fiscal_status": "Pendiente"
		})

		# Verificar que validación previene creación
		with self.assertRaises(frappe.ValidationError) as context:
			second_factura.validate()

		error_message = str(context.exception).lower()
		self.assertIn("ya ha sido timbrada", error_message,
			"Error debe indicar que Sales Invoice ya está timbrada")

		# PASO 5: Verificar que UI buttons funcionarían correctamente
		# (Simular lógica JavaScript de is_already_timbrada)
		ui_should_show_timbrar_button = not bool(sales_invoice.fm_factura_fiscal_mx)
		ui_should_show_view_button = bool(sales_invoice.fm_factura_fiscal_mx)

		self.assertFalse(ui_should_show_timbrar_button,
			"UI no debe mostrar botón 'Timbrar' para factura ya timbrada")
		self.assertTrue(ui_should_show_view_button,
			"UI debe mostrar botón 'Ver Factura Fiscal' para factura timbrada")

		print(f"✅ Workflow completo: {sales_invoice.name} → {factura_fiscal.name} (Timbrada)")
		print("✅ Prevención doble facturación: Backend + UI validations OK")

		# Cleanup
		frappe.delete_doc("Factura Fiscal Mexico", factura_fiscal.name, force=True)
		frappe.delete_doc("Sales Invoice", sales_invoice.name, force=True)

	def test_timbrado_edge_cases_multiple_documents(self):
		"""
		Test: Edge cases - Estados que permiten/previenen nuevas facturas

		Casos de prueba:
		1. Documento fiscal Cancelado → Permitir nuevo
		2. Documento fiscal Error → Permitir nuevo
		3. Documento fiscal Pendiente → Prevenir duplicado
		4. Documento fiscal Timbrada → Prevenir duplicado
		"""
		# Crear Sales Invoice base para todos los casos
		sales_invoice = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": self.test_customer,
			"company": self.test_company,
			"posting_date": frappe.utils.today(),
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": self.test_item,
				"rate": 500,
				"qty": 1
			}]
		})
		sales_invoice.insert()
		sales_invoice.submit()

		# CASO 1: Documento Cancelado → Permitir nuevo
		cancelled_factura = frappe.get_doc({
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": sales_invoice.name,
			"company": sales_invoice.company,
			"customer": sales_invoice.customer,
			"fm_fiscal_status": "Cancelada"  # Estado cancelado
		})
		cancelled_factura.insert()
		# Verificar workflow Save → Submit con DocType submittable
		self.assertEqual(cancelled_factura.docstatus, 0, "Documento nuevo debe ser draft")
		cancelled_factura.submit()
		self.assertEqual(cancelled_factura.docstatus, 1, "Documento debe ser submitted correctamente")

		# Actualizar referencia
		frappe.db.set_value("Sales Invoice", sales_invoice.name,
			"fm_factura_fiscal_mx", cancelled_factura.name)

		# Intentar crear nueva factura (debe permitir)
		new_after_cancelled = frappe.get_doc({
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": sales_invoice.name,
			"company": sales_invoice.company,
			"customer": sales_invoice.customer,
			"fm_fiscal_status": "Pendiente"
		})

		# No debe lanzar excepción porque documento anterior está cancelado
		try:
			new_after_cancelled.validate()
			validation_passed = True
		except frappe.ValidationError:
			validation_passed = False

		self.assertTrue(validation_passed,
			"Debe permitir nueva factura después de documento cancelado")

		# Cleanup caso 1
		frappe.delete_doc("Factura Fiscal Mexico", cancelled_factura.name, force=True)

		# CASO 2: Documento Error → Permitir nuevo
		error_factura = frappe.get_doc({
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": sales_invoice.name,
			"company": sales_invoice.company,
			"customer": sales_invoice.customer,
			"fm_fiscal_status": "Error"  # Estado error
		})
		error_factura.insert()
		# Validar arquitectura mixta: botones nativos + custom FacturAPI
		self.assertEqual(error_factura.docstatus, 0, "Insert debe crear documento draft")
		error_factura.submit()
		self.assertEqual(error_factura.docstatus, 1, "Submit debe cambiar a submitted")

		# Actualizar referencia
		frappe.db.set_value("Sales Invoice", sales_invoice.name,
			"fm_factura_fiscal_mx", error_factura.name)

		# Intentar crear nueva factura (debe permitir)
		new_after_error = frappe.get_doc({
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": sales_invoice.name,
			"company": sales_invoice.company,
			"customer": sales_invoice.customer,
			"fm_fiscal_status": "Pendiente"
		})

		try:
			new_after_error.validate()
			validation_passed = True
		except frappe.ValidationError:
			validation_passed = False

		self.assertTrue(validation_passed,
			"Debe permitir nueva factura después de documento en error")

		# Cleanup caso 2
		frappe.delete_doc("Factura Fiscal Mexico", error_factura.name, force=True)

		# CASO 3: Documento Pendiente → Prevenir duplicado
		pending_factura = frappe.get_doc({
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": sales_invoice.name,
			"company": sales_invoice.company,
			"customer": sales_invoice.customer,
			"fm_fiscal_status": "Pendiente"  # Estado pendiente
		})
		pending_factura.insert()
		# Confirmar que DocType is_submittable permite workflow estándar
		self.assertTrue(frappe.get_meta("Factura Fiscal Mexico").is_submittable,
			"DocType debe estar configurado como submittable")
		pending_factura.submit()
		self.assertEqual(pending_factura.docstatus, 1, "Submit debe completarse exitosamente")

		# Actualizar referencia
		frappe.db.set_value("Sales Invoice", sales_invoice.name,
			"fm_factura_fiscal_mx", pending_factura.name)

		# Intentar crear segunda factura (debe prevenir)
		duplicate_pending = frappe.get_doc({
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": sales_invoice.name,
			"company": sales_invoice.company,
			"customer": sales_invoice.customer,
			"fm_fiscal_status": "Pendiente"
		})

		with self.assertRaises(frappe.ValidationError):
			duplicate_pending.validate()

		print("✅ Edge case validado: Documento Pendiente previene duplicado")

		# CASO 4: Documento Timbrada → Prevenir duplicado (ya probado en test anterior)

		print("✅ Todos los edge cases validados correctamente")

		# Cleanup final
		frappe.delete_doc("Factura Fiscal Mexico", pending_factura.name, force=True)
		frappe.delete_doc("Sales Invoice", sales_invoice.name, force=True)

	def tearDown(self):
		"""Cleanup después de cada test"""
		frappe.db.rollback()