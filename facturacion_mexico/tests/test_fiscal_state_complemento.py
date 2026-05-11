"""
Tests para fiscal_state/complemento_state.py

Casos cubiertos:
  1. Complemento Pendiente con documentos relacionados → PENDING_STAMP, can_stamp=True
  2. Complemento Pendiente sin documentos relacionados → MISSING_RELATED_DOCS
  3. Complemento Timbrado sin PE cancelado → CFDI_STAMPED, can_cancel=True
  4. Complemento Timbrado sin XML/PDF → FILES_MISSING
  5. Complemento Timbrado con PE cancelado → CFDI_STAMPED + PE_CANCELLED
  6. Complemento Cancelado → CFDI_CANCELLED
  7. Complemento Error → STAMP_ERROR, can_stamp=True
  8. Complemento Pendiente Cancelación → CANCELLATION_PENDING, can_retry_cancel=True
  9. Actions derivadas correctamente
"""

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.fiscal_state.complemento_state import (
	_compute_actions,
	_compute_facts,
	_compute_messages,
)


def _mock_comp(
	docstatus=0,
	status="Pendiente",
	uuid_sat="",
	facturapi_id="",
	xml_file="",
	pdf_file="",
	payment_entry="",
	monto_p=1000,
	moneda_p="MXN",
	forma_pago_p="03",
	documentos_relacionados=None,
):
	comp = MagicMock()
	comp.docstatus = docstatus
	comp.name = "COMP-TEST"

	attrs = {
		"status": status,
		"uuid_sat": uuid_sat,
		"facturapi_id": facturapi_id,
		"xml_file": xml_file,
		"pdf_file": pdf_file,
		"payment_entry": payment_entry,
		"monto_p": monto_p,
		"moneda_p": moneda_p,
		"forma_pago_p": forma_pago_p,
		"documentos_relacionados": documentos_relacionados or [],
	}
	comp.get = lambda key, default=None: attrs.get(key, default)
	return comp


class TestFiscalStateComplementoFacts(FrappeTestCase):
	# ── Caso 1: Pendiente con docs ────────────────────────────────────────
	def test_pendiente_con_docs(self):
		comp = _mock_comp(documentos_relacionados=[{"si": "SI-001"}])
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(comp)
		self.assertTrue(facts["is_pendiente"])
		self.assertFalse(facts["has_uuid"])
		self.assertTrue(facts["has_documentos_relacionados"])

	# ── Caso 2: Timbrado con uuid ─────────────────────────────────────────
	def test_timbrado(self):
		comp = _mock_comp(
			status="Timbrado",
			uuid_sat="UUID-123",
			facturapi_id="FAP-001",
			xml_file="/files/comp.xml",
			pdf_file="/files/comp.pdf",
			payment_entry="PE-001",
		)
		with patch("frappe.get_all", return_value=[{"docstatus": 1}]):
			facts = _compute_facts(comp)
		self.assertTrue(facts["is_timbrado"])
		self.assertTrue(facts["has_uuid"])
		self.assertTrue(facts["has_xml"])
		self.assertTrue(facts["has_pdf"])
		self.assertTrue(facts["pe_submitted"])
		self.assertFalse(facts["pe_cancelled"])

	# ── Caso 3: Timbrado con PE cancelado ────────────────────────────────
	def test_timbrado_pe_cancelado(self):
		comp = _mock_comp(
			status="Timbrado",
			uuid_sat="UUID-123",
			payment_entry="PE-001",
		)
		with patch("frappe.get_all", return_value=[{"docstatus": 2}]):
			facts = _compute_facts(comp)
		self.assertTrue(facts["is_timbrado"])
		self.assertTrue(facts["pe_cancelled"])
		self.assertFalse(facts["pe_submitted"])

	# ── Caso 4: Cancelado ────────────────────────────────────────────────
	def test_cancelado(self):
		comp = _mock_comp(status="Cancelado", uuid_sat="UUID-123")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(comp)
		self.assertTrue(facts["is_cancelado"])
		self.assertFalse(facts["is_timbrado"])

	# ── Caso 5: Error ────────────────────────────────────────────────────
	def test_error(self):
		comp = _mock_comp(status="Error")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(comp)
		self.assertTrue(facts["is_error"])

	# ── Caso 6: Pendiente Cancelación ────────────────────────────────────
	def test_pendiente_cancelacion(self):
		comp = _mock_comp(status="Pendiente Cancelación", uuid_sat="UUID-123")
		with patch("frappe.get_all", return_value=[]):
			facts = _compute_facts(comp)
		self.assertTrue(facts["is_pendiente_cancelacion"])


