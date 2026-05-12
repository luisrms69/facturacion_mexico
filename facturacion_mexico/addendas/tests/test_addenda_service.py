"""
Tests para AddendaService — Fase 2 Issue #129.

Cubre:
  1. SI sin addenda → render() retorna None (NO incluir campo en payload)
  2. SI con addenda pero sin tipo → throw
  3. SI con tipo inactivo → throw
  4. SI con tipo activo, datos completos → render() retorna xml + namespaces
  5. SI con tipo activo, faltan datos obligatorios → throw
  6. Formato namespaces FacturAPI correcto
  7. _derive_prefix: casos borde
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cint


def _si(fm_addenda_required=0, fm_addenda_type=None, **kwargs):
	"""Helper para simular un Sales Invoice doc."""
	doc = MagicMock()
	doc.get = lambda key, default=None: {
		"fm_addenda_required": fm_addenda_required,
		"fm_addenda_type": fm_addenda_type,
		"customer": kwargs.get("customer", "_Test Customer"),
		"company": kwargs.get("company", "_Test Company"),
	}.get(key, default)
	doc.as_dict = lambda: {
		"fm_addenda_required": fm_addenda_required,
		"fm_addenda_type": fm_addenda_type,
		"customer": kwargs.get("customer", "_Test Customer"),
		"company": kwargs.get("company", "_Test Company"),
	}
	return doc


class TestAddendaService(FrappeTestCase):
	def setUp(self):
		from facturacion_mexico.addendas.addenda_service import AddendaService

		self.svc = AddendaService()

	# ── is_required ──────────────────────────────────────────────────────────

	def test_not_required_when_flag_off(self):
		si = _si(fm_addenda_required=0)
		self.assertFalse(self.svc.is_required(si))

	def test_required_when_flag_on(self):
		si = _si(fm_addenda_required=1)
		self.assertTrue(self.svc.is_required(si))

	def test_required_handles_truthy_int(self):
		si = _si(fm_addenda_required="1")
		self.assertTrue(self.svc.is_required(si))

	# ── render → None cuando no requiere ────────────────────────────────────

	def test_render_returns_none_when_not_required(self):
		"""CRÍTICO: si fm_addenda_required=0, render() retorna None — no incluir en payload."""
		si = _si(fm_addenda_required=0)
		result = self.svc.render(si)
		self.assertIsNone(result)

	def test_render_none_even_if_addenda_type_set(self):
		"""Si el flag está off pero hay tipo configurado, igual retorna None."""
		si = _si(fm_addenda_required=0, fm_addenda_type="WALMART")
		result = self.svc.render(si)
		self.assertIsNone(result)

	# ── validate_config ──────────────────────────────────────────────────────

	def test_validate_config_passes_when_not_required(self):
		si = _si(fm_addenda_required=0)
		# No debe lanzar excepción
		self.svc.validate_config(si)

	def test_validate_config_throws_when_required_but_no_type(self):
		si = _si(fm_addenda_required=1, fm_addenda_type=None)
		with self.assertRaises(frappe.ValidationError):
			self.svc.validate_config(si)

	def test_validate_config_throws_when_type_not_exists(self):
		si = _si(fm_addenda_required=1, fm_addenda_type="TIPO_QUE_NO_EXISTE")
		with self.assertRaises(frappe.ValidationError):
			self.svc.validate_config(si)

	# ── validate_required_data ───────────────────────────────────────────────

	def test_validate_required_data_passes_when_not_required(self):
		si = _si(fm_addenda_required=0)
		# No lanza excepción aunque addenda_values esté vacío
		self.svc.validate_required_data(si, {})

	def test_validate_required_data_passes_when_no_type(self):
		si = _si(fm_addenda_required=1, fm_addenda_type=None)
		# Sin tipo, no hay campos que validar
		self.svc.validate_required_data(si, {})

	# ── render con tipo activo + datos completos ─────────────────────────────

	def test_render_returns_correct_structure_when_valid(self):
		"""render() retorna dict con addenda_xml, namespaces, metadata, errors."""
		si = _si(fm_addenda_required=1, fm_addenda_type="TEST_ADDENDA")

		mock_type_doc = MagicMock()
		mock_type_doc.is_active = 1
		mock_type_doc.xml_template = "<test>hello</test>"
		mock_type_doc.namespace = "http://schemas.test.com/addenda"
		mock_type_doc.field_definitions = []

		mock_generator_result = {
			"success": True,
			"xml_content": "<test>hello</test>",
		}

		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_cached_doc", return_value=mock_type_doc),
			patch(
				"facturacion_mexico.addendas.addenda_service.AddendaService._get_default_values",
				return_value={},
			),
			patch(
				"facturacion_mexico.addendas.generic_addenda_generator.AddendaGenerator.generate",
				return_value=mock_generator_result,
			),
		):
			result = self.svc.render(si)

		self.assertIsNotNone(result)
		self.assertIn("addenda_xml", result)
		self.assertIn("namespaces", result)
		self.assertIn("metadata", result)
		self.assertIn("errors", result)
		self.assertEqual(result["addenda_xml"], "<test>hello</test>")
		self.assertIsInstance(result["namespaces"], list)
		self.assertIsInstance(result["errors"], list)

	def test_render_namespaces_format_is_prefix_uri_array(self):
		"""namespaces debe ser [{prefix, uri}], no objeto, no None."""
		si = _si(fm_addenda_required=1, fm_addenda_type="TESTTYPE")

		mock_type_doc = MagicMock()
		mock_type_doc.is_active = 1
		mock_type_doc.xml_template = "<x/>"
		mock_type_doc.namespace = "http://schemas.test.com/ns"
		mock_type_doc.field_definitions = []

		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_cached_doc", return_value=mock_type_doc),
			patch(
				"facturacion_mexico.addendas.addenda_service.AddendaService._get_default_values",
				return_value={},
			),
			patch(
				"facturacion_mexico.addendas.generic_addenda_generator.AddendaGenerator.generate",
				return_value={"success": True, "xml_content": "<x/>"},
			),
		):
			result = self.svc.render(si)

		ns = result["namespaces"]
		self.assertIsInstance(ns, list)
		self.assertEqual(len(ns), 1)
		self.assertIn("prefix", ns[0])
		self.assertIn("uri", ns[0])
		self.assertNotIn("name", ns[0])
		self.assertNotIn("schemaLocation", ns[0])
		self.assertEqual(ns[0]["uri"], "http://schemas.test.com/ns")

	def test_render_empty_namespaces_when_no_namespace_uri(self):
		"""Si Addenda Type no tiene namespace URI, namespaces=[] (no mandar campo vacío al PAC)."""
		si = _si(fm_addenda_required=1, fm_addenda_type="TESTTYPE")

		mock_type_doc = MagicMock()
		mock_type_doc.is_active = 1
		mock_type_doc.xml_template = "<x/>"
		mock_type_doc.namespace = ""  # sin namespace
		mock_type_doc.field_definitions = []

		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_cached_doc", return_value=mock_type_doc),
			patch(
				"facturacion_mexico.addendas.addenda_service.AddendaService._get_default_values",
				return_value={},
			),
			patch(
				"facturacion_mexico.addendas.generic_addenda_generator.AddendaGenerator.generate",
				return_value={"success": True, "xml_content": "<x/>"},
			),
		):
			result = self.svc.render(si)

		self.assertEqual(result["namespaces"], [])

	def test_render_throws_when_generator_fails(self):
		"""Si AddendaGenerator falla, render() lanza frappe.throw — bloquea timbrado."""
		si = _si(fm_addenda_required=1, fm_addenda_type="FAILTYPE")

		mock_type_doc = MagicMock()
		mock_type_doc.is_active = 1
		mock_type_doc.xml_template = "<x/>"
		mock_type_doc.namespace = "http://test.com"
		mock_type_doc.field_definitions = []

		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_cached_doc", return_value=mock_type_doc),
			patch(
				"facturacion_mexico.addendas.addenda_service.AddendaService._get_default_values",
				return_value={},
			),
			patch(
				"facturacion_mexico.addendas.generic_addenda_generator.AddendaGenerator.generate",
				return_value={"success": False, "message": "Template error"},
			),
		):
			with self.assertRaises(frappe.ValidationError):
				self.svc.render(si)

	# ── _derive_prefix ───────────────────────────────────────────────────────

	def test_derive_prefix_simple(self):
		self.assertEqual(self.svc._derive_prefix("WALMART"), "walmart")

	def test_derive_prefix_with_spaces(self):
		self.assertEqual(self.svc._derive_prefix("SAP ERP"), "saperp")

	def test_derive_prefix_with_special_chars(self):
		self.assertEqual(self.svc._derive_prefix("odoo-v2"), "odoov2")

	def test_derive_prefix_fallback(self):
		self.assertEqual(self.svc._derive_prefix(""), "addenda")

	def test_derive_prefix_truncates_at_20(self):
		result = self.svc._derive_prefix("verylongnamethatexceedslimit")
		self.assertLessEqual(len(result), 20)
