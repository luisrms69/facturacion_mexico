"""
Tests del motor de resolucion de Items para conceptos CFDI.

Cubre funciones puras (sin frappe) y el motor completo con mocks.
"""

import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rule(
	company="",
	supplier_rfc="",
	sat_product_key="",
	keywords="",
	target_item="ITEM-001",
	match_reason="Regla test",
	priority=10,
):
	return {
		"name": "RICFDI-2024-001",
		"company": company,
		"supplier_rfc": supplier_rfc,
		"sat_product_key": sat_product_key,
		"keywords": keywords,
		"target_item": target_item,
		"match_reason": match_reason,
		"priority": priority,
	}


def _item_data(item_name="Item de prueba", item_group="Servicios"):
	m = MagicMock()
	m.item_name = item_name
	m.item_group = item_group
	return m


# ---------------------------------------------------------------------------
# Tests _match_level — función pura, sin frappe
# ---------------------------------------------------------------------------


class TestMatchLevel(unittest.TestCase):
	def _call(self, rule, company="", supplier_rfc="", sat_product_key="", description=""):
		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import _match_level

		return _match_level(rule, company, supplier_rfc, sat_product_key, description)

	def test_level_1_exact_all_match(self):
		r = _rule(company="TestCo", supplier_rfc="RFC123", sat_product_key="84111501")
		self.assertEqual(self._call(r, "TestCo", "RFC123", "84111501", "desc"), 1)

	def test_level_1_wrong_company_returns_none(self):
		r = _rule(company="TestCo", supplier_rfc="RFC123", sat_product_key="84111501")
		self.assertIsNone(self._call(r, "OtraCo", "RFC123", "84111501", "desc"))

	def test_level_1_wrong_rfc_returns_none(self):
		r = _rule(company="TestCo", supplier_rfc="RFC123", sat_product_key="84111501")
		self.assertIsNone(self._call(r, "TestCo", "RFC999", "84111501", "desc"))

	def test_level_2_rfc_sat_no_company(self):
		r = _rule(supplier_rfc="RFC123", sat_product_key="84111501")
		self.assertEqual(self._call(r, "AnyCompany", "RFC123", "84111501"), 2)

	def test_level_2_wrong_sat_returns_none(self):
		r = _rule(supplier_rfc="RFC123", sat_product_key="84111501")
		self.assertIsNone(self._call(r, "Co", "RFC123", "99999999"))

	def test_level_3_rfc_keywords_match(self):
		r = _rule(supplier_rfc="RFC123", keywords="mantenimiento")
		self.assertEqual(self._call(r, "Co", "RFC123", "", "Mantenimiento de equipos"), 3)

	def test_level_3_keywords_no_match_returns_none(self):
		r = _rule(supplier_rfc="RFC123", keywords="limpieza")
		self.assertIsNone(self._call(r, "Co", "RFC123", "", "Mantenimiento de equipos"))

	def test_level_3_wrong_rfc_returns_none(self):
		r = _rule(supplier_rfc="RFC123", keywords="mantenimiento")
		self.assertIsNone(self._call(r, "Co", "RFC999", "", "Mantenimiento de equipos"))

	def test_level_4_sat_keywords_match(self):
		r = _rule(sat_product_key="84111501", keywords="limpieza")
		self.assertEqual(self._call(r, "Co", "", "84111501", "Servicio de limpieza"), 4)

	def test_level_4_keywords_no_match_returns_none(self):
		r = _rule(sat_product_key="84111501", keywords="limpieza")
		self.assertIsNone(self._call(r, "Co", "", "84111501", "Servicio de mantenimiento"))

	def test_level_4_wrong_sat_returns_none(self):
		r = _rule(sat_product_key="84111501", keywords="limpieza")
		self.assertIsNone(self._call(r, "Co", "", "99999999", "Servicio de limpieza"))

	def test_rule_with_all_fields_matches_level_1(self):
		r = _rule(company="Co", supplier_rfc="RFC1", sat_product_key="SAT1", keywords="palabra")
		result = self._call(r, "Co", "RFC1", "SAT1", "texto con palabra aqui")
		self.assertEqual(result, 1)

	def test_rule_with_all_fields_keywords_no_match_returns_none(self):
		r = _rule(company="Co", supplier_rfc="RFC1", sat_product_key="SAT1", keywords="keyword")
		result = self._call(r, "Co", "RFC1", "SAT1", "texto sin la palabra buscada")
		self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Tests _level_label — función pura
# ---------------------------------------------------------------------------


class TestLevelLabel(unittest.TestCase):
	def test_labels_exist_for_levels_1_to_4(self):
		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import _level_label

		for level in (1, 2, 3, 4):
			label = _level_label(level)
			self.assertIsInstance(label, str)
			self.assertTrue(len(label) > 5)

	def test_unknown_level_returns_string(self):
		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import _level_label

		label = _level_label(99)
		self.assertIn("99", label)


# ---------------------------------------------------------------------------
# Tests _word_overlap — función pura
# ---------------------------------------------------------------------------


