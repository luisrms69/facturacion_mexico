"""
Tests de TaxResolver — arquitectura Configuracion CFDI Recibidos.

Crea y limpia fixtures reales en BD: Configuracion CFDI Recibidos + cuentas de impuesto.
"""

import unittest

import frappe
from frappe.utils import flt

from facturacion_mexico.cfdi_recibidos.services.tax_resolver import resolve_taxes

TEST_COMPANY = "_Test Company"
_H = frappe.generate_hash()[:6]


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------


def _get_or_create_tax_account(account_name: str, company: str) -> str:
	existing = frappe.db.get_value("Account", {"account_name": account_name, "company": company}, "name")
	if existing:
		return existing

	parent = frappe.db.get_value(
		"Account", {"account_type": "Tax", "is_group": 1, "company": company}, "name"
	) or frappe.db.get_value("Account", {"root_type": "Liability", "is_group": 1, "company": company}, "name")

	if not parent:
		frappe.throw(f"No hay cuenta padre disponible para crear cuentas de prueba en {company}")

	acc = frappe.new_doc("Account")
	acc.account_name = account_name
	acc.company = company
	acc.parent_account = parent
	acc.account_type = "Tax"
	acc.insert(ignore_permissions=True)
	frappe.db.commit()
	return acc.name


def _make_config(company: str, reglas: list, *, wizard_completado: bool = True) -> str:
	config_name = f"CFDI-REC-CFG-{company}"
	if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		frappe.delete_doc("Configuracion CFDI Recibidos", config_name, force=True)
	config = frappe.new_doc("Configuracion CFDI Recibidos")
	config.company = company
	config.wizard_completado = 1 if wizard_completado else 0
	for regla in reglas:
		config.append("reglas_impuesto", regla)
	config.insert(ignore_permissions=True, ignore_links=True)
	frappe.db.commit()
	return config_name


def _regla(impuesto_sat, tasa_cuota, descripcion, cuenta, *, es_retencion=False, tipo_factor="Tasa"):
	return {
		"impuesto_sat": impuesto_sat,
		"tipo_factor": tipo_factor,
		"tasa_cuota": tasa_cuota,
		"descripcion": descripcion,
		"es_retencion": 1 if es_retencion else 0,
		"cuenta_impuesto": cuenta,
		"activo": 1,
	}


