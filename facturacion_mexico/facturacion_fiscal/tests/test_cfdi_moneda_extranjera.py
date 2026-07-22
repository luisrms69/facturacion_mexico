"""Moneda del CFDI (currency/exchange) en el payload FacturAPI.

Cambio bajo prueba: el payload declara `currency` y `exchange` derivados de la Sales Invoice, y los
importes de los conceptos van en la moneda de la transacción (`net_rate`), nunca en `base_*`.

Dos niveles:
  1. `resolve_cfdi_currency_exchange` (la regla, sin DB).
  2. Payload real construido por `_prepare_facturapi_data` (MXN y USD sobre una empresa base MXN),
     que falla si alguien deja de poner `currency`/`exchange` o usa `base_net_rate`.

`get_facturapi_client` se parchea; no hay llamadas de red.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.facturacion_fiscal.timbrado_api import (
	TimbradoAPI,
	resolve_cfdi_currency_exchange,
)


class TestResolveCurrencyExchange(FrappeTestCase):
	"""La regla currency/exchange, aislada (sin empresa → sin guard de base)."""

	def test_mxn_exchange_1(self):
		self.assertEqual(
			resolve_cfdi_currency_exchange(frappe._dict(currency="MXN", conversion_rate=1.0)), ("MXN", 1.0)
		)

	def test_mxn_ignora_conversion_rate(self):
		self.assertEqual(
			resolve_cfdi_currency_exchange(frappe._dict(currency="MXN", conversion_rate=17.5)), ("MXN", 1.0)
		)

	def test_sin_currency_default_mxn(self):
		self.assertEqual(
			resolve_cfdi_currency_exchange(frappe._dict(currency=None, conversion_rate=1.0)), ("MXN", 1.0)
		)

	def test_usd_usa_conversion_rate(self):
		self.assertEqual(
			resolve_cfdi_currency_exchange(frappe._dict(name="SI-X", currency="USD", conversion_rate=17.5)),
			("USD", 17.5),
		)

	def test_currency_se_normaliza_mayusculas(self):
		self.assertEqual(
			resolve_cfdi_currency_exchange(frappe._dict(name="SI-Y", currency="usd", conversion_rate=18.0)),
			("USD", 18.0),
		)

	def test_usd_exchange_1_es_valido(self):
		# No se infiere que 1 sea imposible para una divisa: se acepta si es un tipo de cambio real.
		self.assertEqual(
			resolve_cfdi_currency_exchange(frappe._dict(name="SI-P", currency="USD", conversion_rate=1.0)),
			("USD", 1.0),
		)

	def test_usd_sin_tipo_cambio_falla(self):
		for bad in (0, -3):
			with self.assertRaises(frappe.ValidationError):
				resolve_cfdi_currency_exchange(frappe._dict(name="SI-Z", currency="USD", conversion_rate=bad))

	def test_guard_empresa_base_no_mxn(self):
		# `_Test Company` es base INR → emitir en divisa se bloquea (suposición explícita).
		base = frappe.db.get_value("Company", "_Test Company", "default_currency")
		self.assertNotEqual(base, "MXN")  # sanity del entorno de test
		with self.assertRaises(frappe.ValidationError):
			resolve_cfdi_currency_exchange(
				frappe._dict(name="SI-Q", currency="USD", conversion_rate=17.5, company="_Test Company")
			)


class TestPayloadMoneda(FrappeTestCase):
	"""Payload real de `_prepare_facturapi_data` sobre una empresa base MXN."""

	MXN_COMPANY = "_Test FM MXN"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._patcher = patch(
			"facturacion_mexico.facturacion_fiscal.timbrado_api.get_facturapi_client",
			return_value=MagicMock(),
		)
		cls._patcher.start()
		if not frappe.db.exists("Company", cls.MXN_COMPANY):
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": cls.MXN_COMPANY,
					"abbr": "TFMMXN",
					"default_currency": "MXN",
					"country": "Mexico",
				}
			).insert(ignore_permissions=True)
			# La empresa recién creada necesita Round Off configurado para poder submitear SIs.
			co = cls.MXN_COMPANY
			roa = frappe.db.get_value(
				"Account", {"company": co, "account_name": ["like", "Round Off%"], "is_group": 0}, "name"
			) or frappe.db.get_value(
				"Account", {"company": co, "root_type": "Expense", "is_group": 0}, "name"
			)
			roc = frappe.db.get_value("Cost Center", {"company": co, "is_group": 0}, "name")
			frappe.db.set_value("Company", co, {"round_off_account": roa, "round_off_cost_center": roc})
			frappe.db.commit()  # nosemgrep: frappe-manual-commit

	@classmethod
	def tearDownClass(cls):
		cls._patcher.stop()
		# Limpieza dura de la empresa de prueba y TODO lo que cuelga de ella (evita cuentas huérfanas
		# que contaminarían otras suites que buscan "la primera cuenta Receivable"). frappe.db.delete
		# usa DELETE directo → sin problemas de jerarquía de cuentas.
		try:
			for dt in ("Account", "Cost Center", "Warehouse"):
				frappe.db.delete(dt, {"company": cls.MXN_COMPANY})
			frappe.db.delete("Company", {"name": cls.MXN_COMPANY})
			frappe.db.commit()  # nosemgrep: frappe-manual-commit
		except Exception:
			frappe.db.rollback()
		super().tearDownClass()

	def setUp(self):
		self.h = frappe.generate_hash()[:6]
		self.company = self.MXN_COMPANY
		self.debit_to = frappe.db.get_value(
			"Account",
			{"company": self.company, "account_type": "Receivable", "account_currency": "MXN", "is_group": 0},
			"name",
		) or frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Receivable", "is_group": 0}, "name"
		)
		# ERPNext exige que la moneda del debit_to coincida con la del documento → cuenta Receivable USD.
		self.debit_to_usd = frappe.db.get_value(
			"Account",
			{"company": self.company, "account_type": "Receivable", "account_currency": "USD", "is_group": 0},
			"name",
		)
		if not self.debit_to_usd:
			parent = frappe.db.get_value("Account", self.debit_to, "parent_account")
			self.debit_to_usd = (
				frappe.get_doc(
					{
						"doctype": "Account",
						"account_name": "Debtors USD",
						"parent_account": parent,
						"company": self.company,
						"account_type": "Receivable",
						"account_currency": "USD",
						"is_group": 0,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		self.income_acc = frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Income", "is_group": 0}, "name"
		)
		self.cc = frappe.db.get_value("Cost Center", {"is_group": 0, "company": self.company}, "name")
		self.cg = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		self.terr = frappe.db.get_value("Territory", {"is_group": 0}, "name")

		# Clave SAT ObjetoImp=01 (no objeto de impuesto) → payload sin impuestos, mínimo para el builder.
		# `codigo` debe ser numérico.
		self.clave_sat = str(int(self.h, 16))[-8:].zfill(8)
		if not frappe.db.exists("SAT Producto Servicio", {"codigo": self.clave_sat}):
			frappe.get_doc(
				{
					"doctype": "SAT Producto Servicio",
					"codigo": self.clave_sat,
					"descripcion": f"Test 01 {self.h}",
					"incluye_objeto_impuesto": "01",
				}
			).insert(ignore_permissions=True)
		self.sat_name = frappe.db.get_value("SAT Producto Servicio", {"codigo": self.clave_sat}, "name")

		# UOM con clave SAT válida (c_ClaveUnidad H87 = Pieza), exigida por el builder del CFDI.
		if not frappe.db.exists("UOM", "H87"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "H87"}).insert(ignore_permissions=True)

		self.item = f"FM-CUR-{self.h}"
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
					"stock_uom": "H87",
					"is_stock_item": 0,
					"is_sales_item": 1,
					"fm_producto_servicio_sat": self.sat_name,
				}
			).insert(ignore_permissions=True)

		self.uso_cfdi = frappe.db.get_value("Uso CFDI SAT", "G03", "name") or frappe.db.get_value(
			"Uso CFDI SAT", {}, "name"
		)
		# fm_forma_pago_timbrado debe empezar con el código SAT de 2 dígitos (ej. "01 Efectivo").
		self.forma_pago = frappe.db.get_value(
			"Mode of Payment", "01 Efectivo", "name"
		) or frappe.db.get_value("Mode of Payment", {"name": ["like", "0%"]}, "name")

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
		# Dirección primaria (el builder exige CP del receptor).
		frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": f"CLI-{self.h}",
				"address_type": "Billing",
				"address_line1": "Calle Falsa 123",
				"city": "CDMX",
				"pincode": "01000",
				"country": "Mexico",
				"is_primary_address": 1,
				"links": [{"link_doctype": "Customer", "link_name": self.customer.name}],
			}
		).insert(ignore_permissions=True)
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

	def _mk_si(self, currency, conversion_rate, company=None):
		debit_to = self.debit_to if currency == "MXN" else self.debit_to_usd
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": company or self.company,
				"customer": self.customer.name,
				"currency": currency,
				"conversion_rate": conversion_rate,
				"cost_center": self.cc,
				"debit_to": debit_to,
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
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			get_or_create_active_ffm,
		)

		ffm_name = get_or_create_active_ffm(si_name)
		ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		if not ffm.get("fm_cfdi_use") and self.uso_cfdi:
			ffm.fm_cfdi_use = self.uso_cfdi
		if not ffm.get("fm_tax_system"):
			ffm.fm_tax_system = "601"
		if self.forma_pago:
			ffm.fm_forma_pago_timbrado = self.forma_pago
		ffm.fm_payment_method_sat = "PUE"
		ffm.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		self._ffms.append(ffm_name)
		return ffm_name

	def _build_payload(self, si_name):
		si = frappe.get_doc("Sales Invoice", si_name)
		ffm = frappe.get_doc("Factura Fiscal Mexico", self._ffms[-1])
		api = TimbradoAPI(company=si.company)  # get_facturapi_client parcheado (sin red)
		return api._prepare_facturapi_data(si, ffm), si

	# ---------------- MXN ----------------

	def test_payload_mxn(self):
		si_name = self._mk_si("MXN", 1.0)
		self._mk_ffm(si_name)
		payload, si = self._build_payload(si_name)
		self.assertEqual(payload["currency"], "MXN")
		self.assertEqual(payload["exchange"], 1.0)
		price = payload["items"][0]["product"]["price"]
		self.assertEqual(price, si.items[0].net_rate)

	# ---------------- USD (empresa base MXN) ----------------

	def test_payload_usd_no_usa_base(self):
		rate = 17.5
		si_name = self._mk_si("USD", rate)
		self._mk_ffm(si_name)
		payload, si = self._build_payload(si_name)
		self.assertEqual(payload["currency"], "USD")
		self.assertEqual(payload["exchange"], rate)
		price = payload["items"][0]["product"]["price"]
		# El precio permanece en USD (net_rate), NO en base_net_rate (MXN).
		self.assertEqual(price, si.items[0].net_rate)
		self.assertNotEqual(price, si.items[0].base_net_rate)
		self.assertEqual(si.items[0].base_net_rate, si.items[0].net_rate * rate)
