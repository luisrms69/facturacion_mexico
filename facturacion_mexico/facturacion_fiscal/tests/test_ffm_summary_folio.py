"""Regresión issue #211: el widget "Serie y Folio" debe mostrar serie+folio, no solo el folio.

`get_ffm_summary` construye `folio`:
- prefiere `fm_serie_folio` (combinado ya persistido);
- si no, une `serie`-`folio`;
- como último recurso, muestra lo suelto.

Seeding directo por DB (sin red).
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.api.ffm_summary import get_ffm_summary


def _seed_ffm(**fields):
	ffm = frappe.get_doc({"doctype": "Factura Fiscal Mexico", "status": "TIMBRADO", "docstatus": 0, **fields})
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	return ffm.name


class TestFfmSummaryFolio(IntegrationTestCase):
	def test_combina_serie_y_folio(self):
		# serie + folio separados, sin fm_serie_folio → "F-11679" (no solo el folio)
		name = _seed_ffm(serie="F", folio="11679")
		self.assertEqual(get_ffm_summary(name)["folio"], "F-11679")

	def test_prefiere_fm_serie_folio_si_existe(self):
		name = _seed_ffm(serie="F", folio="11679", fm_serie_folio="F-99999")
		self.assertEqual(get_ffm_summary(name)["folio"], "F-99999")

	def test_solo_folio_sin_serie(self):
		name = _seed_ffm(folio="500")
		self.assertEqual(get_ffm_summary(name)["folio"], "500")
