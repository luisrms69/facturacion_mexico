# Copyright (c) 2026, Buzola and contributors
# For license information, please see license.txt

"""
Tests: Limpieza campos SI↔FFM

Verifica que:
- campos fm_ffm_* fueron eliminados de Sales Invoice
- campo fm_es_ppd existe con configuración correcta
- fm_ffm_section eliminada
- fm_fiscal_section y campos esenciales siguen existiendo
- widget fm_ffm_summary_html existe
"""

import unittest

import frappe


def _custom_field_exists(doctype: str, fieldname: str) -> bool:
	return bool(frappe.db.exists("Custom Field", f"{doctype}-{fieldname}"))


def _get_custom_field(doctype: str, fieldname: str):
	name = f"{doctype}-{fieldname}"
	if frappe.db.exists("Custom Field", name):
		return frappe.get_doc("Custom Field", name)
	return None


class TestSIFFMCleanup(unittest.TestCase):
	"""Verifica el estado correcto de campos SI↔FFM después de la limpieza."""

	# -----------------------------------------------------------------------
	# Campos eliminados — deben NO existir
	# -----------------------------------------------------------------------

	def test_fm_ffm_uuid_eliminado(self):
		"""fm_ffm_uuid fue eliminado de Sales Invoice."""
		self.assertFalse(
			_custom_field_exists("Sales Invoice", "fm_ffm_uuid"),
			"fm_ffm_uuid debe haber sido eliminado",
		)

	def test_fm_ffm_numero_eliminado(self):
		"""fm_ffm_numero fue eliminado de Sales Invoice."""
		self.assertFalse(
			_custom_field_exists("Sales Invoice", "fm_ffm_numero"),
			"fm_ffm_numero debe haber sido eliminado",
		)

	def test_fm_ffm_fecha_eliminada(self):
		"""fm_ffm_fecha fue eliminada de Sales Invoice."""
		self.assertFalse(
			_custom_field_exists("Sales Invoice", "fm_ffm_fecha"),
			"fm_ffm_fecha debe haber sido eliminada",
		)

	def test_fm_ffm_estado_eliminado(self):
		"""fm_ffm_estado fue eliminado de Sales Invoice."""
		self.assertFalse(
			_custom_field_exists("Sales Invoice", "fm_ffm_estado"),
			"fm_ffm_estado debe haber sido eliminado",
		)

	def test_fm_ffm_pac_msg_eliminado(self):
		"""fm_ffm_pac_msg fue eliminado de Sales Invoice."""
		self.assertFalse(
			_custom_field_exists("Sales Invoice", "fm_ffm_pac_msg"),
			"fm_ffm_pac_msg debe haber sido eliminado",
		)

	def test_fm_ffm_section_eliminada(self):
		"""Sección fm_ffm_section fue eliminada de Sales Invoice."""
		self.assertFalse(
			_custom_field_exists("Sales Invoice", "fm_ffm_section"),
			"fm_ffm_section debe haber sido eliminada",
		)

	def test_fm_column_break_fiscal_eliminado(self):
		"""fm_column_break_fiscal fue eliminado de Sales Invoice."""
		self.assertFalse(
			_custom_field_exists("Sales Invoice", "fm_column_break_fiscal"),
			"fm_column_break_fiscal debe haber sido eliminado",
		)

	# -----------------------------------------------------------------------
	# Campos esenciales — deben SÍ existir
	# -----------------------------------------------------------------------

	def test_fm_fiscal_status_existe(self):
		"""fm_fiscal_status sigue existiendo en Sales Invoice."""
		self.assertTrue(
			_custom_field_exists("Sales Invoice", "fm_fiscal_status"),
			"fm_fiscal_status debe existir",
		)

	def test_fm_factura_fiscal_mx_existe(self):
		"""fm_factura_fiscal_mx sigue existiendo en Sales Invoice."""
		self.assertTrue(
			_custom_field_exists("Sales Invoice", "fm_factura_fiscal_mx"),
			"fm_factura_fiscal_mx debe existir",
		)

	def test_fm_ffm_summary_html_existe(self):
		"""Widget fm_ffm_summary_html existe en Sales Invoice."""
		self.assertTrue(
			_custom_field_exists("Sales Invoice", "fm_ffm_summary_html"),
			"fm_ffm_summary_html (widget) debe existir",
		)

	def test_fm_fiscal_section_existe(self):
		"""Sección fm_fiscal_section existe en Sales Invoice."""
		self.assertTrue(
			_custom_field_exists("Sales Invoice", "fm_fiscal_section"),
			"fm_fiscal_section debe existir",
		)

	# -----------------------------------------------------------------------
	# Campo fm_es_ppd — configuración correcta
	# -----------------------------------------------------------------------

	def test_fm_es_ppd_existe(self):
		"""fm_es_ppd existe como Custom Field en Sales Invoice."""
		self.assertTrue(
			_custom_field_exists("Sales Invoice", "fm_es_ppd"),
			"fm_es_ppd debe existir en Sales Invoice",
		)

	def test_fm_es_ppd_es_check(self):
		"""fm_es_ppd es de tipo Check."""
		fld = _get_custom_field("Sales Invoice", "fm_es_ppd")
		self.assertIsNotNone(fld)
		self.assertEqual(fld.fieldtype, "Check")

	def test_fm_es_ppd_default_cero(self):
		"""fm_es_ppd tiene default = 0."""
		fld = _get_custom_field("Sales Invoice", "fm_es_ppd")
		self.assertIsNotNone(fld)
		self.assertIn(str(fld.default or "0"), ["0", ""])

	def test_fm_es_ppd_insert_after_fm_factura_fiscal_mx(self):
		"""fm_es_ppd está posicionado después de fm_factura_fiscal_mx."""
		fld = _get_custom_field("Sales Invoice", "fm_es_ppd")
		self.assertIsNotNone(fld)
		self.assertEqual(fld.insert_after, "fm_factura_fiscal_mx")

	def test_fm_es_ppd_allow_on_submit(self):
		"""fm_es_ppd tiene allow_on_submit = 1 para poder escribirse al timbrar."""
		fld = _get_custom_field("Sales Invoice", "fm_es_ppd")
		self.assertIsNotNone(fld)
		self.assertEqual(fld.allow_on_submit, 1)
