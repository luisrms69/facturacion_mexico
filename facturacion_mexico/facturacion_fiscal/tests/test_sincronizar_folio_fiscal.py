"""Pruebas del helper `sincronizar_folio_fiscal`: proyección del folio vigente a Sales Invoice.

`SI.fm_folio_fiscal` refleja el UUID del CFDI VIGENTE de la FFM ligada
(status ∈ {TIMBRADO, PENDIENTE_CANCELACION} y fm_uuid presente); si no hay FFM vigente, se limpia.
La función es idempotente y solo lee campos internos (sin FacturAPI).

Seeding directo por DB (sin red, sin PAC), patrón de test_cancel_guard_draft_ffm.
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.config.fiscal_states_config import FiscalStates
from facturacion_mexico.facturacion_fiscal.utils import sincronizar_folio_fiscal


def _seed_si(fm_folio_fiscal=None, fm_factura_fiscal_mx=None):
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"net_total": 100,
			"grand_total": 116,
			"posting_date": frappe.utils.today(),
			"docstatus": 1,
			"fm_folio_fiscal": fm_folio_fiscal,
			"fm_factura_fiscal_mx": fm_factura_fiscal_mx,
		}
	)
	si.flags.ignore_validate = True
	si.flags.ignore_mandatory = True
	si.flags.ignore_links = True
	si.db_insert()
	return si.name


def _seed_ffm(status, *, uuid=None, docstatus=1):
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"status": status,
			"docstatus": docstatus,
			"fm_uuid": uuid,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	return ffm.name


def _folio(si_name):
	return frappe.db.get_value("Sales Invoice", si_name, "fm_folio_fiscal") or ""


class TestSincronizarFolioFiscal(IntegrationTestCase):
	def test_timbrado_copia_uuid(self):
		uuid = frappe.generate_hash(length=12)
		ffm = _seed_ffm(FiscalStates.TIMBRADO, uuid=uuid)
		si = _seed_si(fm_factura_fiscal_mx=ffm)

		result = sincronizar_folio_fiscal(si)

		self.assertEqual(result, uuid)
		self.assertEqual(_folio(si), uuid)

	def test_pendiente_cancelacion_copia_uuid(self):
		uuid = frappe.generate_hash(length=12)
		ffm = _seed_ffm(FiscalStates.PENDIENTE_CANCELACION, uuid=uuid)
		si = _seed_si(fm_factura_fiscal_mx=ffm)

		self.assertEqual(sincronizar_folio_fiscal(si), uuid)
		self.assertEqual(_folio(si), uuid)

	def test_cancelado_limpia(self):
		# La SI arranca con un folio previo; al recomputar sobre FFM CANCELADO debe quedar vacío
		uuid = frappe.generate_hash(length=12)
		ffm = _seed_ffm(FiscalStates.CANCELADO, uuid=uuid)
		si = _seed_si(fm_folio_fiscal="FOLIO-PREVIO", fm_factura_fiscal_mx=ffm)

		self.assertEqual(sincronizar_folio_fiscal(si), "")
		self.assertEqual(_folio(si), "")

	def test_si_sin_ffm_limpia(self):
		si = _seed_si(fm_folio_fiscal="FOLIO-PREVIO", fm_factura_fiscal_mx=None)

		self.assertEqual(sincronizar_folio_fiscal(si), "")
		self.assertEqual(_folio(si), "")

	def test_retimbrado_actualiza_uuid(self):
		# Ligada a FFM1 TIMBRADO → folio = uuid1; se repunta a FFM2 TIMBRADO → folio = uuid2
		uuid1 = frappe.generate_hash(length=12)
		uuid2 = frappe.generate_hash(length=12)
		ffm1 = _seed_ffm(FiscalStates.TIMBRADO, uuid=uuid1)
		si = _seed_si(fm_factura_fiscal_mx=ffm1)
		self.assertEqual(sincronizar_folio_fiscal(si), uuid1)

		ffm2 = _seed_ffm(FiscalStates.TIMBRADO, uuid=uuid2)
		frappe.db.set_value("Sales Invoice", si, "fm_factura_fiscal_mx", ffm2)

		self.assertEqual(sincronizar_folio_fiscal(si), uuid2)
		self.assertEqual(_folio(si), uuid2)

	def test_idempotencia(self):
		uuid = frappe.generate_hash(length=12)
		ffm = _seed_ffm(FiscalStates.TIMBRADO, uuid=uuid)
		si = _seed_si(fm_factura_fiscal_mx=ffm)

		self.assertEqual(sincronizar_folio_fiscal(si), uuid)
		# Segunda llamada: mismo resultado, sin cambios
		self.assertEqual(sincronizar_folio_fiscal(si), uuid)
		self.assertEqual(_folio(si), uuid)
