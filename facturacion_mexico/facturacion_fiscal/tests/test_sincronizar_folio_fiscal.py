"""Pruebas del helper `sincronizar_folio_fiscal`: proyección del folio vigente a Sales Invoice.

`SI.fm_folio_fiscal` refleja el FOLIO consecutivo del CFDI VIGENTE de la FFM ligada
(status ∈ {TIMBRADO, PENDIENTE_CANCELACION} y `folio` presente); si no hay FFM vigente, se limpia.
Folio = el consecutivo (`FFM.folio`), el que usa el cliente — NO el UUID. La función es
idempotente y solo lee campos internos (sin FacturAPI).

Seeding directo por DB (sin red, sin PAC), patrón de test_cancel_guard_draft_ffm.
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.config.fiscal_states_config import FiscalStates
from facturacion_mexico.facturacion_fiscal.tasks import sync_folio_fiscal_scheduled
from facturacion_mexico.facturacion_fiscal.utils import sincronizar_folio_fiscal


def _folio_unico():
	"""Folio de prueba único (Data), evita colisiones en DB compartida."""
	return frappe.generate_hash(length=8)


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


def _seed_ffm(status, *, folio=None, docstatus=1):
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"status": status,
			"docstatus": docstatus,
			"folio": folio,
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
	def test_timbrado_copia_folio(self):
		folio = _folio_unico()
		ffm = _seed_ffm(FiscalStates.TIMBRADO, folio=folio)
		si = _seed_si(fm_factura_fiscal_mx=ffm)

		result = sincronizar_folio_fiscal(si)

		self.assertEqual(result, folio)
		self.assertEqual(_folio(si), folio)

	def test_pendiente_cancelacion_copia_folio(self):
		folio = _folio_unico()
		ffm = _seed_ffm(FiscalStates.PENDIENTE_CANCELACION, folio=folio)
		si = _seed_si(fm_factura_fiscal_mx=ffm)

		self.assertEqual(sincronizar_folio_fiscal(si), folio)
		self.assertEqual(_folio(si), folio)

	def test_cancelado_limpia(self):
		# La SI arranca con un folio previo; al recomputar sobre FFM CANCELADO debe quedar vacío
		folio = _folio_unico()
		ffm = _seed_ffm(FiscalStates.CANCELADO, folio=folio)
		si = _seed_si(fm_folio_fiscal="FOLIO-PREVIO", fm_factura_fiscal_mx=ffm)

		self.assertEqual(sincronizar_folio_fiscal(si), "")
		self.assertEqual(_folio(si), "")

	def test_si_sin_ffm_limpia(self):
		si = _seed_si(fm_folio_fiscal="FOLIO-PREVIO", fm_factura_fiscal_mx=None)

		self.assertEqual(sincronizar_folio_fiscal(si), "")
		self.assertEqual(_folio(si), "")

	def test_retimbrado_actualiza_folio(self):
		# Ligada a FFM1 TIMBRADO → folio1; se repunta a FFM2 TIMBRADO → folio2
		folio1 = _folio_unico()
		folio2 = _folio_unico()
		ffm1 = _seed_ffm(FiscalStates.TIMBRADO, folio=folio1)
		si = _seed_si(fm_factura_fiscal_mx=ffm1)
		self.assertEqual(sincronizar_folio_fiscal(si), folio1)

		ffm2 = _seed_ffm(FiscalStates.TIMBRADO, folio=folio2)
		frappe.db.set_value("Sales Invoice", si, "fm_factura_fiscal_mx", ffm2)

		self.assertEqual(sincronizar_folio_fiscal(si), folio2)
		self.assertEqual(_folio(si), folio2)

	def test_idempotencia(self):
		folio = _folio_unico()
		ffm = _seed_ffm(FiscalStates.TIMBRADO, folio=folio)
		si = _seed_si(fm_factura_fiscal_mx=ffm)

		self.assertEqual(sincronizar_folio_fiscal(si), folio)
		# Segunda llamada: mismo resultado, sin cambios
		self.assertEqual(sincronizar_folio_fiscal(si), folio)
		self.assertEqual(_folio(si), folio)


class TestSyncFolioFiscalScheduled(IntegrationTestCase):
	"""La tarea programada reutiliza el helper y reconcilia (corrige/limpia) con conteos correctos."""

	def test_tarea_reconcilia_y_cuenta(self):
		# actualiza: FFM TIMBRADO con folio, SI sin folio
		folio_a = _folio_unico()
		ffm_a = _seed_ffm(FiscalStates.TIMBRADO, folio=folio_a)
		si_a = _seed_si(fm_factura_fiscal_mx=ffm_a)
		# limpia: FFM CANCELADO, SI con folio previo (no vigente → se limpia)
		ffm_c = _seed_ffm(FiscalStates.CANCELADO, folio=_folio_unico())
		si_c = _seed_si(fm_folio_fiscal="FOLIO-PREVIO", fm_factura_fiscal_mx=ffm_c)
		# sin cambio: FFM TIMBRADO con folio ya sincronizado
		folio_s = _folio_unico()
		ffm_s = _seed_ffm(FiscalStates.TIMBRADO, folio=folio_s)
		si_s = _seed_si(fm_folio_fiscal=folio_s, fm_factura_fiscal_mx=ffm_s)

		stats = sync_folio_fiscal_scheduled()

		# Los 3 seeds terminaron en el estado esperado (la tarea llamó la sincronización)
		self.assertEqual(_folio(si_a), folio_a)  # actualizado
		self.assertEqual(_folio(si_c), "")  # limpiado
		self.assertEqual(_folio(si_s), folio_s)  # sin cambio

		# Conteos consistentes, sin errores
		self.assertEqual(stats["errores"], 0)
		self.assertEqual(
			stats["revisadas"],
			stats["actualizadas"] + stats["limpiadas"] + stats["sin_cambio"] + stats["errores"],
		)
		# Nuestros seeds aportan al menos 1 a cada categoría
		self.assertGreaterEqual(stats["actualizadas"], 1)
		self.assertGreaterEqual(stats["limpiadas"], 1)
		self.assertGreaterEqual(stats["sin_cambio"], 1)
