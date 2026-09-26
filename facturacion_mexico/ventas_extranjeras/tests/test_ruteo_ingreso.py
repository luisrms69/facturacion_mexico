"""Tests — ruteo de ingreso para ventas extranjeras + two-phase (anti-contaminación).

Tres bloques:
  1. Unit (mock): fases del two-phase, fail-closed en submit y lectura de la cuenta.
  2. Unit (mock): validación del campo en `Configuracion Fiscal Mexico`.
  3. Integración (site real): Sales Invoice real por `insert()` y por el importador
     `cfdi_emitidos`, probando que ambos reutilizan el MISMO resolver server-side y que
     `Item Default.income_account` no se contamina.

Integración: `unittest.TestCase` con `frappe.db.commit` -> no-op y rollback total en
teardown (patrón de `test_importer_pricing`). Requiere ERPNext; `frappe.flags.in_test`
desactiva la validación fiscal de líneas y de RFC.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

import frappe

from facturacion_mexico.facturacion_fiscal.doctype.configuracion_fiscal_mexico.configuracion_fiscal_mexico import (
	ConfiguracionFiscalMexico,
)
from facturacion_mexico.ventas_extranjeras import ruteo_ingreso
from facturacion_mexico.ventas_extranjeras.clasificacion import EXTRANJERA, NACIONAL

XEXX = "XEXX010101000"


# ── Doc de mentira para tests unitarios de las fases ──────────────────────────
class _FakeRow(frappe._dict):
	pass


class _FakeDoc:
	def __init__(self, company="ACME", items=None, docstatus=0):
		self._d = {"company": company, "items": items or []}
		self.docstatus = docstatus
		self.flags = frappe._dict()

	def get(self, key, default=None):
		return self._d.get(key, default)


def _doc(income_accounts, docstatus=0, company="ACME"):
	items = [_FakeRow(item_code=f"IT{i}", income_account=ia) for i, ia in enumerate(income_accounts)]
	return _FakeDoc(company=company, items=items, docstatus=docstatus)


# ── 1. Unit: two-phase + fail-closed ──────────────────────────────────────────
class TestRuteoUnit(unittest.TestCase):
	def test_before_validate_blanquea_lineas_extranjeras(self):
		doc = _doc(["Sales - X", "Sales - X"])
		with patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=EXTRANJERA):
			ruteo_ingreso.before_validate(doc)
		self.assertTrue(all(r.income_account is None for r in doc.get("items")))

	def test_before_validate_no_toca_nacional(self):
		doc = _doc(["Sales - X"])
		with patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=NACIONAL):
			ruteo_ingreso.before_validate(doc)
		self.assertEqual(doc.get("items")[0].income_account, "Sales - X")

	def test_validate_aplica_cuenta_extranjera(self):
		doc = _doc([None, None])
		with (
			patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=EXTRANJERA),
			patch.object(ruteo_ingreso, "get_cuenta_ingreso_extranjera", return_value="Export Income - X"),
			patch.object(ruteo_ingreso, "_cuenta_valida", return_value=True),
		):
			ruteo_ingreso.validate(doc)
		self.assertTrue(all(r.income_account == "Export Income - X" for r in doc.get("items")))

	def test_validate_nacional_no_toca(self):
		doc = _doc(["nativo"])
		with patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=NACIONAL):
			ruteo_ingreso.validate(doc)
		self.assertEqual(doc.get("items")[0].income_account, "nativo")

	def test_failclosed_submit_sin_cuenta_bloquea(self):
		doc = _doc([None], docstatus=1)
		with (
			patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=EXTRANJERA),
			patch.object(ruteo_ingreso, "get_cuenta_ingreso_extranjera", return_value=None),
		):
			with self.assertRaises(frappe.exceptions.ValidationError):
				ruteo_ingreso.validate(doc)

	def test_failclosed_submit_cuenta_invalida_bloquea(self):
		doc = _doc([None], docstatus=1)
		with (
			patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=EXTRANJERA),
			patch.object(ruteo_ingreso, "get_cuenta_ingreso_extranjera", return_value="BAD - X"),
			patch.object(ruteo_ingreso, "_cuenta_valida", return_value=False),
		):
			with self.assertRaises(frappe.exceptions.ValidationError):
				ruteo_ingreso.validate(doc)

	def test_draft_sin_cuenta_no_bloquea(self):
		doc = _doc([None], docstatus=0)
		with (
			patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=EXTRANJERA),
			patch.object(ruteo_ingreso, "get_cuenta_ingreso_extranjera", return_value=None),
		):
			ruteo_ingreso.validate(doc)  # no debe lanzar
		self.assertIsNone(doc.get("items")[0].income_account)

	def test_get_cuenta_lee_configuracion(self):
		def fake_gv(doctype, filters, field, *a, **k):
			if field == "name":
				return "CFM-ACME"
			if field == "cuenta_ingreso_venta_extranjera":
				return "Export Income - X"
			return None

		with patch.object(ruteo_ingreso.frappe.db, "get_value", side_effect=fake_gv):
			self.assertEqual(ruteo_ingreso.get_cuenta_ingreso_extranjera("ACME"), "Export Income - X")

	# Regresión: cuenta_descuentos > routing extranjero -------------------------
	def test_before_validate_preserva_linea_descuento(self):
		doc = _doc(["Descuentos - X"])
		with (
			patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=EXTRANJERA),
			patch.object(ruteo_ingreso, "get_cuenta_descuentos", return_value="Descuentos - X"),
		):
			ruteo_ingreso.before_validate(doc)
		self.assertEqual(doc.get("items")[0].income_account, "Descuentos - X")

	def test_validate_no_reemplaza_linea_descuento(self):
		doc = _doc(["Descuentos - X"])
		with (
			patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=EXTRANJERA),
			patch.object(ruteo_ingreso, "get_cuenta_descuentos", return_value="Descuentos - X"),
			patch.object(ruteo_ingreso, "get_cuenta_ingreso_extranjera", return_value="Export Income - X"),
			patch.object(ruteo_ingreso, "_cuenta_valida", return_value=True),
		):
			ruteo_ingreso.validate(doc)
		self.assertEqual(doc.get("items")[0].income_account, "Descuentos - X")

	def test_validate_mixto_rutea_solo_no_descuento(self):
		doc = _doc(["Descuentos - X", None])
		with (
			patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=EXTRANJERA),
			patch.object(ruteo_ingreso, "get_cuenta_descuentos", return_value="Descuentos - X"),
			patch.object(ruteo_ingreso, "get_cuenta_ingreso_extranjera", return_value="Export Income - X"),
			patch.object(ruteo_ingreso, "_cuenta_valida", return_value=True),
		):
			ruteo_ingreso.validate(doc)
		rows = doc.get("items")
		self.assertEqual(rows[0].income_account, "Descuentos - X")
		self.assertEqual(rows[1].income_account, "Export Income - X")

	def test_nc_descuento_total_no_falla_en_submit_sin_cuenta(self):
		# Todas las líneas son de descuento -> nada que rutear -> NO fail-closed aunque falte cuenta.
		doc = _doc(["Descuentos - X"], docstatus=1)
		with (
			patch.object(ruteo_ingreso, "clasificar_territorialidad", return_value=EXTRANJERA),
			patch.object(ruteo_ingreso, "get_cuenta_descuentos", return_value="Descuentos - X"),
			patch.object(ruteo_ingreso, "get_cuenta_ingreso_extranjera", return_value=None),
		):
			ruteo_ingreso.validate(doc)  # no debe lanzar
		self.assertEqual(doc.get("items")[0].income_account, "Descuentos - X")


# ── 2. Unit: validación del campo en Configuracion Fiscal Mexico ───────────────
class _FakeCFM:
	def __init__(self, cuenta, company="ACME"):
		self.cuenta_ingreso_venta_extranjera = cuenta
		self.company = company


class TestValidacionCampoCFM(unittest.TestCase):
	def _run(self, account_data):
		fake = _FakeCFM("ACC")
		with (
			patch.object(frappe.db, "exists", return_value=True),
			patch.object(frappe.db, "get_value", return_value=frappe._dict(account_data)),
		):
			ConfiguracionFiscalMexico._validar_cuenta_ingreso_extranjera(fake)

	def test_income_valida_ok(self):
		self._run({"root_type": "Income", "company": "ACME", "is_group": 0, "disabled": 0})

	def test_no_income_bloquea(self):
		with self.assertRaises(frappe.exceptions.ValidationError):
			self._run({"root_type": "Asset", "company": "ACME", "is_group": 0, "disabled": 0})

	def test_otra_empresa_bloquea(self):
		with self.assertRaises(frappe.exceptions.ValidationError):
			self._run({"root_type": "Income", "company": "OTRA", "is_group": 0, "disabled": 0})

	def test_grupo_bloquea(self):
		with self.assertRaises(frappe.exceptions.ValidationError):
			self._run({"root_type": "Income", "company": "ACME", "is_group": 1, "disabled": 0})

	def test_deshabilitada_bloquea(self):
		with self.assertRaises(frappe.exceptions.ValidationError):
			self._run({"root_type": "Income", "company": "ACME", "is_group": 0, "disabled": 1})

	def test_sin_valor_no_valida(self):
		# Campo vacío: no valida nada (fail-closed ocurre al enviar, no al guardar la config).
		fake = _FakeCFM(None)
		ConfiguracionFiscalMexico._validar_cuenta_ingreso_extranjera(fake)  # no lanza


# ── 3. Integración (site real) ────────────────────────────────────────────────
_CFDI = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0" Fecha="2026-06-15T12:00:00" SubTotal="{vu}" Total="{vu}" Moneda="{mon}" TipoDeComprobante="I" LugarExpedicion="00000" Exportacion="01" MetodoPago="PUE" FormaPago="01">
<cfdi:Emisor Rfc="EMI010101AAA" Nombre="Emisor Test" RegimenFiscal="601"/>
<cfdi:Receptor Rfc="{rfc}" Nombre="{rname}" UsoCFDI="G03" DomicilioFiscalReceptor="00000" RegimenFiscalReceptor="601"/>
<cfdi:Conceptos>
<cfdi:Concepto NoIdentificacion="{noid}" ClaveProdServ="81112501" Cantidad="1" ClaveUnidad="H87" Descripcion="Servicio Test" ValorUnitario="{vu}" Importe="{vu}" ObjetoImp="01"/>
</cfdi:Conceptos>
<cfdi:Complemento>
<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="1.1" UUID="{uuid}" FechaTimbrado="2026-06-15T12:00:01" SelloCFD="x" NoCertificadoSAT="00001000000000000000" SelloSAT="x"/>
</cfdi:Complemento>
</cfdi:Comprobante>"""


