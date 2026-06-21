"""Correlación estricta por FFM.name en la persistencia de respuestas PAC.

Corrección 1 (integridad fiscal): la respuesta del PAC se asocia EXCLUSIVAMENTE
al FFM que inició la operación, nunca se resuelve por Sales Invoice. Estas pruebas
ejercen la capa de persistencia (`PACResponseWriter`) con respuestas SIMULADAS —
no hay ninguna llamada al PAC ni red fiscal.

Cobertura:
1. Timbrado simulado se aplica al FFM explícito aunque existan 2 FFM para la misma SI.
2. Cancelación simulada se aplica al FFM explícito.
3. El Response Log queda vinculado al mismo FFM.
4. El otro FFM de la misma SI permanece sin cambios.
5. FFM.name inexistente → no modifica, error controlado.
6. FFM de otra SI → no modifica, error controlado.
7. UUID contradictorio → no modifica, alerta.
8. facturapi_id contradictorio → no modifica, alerta.
9. (estático) el flujo no resuelve el FFM por {"sales_invoice"}.
10. Ninguna prueba llama a FacturAPI (no se instancia ni se parchea cliente HTTP).
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.api import (
	FiscalCorrelationError,
	PACResponseWriter,
)


def _make_ffm(sales_invoice: str, *, status: str = "BORRADOR", uuid: str = "", facturapi_id: str = "") -> str:
	"""Crea un FFM de prueba sin pasar por validaciones ni links (sin tocar el PAC)."""
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"naming_series": "FFM-TEST-.YYYY.-",
			"sales_invoice": sales_invoice,
			"status": status,
			"fm_tipo_comprobante": "I",
			"company": frappe.defaults.get_global_default("company") or "_Test Company",
			"fm_uuid": uuid or None,
			"facturapi_id": facturapi_id or None,
			"docstatus": 1,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	return ffm.name


def _timbrado_response(uuid: str = "TEST-UUID-A", facturapi_id: str = "facturapi-A") -> dict:
	return {
		"success": True,
		"status_code": 200,
		"uuid": uuid,
		"raw_response": {"uuid": uuid, "id": facturapi_id, "total": 100},
	}


def _cancelacion_response() -> dict:
	return {"success": True, "status_code": 200, "raw_response": {"status": "canceled"}}


class TestPACResponseCorrelacion(IntegrationTestCase):
	def setUp(self):
		self.si = "TEST-SI-" + frappe.generate_hash()[:8]
		self.ffm_names = []
		self.writer = PACResponseWriter()
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		for name in self.ffm_names:
			frappe.db.delete("FacturAPI Response Log", {"factura_fiscal_mexico": name})
			frappe.db.delete("Factura Fiscal Mexico", {"name": name})
		frappe.db.commit()

	def _ffm(self, **kwargs):
		name = _make_ffm(self.si, **kwargs)
		self.ffm_names.append(name)
		return name

	# 1 + 3 + 4
	def test_timbrado_se_aplica_al_ffm_explicito_con_dos_ffm(self):
		ffm_a = self._ffm(status="BORRADOR")  # el que opera
		ffm_b = self._ffm(status="BORRADOR")  # el otro, debe quedar intacto

		result = self.writer.write_pac_response(
			self.si, {"req": 1}, _timbrado_response(), "timbrado", factura_fiscal_name=ffm_a
		)
		self.assertTrue(result["success"])

		# Estado aplicado SOLO al FFM explícito (ffm_a)
		a = frappe.db.get_value(
			"Factura Fiscal Mexico", ffm_a, ["status", "fm_uuid", "fm_sync_status"], as_dict=True
		)
		self.assertEqual(a["status"], "TIMBRADO")
		self.assertEqual(a["fm_uuid"], "TEST-UUID-A")
		self.assertEqual(a["fm_sync_status"], "synced")

		# Response Log vinculado a ffm_a, no a ffm_b
		log_ffm = frappe.db.get_value(
			"FacturAPI Response Log", result["response_log_name"], "factura_fiscal_mexico"
		)
		self.assertEqual(log_ffm, ffm_a)

		# ffm_b permanece sin cambios
		b = frappe.db.get_value(
			"Factura Fiscal Mexico", ffm_b, ["status", "fm_uuid", "fm_sync_status"], as_dict=True
		)
		self.assertEqual(b["status"], "BORRADOR")
		self.assertFalse(b["fm_uuid"])
		# El otro FFM no fue tocado por el writer: nunca quedó 'synced'.
		self.assertNotEqual(b["fm_sync_status"], "synced")
		self.assertEqual(frappe.db.count("FacturAPI Response Log", {"factura_fiscal_mexico": ffm_b}), 0)

	# 2
	def test_cancelacion_se_aplica_al_ffm_explicito(self):
		ffm_a = self._ffm(status="TIMBRADO", uuid="UUID-A", facturapi_id="fa-A")
		ffm_b = self._ffm(status="TIMBRADO", uuid="UUID-B", facturapi_id="fa-B")

		result = self.writer.write_pac_response(
			self.si, {"req": 1}, _cancelacion_response(), "cancelacion", factura_fiscal_name=ffm_a
		)
		self.assertTrue(result["success"])
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm_a, "status"), "CANCELADO")
		# ffm_b intacto
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm_b, "status"), "TIMBRADO")

	# 5
	def test_ffm_inexistente_no_modifica_y_error_controlado(self):
		ffm_a = self._ffm(status="BORRADOR")
		with self.assertRaises(FiscalCorrelationError):
			self.writer.write_pac_response(
				self.si,
				{"req": 1},
				_timbrado_response(),
				"timbrado",
				factura_fiscal_name="FFM-NO-EXISTE-XYZ",
			)
		# Nada cambió en el FFM real
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm_a, "status"), "BORRADOR")

	# 5b — sin factura_fiscal_name
	def test_sin_factura_fiscal_name_no_modifica_y_error_controlado(self):
		ffm_a = self._ffm(status="BORRADOR")
		with self.assertRaises(FiscalCorrelationError):
			self.writer.write_pac_response(
				self.si, {"req": 1}, _timbrado_response(), "timbrado", factura_fiscal_name=None
			)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm_a, "status"), "BORRADOR")

	# 6
	def test_ffm_de_otra_si_no_modifica_y_error_controlado(self):
		ffm_a = self._ffm(status="BORRADOR")
		with self.assertRaises(FiscalCorrelationError):
			self.writer.write_pac_response(
				"OTRA-SI-DISTINTA",
				{"req": 1},
				_timbrado_response(),
				"timbrado",
				factura_fiscal_name=ffm_a,
			)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm_a, "status"), "BORRADOR")

	# 7
	def test_uuid_contradictorio_no_modifica_y_alerta(self):
		ffm_a = self._ffm(status="TIMBRADO", uuid="UUID-EXISTENTE", facturapi_id="fa-A")
		with self.assertRaises(FiscalCorrelationError):
			self.writer.write_pac_response(
				self.si,
				{"req": 1},
				_timbrado_response(uuid="UUID-DIFERENTE", facturapi_id="fa-A"),
				"timbrado",
				factura_fiscal_name=ffm_a,
			)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm_a, "fm_uuid"), "UUID-EXISTENTE")

	# 8
	def test_facturapi_id_contradictorio_no_modifica_y_alerta(self):
		ffm_a = self._ffm(status="TIMBRADO", uuid="UUID-A", facturapi_id="fa-EXISTENTE")
		with self.assertRaises(FiscalCorrelationError):
			self.writer.write_pac_response(
				self.si,
				{"req": 1},
				_timbrado_response(uuid="UUID-A", facturapi_id="fa-DIFERENTE"),
				"timbrado",
				factura_fiscal_name=ffm_a,
			)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm_a, "facturapi_id"), "fa-EXISTENTE")

	# 9 — estático: la persistencia no resuelve el FFM por sales_invoice
	def test_persistencia_no_busca_ffm_por_sales_invoice(self):
		import inspect

		from facturacion_mexico.facturacion_fiscal import api as api_mod

		src = inspect.getsource(api_mod.PACResponseWriter._write_to_database)
		src += inspect.getsource(api_mod.PACResponseWriter._update_factura_fiscal)
		self.assertNotIn(
			'{"sales_invoice"',
			src,
			"La persistencia no debe resolver el FFM por {'sales_invoice': ...}",
		)

	# 10 — ninguna prueba usa el cliente FacturAPI
	def test_ninguna_llamada_al_pac(self):
		"""El namespace de este módulo no contiene símbolos del cliente HTTP del PAC.

		La capa probada (PACResponseWriter) trabaja solo con dicts simulados; no se
		importa, instancia ni parchea ningún cliente FacturAPI.
		"""
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "cancel_invoice", "requests"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