class TestFiscalStateComplementoActions(FrappeTestCase):
	def _base(self, **overrides):
		facts = {
			"is_draft": False,
			"is_submitted": True,
			"is_cancelled": False,
			"status": "Timbrado",
			"is_timbrado": True,
			"is_cancelado": False,
			"is_pendiente": False,
			"is_error": False,
			"is_pendiente_cancelacion": False,
			"has_uuid": True,
			"has_facturapi_id": True,
			"has_xml": True,
			"has_pdf": True,
			"has_payment_entry": True,
			"pe_submitted": True,
			"pe_cancelled": False,
			"has_documentos_relacionados": True,
		}
		facts.update(overrides)
		return facts

	def test_puede_timbrar_pendiente(self):
		"""Timbrar requiere docstatus=0 (draft) con status Pendiente."""
		facts = self._base(
			is_draft=True,
			is_submitted=False,
			status="Pendiente",
			is_timbrado=False,
			is_pendiente=True,
			has_uuid=False,
		)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_stamp"])
		self.assertFalse(actions["can_cancel"])

	def test_puede_timbrar_error(self):
		"""Timbrar requiere docstatus=0 (draft) con status Error."""
		facts = self._base(
			is_draft=True,
			is_submitted=False,
			status="Error",
			is_timbrado=False,
			is_error=True,
			has_uuid=False,
		)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_stamp"])

	def test_puede_cancelar_timbrado(self):
		facts = self._base()
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_cancel"])
		self.assertFalse(actions["can_stamp"])

	def test_puede_reintentar_cancelacion(self):
		facts = self._base(status="Pendiente Cancelación", is_timbrado=False, is_pendiente_cancelacion=True)
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_retry_cancel"])
		self.assertFalse(actions["can_cancel"])

	def test_puede_descargar(self):
		facts = self._base()
		actions = _compute_actions(facts)
		self.assertTrue(actions["can_download_xml"])
		self.assertTrue(actions["can_download_pdf"])

	def test_no_puede_descargar_sin_uuid(self):
		facts = self._base(has_uuid=False, has_xml=False, has_pdf=False)
		actions = _compute_actions(facts)
		self.assertFalse(actions["can_download_xml"])
		self.assertFalse(actions["can_download_pdf"])


class TestFiscalStateComplementoMessages(FrappeTestCase):
	def _base(self, **overrides):
		facts = {
			"is_timbrado": True,
			"is_cancelado": False,
			"is_pendiente": False,
			"is_error": False,
			"is_pendiente_cancelacion": False,
			"has_uuid": True,
			"has_xml": True,
			"has_pdf": True,
			"has_documentos_relacionados": True,
			"pe_submitted": True,
			"pe_cancelled": False,
		}
		facts.update(overrides)
		return facts

	def test_pendiente_con_docs(self):
		codes = [m["code"] for m in _compute_messages(self._base(is_timbrado=False, is_pendiente=True))]
		self.assertIn("PENDING_STAMP", codes)

	def test_pendiente_sin_docs(self):
		codes = [
			m["code"]
			for m in _compute_messages(
				self._base(is_timbrado=False, is_pendiente=True, has_documentos_relacionados=False)
			)
		]
		self.assertIn("MISSING_RELATED_DOCS", codes)
		self.assertNotIn("PENDING_STAMP", codes)

	def test_timbrado(self):
		codes = [m["code"] for m in _compute_messages(self._base())]
		self.assertIn("CFDI_STAMPED", codes)

	def test_timbrado_sin_archivos(self):
		codes = [m["code"] for m in _compute_messages(self._base(has_xml=False, has_pdf=False))]
		self.assertIn("FILES_MISSING", codes)

	def test_timbrado_pe_cancelado(self):
		codes = [m["code"] for m in _compute_messages(self._base(pe_cancelled=True))]
		self.assertIn("CFDI_STAMPED", codes)
		self.assertIn("PE_CANCELLED", codes)

	def test_cancelado(self):
		codes = [m["code"] for m in _compute_messages(self._base(is_timbrado=False, is_cancelado=True))]
		self.assertIn("CFDI_CANCELLED", codes)

	def test_error(self):
		codes = [m["code"] for m in _compute_messages(self._base(is_timbrado=False, is_error=True))]
		self.assertIn("STAMP_ERROR", codes)

	def test_pendiente_cancelacion(self):
		codes = [
			m["code"] for m in _compute_messages(self._base(is_timbrado=False, is_pendiente_cancelacion=True))
		]
		self.assertIn("CANCELLATION_PENDING", codes)
