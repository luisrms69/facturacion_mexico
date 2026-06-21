"""Persistencia fiscal correcta del timbrado en write_pac_response (Corrección 6B0).

El UUID de un timbrado exitoso llega dentro de `raw_response`, no a nivel superior.
Antes, `_derive_status_from_response` solo lo buscaba arriba y derivaba `ERROR`, que se
commiteaba temporalmente hasta que la FASE 3 lo corregía. Ahora el writer usa el extractor
normalizado `_extract_response_identifiers` y persiste `TIMBRADO` + UUID + facturapi_id
directamente, sin pasar por `ERROR`.

Todo con respuestas SIMULADAS. Cero llamadas reales al PAC.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.api import PACResponseWriter

_TIMBRADO_API = "facturacion_mexico.facturacion_fiscal.timbrado_api"


def _seed_si() -> str:
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"net_total": 100,
			"grand_total": 116,
			"posting_date": frappe.utils.today(),
			"docstatus": 1,
		}
	)
	si.flags.ignore_validate = True
	si.flags.ignore_mandatory = True
	si.flags.ignore_links = True
	si.db_insert()
	frappe.db.commit()
	return si.name


def _seed_ffm(sales_invoice: str, status: str = "BORRADOR") -> str:
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"naming_series": "FFM-TEST-.YYYY.-",
			"sales_invoice": sales_invoice,
			"status": status,
			"fm_tipo_comprobante": "I",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"docstatus": 1,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	frappe.db.commit()
	return ffm.name


class TestWriterTimbradoUUID(IntegrationTestCase):
	def setUp(self):
		self.si_names = []
		self.ffm_names = []
		self.writer = PACResponseWriter()
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		for ffm in self.ffm_names:
			frappe.db.delete("FacturAPI Response Log", {"factura_fiscal_mexico": ffm})
			frappe.db.delete("Factura Fiscal Mexico", {"name": ffm})
		for si in self.si_names:
			frappe.db.delete("Sales Invoice", {"name": si})
		frappe.db.commit()

	def _si(self):
		name = _seed_si()
		self.si_names.append(name)
		return name

	def _ffm(self, si, status="BORRADOR"):
		name = _seed_ffm(si, status)
		self.ffm_names.append(name)
		return name

	def _ffm_row(self, ffm):
		return frappe.db.get_value(
			"Factura Fiscal Mexico",
			ffm,
			["status", "fm_uuid", "facturapi_id", "fm_sync_status"],
			as_dict=True,
		)

	# 1 — timbrado exitoso con UUID a nivel superior
	def test_01_uuid_top_level_deja_timbrado(self):
		si = self._si()
		ffm = self._ffm(si)
		self.writer.write_pac_response(
			si,
			{"req": 1},
			{"success": True, "status_code": 200, "uuid": "UUID-TOP"},
			"timbrado",
			factura_fiscal_name=ffm,
		)
		d = self._ffm_row(ffm)
		self.assertEqual(d["status"], "TIMBRADO")
		self.assertEqual(d["fm_uuid"], "UUID-TOP")
		self.assertEqual(d["fm_sync_status"], "synced")

	# 2 — timbrado exitoso con UUID SOLO dentro de raw_response (el caso real)
	def test_02_uuid_en_raw_response_deja_timbrado_nunca_error(self):
		si = self._si()
		ffm = self._ffm(si)
		self.writer.write_pac_response(
			si,
			{"req": 1},
			{"success": True, "status_code": 200, "raw_response": {"uuid": "UUID-RAW", "id": "FA-RAW"}},
			"timbrado",
			factura_fiscal_name=ffm,
		)
		d = self._ffm_row(ffm)
		self.assertEqual(d["status"], "TIMBRADO", "Nunca debe quedar ERROR en un timbrado exitoso")
		self.assertEqual(d["fm_uuid"], "UUID-RAW")
		self.assertEqual(d["fm_sync_status"], "synced")

	# 3 — facturapi_id dentro de raw_response queda guardado
	def test_03_facturapi_id_en_raw_response_se_guarda(self):
		si = self._si()
		ffm = self._ffm(si)
		self.writer.write_pac_response(
			si,
			{"req": 1},
			{"success": True, "status_code": 200, "raw_response": {"uuid": "UUID-RAW", "id": "FA-123"}},
			"timbrado",
			factura_fiscal_name=ffm,
		)
		d = self._ffm_row(ffm)
		self.assertEqual(d["facturapi_id"], "FA-123")
		self.assertEqual(d["status"], "TIMBRADO")

	# 4 — éxito declarado pero SIN UUID en ningún nivel: comportamiento seguro documentado.
	#     Se mantiene el comportamiento existente: NO marca TIMBRADO (deriva ERROR). No se
	#     inventa UUID ni se presenta como éxito limpio.
	def test_04_sin_uuid_no_marca_timbrado(self):
		si = self._si()
		ffm = self._ffm(si)
		self.writer.write_pac_response(
			si,
			{"req": 1},
			{"success": True, "status_code": 200, "raw_response": {}},
			"timbrado",
			factura_fiscal_name=ffm,
		)
		d = self._ffm_row(ffm)
		self.assertNotEqual(d["status"], "TIMBRADO")
		self.assertEqual(d["status"], "ERROR")  # comportamiento seguro existente, documentado
		self.assertFalse(d["fm_uuid"])

	# 5 — si la FASE 3 NO se ejecuta, el estado dejado por el writer ya es correcto.
	#     (Se invoca SOLO write_pac_response, sin la FASE 3 del orquestador.)
	def test_05_estado_correcto_sin_fase3(self):
		si = self._si()
		ffm = self._ffm(si)
		self.writer.write_pac_response(
			si,
			{"req": 1},
			{"success": True, "status_code": 200, "raw_response": {"uuid": "UUID-RAW", "id": "FA-RAW"}},
			"timbrado",
			factura_fiscal_name=ffm,
		)
		# Sin ejecutar nada más, el FFM ya es fiscalmente correcto.
		d = self._ffm_row(ffm)
		self.assertEqual(d["status"], "TIMBRADO")
		self.assertEqual(d["fm_uuid"], "UUID-RAW")
		self.assertEqual(d["facturapi_id"], "FA-RAW")

	# 6 — la FASE 3 posterior NO degrada el TIMBRADO ya correcto.
	def test_06_fase3_posterior_no_degrada_timbrado(self):
		si = self._si()
		ffm = self._ffm(si)
		pac_response = {"uuid": "UUID-RAW", "id": "FA-RAW", "total": 116}
		self.writer.write_pac_response(
			si,
			{"req": 1},
			{"success": True, "status_code": 200, "raw_response": pac_response},
			"timbrado",
			factura_fiscal_name=ffm,
		)
		self.assertEqual(self._ffm_row(ffm)["status"], "TIMBRADO")

		# Ejecutar la FASE 3 real con sus boundaries de IO neutralizados.
		from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI

		si_doc = frappe.get_doc("Sales Invoice", si)
		ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm)

		# Neutralizar SOLO la escritura sobre la Sales Invoice mínima (validación mandatory);
		# la escritura sobre el FFM (lo que se prueba) se deja real.
		_orig_set_value = frappe.set_value

		def _set_value_si_noop(dt, dn, *args, **kwargs):
			if dt == "Sales Invoice":
				return None
			return _orig_set_value(dt, dn, *args, **kwargs)

		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=MagicMock()):
			api = TimbradoAPI(company="_Test Company")
			with (
				patch.object(TimbradoAPI, "_validate_amount_discrepancies"),
				patch.object(TimbradoAPI, "_download_fiscal_files"),
				patch.object(TimbradoAPI, "_send_fiscal_email"),
				patch("frappe.set_value", side_effect=_set_value_si_noop),
			):
				api._process_timbrado_success(si_doc, ffm_doc, pac_response)

		# Sigue TIMBRADO (la FASE 3 no lo cambió a un estado incorrecto).
		self.assertEqual(self._ffm_row(ffm)["status"], "TIMBRADO")
		self.assertEqual(self._ffm_row(ffm)["fm_uuid"], "UUID-RAW")

	# 7 — cancelación y consulta conservan su semántica (no cambian status vía el writer)
	def test_07_cancelacion_y_consulta_sin_cambio_de_semantica(self):
		# Cancelación: el raw del PAC no trae "success" → ok=False → new_status=None → el writer
		# NO cambia el status (lo fija la FASE 3). Se incluye status_code para no depender del
		# parser de error (comportamiento de cancelación sin cambios en esta corrección).
		si_c = self._si()
		ffm_c = self._ffm(si_c, status="TIMBRADO")
		self.writer.write_pac_response(
			si_c,
			{"req": 1},
			{"status_code": 200, "raw_response": {"status": "canceled"}},
			"cancelacion",
			factura_fiscal_name=ffm_c,
		)
		self.assertEqual(self._ffm_row(ffm_c)["status"], "TIMBRADO")  # el writer NO lo cambió

		# Consulta: tampoco cambia el status vía el writer.
		si_q = self._si()
		ffm_q = self._ffm(si_q, status="PENDIENTE_CANCELACION")
		self.writer.write_pac_response(
			si_q,
			{"req": 1},
			{"success": True, "status_code": 200, "raw_response": {"status": "pending"}},
			"consulta",
			factura_fiscal_name=ffm_q,
		)
		self.assertEqual(self._ffm_row(ffm_q)["status"], "PENDIENTE_CANCELACION")

	# 9 — cero referencias al cliente del PAC en este módulo
	def test_09_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "requests", "get_facturapi_client"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
