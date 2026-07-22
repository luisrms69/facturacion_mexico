"""Regresión del fix "FFM nace en estado ERROR".

Bug: los eventos de ciclo de vida de la FFM (create/status_change) se escribían, vía fallback,
como respuestas PAC fallidas (success=0, operation_type mapeado a "Consulta Estado"), y
`calculate_fiscal_status_from_logs` marcaba ERROR ante CUALQUIER success=0. Resultado: toda FFM
nueva nacía en ERROR sin ninguna llamada a FacturAPI.

Fix:
  Capa 1 — se retiró el fallback (create_fiscal_event / _log_event_to_response_log); una FFM
           nueva ya no genera logs sintéticos success=0.
  Capa 2 — `calculate_fiscal_status_from_logs` deriva ERROR fiscal SOLO de un "Timbrado" fallido
           (consistente con la regla canónica por operación de api/__init__.py). Consulta,
           reconciliación y eventos sintéticos NO marcan ERROR.

No se mockea el PAC: no hay ninguna llamada externa en estos flujos (esa es la tesis del fix).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.config.fiscal_states_config import FiscalStates


class TestFFMNaceErrorFiscalEvent(FrappeTestCase):
	def setUp(self):
		self.h = frappe.generate_hash()[:6]
		self.debit_to = frappe.db.get_value(
			"Account", {"account_type": "Receivable", "is_group": 0}, ["name", "company"], as_dict=True
		)
		self.company = self.debit_to.company
		self.debit_to = self.debit_to.name
		self.si_currency = frappe.db.get_value(
			"Account", self.debit_to, "account_currency"
		) or frappe.db.get_value("Company", self.company, "default_currency")
		self.income_acc = frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Income", "is_group": 0}, "name"
		)
		self.cg = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		self.terr = frappe.db.get_value("Territory", {"is_group": 0}, "name")
		self.cc = frappe.db.get_value("Cost Center", {"is_group": 0, "company": self.company}, "name")

		self.item = f"FM-NACEERR-{self.h}"
		if not frappe.db.exists("Item", self.item):
			ig = frappe.db.get_value("Item Group", "Products", "name") or frappe.db.get_value(
				"Item Group", {"is_group": 0}, "name"
			)
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": self.item,
					"item_name": self.item,
					"item_group": ig,
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_sales_item": 1,
					"fm_producto_servicio_sat": "84111506",
				}
			).insert(ignore_permissions=True)

		self.uso_cfdi = frappe.db.get_value("Uso CFDI SAT", "G03", "name") or frappe.db.get_value(
			"Uso CFDI SAT", {}, "name"
		)
		self.forma_pago = frappe.db.get_value("Mode of Payment", {}, "name")

		self.customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": f"CLI-{self.h}",
				"customer_type": "Company",
				"customer_group": self.cg,
				"territory": self.terr,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value(
			"Customer",
			self.customer.name,
			{
				"tax_id": "XAXX010101000",
				"fm_rfc_validated": 1,
				"fm_uso_cfdi_default": "G03",
				"fm_tax_regime": "601",
			},
		)
		self._sis = []
		self._ffms = []

	def tearDown(self):
		super().tearDown()
		for ffm in self._ffms:
			frappe.db.delete("FacturAPI Response Log", {"factura_fiscal_mexico": ffm})
			frappe.db.delete("Factura Fiscal Mexico", {"name": ffm})
		for si in self._sis:
			frappe.db.delete("Sales Invoice Item", {"parent": si})
			frappe.db.delete("Sales Invoice", {"name": si})
		frappe.db.commit()  # nosemgrep: frappe-manual-commit

	# ---------------- helpers ----------------

	def _mk_si(self):
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": self.company,
				"customer": self.customer.name,
				"currency": self.si_currency,
				"cost_center": self.cc,
				"debit_to": self.debit_to,
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"rate": 100,
						"cost_center": self.cc,
						"income_account": self.income_acc,
					}
				],
			}
		)
		si.insert(ignore_permissions=True)
		si.submit()
		self._sis.append(si.name)
		return si.name

	def _mk_ffm(self, si_name):
		"""Crea la FFM por el flujo real (mismo path que la app)."""
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			get_or_create_active_ffm,
		)

		ffm_name = get_or_create_active_ffm(si_name)
		self._ffms.append(ffm_name)
		return ffm_name

	def _seed_log(self, ffm_name, operation_type, success, offset_secs=0):
		ts = frappe.utils.add_to_date(frappe.utils.now_datetime(), seconds=offset_secs)
		frappe.get_doc(
			{
				"doctype": "FacturAPI Response Log",
				"factura_fiscal_mexico": ffm_name,
				"operation_type": operation_type,
				"success": 1 if success else 0,
				"status_code": 200 if success else 400,
				"timestamp": ts,
				"facturapi_response": "{}",
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit

	def _recalc(self, ffm_name):
		ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		ffm.calculate_fiscal_status_from_logs()
		return frappe.db.get_value("Factura Fiscal Mexico", ffm_name, "status")

	# ---------------- Capa 1 ----------------

	def test_01_ffm_nueva_nace_borrador_sin_llamada_pac(self):
		"""FFM nueva → BORRADOR (no ERROR) y SIN logs sintéticos success=0."""
		si = self._mk_si()
		ffm = self._mk_ffm(si)

		status = frappe.db.get_value("Factura Fiscal Mexico", ffm, "status")
		self.assertEqual(status, FiscalStates.BORRADOR, "La FFM nueva debe nacer en BORRADOR, no en ERROR")

		# Capa 1: no se escribió ningún log sintético (fallback) ni respuesta PAC fallida.
		logs = frappe.get_all(
			"FacturAPI Response Log",
			filters={"factura_fiscal_mexico": ffm},
			fields=["operation_type", "success", "request_payload"],
		)
		self.assertFalse(
			[r for r in logs if not r.success],
			f"No debe existir ningún Response Log success=0 al crear la FFM; encontrados: {logs}",
		)
		self.assertFalse(
			[r for r in logs if "fiscal_event" in (r.request_payload or "")],
			"No debe existir ningún log 'fiscal_event_*' (fallback eliminado)",
		)

	# ---------------- Capa 2 ----------------

	def test_02_timbrado_fallido_marca_error(self):
		"""Un Timbrado realmente fallido SÍ deriva ERROR fiscal."""
		si = self._mk_si()
		ffm = self._mk_ffm(si)
		self._seed_log(ffm, "Timbrado", success=False)
		self.assertEqual(self._recalc(ffm), FiscalStates.ERROR)

	def test_03_timbrado_fallido_luego_exitoso_es_timbrado(self):
		"""Un éxito posterior prevalece sobre el ERROR."""
		si = self._mk_si()
		ffm = self._mk_ffm(si)
		self._seed_log(ffm, "Timbrado", success=False, offset_secs=0)
		self._seed_log(ffm, "Timbrado", success=True, offset_secs=5)
		self.assertEqual(self._recalc(ffm), FiscalStates.TIMBRADO)

	def test_04_consulta_estado_fallida_no_marca_error(self):
		"""Una 'Consulta Estado' success=0 (o evento sintético) NO debe marcar ERROR fiscal."""
		si = self._mk_si()
		ffm = self._mk_ffm(si)
		self._seed_log(ffm, "Consulta Estado", success=False)
		self.assertEqual(
			self._recalc(ffm),
			FiscalStates.BORRADOR,
			"Consulta/reconciliación fallida pertenece a fm_sync_status, no al estado fiscal",
		)

	def test_05_pendiente_cancelacion_intacto(self):
		"""Regresión: Timbrado OK + Solicitud Cancelación OK sin Confirmación → PENDIENTE_CANCELACION."""
		si = self._mk_si()
		ffm = self._mk_ffm(si)
		self._seed_log(ffm, "Timbrado", success=True, offset_secs=0)
		self._seed_log(ffm, "Solicitud Cancelación", success=True, offset_secs=5)
		self.assertEqual(self._recalc(ffm), FiscalStates.PENDIENTE_CANCELACION)
