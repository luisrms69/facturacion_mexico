"""
Tests para fiscal_state/ffm_state.py

Casos cubiertos:
  1. FFM borrador → sin mensajes
  2. FFM submitted BORRADOR con tax_system válido → PENDING_STAMP, can_stamp=True
  3. FFM submitted BORRADOR sin tax_system → TAX_SYSTEM_INVALID, can_stamp=False
  4. FFM submitted TIMBRADO sin PE activo → CFDI_STAMPED, can_cancel=True
  5. FFM submitted TIMBRADO con PE activo → CANCEL_BLOCKED_ACTIVE_PE, can_cancel=False
  6. FFM submitted CANCELADO → CFDI_CANCELLED, can_cancel=False
  7. FFM submitted PENDIENTE_CANCELACION → CANCELLATION_PENDING, can_retry_cancel=True
  8. FFM submitted ERROR → STAMP_ERROR
  9. sync_pending bloquea acciones
  10. Actions derivadas correctamente
"""

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.fiscal_state.ffm_state import (
	_compute_actions,
	_compute_facts,
	_compute_messages,
)


def _mock_ffm(
	docstatus=1,
	status="BORRADOR",
	fm_uuid="",
	facturapi_id="",
	fm_tipo_comprobante="I - Ingreso",
	fm_payment_method_sat="PUE",
	fm_xml_url="",
	fm_pdf_url="",
	fm_motivo_cancelacion="",
	cancellation_reason="",
	fm_sync_status="idle",
	fm_tax_system="601 - General de Ley",
	sales_invoice="",
):
	ffm = MagicMock()
	ffm.docstatus = docstatus
	ffm.name = "FFMX-TEST"

	attrs = {
		"status": status,
		"fm_uuid": fm_uuid,
		"facturapi_id": facturapi_id,
		"fm_tipo_comprobante": fm_tipo_comprobante,
		"fm_payment_method_sat": fm_payment_method_sat,
		"fm_xml_url": fm_xml_url,
		"fm_pdf_url": fm_pdf_url,
		"fm_motivo_cancelacion": fm_motivo_cancelacion,
		"cancellation_reason": cancellation_reason,
		"fm_sync_status": fm_sync_status,
		"fm_tax_system": fm_tax_system,
		"sales_invoice": sales_invoice,
	}
	ffm.get = lambda key, default=None: attrs.get(key, default)
	return ffm


class TestFiscalStateFFMFacts(FrappeTestCase):
	# ── Caso 1: borrador ──────────────────────────────────────────────────
	def test_borrador_docstatus(self):
		ffm = _mock_ffm(docstatus=0)
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(ffm)
		self.assertTrue(facts["is_draft"])
		self.assertFalse(facts["is_submitted"])

	# ── Caso 2: TIMBRADO con uuid ─────────────────────────────────────────
	def test_timbrado_con_uuid(self):
		ffm = _mock_ffm(status="TIMBRADO", fm_uuid="UUID-123", facturapi_id="FAP-001")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(ffm)
		self.assertTrue(facts["is_timbrado"])
		self.assertTrue(facts["has_uuid"])
		self.assertTrue(facts["has_facturapi_id"])
		self.assertFalse(facts["has_active_payment_entry"])

	# ── Caso 3: TIMBRADO con PE activo ───────────────────────────────────
	def test_timbrado_con_pe_activo(self):
		ffm = _mock_ffm(status="TIMBRADO", fm_uuid="UUID-123", sales_invoice="SI-001")
		pe_refs = [{"parent": "PE-001"}]
		submitted_pe = [{"name": "PE-001"}]
		with patch("frappe.get_all", side_effect=[pe_refs, submitted_pe]):
			facts = _compute_facts(ffm)
		self.assertTrue(facts["has_active_payment_entry"])
		self.assertTrue(facts["has_sales_invoice"])

	# ── Caso 4: CANCELADO ────────────────────────────────────────────────
	def test_cancelado(self):
		ffm = _mock_ffm(status="CANCELADO", fm_uuid="UUID-123", fm_motivo_cancelacion="02")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(ffm)
		self.assertTrue(facts["is_cancelado"])
		self.assertEqual(facts["motivo_cancelacion"], "02")

	# ── Caso 5: sync_pending ─────────────────────────────────────────────
	def test_sync_pending(self):
		ffm = _mock_ffm(fm_sync_status="pending")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(ffm)
		self.assertTrue(facts["sync_pending"])

	# ── Caso 6: tax_system inválido ───────────────────────────────────────
	def test_tax_system_invalido(self):
		ffm = _mock_ffm(fm_tax_system="⚠️ Sin configurar")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(ffm)
		self.assertFalse(facts["tax_system_valid"])

	def test_tax_system_valido(self):
		ffm = _mock_ffm(fm_tax_system="601 - General de Ley")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(ffm)
		self.assertTrue(facts["tax_system_valid"])

	# ── Caso 7: PPD vs PUE ───────────────────────────────────────────────
	def test_ppd(self):
		ffm = _mock_ffm(fm_payment_method_sat="PPD")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(ffm)
		self.assertTrue(facts["is_ppd"])
		self.assertFalse(facts["is_pue"])

	def test_pue(self):
		ffm = _mock_ffm(fm_payment_method_sat="PUE")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(ffm)
		self.assertFalse(facts["is_ppd"])
		self.assertTrue(facts["is_pue"])


