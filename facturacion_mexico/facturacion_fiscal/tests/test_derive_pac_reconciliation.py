"""Helper único de mapeo PAC -> (estado_fiscal, fm_sync_status) y su unificación (Paso 1 del motor).

`derive_pac_reconciliation` es la ÚNICA fuente de verdad del mapeo de respuestas de cancelación,
consumida por: cancelar_factura FASE 3, revisar_estatus_cancelacion y (después) el motor.

Decisiones fijadas:
- accepted -> CANCELADO (con o sin `status`), conserva el comportamiento productivo y test_06.
- expired  -> TIMBRADO (nuevo, unificado en los tres flujos; antes caía a PENDIENTE_CANCELACION).

Matriz del helper SIN red ni BD. Las dos pruebas de flujo mockean el boundary del PAC. Cero PAC real.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.config.fiscal_states_config import FiscalStates, SyncStates, derive_pac_reconciliation
from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI, revisar_estatus_cancelacion

_TIMBRADO_API = "facturacion_mexico.facturacion_fiscal.timbrado_api"


class TestDerivePacReconciliation(IntegrationTestCase):
	"""Matriz pura del helper (sin red ni BD)."""

	def _assert(self, remote, cancel, estado, sync):
		self.assertEqual(derive_pac_reconciliation(remote, cancel), (estado, sync))

	# --- canceled / accepted -> CANCELADO ---
	def test_canceled_cualquiera(self):
		self._assert("canceled", "", FiscalStates.CANCELADO, SyncStates.SYNCED)
		self._assert("canceled", "accepted", FiscalStates.CANCELADO, SyncStates.SYNCED)

	# Precedencia: un CFDI `canceled` manda sobre un cancellation_status contradictorio.
	def test_canceled_precede_a_cancellation_contradictoria(self):
		self._assert("canceled", "rejected", FiscalStates.CANCELADO, SyncStates.SYNCED)
		self._assert("canceled", "expired", FiscalStates.CANCELADO, SyncStates.SYNCED)
		self._assert("canceled", "pending", FiscalStates.CANCELADO, SyncStates.SYNCED)

	def test_accepted_sin_status(self):
		# Caso de query_pac_status / test_06: accepted sin `status` sigue siendo CANCELADO.
		self._assert("", "accepted", FiscalStates.CANCELADO, SyncStates.SYNCED)

	def test_accepted_con_valid(self):
		self._assert("valid", "accepted", FiscalStates.CANCELADO, SyncStates.SYNCED)

	# --- valid + cancellation ---
	def test_valid_pending(self):
		self._assert("valid", "pending", FiscalStates.PENDIENTE_CANCELACION, SyncStates.SYNCED)

	def test_valid_verifying(self):
		self._assert("valid", "verifying", FiscalStates.PENDIENTE_CANCELACION, SyncStates.SYNCED)

	def test_valid_rejected(self):
		self._assert("valid", "rejected", FiscalStates.TIMBRADO, SyncStates.SYNCED)

	def test_valid_expired(self):
		# NUEVO comportamiento unificado.
		self._assert("valid", "expired", FiscalStates.TIMBRADO, SyncStates.SYNCED)

	def test_valid_none_o_vacio(self):
		self._assert("valid", "none", FiscalStates.TIMBRADO, SyncStates.SYNCED)
		self._assert("valid", "", FiscalStates.TIMBRADO, SyncStates.SYNCED)

	# --- no definitivo / error ---
	def test_remote_pending(self):
		self._assert("pending", "", None, SyncStates.PENDING)

	def test_draft_desconocido(self):
		self._assert("draft", "", None, SyncStates.ERROR)
		self._assert("loquesea", "", None, SyncStates.ERROR)

	def test_valid_cancellation_desconocida(self):
		self._assert("valid", "no_existe", None, SyncStates.ERROR)

	# --- normalización ---
	def test_normaliza_mayusculas_y_espacios(self):
		self._assert("  CANCELED ", "", FiscalStates.CANCELADO, SyncStates.SYNCED)
		self._assert("Valid", "EXPIRED", FiscalStates.TIMBRADO, SyncStates.SYNCED)
		self._assert(None, None, None, SyncStates.ERROR)


# Identidades fiscales únicas por corrida (evita colisiones con registros residuales y cumple la
# regla de IDs generados).
_FA_ID = "FA-" + frappe.generate_hash()[:10]
_UUID = "U-" + frappe.generate_hash()[:10]


def _seed_si(*, fiscal_status="", ffm=None):
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"net_total": 100,
			"grand_total": 116,
			"posting_date": frappe.utils.today(),
			"docstatus": 1,
			"fm_fiscal_status": fiscal_status or None,
			"fm_factura_fiscal_mx": ffm,
		}
	)
	si.flags.ignore_validate = True
	si.flags.ignore_mandatory = True
	si.flags.ignore_links = True
	si.db_insert()
	frappe.db.commit()
	return si.name


def _seed_ffm(sales_invoice, status, *, facturapi_id="", uuid=""):
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"naming_series": "FFM-TEST-.YYYY.-",
			"sales_invoice": sales_invoice,
			"status": status,
			"fm_tipo_comprobante": "I",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"facturapi_id": facturapi_id or None,
			"fm_uuid": uuid or None,
			"docstatus": 1,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	frappe.db.commit()
	return ffm.name


def _set_value_factory():
	orig = frappe.set_value

	def _fake(dt, dn, *args, **kwargs):
		if dt == "Sales Invoice":
			return None
		if dt == "Factura Fiscal Mexico":
			return frappe.db.set_value(dt, dn, *args, **kwargs)
		return orig(dt, dn, *args, **kwargs)

	return _fake


class TestExpiredUnificado(IntegrationTestCase):
	"""expired -> TIMBRADO en los flujos reales de cancelación (boundary PAC mockeado)."""

	def setUp(self):
		self.si_names = []
		self.ffm_names = []
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		for ffm in self.ffm_names:
			frappe.db.delete("FacturAPI Response Log", {"factura_fiscal_mexico": ffm})
			frappe.db.delete("Factura Fiscal Mexico", {"name": ffm})
		for si in self.si_names:
			frappe.db.delete("Sales Invoice", {"name": si})
		frappe.db.commit()

	def _si(self, **kwargs):
		name = _seed_si(**kwargs)
		self.si_names.append(name)
		return name

	def _ffm(self, *args, **kwargs):
		name = _seed_ffm(*args, **kwargs)
		self.ffm_names.append(name)
		return name

	# FASE 3 de cancelar_factura: una cancelación EXPIRED deja el FFM en TIMBRADO (antes PENDIENTE).
	def test_fase3_expired_timbrado(self):
		ffm = self._ffm(None, "TIMBRADO", facturapi_id=_FA_ID, uuid=_UUID)
		si = self._si(fiscal_status="TIMBRADO", ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		frappe.db.commit()
		client = MagicMock()
		client.cancel_invoice.return_value = {
			"success": True,
			"raw_response": {"status": "valid", "cancellation_status": "expired"},
		}
		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			with (
				patch("frappe.set_value", side_effect=_set_value_factory()),
				patch(f"{_TIMBRADO_API}.write_pac_response", return_value={"success": True}),
			):
				api.cancelar_factura(si, "02")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")

	# Consolidación: revisar delega en reconcile_ffm; la clasificación expired→TIMBRADO la cubre el
	# clasificador acotado (y el motor). revisar no realiza una 2ª consulta al PAC.
	def test_revisar_delega_en_motor(self):
		ffm = self._ffm(self._si(), "PENDIENTE_CANCELACION", facturapi_id=_FA_ID, uuid=_UUID)
		with (
			patch(
				"facturacion_mexico.facturacion_fiscal.services.ffm_reconciliation.reconcile_ffm",
				return_value={"ffm": ffm, "outcome": "changed"},
			) as rec,
			patch("facturacion_mexico.facturacion_fiscal.api_client.query_pac_status") as qps,
		):
			out = revisar_estatus_cancelacion(ffm)
		rec.assert_called_once_with(ffm)
		qps.assert_not_called()
		self.assertEqual(out, {"ffm": ffm, "outcome": "changed"})

	# cero referencias al cliente PAC importadas en el módulo de prueba
	def test_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "requests", "get_facturapi_client"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
