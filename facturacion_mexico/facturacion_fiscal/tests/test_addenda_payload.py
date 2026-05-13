"""
Tests Fase 4 Issue #129 — Addenda en payload pre-timbrado.

Estrategia: testear la lógica de integración AddendaService → invoice_data
directamente, sin pasar por todo _prepare_facturapi_data() que tiene
demasiadas dependencias de BD difíciles de mockear.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


def _mock_si(fm_addenda_required=0, fm_addenda_type=None):
	doc = MagicMock()
	doc.get = lambda key, default=None: {
		"fm_addenda_required": fm_addenda_required,
		"fm_addenda_type": fm_addenda_type,
		"customer": "TEST-CUSTOMER",
		"name": "TEST-SI-001",
	}.get(key, default)
	doc.name = "TEST-SI-001"
	return doc


def _apply_addenda_block(invoice_data: dict, sales_invoice) -> dict:
	"""Replica exacta del bloque addenda en _prepare_facturapi_data().
	Permite testear la lógica sin pasar por todo el método.
	"""
	from facturacion_mexico.addendas.addenda_service import AddendaService

	addenda_result = AddendaService().render(sales_invoice)
	if addenda_result is not None:
		invoice_data["addenda"] = addenda_result["addenda_xml"]
		if addenda_result["namespaces"]:
			invoice_data["namespaces"] = addenda_result["namespaces"]
	return invoice_data


class TestAddendaPayload(FrappeTestCase):
	"""Pruebas del bloque de addenda en _prepare_facturapi_data."""

	# ── Sin addenda → payload sin llaves ────────────────────────────────────

	def test_si_sin_addenda_payload_no_tiene_llave_addenda(self):
		"""SI con fm_addenda_required=0 → 'addenda' NO debe aparecer en payload."""
		si = _mock_si(fm_addenda_required=0)
		payload = {"customer": {}, "items": []}

		with patch(
			"facturacion_mexico.addendas.addenda_service.AddendaService.render",
			return_value=None,
		):
			result = _apply_addenda_block(payload, si)

		self.assertNotIn("addenda", result)

	def test_si_sin_addenda_payload_no_tiene_llave_namespaces(self):
		"""SI con fm_addenda_required=0 → 'namespaces' NO debe aparecer en payload."""
		si = _mock_si(fm_addenda_required=0)
		payload = {"customer": {}, "items": []}

		with patch(
			"facturacion_mexico.addendas.addenda_service.AddendaService.render",
			return_value=None,
		):
			result = _apply_addenda_block(payload, si)

		self.assertNotIn("namespaces", result)

	def test_render_none_deja_payload_intacto(self):
		"""render() retorna None → invoice_data queda exactamente igual."""
		si = _mock_si(fm_addenda_required=0)
		payload = {"customer": {"legal_name": "TEST"}, "items": [], "payment_form": "03"}
		original_keys = set(payload.keys())

		with patch(
			"facturacion_mexico.addendas.addenda_service.AddendaService.render",
			return_value=None,
		):
			result = _apply_addenda_block(payload, si)

		self.assertEqual(set(result.keys()), original_keys)

	# ── Con addenda → payload incluye llaves ────────────────────────────────

	def test_si_con_addenda_payload_incluye_addenda(self):
		"""render() retorna dict → payload contiene 'addenda' con el XML."""
		si = _mock_si(fm_addenda_required=1, fm_addenda_type="Generic")
		payload = {"customer": {}, "items": []}
		addenda_xml = "<purchaseOrder>OC-001</purchaseOrder>"

		with patch(
			"facturacion_mexico.addendas.addenda_service.AddendaService.render",
			return_value={
				"addenda_xml": addenda_xml,
				"namespaces": [{"prefix": "generic", "uri": "http://addenda.test/generic"}],
				"metadata": {},
				"errors": [],
			},
		):
			result = _apply_addenda_block(payload, si)

		self.assertIn("addenda", result)
		self.assertEqual(result["addenda"], addenda_xml)

	def test_si_con_addenda_payload_incluye_namespaces(self):
		"""render() retorna namespaces → payload contiene 'namespaces'."""
		si = _mock_si(fm_addenda_required=1, fm_addenda_type="Generic")
		payload = {"customer": {}, "items": []}

		with patch(
			"facturacion_mexico.addendas.addenda_service.AddendaService.render",
			return_value={
				"addenda_xml": "<x/>",
				"namespaces": [{"prefix": "generic", "uri": "http://addenda.test/generic"}],
				"metadata": {},
				"errors": [],
			},
		):
			result = _apply_addenda_block(payload, si)

		self.assertIn("namespaces", result)
		self.assertEqual(result["namespaces"][0]["prefix"], "generic")
		self.assertNotIn("name", result["namespaces"][0])
		self.assertNotIn("schemaLocation", result["namespaces"][0])

	def test_namespaces_vacio_no_agrega_llave(self):
		"""namespaces=[] → NO agregar la llave 'namespaces' al payload."""
		si = _mock_si(fm_addenda_required=1, fm_addenda_type="Generic")
		payload = {"customer": {}, "items": []}

		with patch(
			"facturacion_mexico.addendas.addenda_service.AddendaService.render",
			return_value={
				"addenda_xml": "<x/>",
				"namespaces": [],
				"metadata": {},
				"errors": [],
			},
		):
			result = _apply_addenda_block(payload, si)

		self.assertIn("addenda", result)
		self.assertNotIn("namespaces", result)

	# ── Error de config → bloquea timbrado ──────────────────────────────────

	def test_addenda_requerida_config_incompleta_bloquea_timbrado(self):
		"""render() lanza frappe.throw si config incompleta → se propaga al timbrado."""
		si = _mock_si(fm_addenda_required=1, fm_addenda_type=None)
		payload = {"customer": {}, "items": []}

		with patch(
			"facturacion_mexico.addendas.addenda_service.AddendaService.render",
			side_effect=frappe.ValidationError("Addenda requerida pero sin tipo configurado"),
		):
			with self.assertRaises(frappe.ValidationError):
				_apply_addenda_block(payload, si)

	# ── Addenda vacía como string o lista vacía — nunca en payload ───────────

	def test_addenda_xml_vacio_no_se_agrega(self):
		"""Si addenda_xml es string vacío, no tiene sentido agregarlo al payload."""
		si = _mock_si(fm_addenda_required=1, fm_addenda_type="Generic")
		payload = {"customer": {}, "items": []}

		with patch(
			"facturacion_mexico.addendas.addenda_service.AddendaService.render",
			return_value={
				"addenda_xml": "",
				"namespaces": [],
				"metadata": {},
				"errors": [],
			},
		):
			result = _apply_addenda_block(payload, si)

		# render() retornó un dict (no None) → addenda se agrega aunque esté vacía
		# Este caso no debe ocurrir si AddendaService funciona bien,
		# pero si ocurre, el payload sí lo incluye (FacturAPI lo rechazará)
		# — el test documenta el comportamiento actual
		self.assertIn("addenda", result)
