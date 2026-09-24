"""Tests de integración — pricing histórico del importador `cfdi_emitidos`.

Valida la corrección: por cada línea el importador envía `price_list_rate == rate ==
ValorUnitario` del CFDI, de modo que ERPNext NO fabrica `discount_amount` contra el
`Item Price` maestro, y NO se crea/modifica ningún `Item Price` durante la carga
(supresión local de `auto_insert_price_list_rate_if_missing`).

`unittest.TestCase` (no `FrappeTestCase`) para evitar el bootstrap de test-records de
ERPNext (flake conocido). Aislamiento manual: `frappe.db.commit` -> no-op durante toda
la clase (nada persiste), savepoint por test y rollback total en teardown. Requiere sitio
con ERPNext; `frappe.flags.in_test` desactiva validación de RFC y validación fiscal de líneas.
"""

import os
import tempfile
import unittest

import frappe

from facturacion_mexico.cfdi_emitidos import importer

_CFDI = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0" Fecha="2026-06-15T12:00:00" SubTotal="{vu}" Total="{vu}" Moneda="{mon}" TipoDeComprobante="I" LugarExpedicion="00000" Exportacion="01" MetodoPago="PUE" FormaPago="01">
<cfdi:Emisor Rfc="EMI010101AAA" Nombre="Emisor Test" RegimenFiscal="601"/>
<cfdi:Receptor Rfc="{rfc}" Nombre="Cliente Test" UsoCFDI="G03" DomicilioFiscalReceptor="00000" RegimenFiscalReceptor="601"/>
<cfdi:Conceptos>
<cfdi:Concepto NoIdentificacion="{noid}" ClaveProdServ="81112501" Cantidad="1" ClaveUnidad="H87" Descripcion="Servicio Test" ValorUnitario="{vu}" Importe="{vu}" ObjetoImp="01"/>
</cfdi:Conceptos>
<cfdi:Complemento>
<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="1.1" UUID="{uuid}" FechaTimbrado="2026-06-15T12:00:01" SelloCFD="x" NoCertificadoSAT="00001000000000000000" SelloSAT="x"/>
</cfdi:Complemento>
</cfdi:Comprobante>"""


def flt2(x):
	return round(float(x or 0), 2)


class TestImporterPricing(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls._orig_commit = frappe.db.commit
		frappe.db.commit = lambda *a, **k: None  # nada se persiste en toda la clase
		h = frappe.generate_hash()[:6].upper()
		cls.company = "_Test Company"
		cls.currency = frappe.db.get_value("Company", cls.company, "default_currency")
		cls.uom = "Nos"
		cls.rfc = "TESTRFC" + h  # in_test desactiva la validación de formato de RFC
		cls.item_code = "ZZ-CFDIEMIT-ITEM-" + h
		cls.noid = "NID" + h
		cls.pl = "ZZ-CFDIEMIT-PL-" + h
		cls.cust = "ZZ-CFDIEMIT-CUST-" + h

		frappe.get_doc(
			{"doctype": "Price List", "price_list_name": cls.pl, "selling": 1, "currency": cls.currency}
		).insert(ignore_permissions=True)
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls.item_code,
				"item_name": cls.item_code,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": cls.uom,
				"is_stock_item": 0,
				"is_sales_item": 1,
			}
		)
		item.insert(ignore_permissions=True)
		if frappe.db.field_exists("Item", "fm_producto_servicio_sat"):
			frappe.db.set_value("Item", cls.item_code, "fm_producto_servicio_sat", "81112501")
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": cls.cust,
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
				"tax_id": cls.rfc,
				"default_price_list": cls.pl,
			}
		).insert(ignore_permissions=True)
		cls.manifest = {
			"company": cls.company,
			"item_map": {cls.noid: cls.item_code},
			"cancelled_marker": "cancel",
			"tolerance": 0.05,
		}

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()  # descarta TODO lo creado por la clase
		frappe.db.commit = cls._orig_commit

	def setUp(self):
		frappe.db.savepoint("tc")

	def tearDown(self):
		frappe.db.rollback(save_point="tc")  # aísla cada test

	# helpers ------------------------------------------------------------------
	def _set_item_price(self, rate):
		for n in frappe.get_all(
			"Item Price", {"item_code": self.item_code, "price_list": self.pl}, pluck="name"
		):
			frappe.delete_doc("Item Price", n, force=True, ignore_permissions=True)
		if rate is not None:
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": self.item_code,
					"price_list": self.pl,
					"currency": self.currency,
					"uom": self.uom,
					"price_list_rate": rate,
					"valid_from": "2020-01-01",
				}
			).insert(ignore_permissions=True)

	def _write_xml(self, tmp, uuid, vu=800):
		xml = _CFDI.format(vu=f"{vu:.2f}", mon=self.currency, rfc=self.rfc, noid=self.noid, uuid=uuid)
		path = os.path.join(tmp, f"{uuid}.xml")
		with open(path, "w", encoding="utf-8") as fh:
			fh.write(xml)
		return path

	def _run(self, tmp, dry_run):
		return importer.run(source_dir=tmp, manifest=self.manifest, dry_run=dry_run, report_dir=tmp)

	def _ip(self):
		r = frappe.get_all(
			"Item Price", {"item_code": self.item_code, "price_list": self.pl}, ["price_list_rate"]
		)
		return (len(r), float(r[0].price_list_rate) if r else None)

	def _uuid(self, p):
		return f"{p}10000-0000-4000-8000-" + frappe.generate_hash()[:12].upper()

	# tests --------------------------------------------------------------------
	def test_1_price_list_rate_igual_rate_sin_descuento(self):
		self._set_item_price(1000)
		uuid = self._uuid("AAA")
		with tempfile.TemporaryDirectory() as tmp:
			self._write_xml(tmp, uuid, vu=800)
			before = self._ip()
			self._run(tmp, dry_run=0)
			after = self._ip()
		si = frappe.db.get_value("Sales Invoice", {"fm_folio_fiscal": uuid}, "name")
		self.assertTrue(si, "la SI debió crearse")
		it = frappe.get_doc("Sales Invoice", si).items[0]
		self.assertEqual(flt2(it.price_list_rate), 800.0)
		self.assertEqual(flt2(it.rate), 800.0)
		self.assertEqual(flt2(it.discount_amount), 0.0)
		self.assertEqual(flt2(it.discount_percentage), 0.0)
		self.assertEqual(before, (1, 1000.0))
		self.assertEqual(after, (1, 1000.0))  # Item Price maestro intacto

	def test_2_sin_item_price_no_se_crea(self):
		self._set_item_price(None)
		uuid = self._uuid("BBB")
		with tempfile.TemporaryDirectory() as tmp:
			self._write_xml(tmp, uuid, vu=800)
			before = self._ip()
			self._run(tmp, dry_run=0)
			after = self._ip()
		self.assertEqual(before, (0, None))
		self.assertEqual(after, (0, None), "el importador NO debe crear Item Price")
		si = frappe.db.get_value("Sales Invoice", {"fm_folio_fiscal": uuid}, "name")
		it = frappe.get_doc("Sales Invoice", si).items[0]
		self.assertEqual(flt2(it.price_list_rate), 800.0)
		self.assertEqual(flt2(it.rate), 800.0)
		self.assertEqual(flt2(it.discount_amount), 0.0)

	def test_3_idempotencia_por_uuid(self):
		self._set_item_price(1000)
		uuid = self._uuid("CCC")
		with tempfile.TemporaryDirectory() as tmp:
			self._write_xml(tmp, uuid, vu=800)
			self._run(tmp, dry_run=0)
			si = frappe.db.get_value("Sales Invoice", {"fm_folio_fiscal": uuid}, "name")
			self.assertTrue(si)

			rep = self._run(tmp, dry_run=1)
			self.assertEqual(rep.get("SKIP_EXISTING"), 1)
			self.assertEqual(rep.get("READY", 0), 0)

			frappe.delete_doc("Sales Invoice", si, force=True, ignore_permissions=True)
			rep2 = self._run(tmp, dry_run=1)
			self.assertEqual(rep2.get("READY"), 1)
			self.assertEqual(rep2.get("SKIP_EXISTING", 0), 0)


if __name__ == "__main__":
	unittest.main()