class TestWordOverlap(unittest.TestCase):
	def test_common_words(self):
		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import _word_overlap

		self.assertEqual(_word_overlap("mantenimiento preventivo", "mantenimiento equipos"), 1)

	def test_no_common_words(self):
		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import _word_overlap

		self.assertEqual(_word_overlap("limpieza oficina", "reparacion equipos"), 0)

	def test_all_common(self):
		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import _word_overlap

		self.assertEqual(_word_overlap("a b c", "c b a"), 3)

	def test_empty_strings(self):
		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import _word_overlap

		self.assertEqual(_word_overlap("", "mantenimiento"), 0)


# ---------------------------------------------------------------------------
# Tests get_resolution_options — con mocks de frappe
# ---------------------------------------------------------------------------


class TestGetResolutionOptions(unittest.TestCase):
	def _concepto(self, **kwargs):
		return {
			"sat_product_key": kwargs.get("sat_product_key", "84111501"),
			"no_identificacion": kwargs.get("no_identificacion", ""),
			"description": kwargs.get("description", "Servicio de limpieza"),
			"item_group": kwargs.get("item_group", ""),
		}

	def _cfdi(self, **kwargs):
		return {
			"company": kwargs.get("company", "_Test Company"),
			"supplier": kwargs.get("supplier", "Proveedor Test"),
			"supplier_rfc": kwargs.get("supplier_rfc", "EMP930101ABC"),
		}

	@patch("facturacion_mexico.cfdi_recibidos.services.item_resolution_engine.frappe")
	def test_no_rules_no_items_returns_empty_primary(self, mock_frappe):
		mock_frappe.get_all.return_value = []
		mock_frappe.db.get_value.return_value = None

		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import (
			get_resolution_options,
		)

		result = get_resolution_options(self._concepto(), self._cfdi())

		self.assertIsNone(result["primary"])
		self.assertEqual(result["alternatives"], [])
		self.assertTrue(result["can_create"])

	@patch("facturacion_mexico.cfdi_recibidos.services.item_resolution_engine.frappe")
	def test_rule_level1_becomes_primary_mapeado_alta(self, mock_frappe):
		mock_frappe.get_all.side_effect = [
			[
				_rule(
					company="_Test Company",
					supplier_rfc="EMP930101ABC",
					sat_product_key="84111501",
					target_item="SERV-LIMP-001",
					match_reason="Limpieza mensual",
				)
			],
			[],  # item groups (from _get_expense_item_groups)
			[],  # text search candidates (Item)
		]
		mock_frappe.db.get_value.return_value = _item_data("Limpieza mensual", "Servicios")
		mock_frappe.db.get_value.return_value.lft = 1
		mock_frappe.db.get_value.return_value.rgt = 10

		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import (
			get_resolution_options,
		)

		result = get_resolution_options(self._concepto(), self._cfdi())

		self.assertIsNotNone(result["primary"])
		self.assertEqual(result["primary"]["item_code"], "SERV-LIMP-001")
		self.assertEqual(result["primary"]["item_resolution"], "Mapeado")
		self.assertEqual(result["primary"]["match_confidence"], "Alta")

	@patch("facturacion_mexico.cfdi_recibidos.services.item_resolution_engine.frappe")
	def test_no_identificacion_match_codigo_proveedor(self, mock_frappe):
		mock_frappe.get_all.return_value = []  # no rules, no text candidates
		item_mock = MagicMock()
		item_mock.item_name = "Producto Proveedor"
		item_mock.item_group = "Materiales"
		item_mock.is_purchase_item = 1
		item_mock.is_stock_item = 0
		mock_frappe.db.get_value.return_value = item_mock

		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import (
			get_resolution_options,
		)

		result = get_resolution_options(
			self._concepto(no_identificacion="PROD-ABC-123"),
			self._cfdi(),
		)

		self.assertIsNotNone(result["primary"])
		self.assertEqual(result["primary"]["item_code"], "PROD-ABC-123")
		self.assertEqual(result["primary"]["item_resolution"], "Código proveedor")
		self.assertEqual(result["primary"]["match_confidence"], "Alta")

	@patch("facturacion_mexico.cfdi_recibidos.services.item_resolution_engine.frappe")
	def test_generic_fallback_present_when_item_group_set(self, mock_frappe):
		# No rules, no no_identificacion, no text candidates → only generic
		mock_frappe.get_all.side_effect = [
			[],  # rules
			[],  # text candidates
			# generic search
			[
				MagicMock(
					name="GASTO-SRV-001",
					item_name="Servicio generico",
					item_group="Servicios generales",
				)
			],
		]
		mock_frappe.db.get_value.return_value = None

		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import (
			get_resolution_options,
		)

		result = get_resolution_options(
			self._concepto(item_group="Servicios generales", description=""),
			self._cfdi(),
		)

		self.assertTrue(result["can_create"])

	def test_always_returns_can_create_true(self):
		from unittest.mock import patch as _patch

		with _patch(
			"facturacion_mexico.cfdi_recibidos.services.item_resolution_engine.frappe"
		) as mock_frappe:
			mock_frappe.get_all.return_value = []
			mock_frappe.db.get_value.return_value = None

			from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import (
				get_resolution_options,
			)

			result = get_resolution_options(self._concepto(), self._cfdi())
			self.assertTrue(result["can_create"])
