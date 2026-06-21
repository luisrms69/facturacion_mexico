"""Estado fiscal independiente del FacturAPI Response Log (Corrección 2).

Una respuesta exitosa del PAC debe actualizar y persistir el FFM ANTES e
independientemente del Response Log. Si el log falla, el estado fiscal ya
persistido se conserva; no hay rollback fiscal, ni reintento, ni degradación
a filesystem. Si la actualización del FFM falla, no se presenta como persistido
y no se crea el log.

Todas las pruebas usan respuestas SIMULADAS y parches locales — cero llamadas al
PAC y cero tráfico de red.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.api import (
	FiscalCorrelationError,
	PACResponseWriter,
)


def _make_ffm(sales_invoice: str, *, status: str = "BORRADOR", uuid: str = "", facturapi_id: str = "") -> str:
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
	frappe.db.commit()
	return ffm.name


def _timbrado_response() -> dict:
	return {
		"success": True,
		"status_code": 200,
		"uuid": "TEST-UUID-OK",
		"raw_response": {"uuid": "TEST-UUID-OK", "id": "fa-OK", "total": 100},
	}


class TestEstadoFiscalIndependienteLog(IntegrationTestCase):
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

	# 1 — éxito completo: FFM actualizado y log guardado
	def test_exito_completo_ffm_actualizado_y_log_guardado(self):
		ffm = self._ffm(status="BORRADOR", facturapi_id="fa-OK")
		result = self.writer.write_pac_response(
			self.si, {"req": 1}, _timbrado_response(), "timbrado", factura_fiscal_name=ffm
		)
		self.assertTrue(result["success"])
		self.assertTrue(result.get("fiscal_updated"))
		self.assertIsNotNone(result.get("response_log_name"))
		self.assertNotIn("audit_log_failed", result)

		d = frappe.db.get_value(
			"Factura Fiscal Mexico",
			ffm,
			["status", "fm_uuid", "facturapi_id", "fm_sync_status", "fm_last_response_log"],
			as_dict=True,
		)
		self.assertEqual(d["status"], "TIMBRADO")
		self.assertEqual(d["fm_uuid"], "TEST-UUID-OK")
		self.assertEqual(d["facturapi_id"], "fa-OK")
		self.assertEqual(d["fm_sync_status"], "synced")
		self.assertEqual(d["fm_last_response_log"], result["response_log_name"])

	# 2 — éxito fiscal + fallo del Response Log: estado fiscal se conserva
	def test_fallo_log_conserva_estado_fiscal(self):
		# facturapi_id igual al de la respuesta (sin contradicción de correlación);
		# se verifica que se conserva tras el fallo del log.
		ffm = self._ffm(status="PROCESANDO", facturapi_id="fa-OK")

		# Forzar fallo SOLO en la creación del Response Log (no en la actualización fiscal)
		with patch.object(PACResponseWriter, "_write_to_database", side_effect=RuntimeError("DB log caído")):
			result = self.writer.write_pac_response(
				self.si, {"req": 1}, _timbrado_response(), "timbrado", factura_fiscal_name=ffm
			)

		# La operación fiscal se procesó (no se relanza, no se revierte)
		self.assertTrue(result["success"])
		self.assertTrue(result.get("fiscal_updated"))
		self.assertTrue(result.get("audit_log_failed"))
		self.assertIsNone(result.get("response_log_name"))

		# El FFM conserva el estado fiscal confirmado
		d = frappe.db.get_value(
			"Factura Fiscal Mexico",
			ffm,
			["status", "fm_uuid", "facturapi_id", "fm_sync_status"],
			as_dict=True,
		)
		self.assertEqual(d["status"], "TIMBRADO")
		self.assertEqual(d["fm_uuid"], "TEST-UUID-OK")
		self.assertEqual(d["facturapi_id"], "fa-OK")  # facturapi_id no se pierde
		self.assertEqual(d["fm_sync_status"], "synced")  # sync cerrado, no queda pending

		# No se creó ningún Response Log para este FFM
		self.assertEqual(frappe.db.count("FacturAPI Response Log", {"factura_fiscal_mexico": ffm}), 0)

	# 3 — fallo de actualización del FFM: no se presenta como persistido, no se crea log
	def test_fallo_actualizacion_ffm_propaga_y_no_crea_log(self):
		ffm = self._ffm(status="BORRADOR")

		with patch.object(
			PACResponseWriter, "_update_factura_fiscal", side_effect=RuntimeError("update FFM caído")
		):
			with self.assertRaises(RuntimeError):
				self.writer.write_pac_response(
					self.si, {"req": 1}, _timbrado_response(), "timbrado", factura_fiscal_name=ffm
				)

		# No se creó Response Log: el fallo fiscal no se esconde guardando solo el log
		self.assertEqual(frappe.db.count("FacturAPI Response Log", {"factura_fiscal_mexico": ffm}), 0)

	# 4 — el fallo del log NO genera archivo de fallback en filesystem
	def test_fallo_log_no_genera_fallback_filesystem(self):
		from facturacion_mexico.facturacion_fiscal.api import _get_fallback_dir

		ffm = self._ffm(status="PROCESANDO")
		fallback_dir = _get_fallback_dir()
		import os

		antes = set(os.listdir(fallback_dir)) if os.path.isdir(fallback_dir) else set()

		with patch.object(PACResponseWriter, "_write_to_database", side_effect=RuntimeError("DB log caído")):
			result = self.writer.write_pac_response(
				self.si, {"req": 1}, _timbrado_response(), "timbrado", factura_fiscal_name=ffm
			)

		despues = set(os.listdir(fallback_dir)) if os.path.isdir(fallback_dir) else set()
		self.assertEqual(antes, despues, "El fallo del log no debe escribir archivos de fallback")
		self.assertTrue(result.get("audit_log_failed"))
		self.assertIsNone(result.get("fallback_file"))  # no hubo degradación a filesystem

	# 4b — refuerzo: el flujo NO invoca el escritor de filesystem aunque éste falle.
	#       Verifica que no hay ruta a /tmp ante fallo del log, sin tocar permisos reales.
	def test_flujo_no_invoca_escritor_filesystem(self):
		ffm = self._ffm(status="PROCESANDO", facturapi_id="fa-OK")

		# _write_to_filesystem montado para FALLAR si llega a invocarse (no debe).
		fs_mock = patch.object(
			PACResponseWriter,
			"_write_to_filesystem",
			side_effect=AssertionError("El flujo no debe intentar escribir en filesystem"),
		)
		# El log falla → debe aislarse, sin degradar a filesystem.
		# (no tocamos permisos reales de /tmp; solo simulamos el fallo del log)
		log_fail = patch.object(
			PACResponseWriter, "_write_to_database", side_effect=RuntimeError("DB log caído")
		)
		with fs_mock as fs_called, log_fail:
			result = self.writer.write_pac_response(
				self.si, {"req": 1}, _timbrado_response(), "timbrado", factura_fiscal_name=ffm
			)

		# El escritor de filesystem NUNCA se invocó
		self.assertEqual(fs_called.call_count, 0, "No debe intentarse escritura a filesystem")
		# FFM conserva el estado fiscal; auditoría marcada como fallida; sin excepción de permisos
		self.assertTrue(result.get("audit_log_failed"))
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_sync_status"), "synced")

	# 5 — la correlación estricta (Corrección 1) sigue vigente
	def test_correlacion_estricta_sigue_vigente(self):
		ffm = self._ffm(status="BORRADOR")
		with self.assertRaises(FiscalCorrelationError):
			self.writer.write_pac_response(
				"OTRA-SI", {"req": 1}, _timbrado_response(), "timbrado", factura_fiscal_name=ffm
			)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "BORRADOR")

	# 6 — cero referencias al cliente del PAC en este módulo
	def test_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "cancel_invoice", "requests"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