class TestFiscalStateFFMActions(FrappeTestCase):
	def _base(self, **overrides):
		facts = {
			"is_draft": False,
			"is_submitted": True,
			"is_cancelled": False,
			"status": "TIMBRADO",
			"is_timbrado": True,
			"is_cancelado": False,
			"is_pendiente_cancelacion": False,
			"is_borrador": False,
			"is_error": False,
			"sync_pending": False,
			"has_uuid": True,
			"has_facturapi_id": True,
			"has_xml": True,
			"has_pdf": True,
			"tax_system_valid": True,
			"has_active_payment_entry": False,
			"has_sales_invoice": True,
		}
		facts.update(overrides)
		return facts

	def test_can_stamp_borrador(self):
		facts = self._base(status="BORRADOR", is_timbrado=False, is_borrador=True, has_uuid=False)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_stamp"])
		self.assertFalse(actions["can_cancel"])

	def test_no_puede_timbrar_sin_tax_system(self):
		facts = self._base(
			status="BORRADOR", is_timbrado=False, is_borrador=True, has_uuid=False, tax_system_valid=False
		)
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_stamp"])

	def test_puede_cancelar_timbrado_sin_pe(self):
		facts = self._base()
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_cancel"])
		self.assertFalse(actions["can_stamp"])

	def test_no_puede_cancelar_con_pe_activo(self):
		facts = self._base(has_active_payment_entry=True)
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_cancel"])

	def test_no_puede_cancelar_con_sync_pending(self):
		facts = self._base(sync_pending=True)
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_cancel"])
		self.assertFalse(actions["can_stamp"])

	def test_puede_reintentar_cancelacion(self):
		facts = self._base(status="PENDIENTE_CANCELACION", is_timbrado=False, is_pendiente_cancelacion=True)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_retry_cancel"])
		self.assertFalse(actions["can_cancel"])

	def test_puede_descargar_archivos(self):
		facts = self._base()
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_download_xml"])
		self.assertTrue(actions["can_download_pdf"])
		self.assertTrue(actions["can_send_email"])

	def test_no_puede_descargar_sin_uuid(self):
		facts = self._base(has_uuid=False, has_xml=False, has_pdf=False)
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_download_xml"])
		self.assertFalse(actions["can_download_pdf"])


class TestFiscalStateFFMMessages(FrappeTestCase):
	def _base(self, **overrides):
		facts = {
			"is_submitted": True,
			"status": "TIMBRADO",
			"is_timbrado": True,
			"is_cancelado": False,
			"is_pendiente_cancelacion": False,
			"is_borrador": False,
			"is_error": False,
			"sync_pending": False,
			"has_uuid": True,
			"has_facturapi_id": True,
			"has_xml": True,
			"has_pdf": True,
			"tax_system_valid": True,
			"has_active_payment_entry": False,
		}
		facts.update(overrides)
		return facts

	def test_sin_mensajes_borrador(self):
		msgs = _compute_messages(self._base(is_submitted=False))
		self.assertEqual(msgs, [])

	def test_sync_pending(self):
		codes = [m["code"] for m in _compute_messages(self._base(sync_pending=True))]
		self.assertIn("SYNC_PENDING", codes)

	def test_pending_stamp(self):
		codes = [
			m["code"]
			for m in _compute_messages(self._base(status="BORRADOR", is_timbrado=False, is_borrador=True))
		]
		self.assertIn("PENDING_STAMP", codes)

	def test_tax_system_invalid(self):
		codes = [
			m["code"]
			for m in _compute_messages(
				self._base(status="BORRADOR", is_timbrado=False, is_borrador=True, tax_system_valid=False)
			)
		]
		self.assertIn("TAX_SYSTEM_INVALID", codes)
		self.assertNotIn("PENDING_STAMP", codes)

	def test_cfdi_stamped(self):
		codes = [m["code"] for m in _compute_messages(self._base())]
		self.assertIn("CFDI_STAMPED", codes)

	def test_files_missing(self):
		codes = [m["code"] for m in _compute_messages(self._base(has_xml=False, has_pdf=False))]
		self.assertIn("FILES_MISSING", codes)

	def test_cancel_blocked_active_pe(self):
		codes = [m["code"] for m in _compute_messages(self._base(has_active_payment_entry=True))]
		self.assertIn("CANCEL_BLOCKED_ACTIVE_PE", codes)
		self.assertIn("CFDI_STAMPED", codes)

	def test_cfdi_cancelled(self):
		codes = [
			m["code"]
			for m in _compute_messages(self._base(status="CANCELADO", is_timbrado=False, is_cancelado=True))
		]
		self.assertIn("CFDI_CANCELLED", codes)

	def test_cancellation_pending(self):
		codes = [
			m["code"]
			for m in _compute_messages(
				self._base(status="PENDIENTE_CANCELACION", is_timbrado=False, is_pendiente_cancelacion=True)
			)
		]
		self.assertIn("CANCELLATION_PENDING", codes)

	def test_stamp_error(self):
		codes = [
			m["code"] for m in _compute_messages(self._base(status="ERROR", is_timbrado=False, is_error=True))
		]
		self.assertIn("STAMP_ERROR", codes)
