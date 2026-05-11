"""
Tests para fiscal_state/sales_invoice_state.py

Casos cubiertos:
  1. SI borrador → BLOCKED_DRAFT, sin acciones
  2. SI submitted sin FFM → CFDI_NOT_STAMPED, can_stamp=True
  3. SI submitted con FFM timbrada (PUE) → CFDI_STAMPED, can_cancel=True
  4. SI submitted con FFM timbrada (PPD) + PE + sin complemento → COMPLEMENT_REQUIRED
  5. SI submitted con FFM timbrada (PPD) + PE + complemento activo → COMPLEMENT_EXISTS
  6. SI submitted con FFM cancelada motivo 02 → CFDI_CANCELLED, can_refacturar=True
  7. SI submitted con FFM cancelada motivo 01 → can_substitute=False (motivo 01 no es refacturar)
  8. SI cancelada → BLOCKED_CANCELLED
  9. Actions derivadas correctamente
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.fiscal_state.sales_invoice_state import (
	_compute_actions,
	_compute_facts,
	_compute_messages,
)


def _mock_si(
	docstatus=1,
	fm_fiscal_status="",
	fm_factura_fiscal_mx="",
	fm_es_ppd=0,
	is_return=0,
	outstanding_amount=1000,
	grand_total=1000,
):
	si = MagicMock()
	si.docstatus = docstatus
	si.name = "ACC-SINV-TEST"
	si.fm_fiscal_status = fm_fiscal_status
	si.fm_factura_fiscal_mx = fm_factura_fiscal_mx
	si.fm_es_ppd = fm_es_ppd
	si.is_return = is_return
	si.outstanding_amount = outstanding_amount
	si.grand_total = grand_total

	def _get(key, default=None):
		return getattr(si, key, default)

	si.get = _get
	return si


def _ffm(status="TIMBRADO", fm_uuid="UUID-123", motivo=None, docstatus=1):
	return [
		{
			"name": "FFMX-TEST",
			"status": status,
			"fm_uuid": fm_uuid,
			"fm_motivo_cancelacion": motivo,
			"docstatus": docstatus,
		}
	]


class TestFiscalStateSIFacts(FrappeTestCase):
	# ── Caso 1: borrador ──────────────────────────────────────────────────
	def test_borrador(self):
		si = _mock_si(docstatus=0, fm_fiscal_status="")
		with patch("frappe.get_all", return_value=[]), patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(si)
		self.assertTrue(facts["is_draft"])
		self.assertFalse(facts["is_submitted"])

	# ── Caso 2: submitted sin FFM ─────────────────────────────────────────
	def test_submitted_sin_ffm(self):
		si = _mock_si(fm_fiscal_status="BORRADOR")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(si)
		self.assertTrue(facts["is_submitted"])
		self.assertFalse(facts["has_ffm"])
		self.assertFalse(facts["has_stamped_ffm"])
		self.assertEqual(facts["fiscal_status"], "BORRADOR")

	# ── Caso 3: FFM timbrada PUE ─────────────────────────────────────────
	def test_ffm_timbrada_pue(self):
		si = _mock_si(fm_fiscal_status="TIMBRADO", fm_factura_fiscal_mx="FFMX-001", fm_es_ppd=0)
		with patch("frappe.get_all", side_effect=[_ffm(), [], [], []]):
			facts = _compute_facts(si)
		self.assertTrue(facts["has_ffm"])
		self.assertTrue(facts["has_stamped_ffm"])
		self.assertTrue(facts["has_active_ffm"])
		self.assertFalse(facts["has_cancelled_ffm"])
		self.assertFalse(facts["is_ppd"])
		self.assertFalse(facts["requires_complement"])

	# ── Caso 4: FFM timbrada PPD + PE submitted + sin complemento ─────────
	def test_ppd_con_pe_sin_complemento(self):
		si = _mock_si(fm_fiscal_status="TIMBRADO", fm_factura_fiscal_mx="FFMX-001", fm_es_ppd=1)
		ffm_data = _ffm()
		pe_refs = [{"parent": "PE-001"}]
		submitted_pe = [{"name": "PE-001"}]
		comps = []

		with patch("frappe.get_all", side_effect=[ffm_data, [], pe_refs, submitted_pe, submitted_pe, comps]):
			facts = _compute_facts(si)

		self.assertTrue(facts["is_ppd"])
		self.assertTrue(facts["has_submitted_payment_entries"])
		self.assertTrue(facts["requires_complement"])
		self.assertFalse(facts["has_active_complement"])

	# ── Caso 5: PPD con complemento activo ───────────────────────────────
	def test_ppd_con_complemento_activo(self):
		si = _mock_si(fm_fiscal_status="TIMBRADO", fm_factura_fiscal_mx="FFMX-001", fm_es_ppd=1)
		ffm_data = _ffm()
		pe_refs = [{"parent": "PE-001"}]
		submitted_pe = [{"name": "PE-001"}]
		comps = [{"name": "COMP-001", "status": "Timbrado"}]

		with patch("frappe.get_all", side_effect=[ffm_data, [], pe_refs, submitted_pe, submitted_pe, comps]):
			facts = _compute_facts(si)

		self.assertTrue(facts["has_complement"])
		self.assertTrue(facts["has_active_complement"])

	# ── Caso 6: FFM cancelada motivo 02 ──────────────────────────────────
	def test_ffm_cancelada_motivo_02(self):
		si = _mock_si(fm_fiscal_status="CANCELADO", fm_factura_fiscal_mx="FFMX-001")
		ffm_data = _ffm(status="CANCELADO", motivo="02")

		with patch("frappe.get_all", side_effect=[ffm_data, [], [], []]):
			facts = _compute_facts(si)

		self.assertTrue(facts["has_cancelled_ffm"])
		self.assertFalse(facts["has_active_ffm"])
		self.assertEqual(facts["ffm_motivo_cancelacion"], "02")

	# ── Caso 7: cancelada ────────────────────────────────────────────────
	def test_si_cancelada(self):
		si = _mock_si(docstatus=2, fm_fiscal_status="CANCELADO")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(si)
		self.assertTrue(facts["is_cancelled"])
		self.assertFalse(facts["is_submitted"])


class TestFiscalStateSIActions(FrappeTestCase):
	def _base_facts(self, **overrides):
		facts = {
			"is_draft": False,
			"is_submitted": True,
			"is_cancelled": False,
			"is_ppd": False,
			"is_pue": True,
			"fiscal_status": "TIMBRADO",
			"has_ffm": True,
			"has_active_ffm": True,
			"has_cancelled_ffm": False,
			"has_stamped_ffm": True,
			"has_uuid": True,
			"has_xml": True,
			"has_pdf": True,
			"outstanding_amount": 0,
			"is_paid": True,
			"is_partially_paid": False,
			"has_payment_entries": False,
			"has_submitted_payment_entries": False,
			"requires_complement": False,
			"has_complement": False,
			"has_active_complement": False,
			"ffm_motivo_cancelacion": None,
		}
		facts.update(overrides)
		return facts

	def test_can_stamp_cuando_sin_ffm(self):
		facts = self._base_facts(
			fiscal_status="BORRADOR",
			has_ffm=False,
			has_active_ffm=False,
			has_stamped_ffm=False,
			has_uuid=False,
			has_xml=False,
			has_pdf=False,
		)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_stamp"])
		self.assertFalse(actions["can_view_ffm"])

	def test_no_puede_timbrar_si_tiene_ffm_activa(self):
		facts = self._base_facts()
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_stamp"])
		self.assertTrue(actions["can_view_ffm"])
		self.assertTrue(actions["can_cancel_cfdi"])

	def test_puede_refacturar_motivo_02(self):
		facts = self._base_facts(
			fiscal_status="CANCELADO",
			has_active_ffm=False,
			has_cancelled_ffm=True,
			ffm_motivo_cancelacion="02",
		)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_refacturar"])
		self.assertFalse(actions["can_cancel_cfdi"])

	def test_no_puede_refacturar_motivo_01(self):
		facts = self._base_facts(
			fiscal_status="CANCELADO",
			has_active_ffm=False,
			has_cancelled_ffm=True,
			ffm_motivo_cancelacion="01",
		)
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_refacturar"])

	def test_puede_sustituir_cuando_timbrado(self):
		facts = self._base_facts(fiscal_status="TIMBRADO")
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_substitute"])

	def test_puede_generar_complemento_ppd(self):
		facts = self._base_facts(
			is_ppd=True,
			is_pue=False,
			has_submitted_payment_entries=True,
			requires_complement=True,
			has_active_complement=False,
		)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_generate_payment_complement"])

	def test_no_puede_cancelar_si_tiene_complemento_activo(self):
		facts = self._base_facts(has_active_complement=True)
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_cancel_cfdi"])

	# ── can_register_payment ─────────────────────────────────────────────
	def test_puede_registrar_pago_sin_ffm(self):
		"""SI submitted sin FFM → can_register_payment = True."""
		facts = self._base_facts(
			has_ffm=False,
			has_active_ffm=False,
			has_stamped_ffm=False,
			has_uuid=False,
			has_xml=False,
			has_pdf=False,
			fiscal_status="BORRADOR",
		)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_register_payment"])

	def test_puede_registrar_pago_con_ffm_activa(self):
		"""SI submitted con FFM activa (TIMBRADO) → can_register_payment = True."""
		facts = self._base_facts(fiscal_status="TIMBRADO", has_active_ffm=True)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_register_payment"])

	def test_no_puede_registrar_pago_con_ffm_cancelada(self):
		"""SI submitted con FFM CANCELADA → can_register_payment = False."""
		facts = self._base_facts(
			fiscal_status="CANCELADO",
			has_ffm=True,
			has_active_ffm=False,
			has_cancelled_ffm=True,
		)
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_register_payment"])

	def test_no_puede_registrar_pago_si_cancelada(self):
		"""SI cancelada (docstatus=2) → can_register_payment = False."""
		facts = self._base_facts(
			is_submitted=False,
			is_cancelled=True,
		)
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_register_payment"])


class TestFiscalStateSIMessages(FrappeTestCase):
	def _base(self, **overrides):
		facts = {
			"is_draft": False,
			"is_submitted": True,
			"is_cancelled": False,
			"fiscal_status": "TIMBRADO",
			"has_stamped_ffm": True,
			"has_cancelled_ffm": False,
			"has_uuid": True,
			"has_xml": True,
			"has_pdf": True,
			"requires_complement": False,
			"has_complement": False,
			"has_active_complement": False,
			"ffm_motivo_cancelacion": None,
		}
		facts.update(overrides)
		return facts

	def test_borrador(self):
		codes = [m["code"] for m in _compute_messages(self._base(is_draft=True, is_submitted=False))]
		self.assertIn("BLOCKED_DRAFT", codes)

	def test_cancelado(self):
		codes = [m["code"] for m in _compute_messages(self._base(is_cancelled=True, is_submitted=False))]
		self.assertIn("BLOCKED_CANCELLED", codes)

	def test_cfdi_not_stamped(self):
		"""CFDI_NOT_STAMPED solo cuando no hay cancelación y no hay UUID."""
		codes = [
			m["code"]
			for m in _compute_messages(
				self._base(
					has_stamped_ffm=False,
					has_uuid=False,
					fiscal_status="BORRADOR",
					has_cancelled_ffm=False,
				)
			)
		]
		self.assertIn("CFDI_NOT_STAMPED", codes)
		self.assertNotIn("CFDI_CANCELLED", codes)

	def test_cfdi_cancelled_con_uuid(self):
		"""CFDI_CANCELLED cuando fiscal_status=CANCELADO con UUID."""
		codes = [m["code"] for m in _compute_messages(self._base(fiscal_status="CANCELADO"))]
		self.assertIn("CFDI_CANCELLED", codes)
		self.assertNotIn("CFDI_NOT_STAMPED", codes)

	def test_cfdi_cancelled_sin_uuid(self):
		"""CFDI_CANCELLED tiene prioridad sobre CFDI_NOT_STAMPED cuando fiscal_status=CANCELADO."""
		codes = [
			m["code"]
			for m in _compute_messages(
				self._base(
					fiscal_status="CANCELADO",
					has_stamped_ffm=False,
					has_uuid=False,
					has_cancelled_ffm=False,
				)
			)
		]
		self.assertIn("CFDI_CANCELLED", codes)
		self.assertNotIn("CFDI_NOT_STAMPED", codes)

	def test_cfdi_cancelled_por_ffm_cancelada(self):
		"""CFDI_CANCELLED también cuando has_cancelled_ffm=True aunque fiscal_status no sea CANCELADO."""
		codes = [
			m["code"]
			for m in _compute_messages(
				self._base(
					fiscal_status="",
					has_stamped_ffm=False,
					has_uuid=False,
					has_cancelled_ffm=True,
				)
			)
		]
		self.assertIn("CFDI_CANCELLED", codes)
		self.assertNotIn("CFDI_NOT_STAMPED", codes)

	def test_cfdi_stamped(self):
		codes = [m["code"] for m in _compute_messages(self._base())]
		self.assertIn("CFDI_STAMPED", codes)

	def test_cfdi_files_missing(self):
		codes = [m["code"] for m in _compute_messages(self._base(has_xml=False, has_pdf=False))]
		self.assertIn("CFDI_FILES_MISSING", codes)

	def test_cfdi_cancelled(self):
		codes = [m["code"] for m in _compute_messages(self._base(fiscal_status="CANCELADO"))]
		self.assertIn("CFDI_CANCELLED", codes)

	def test_complement_required(self):
		codes = [m["code"] for m in _compute_messages(self._base(requires_complement=True))]
		self.assertIn("COMPLEMENT_REQUIRED", codes)

	def test_complement_exists(self):
		codes = [
			m["code"]
			for m in _compute_messages(self._base(requires_complement=True, has_active_complement=True))
		]
		self.assertIn("COMPLEMENT_EXISTS", codes)

	def test_complement_pending(self):
		codes = [
			m["code"] for m in _compute_messages(self._base(requires_complement=True, has_complement=True))
		]
		self.assertIn("COMPLEMENT_PENDING", codes)
