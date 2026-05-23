"""
Tests de TaxResolver — Fase 3b.

Crea y limpia fixtures reales en BD: CFM, template y cuentas de impuesto.
"""

import unittest

import frappe
from frappe.utils import flt

from facturacion_mexico.cfdi_recibidos.services.tax_resolver import resolve_taxes

TEST_COMPANY = "_Test Company"
_H = frappe.generate_hash()[:6]
_TEMPLATE_FULL = f"_Test TR Full {_H}"


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


def _make_template(title: str, accounts: list) -> str:
	if frappe.db.exists("Purchase Taxes and Charges Template", title):
		frappe.delete_doc("Purchase Taxes and Charges Template", title, force=True)
	tmpl = frappe.new_doc("Purchase Taxes and Charges Template")
	tmpl.title = title
	tmpl.company = TEST_COMPANY
	for account in accounts:
		tmpl.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": account,
				"description": account,
				"tax_amount": 0,
			},
		)
	tmpl.insert(ignore_permissions=True)
	frappe.db.commit()
	return tmpl.name


def _make_cfm(company: str, template: str, mapeos: list, *, ignore_links: bool = False) -> str:
	cfm_name = f"CFM-{company}"
	if frappe.db.exists("Configuracion Fiscal Mexico", cfm_name):
		frappe.delete_doc("Configuracion Fiscal Mexico", cfm_name, force=True)
	cfm = frappe.new_doc("Configuracion Fiscal Mexico")
	cfm.company = company
	cfm.cfdi_recibidos_tax_template = template
	for rol, cuenta in mapeos:
		cfm.append("mapeo_cuentas", {"rol_fiscal": rol, "cuenta_impuesto": cuenta})
	cfm.insert(
		ignore_permissions=True,
		ignore_links=ignore_links,
		ignore_mandatory=not mapeos,
	)
	frappe.db.commit()
	return cfm_name


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

		# Crear cuentas de impuesto únicas para esta ejecución
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

		# Template completo con las 6 cuentas
		cls.template_full = _make_template(_TEMPLATE_FULL, cls.all_accounts)

		# CFM completo para _Test Company
		cls.cfm_name = _make_cfm(
			TEST_COMPANY,
			cls.template_full,
			[
				("IVA Acreditable (Nacional)", cls.acc_iva_nac),
				("IVA Acreditable (Frontera)", cls.acc_iva_fro),
				("IVA Acreditable (0% exportación)", cls.acc_iva_cero),
				("IEPS Acreditable", cls.acc_ieps),
				("IVA Retenido (Honorarios)", cls.acc_ret_iva),
				("ISR Retenido (Honorarios)", cls.acc_ret_isr),
			],
		)

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("Configuracion Fiscal Mexico", cls.cfm_name)
		_delete_if_exists("Purchase Taxes and Charges Template", cls.template_full)
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
		rows = resolve_taxes(self._imp("002", "Tasa", "0.160000", 160.0), TEST_COMPANY, [])
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_iva_nac)
		self.assertAlmostEqual(rows[0]["tax_amount"], 160.0)

	def test_iva_8_frontera(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.080000", 80.0), TEST_COMPANY, [])
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_iva_fro)
		self.assertAlmostEqual(rows[0]["tax_amount"], 80.0)

	def test_iva_tasa_0(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.000000", 0.0), TEST_COMPANY, [])
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_iva_cero)
		self.assertAlmostEqual(rows[0]["tax_amount"], 0.0)

	def test_iva_exento_no_genera_linea(self):
		rows = resolve_taxes(self._imp("002", "Exento", "", 0.0), TEST_COMPANY, [])
		self.assertEqual(len(rows), 0)

	def test_ieps_genera_linea(self):
		rows = resolve_taxes(self._imp("003", "Tasa", "0.265000", 26.5), TEST_COMPANY, [])
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_ieps)
		self.assertAlmostEqual(rows[0]["tax_amount"], 26.5)

	# ------------------------------------------------------------------ #
	# Campos obligatorios en cada fila generada                            #
	# ------------------------------------------------------------------ #

	def test_fila_usa_charge_type_actual(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.160000", 100.0), TEST_COMPANY, [])
		self.assertEqual(rows[0]["charge_type"], "Actual")

	def test_fila_usa_dont_recompute_tax(self):
		rows = resolve_taxes(self._imp("002", "Tasa", "0.160000", 100.0), TEST_COMPANY, [])
		self.assertEqual(rows[0]["dont_recompute_tax"], 1)

	def test_tax_amount_igual_al_xml(self):
		importe_xml = 237.89
		rows = resolve_taxes(self._imp("002", "Tasa", "0.160000", importe_xml), TEST_COMPANY, [])
		self.assertAlmostEqual(flt(rows[0]["tax_amount"]), importe_xml, places=2)

	# ------------------------------------------------------------------ #
	# Retenciones                                                          #
	# ------------------------------------------------------------------ #

	def test_retencion_isr_con_rol_explicito(self):
		impuestos = {
			"traslados": [],
			"retenciones": [{"impuesto": "001", "importe": 10.0}],
		}
		mapping = {
			"retencion_isr_rol_fiscal": "ISR Retenido (Honorarios)",
			"retencion_iva_rol_fiscal": "",
		}
		rows = resolve_taxes(impuestos, TEST_COMPANY, [mapping])
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_ret_isr)
		self.assertAlmostEqual(rows[0]["tax_amount"], -10.0)

	def test_retencion_iva_con_rol_explicito(self):
		impuestos = {
			"traslados": [],
			"retenciones": [{"impuesto": "002", "importe": 21.33}],
		}
		mapping = {
			"retencion_iva_rol_fiscal": "IVA Retenido (Honorarios)",
			"retencion_isr_rol_fiscal": "",
		}
		rows = resolve_taxes(impuestos, TEST_COMPANY, [mapping])
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["account_head"], self.acc_ret_iva)
		self.assertAlmostEqual(rows[0]["tax_amount"], -21.33)

	def test_retencion_sin_rol_bloquea(self):
		"""Retención ISR sin rol configurado en ningún mapping lanza ValidationError."""
		impuestos = {"traslados": [], "retenciones": [{"impuesto": "001", "importe": 10.0}]}
		with self.assertRaises(frappe.ValidationError):
			resolve_taxes(impuestos, TEST_COMPANY, [])

	def test_rol_sin_cuenta_en_cfm_bloquea(self):
		"""Rol apuntado por mapping pero ausente en CFM.mapeo_cuentas lanza ValidationError."""
		# El CFM de prueba tiene solo Honorarios; Arrendamiento no está configurado
		impuestos = {"traslados": [], "retenciones": [{"impuesto": "002", "importe": 21.33}]}
		mapping = {"retencion_iva_rol_fiscal": "IVA Retenido (Arrendamiento)"}
		with self.assertRaises(frappe.ValidationError):
			resolve_taxes(impuestos, TEST_COMPANY, [mapping])

	# ------------------------------------------------------------------ #
	# Configuración faltante                                               #
	# ------------------------------------------------------------------ #

	def test_cfm_sin_template_bloquea(self):
		"""CFM sin cfdi_recibidos_tax_template lanza ValidationError."""
		fake_co = f"_TRTNT_{frappe.generate_hash()[:4]}"
		cfm_name = f"CFM-{fake_co}"
		try:
			cfm = frappe.new_doc("Configuracion Fiscal Mexico")
			cfm.company = fake_co
			# Sin template ni mapeo_cuentas
			cfm.insert(ignore_permissions=True, ignore_links=True, ignore_mandatory=True)
			frappe.db.commit()
			with self.assertRaises(frappe.ValidationError):
				resolve_taxes({"traslados": [], "retenciones": []}, fake_co, [])
		finally:
			_delete_if_exists("Configuracion Fiscal Mexico", cfm_name)

	def test_template_sin_cuenta_compatible_bloquea(self):
		"""Template que no contiene la cuenta del CFM lanza ValidationError."""
		# Creamos un template parcial (sin acc_ieps) dentro de _Test Company
		partial_tpl = f"_Test TR Part {frappe.generate_hash()[:4]}"
		try:
			_make_template(partial_tpl, [self.acc_iva_nac])  # solo IVA Nac, sin IEPS

			# Temporalmente apuntamos el CFM principal al template parcial
			original_template = frappe.db.get_value(
				"Configuracion Fiscal Mexico", self.cfm_name, "cfdi_recibidos_tax_template"
			)
			frappe.db.set_value(
				"Configuracion Fiscal Mexico",
				self.cfm_name,
				"cfdi_recibidos_tax_template",
				partial_tpl,
			)
			frappe.db.commit()
			try:
				# IEPS traslado: CFM tiene IEPS → acc_ieps,
				# pero el template parcial no tiene acc_ieps → debe bloquear
				impuestos = {
					"traslados": [
						{
							"impuesto": "003",
							"tipo_factor": "Tasa",
							"tasa_cuota": "0.265000",
							"importe": 26.5,
						}
					],
					"retenciones": [],
				}
				with self.assertRaises(frappe.ValidationError):
					resolve_taxes(impuestos, TEST_COMPANY, [])
			finally:
				frappe.db.set_value(
					"Configuracion Fiscal Mexico",
					self.cfm_name,
					"cfdi_recibidos_tax_template",
					original_template,
				)
				frappe.db.commit()
		finally:
			_delete_if_exists("Purchase Taxes and Charges Template", partial_tpl)
