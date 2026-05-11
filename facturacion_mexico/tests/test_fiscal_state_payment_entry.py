"""
Tests para fiscal_state/payment_entry_state.py y el endpoint get_fiscal_ui_state.

Casos cubiertos (unitarios con mocks):
  1. PE Receive PPD timbrado sin complemento → COMPLEMENT_REQUIRED
  2. PE Receive PPD timbrado con complemento activo (Timbrado) → COMPLEMENT_EXISTS
  3. PE Receive PPD timbrado con complemento cancelado → COMPLEMENT_CANCELLED
  4. PE Receive PPD timbrado con complemento en error → COMPLEMENT_ERROR
  5. PE Receive PPD sin SI timbrada → COMPLEMENT_BLOCKED_NO_STAMPED_SI
  6. PE Receive PUE → COMPLEMENT_NOT_REQUIRED
  7. PE cancelado → sin mensajes
  8. Actions derivadas correctamente por estado

Ejecutar:
  bench --site test-facturacion.localhost execute facturacion_mexico.tests.ci_pre_tests.run
  bench --site test-facturacion.localhost run-tests --app facturacion_mexico \
    --module facturacion_mexico.tests.test_fiscal_state_payment_entry --lightmode
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.fiscal_state.payment_entry_state import (
	_compute_actions,
	_compute_facts,
	_compute_messages,
	get_payment_entry_fiscal_state,
)


def _mock_pe(
	docstatus=1,
	payment_type="Receive",
	party_type="Customer",
	references=None,
	fm_require_complement=0,
	fm_complemento_pago=None,
):
	"""Crea un mock de Payment Entry para tests unitarios."""
	pe = MagicMock()
	pe.docstatus = docstatus
	pe.payment_type = payment_type
	pe.party_type = party_type
	pe.fm_require_complement = fm_require_complement
	pe.fm_complemento_pago = fm_complemento_pago

	ref_list = references or []
	pe.get = lambda key, default=None: ref_list if key == "references" else getattr(pe, key, default)

	return pe


def _si_ref(name, is_ppd=True, fiscal_status="TIMBRADO", allocated=1000):
	ref = MagicMock()
	ref.reference_doctype = "Sales Invoice"
	ref.reference_name = name
	ref.allocated_amount = allocated
	return ref


class TestFiscalStatePaymentEntryFacts(FrappeTestCase):
	"""Tests unitarios para _compute_facts()."""

	def _facts(self, pe, si_data=None, comp_data=None):
		"""Helper: computa facts con datos controlados vía mocks."""
		si_return = si_data if si_data is not None else []
		comp_return = comp_data if comp_data is not None else []

		with patch(
			"frappe.get_all", side_effect=[si_return, comp_return] if comp_data is not None else [si_return]
		):
			return _compute_facts(pe)

	# ── Caso 1: PPD timbrada, sin complemento ─────────────────────────────
	def test_ppd_timbrada_sin_complemento(self):
		pe = _mock_pe(fm_require_complement=1, references=[_si_ref("SI-001")])
		with patch(
			"frappe.get_all",
			return_value=[{"name": "SI-001", "fm_es_ppd": 1, "fm_fiscal_status": "TIMBRADO"}],
		):
			facts = _compute_facts(pe)
		self.assertTrue(facts["has_ppd_invoice"])
		self.assertTrue(facts["has_ppd_stamped_invoice"])
		self.assertTrue(facts["requires_complement"])
		self.assertFalse(facts["has_complement"])
		self.assertFalse(facts["has_active_complement"])

	# ── Caso 2: PPD timbrada, complemento activo ──────────────────────────
	def test_ppd_con_complemento_timbrado(self):
		pe = _mock_pe(fm_require_complement=1, fm_complemento_pago="COMP-001", references=[_si_ref("SI-001")])
		si_data = [{"name": "SI-001", "fm_es_ppd": 1, "fm_fiscal_status": "TIMBRADO"}]
		comp_data = [
			{"name": "COMP-001", "status": "Timbrado", "uuid_sat": "UUID-123", "facturapi_id": "FAP-001"}
		]
		with patch("frappe.get_all", side_effect=[si_data, comp_data]):
			facts = _compute_facts(pe)
		self.assertTrue(facts["has_active_complement"])
		self.assertFalse(facts["has_cancelled_complement"])
		self.assertEqual(facts["complement_status"], "Timbrado")
		self.assertTrue(facts["complement_has_uuid"])
		self.assertTrue(facts["complement_has_file"])

	# ── Caso 3: complemento cancelado ────────────────────────────────────
	def test_complemento_cancelado(self):
		pe = _mock_pe(fm_require_complement=1, fm_complemento_pago="COMP-001", references=[_si_ref("SI-001")])
		si_data = [{"name": "SI-001", "fm_es_ppd": 1, "fm_fiscal_status": "TIMBRADO"}]
		comp_data = [
			{"name": "COMP-001", "status": "Cancelado", "uuid_sat": "UUID-123", "facturapi_id": "FAP-001"}
		]
		with patch("frappe.get_all", side_effect=[si_data, comp_data]):
			facts = _compute_facts(pe)
		self.assertFalse(facts["has_active_complement"])
		self.assertTrue(facts["has_cancelled_complement"])
		self.assertFalse(facts["has_complement_error"])

	# ── Caso 4: complemento con error ────────────────────────────────────
	def test_complemento_error(self):
		pe = _mock_pe(fm_require_complement=1, fm_complemento_pago="COMP-001", references=[_si_ref("SI-001")])
		si_data = [{"name": "SI-001", "fm_es_ppd": 1, "fm_fiscal_status": "TIMBRADO"}]
		comp_data = [{"name": "COMP-001", "status": "Error", "uuid_sat": None, "facturapi_id": None}]
		with patch("frappe.get_all", side_effect=[si_data, comp_data]):
			facts = _compute_facts(pe)
		self.assertTrue(facts["has_complement_error"])
		self.assertFalse(facts["has_active_complement"])

	# ── Caso 5: PPD sin SI timbrada ───────────────────────────────────────
	def test_ppd_sin_si_timbrada(self):
		pe = _mock_pe(fm_require_complement=0, references=[_si_ref("SI-001")])
		si_data = [{"name": "SI-001", "fm_es_ppd": 1, "fm_fiscal_status": "BORRADOR"}]
		with patch("frappe.get_all", return_value=si_data):
			facts = _compute_facts(pe)
		self.assertTrue(facts["has_ppd_invoice"])
		self.assertFalse(facts["has_ppd_stamped_invoice"])
		self.assertFalse(facts["requires_complement"])

	# ── Caso 6: PUE ───────────────────────────────────────────────────────
	def test_pue_no_requiere_complemento(self):
		pe = _mock_pe(fm_require_complement=0, references=[_si_ref("SI-001")])
		si_data = [{"name": "SI-001", "fm_es_ppd": 0, "fm_fiscal_status": "TIMBRADO"}]
		with patch("frappe.get_all", return_value=si_data):
			facts = _compute_facts(pe)
		self.assertFalse(facts["has_ppd_invoice"])
		self.assertFalse(facts["requires_complement"])

	# ── Caso 7: PE cancelado ──────────────────────────────────────────────
	def test_pe_cancelado_estado_documental(self):
		pe = _mock_pe(docstatus=2)
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(pe)
		self.assertFalse(facts["is_submitted"])
		self.assertTrue(facts["is_cancelled"])


class TestFiscalStatePaymentEntryActions(FrappeTestCase):
	"""Tests unitarios para _compute_actions() — solo lógica derivada, sin BD."""

	def test_can_create_complement_cuando_requiere_y_no_tiene(self):
		facts = {
			"is_submitted": True,
			"payment_type": "Receive",
			"requires_complement": True,
			"has_active_complement": False,
			"has_cancelled_complement": False,
			"has_complement": False,
			"has_complement_error": False,
			"complement_status": None,
			"complement_has_file": False,
		}
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_create_complement"])
		self.assertFalse(actions["can_view_complement"])

	def test_no_puede_crear_si_ya_tiene_activo(self):
		facts = {
			"is_submitted": True,
			"payment_type": "Receive",
			"requires_complement": True,
			"has_active_complement": True,
			"has_cancelled_complement": False,
			"has_complement": True,
			"has_complement_error": False,
			"complement_status": "Timbrado",
			"complement_has_file": True,
		}
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_create_complement"])
		self.assertTrue(actions["can_view_complement"])
		self.assertTrue(actions["can_cancel_complement"])
		self.assertTrue(actions["can_download_complement_xml"])

	def test_puede_reintentar_si_error(self):
		facts = {
			"is_submitted": True,
			"payment_type": "Receive",
			"requires_complement": True,
			"has_active_complement": False,
			"has_cancelled_complement": False,
			"has_complement": True,
			"has_complement_error": True,
			"complement_status": "Error",
			"complement_has_file": False,
		}
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_retry_complement"])
		self.assertFalse(actions["can_cancel_complement"])


class TestFiscalStatePaymentEntryMessages(FrappeTestCase):
	"""Tests unitarios para _compute_messages() — solo lógica de mensajes."""

	def _base_facts(self, **overrides):
		facts = {
			"is_submitted": True,
			"is_cancelled": False,
			"is_draft": False,
			"payment_type": "Receive",
			"party_type": "Customer",
			"has_ppd_invoice": True,
			"has_ppd_stamped_invoice": True,
			"requires_complement": True,
			"has_complement": False,
			"has_active_complement": False,
			"has_cancelled_complement": False,
			"has_complement_error": False,
			"complement_status": None,
			"complement_has_uuid": False,
			"complement_has_file": False,
			"has_sales_invoice_references": True,
			"has_allocated_sales_invoice_references": True,
		}
		facts.update(overrides)
		return facts

	def test_mensaje_complement_required(self):
		msgs = _compute_messages(self._base_facts())
		codes = [m["code"] for m in msgs]
		self.assertIn("COMPLEMENT_REQUIRED", codes)

	def test_mensaje_complement_exists(self):
		msgs = _compute_messages(self._base_facts(has_active_complement=True, complement_status="Timbrado"))
		codes = [m["code"] for m in msgs]
		self.assertIn("COMPLEMENT_EXISTS", codes)

	def test_mensaje_complement_cancelled(self):
		msgs = _compute_messages(self._base_facts(has_cancelled_complement=True))
		codes = [m["code"] for m in msgs]
		self.assertIn("COMPLEMENT_CANCELLED", codes)

	def test_mensaje_complement_error(self):
		msgs = _compute_messages(self._base_facts(has_complement_error=True))
		codes = [m["code"] for m in msgs]
		self.assertIn("COMPLEMENT_ERROR", codes)

	def test_mensaje_not_required_cuando_pue(self):
		msgs = _compute_messages(
			self._base_facts(has_ppd_invoice=False, has_ppd_stamped_invoice=False, requires_complement=False)
		)
		codes = [m["code"] for m in msgs]
		self.assertIn("COMPLEMENT_NOT_REQUIRED", codes)

	def test_mensaje_blocked_ppd_sin_timbrar(self):
		msgs = _compute_messages(
			self._base_facts(has_ppd_invoice=True, has_ppd_stamped_invoice=False, requires_complement=False)
		)
		codes = [m["code"] for m in msgs]
		self.assertIn("COMPLEMENT_BLOCKED_NO_STAMPED_SI", codes)

	def test_sin_mensajes_pe_cancelado(self):
		msgs = _compute_messages(self._base_facts(is_submitted=False, is_cancelled=True))
		self.assertEqual(msgs, [])

	def test_sin_mensajes_pe_no_receive(self):
		msgs = _compute_messages(self._base_facts(payment_type="Pay"))
		self.assertEqual(msgs, [])