class TestRuteoIntegracion(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		# Guardar originales ANTES de parchear y registrar la restauración con addClassCleanup:
		# así se restaura commit/resolver y se hace rollback AUNQUE setUpClass falle a mitad
		# (tearDownClass NO corre si setUpClass lanza; sin esto, un commit=no-op se filtraría
		# a toda la suite y rompería otros tests — aislamiento).
		cls._orig_commit = frappe.db.commit
		cls._orig_getc = ruteo_ingreso.get_cuenta_ingreso_extranjera
		cls.addClassCleanup(cls._restaurar_entorno)
		frappe.db.commit = lambda *a, **k: None
		# Fuente de la cuenta: se fuerza el resolver a una cuenta Income real (≠ default).
		cls.foreign = "Service - _TC"  # Income leaf ≠ default_income_account (_Test Company)
		_foreign = cls.foreign
		ruteo_ingreso.get_cuenta_ingreso_extranjera = lambda company: _foreign

		h = frappe.generate_hash()[:6].upper()
		cls.company = "_Test Company"
		cls.default_income = frappe.db.get_value("Company", cls.company, "default_income_account")
		cls.company_country = frappe.db.get_value("Company", cls.company, "country")
		# CI puede no tener un Address Template por defecto; crear Address sin él lanza. Garantizarlo
		# (transitorio: se revierte con el rollback de _restaurar_entorno).
		if not frappe.db.exists("Address Template", {"is_default": 1}):
			existente = frappe.db.get_value("Address Template", {}, "name")
			if existente:
				frappe.db.set_value("Address Template", existente, "is_default", 1)
			else:
				frappe.get_doc(
					{
						"doctype": "Address Template",
						"country": cls.company_country or "United States",
						"is_default": 1,
						"template": "{{ address_line1 }}",
					}
				).insert(ignore_permissions=True)
		cls.cost_center = frappe.db.get_value("Cost Center", {"company": cls.company, "is_group": 0}, "name")
		cls.uom = "Nos"
		cls.cgroup = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		cls.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
		cls.item = "ZZ-VEXT-ITEM-" + h
		cls.noid = "NIDVX" + h

		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls.item,
				"item_name": cls.item,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": cls.uom,
				"is_stock_item": 0,
				"is_sales_item": 1,
			}
		).insert(ignore_permissions=True)
		if frappe.db.field_exists("Item", "fm_producto_servicio_sat"):
			frappe.db.set_value("Item", cls.item, "fm_producto_servicio_sat", "81112501")
		cls.item_doc = item

		cls.cust_xexx = cls._customer("ZZ-VEXT-XEXX-" + h, XEXX)
		cls.cust_addr_ext = cls._customer("ZZ-VEXT-EXT-" + h, "ABC010101AAA", addr_country="United States")
		cls.cust_nac = cls._customer("ZZ-VEXT-NAC-" + h, "ABC010101AAA", addr_country=cls.company_country)
		cls.cust_indet = cls._customer("ZZ-VEXT-IND-" + h, "ABC010101AAA")

	@classmethod
	def _restaurar_entorno(cls):
		"""Restaura commit/resolver y descarta lo creado. Corre vía addClassCleanup,
		incluso si setUpClass falló a mitad (garantiza aislamiento de la suite)."""
		frappe.db.rollback()
		frappe.db.commit = cls._orig_commit
		ruteo_ingreso.get_cuenta_ingreso_extranjera = cls._orig_getc

	def setUp(self):
		frappe.db.savepoint("vx")

	def tearDown(self):
		frappe.db.rollback(save_point="vx")

	@classmethod
	def _customer(cls, name, tax_id, addr_country=None):
		c = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_group": cls.cgroup,
				"territory": cls.territory,
				"tax_id": tax_id,
			}
		).insert(ignore_permissions=True)
		if addr_country:
			addr = frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": name,
					"address_type": "Billing",
					"address_line1": "Calle 1",
					"city": "Ciudad",
					"country": addr_country,
					"links": [{"link_doctype": "Customer", "link_name": c.name}],
				}
			).insert(ignore_permissions=True)
			frappe.db.set_value("Customer", c.name, "customer_primary_address", addr.name)
		return c.name

	def _make_si(self, customer, rate=100, income_account=None):
		doc = frappe.new_doc("Sales Invoice")
		doc.customer = customer
		doc.company = self.company
		doc.cost_center = self.cost_center
		row = doc.append("items", {})
		row.item_code = self.item
		row.qty = 1
		row.rate = rate
		row.uom = self.uom
		row.cost_center = self.cost_center
		if income_account:
			row.income_account = income_account
		doc.flags.ignore_permissions = True
		doc.insert()
		return doc

	def _item_default_income(self):
		it = frappe.get_doc("Item", self.item)
		for d in it.item_defaults:
			if d.company == self.company:
				return d.income_account
		return None

	# tests -------------------------------------------------------------------
	def test_extranjero_xexx_usa_cuenta_configurada(self):
		doc = self._make_si(self.cust_xexx)
		self.assertEqual(doc.items[0].income_account, self.foreign)

	def test_extranjero_por_address_usa_cuenta(self):
		doc = self._make_si(self.cust_addr_ext)
		self.assertEqual(doc.items[0].income_account, self.foreign)

	def test_nacional_conserva_resolucion_nativa(self):
		doc = self._make_si(self.cust_nac)
		self.assertEqual(doc.items[0].income_account, self.default_income)
		self.assertNotEqual(doc.items[0].income_account, self.foreign)

	def test_indeterminado_conserva_resolucion_nativa(self):
		doc = self._make_si(self.cust_indet)
		self.assertEqual(doc.items[0].income_account, self.default_income)

	def test_no_contamina_item_default(self):
		antes = self._item_default_income()
		self._make_si(self.cust_xexx)
		despues = self._item_default_income()
		self.assertEqual(antes, despues)
		self.assertNotEqual(despues, self.foreign)

	def test_reload_save_mantiene_cuenta_y_no_contamina(self):
		doc = self._make_si(self.cust_xexx)
		name = doc.name
		reloaded = frappe.get_doc("Sales Invoice", name)
		reloaded.flags.ignore_permissions = True
		reloaded.save()
		self.assertEqual(reloaded.items[0].income_account, self.foreign)
		self.assertNotEqual(self._item_default_income(), self.foreign)

	def test_nc_descuento_extranjera_preserva_cuenta_descuentos(self):
		# Línea marcada con cuenta_descuentos en una venta extranjera: el two-phase NO la
		# blanquea ni la reemplaza por la cuenta extranjera (precedencia del descuento).
		desc_acct = "_Test Account Sales - _TC"  # Income leaf usado como cuenta de descuentos
		self.assertNotEqual(desc_acct, self.foreign)
		with patch.object(ruteo_ingreso, "get_cuenta_descuentos", return_value=desc_acct):
			doc = self._make_si(self.cust_xexx, income_account=desc_acct)
		self.assertEqual(doc.items[0].income_account, desc_acct)

	def test_importador_cfdi_emitidos_reutiliza_resolver(self):
		from facturacion_mexico.cfdi_emitidos import importer

		manifest = {
			"company": self.company,
			"item_map": {self.noid: self.item},
			"cancelled_marker": "cancel",
			"tolerance": 0.05,
		}
		cust_name = frappe.db.get_value("Customer", self.cust_xexx, "customer_name")
		uuid = "AAA10000-0000-4000-8000-" + frappe.generate_hash()[:12].upper()
		currency = frappe.db.get_value("Company", self.company, "default_currency")
		xml = _CFDI.format(vu="100.00", mon=currency, rfc=XEXX, rname=cust_name, noid=self.noid, uuid=uuid)
		with tempfile.TemporaryDirectory() as tmp:
			with open(os.path.join(tmp, f"{uuid}.xml"), "w", encoding="utf-8") as fh:
				fh.write(xml)
			importer.run(source_dir=tmp, manifest=manifest, dry_run=0, report_dir=tmp)
		si = frappe.db.get_value("Sales Invoice", {"fm_folio_fiscal": uuid}, "name")
		self.assertTrue(si, "el importador debió crear la SI")
		it = frappe.get_doc("Sales Invoice", si).items[0]
		self.assertEqual(it.income_account, self.foreign)


if __name__ == "__main__":
	unittest.main()
