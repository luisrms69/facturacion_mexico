"""Tests para _build_pdf_custom_section y render_pdf_note_template.

Cubre los 15 casos definidos en el plan de implementación.
Sin red, sin FacturAPI, sin base de datos de producción.

_build_pdf_custom_section recibe el objeto settings ya cargado — sin acceso a Frappe.
Los tests pasan MagicMock como settings sin necesidad de mockear frappe.get_doc.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.facturacion_fiscal.timbrado_api import (
	_build_pdf_custom_section,
	render_pdf_note_template,
)


def _mock_settings(**kwargs):
	s = MagicMock()
	s.pdf_nota_pue = kwargs.get("pdf_nota_pue", "")
	s.pdf_nota_ppd = kwargs.get("pdf_nota_ppd", "")
	s.pdf_incluir_po_no = kwargs.get("pdf_incluir_po_no", 1)
	s.pdf_incluir_remarks = kwargs.get("pdf_incluir_remarks", 1)
	s.company = kwargs.get("company", "TestCo")
	return s


def _mock_si(**kwargs):
	si = MagicMock()
	si.po_no = kwargs.get("po_no", "")
	si.remarks = kwargs.get("remarks", "")
	si.grand_total = kwargs.get("grand_total", 1000.0)
	si.currency = kwargs.get("currency", "MXN")
	si.due_date = kwargs.get("due_date", "2026-07-31")
	si.payment_schedule = kwargs.get("payment_schedule", [])
	return si


def _apply_settings_and_build(si, payment_method, settings):
	"""Llama _build_pdf_custom_section sin mockear frappe — settings se pasa directo."""
	with (
		patch(
			"facturacion_mexico.facturacion_fiscal.timbrado_api.fmt_money",
			side_effect=lambda amount, **_: f"${amount:,.2f}",
		),
		patch(
			"facturacion_mexico.facturacion_fiscal.timbrado_api.format_date",
			side_effect=lambda d: str(d) if d else "",
		),
	):
		return _build_pdf_custom_section(si, payment_method, settings)


class TestRenderPdfNoteTemplate(unittest.TestCase):
	def test_variables_permitidas(self):
		result = render_pdf_note_template(
			"Pagar a {company} ${total} antes de {due_date}",
			company="ACME",
			total="$1,000.00",
			due_date="31/07/2026",
		)
		self.assertIn("ACME", result)
		self.assertIn("31/07/2026", result)

	def test_variable_desconocida_lanza_error(self):
		# Caso 11: placeholder inválido
		with self.assertRaises(frappe.ValidationError):
			render_pdf_note_template("Pagar antes de {fecha}", company="A", total="B", due_date="C")

	def test_template_sin_variables(self):
		result = render_pdf_note_template("Texto fijo", company="A", total="B", due_date="C")
		self.assertEqual(result, "Texto fijo")


class TestBuildPdfCustomSection(unittest.TestCase):
	# Caso 1: PUE con leyenda configurada
	def test_pue_con_leyenda(self):
		settings = _mock_settings(pdf_nota_pue="Gracias por su compra.")
		si = _mock_si()
		result = _apply_settings_and_build(si, "PUE", settings)
		self.assertIn("Gracias por su compra.", result)

	# Caso 2: PUE con leyenda vacía
	def test_pue_sin_leyenda(self):
		settings = _mock_settings(pdf_nota_pue="")
		si = _mock_si()
		result = _apply_settings_and_build(si, "PUE", settings)
		self.assertEqual(result, "")

	# Caso 3: PPD con leyenda configurada y variables renderizadas
	def test_ppd_con_leyenda_y_variables(self):
		settings = _mock_settings(pdf_nota_ppd="Pagar a {company} antes de {due_date}", company="LlantasCS")
		si = _mock_si(due_date="2026-08-15")
		result = _apply_settings_and_build(si, "PPD", settings)
		self.assertIn("LlantasCS", result)
		self.assertIn("2026", result)

	# Caso 4: PPD con leyenda vacía
	def test_ppd_sin_leyenda(self):
		settings = _mock_settings(pdf_nota_ppd="")
		si = _mock_si()
		result = _apply_settings_and_build(si, "PPD", settings)
		self.assertEqual(result, "")

	# Caso 5: Company A y Company B con textos distintos
	def test_multiempresa(self):
		settings_a = _mock_settings(pdf_nota_pue="Texto empresa A")
		settings_b = _mock_settings(pdf_nota_pue="Texto empresa B")
		si = _mock_si()

		result_a = _apply_settings_and_build(si, "PUE", settings_a)
		result_b = _apply_settings_and_build(si, "PUE", settings_b)

		self.assertIn("empresa A", result_a)
		self.assertIn("empresa B", result_b)
		self.assertNotEqual(result_a, result_b)

	# Caso 6: Inclusión de po_no
	def test_incluir_po_no(self):
		settings = _mock_settings(pdf_incluir_po_no=1)
		si = _mock_si(po_no="OC-12345")
		result = _apply_settings_and_build(si, "PUE", settings)
		self.assertIn("OC-12345", result)

	# Caso 6 (exclusión): No incluir po_no
	def test_excluir_po_no(self):
		settings = _mock_settings(pdf_incluir_po_no=0)
		si = _mock_si(po_no="OC-12345")
		result = _apply_settings_and_build(si, "PUE", settings)
		self.assertNotIn("OC-12345", result)

	# Caso 7: Inclusión de remarks
	def test_incluir_remarks(self):
		settings = _mock_settings(pdf_incluir_remarks=1)
		si = _mock_si(remarks="Entrega en bodega central")
		result = _apply_settings_and_build(si, "PUE", settings)
		self.assertIn("Entrega en bodega central", result)

	# Caso 7 (exclusión): No incluir remarks
	def test_excluir_remarks(self):
		settings = _mock_settings(pdf_incluir_remarks=0)
		si = _mock_si(remarks="Entrega en bodega central")
		result = _apply_settings_and_build(si, "PUE", settings)
		self.assertNotIn("Entrega en bodega central", result)

	# Caso 8: Filtrado de remarks legacy vacíos
	def test_filtrar_remarks_legacy(self):
		settings = _mock_settings(pdf_incluir_remarks=1, pdf_nota_pue="")
		for legacy in ["No Remarks", "None", "", "No hay observaciones"]:
			si = _mock_si(remarks=legacy)
			result = _apply_settings_and_build(si, "PUE", settings)
			# Con leyenda PUE vacía y remarks filtrados, el resultado debe estar vacío
			self.assertEqual(result, "", f"Remarks legacy '{legacy}' no debería generar output")

	# Caso 9: Varias filas en payment_schedule — usar fecha máxima
	def test_ppd_usa_fecha_maxima_payment_schedule(self):
		row1 = MagicMock()
		row1.due_date = "2026-07-15"
		row2 = MagicMock()
		row2.due_date = "2026-08-30"
		settings = _mock_settings(pdf_nota_ppd="Vence el {due_date}")
		si = _mock_si(payment_schedule=[row1, row2])
		result = _apply_settings_and_build(si, "PPD", settings)
		self.assertIn("2026", result)
		self.assertNotIn("07/15", result.replace("-", "/"))

	# Caso 10: payment_schedule vacío — usar si_doc.due_date
	def test_ppd_sin_payment_schedule_usa_due_date(self):
		settings = _mock_settings(pdf_nota_ppd="Vence el {due_date}")
		si = _mock_si(payment_schedule=[], due_date="2026-09-01")
		result = _apply_settings_and_build(si, "PPD", settings)
		self.assertIn("2026", result)

	# Caso 11: Template con placeholder inválido
	def test_template_invalido_lanza_error(self):
		settings = _mock_settings(pdf_nota_ppd="Pagar antes de {fecha_invalida}")
		si = _mock_si()
		with self.assertRaises(frappe.ValidationError):
			_apply_settings_and_build(si, "PPD", settings)

	# Caso 15: No hay textos hardcoded PUE o PPD en el código
	def test_sin_textos_hardcoded(self):
		import inspect

		from facturacion_mexico.facturacion_fiscal import timbrado_api

		source = inspect.getsource(timbrado_api)
		self.assertNotIn("Gracias por su Compra", source)
		self.assertNotIn("Gracias por su compra", source)
		self.assertNotIn("Me obligo incondicionalmente", source)
		self.assertNotIn("fecha límite", source)