def _delete_if_exists(doctype: str, name: str):
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True)
		frappe.db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTaxResolver(unittest.TestCase):
	"""Tests del TaxResolver — resolución XML impuesto → fila Purchase Invoice."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		cls.acc_iva_nac = _get_or_create_tax_account(f"_TR IVA Nac {_H}", TEST_COMPANY)
		cls.acc_iva_fro = _get_or_create_tax_account(f"_TR IVA Fro {_H}", TEST_COMPANY)
		cls.acc_iva_cero = _get_or_create_tax_account(f"_TR IVA Cero {_H}", TEST_COMPANY)
		cls.acc_ieps = _get_or_create_tax_account(f"_TR IEPS {_H}", TEST_COMPANY)
		cls.acc_ret_iva = _get_or_create_tax_account(f"_TR Ret IVA {_H}", TEST_COMPANY)
		cls.acc_ret_isr = _get_or_create_tax_account(f"_TR Ret ISR {_H}", TEST_COMPANY)
		cls.all_accounts = [
			cls.acc_iva_nac,
			cls.acc_iva_fro,
			cls.acc_iva_cero,
			cls.acc_ieps,
			cls.acc_ret_iva,
			cls.acc_ret_isr,
		]

		cls.config_name = _make_config(
			TEST_COMPANY,
			[
				_regla("002", 0.16, "IVA Acreditable (Nacional)", cls.acc_iva_nac),
				_regla("002", 0.08, "IVA Acreditable (Frontera)", cls.acc_iva_fro),
				_regla("002", 0.00, "IVA Acreditable (0% exportación)", cls.acc_iva_cero),
				_regla("003", 0.00, "IEPS Acreditable", cls.acc_ieps),
				_regla("002", 0.00, "IVA Retenido", cls.acc_ret_iva, es_retencion=True),
				_regla("001", 0.00, "ISR Retenido", cls.acc_ret_isr, es_retencion=True),
			],
		)

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("Configuracion CFDI Recibidos", cls.config_name)
		for acc in getattr(cls, "all_accounts", []):
			try:
				_delete_if_exists("Account", acc)
			except Exception:
				pass
		super().tearDownClass()

	# ------------------------------------------------------------------ #
	# Helper interno                                                        #
	# ------------------------------------------------------------------ #

	def _imp(self, impuesto, tipo_factor, tasa_cuota, importe):
		return {
			"traslados": [
				{
					"impuesto": impuesto,
					"tipo_factor": tipo_factor,
					"tasa_cuota": tasa_cuota,
					"importe": importe,
				}
			],
			"retenciones": [],
		}

	# ------------------------------------------------------------------ #
	# Traslados IVA                                                        #
	# ------------------------------------------------------------------ #

	def test_iva_16_nacional(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.160000", 160.0), TEST_COMPANY)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_iva_nac)
		self.assertAlmostEqual(rows[0]["tax_amount"], 160.0)

	def test_iva_8_frontera(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.080000", 80.0), TEST_COMPANY)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_iva_fro)
		self.assertAlmostEqual(rows[0]["tax_amount"], 80.0)

	def test_iva_tasa_0(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.000000", 0.0), TEST_COMPANY)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_iva_cero)
		self.assertAlmostEqual(rows[0]["tax_amount"], 0.0)

	def test_iva_exento_no_genera_linea(self):
		rows = resolve_taxes(self._imp("002", "Exento", "", 0.0), TEST_COMPANY)
		self.assertEqual(len(rows), 0)

	def test_ieps_genera_linea(self):
		rows = resolve_taxes(self._imp("003", "Tasa", "0.265000", 26.5), TEST_COMPANY)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_ieps)
		self.assertAlmostEqual(rows[0]["tax_amount"], 26.5)

	# ------------------------------------------------------------------ #
	# Campos obligatorios en cada fila generada                            #
	# ------------------------------------------------------------------ #

	def test_fila_usa_charge_type_actual(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.160000", 100.0), TEST_COMPANY)
		self.assertEqual(rows[0]["charge_type"], "Actual")

	def test_fila_usa_dont_recompute_tax(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.160000", 100.0), TEST_COMPANY)
		self.assertEqual(rows[0]["dont_recompute_tax"], 1)

	def test_tax_amount_igual_al_xml(self):
		importe_xml = 237.89
		rows = resolve_taxes(self._imp("002", "Tasa", "0.160000", importe_xml), TEST_COMPANY)
		self.assertAlmostEqual(flt(rows[0]["tax_amount"]), importe_xml, places=2)

	def test_descripcion_viene_de_regla(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.160000", 100.0), TEST_COMPANY)
		self.assertEqual(rows[0]["description"], "IVA Acreditable (Nacional)")

	# ------------------------------------------------------------------ #
	# Retenciones                                                          #
	# ------------------------------------------------------------------ #

	def test_retencion_isr_genera_linea_negativa(self):
		impuestos = {"traslados": [], "retenciones": [{"impuesto": "001", "importe": 10.0}]}
		rows = resolve_taxes(impuestos, TEST_COMPANY)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_ret_isr)
		self.assertAlmostEqual(rows[0]["tax_amount"], -10.0)

	def test_retencion_iva_genera_linea_negativa(self):
		impuestos = {"traslados": [], "retenciones": [{"impuesto": "002", "importe": 21.33}]}
		rows = resolve_taxes(impuestos, TEST_COMPANY)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_ret_iva)
		self.assertAlmostEqual(rows[0]["tax_amount"], -21.33)

	def test_retencion_sin_regla_bloquea(self):
		"""Retención ISR sin regla configurada en Configuracion CFDI Recibidos lanza ValidationError."""
		fake_co = f"_TRNR_{_H}"
		config_name = _make_config(fake_co, [], wizard_completado=True)
		try:
			impuestos = {"traslados": [], "retenciones": [{"impuesto": "001", "importe": 10.0}]}
			with self.assertRaises(frappe.ValidationError):
				resolve_taxes(impuestos, fake_co)
		finally:
			_delete_if_exists("Configuracion CFDI Recibidos", config_name)

	# ------------------------------------------------------------------ #
	# Configuración faltante                                               #
	# ------------------------------------------------------------------ #

	def test_config_no_existe_bloquea(self):
		"""Empresa sin Configuracion CFDI Recibidos lanza ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			resolve_taxes({"traslados": [], "retenciones": []}, "_EmpresaSinConfig_")

	def test_wizard_no_completado_bloquea(self):
		"""Config existente pero wizard_completado=0 lanza ValidationError."""
		fake_co = f"_TRNC_{_H}"
		config_name = _make_config(fake_co, [], wizard_completado=False)
		try:
			with self.assertRaises(frappe.ValidationError):
				resolve_taxes({"traslados": [], "retenciones": []}, fake_co)
		finally:
			_delete_if_exists("Configuracion CFDI Recibidos", config_name)

	def test_traslado_impuesto_desconocido_bloquea(self):
		"""Código de impuesto SAT no reconocido (ej: 999) lanza ValidationError."""
		impuestos = {
			"traslados": [{"impuesto": "999", "tipo_factor": "Tasa", "tasa_cuota": "0.1", "importe": 10.0}],
			"retenciones": [],
		}
		with self.assertRaises(frappe.ValidationError):
			resolve_taxes(impuestos, TEST_COMPANY)

	def test_retencion_impuesto_desconocido_bloquea(self):
		"""Código de retención SAT desconocido lanza ValidationError."""
		impuestos = {"traslados": [], "retenciones": [{"impuesto": "999", "importe": 10.0}]}
		with self.assertRaises(frappe.ValidationError):
			resolve_taxes(impuestos, TEST_COMPANY)
