"""Tests — preparación de Customers/Suppliers desde XML CFDI (V1 solo lectura).

Verifica: parseo local de partes, determinación de rol por RFC de Company, dedupe
(nacional por RFC; extranjero genérico por NumRegIdTrib/nombre), detección de existencia
(read-only), y la corrida completa con generación de CSV para Data Import.

Parsing real (`secure_parse_xml`); existencia y Company mockeadas. `unittest.TestCase`.
"""

import csv
import os
import tempfile
import unittest
from unittest.mock import patch

import frappe

from facturacion_mexico.preparacion_terceros import preparador as P

CO_RFC = "AAA010101AAA"  # RFC de la Company de prueba

_TPL = (
	'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0" '
	'TipoDeComprobante="I" LugarExpedicion="{cp}">'
	'<cfdi:Emisor Rfc="{erfc}" Nombre="{enom}" RegimenFiscal="{ereg}"/>'
	'<cfdi:Receptor Rfc="{rrfc}" Nombre="{rnom}" RegimenFiscalReceptor="{rreg}" '
	'DomicilioFiscalReceptor="{rcp}" UsoCFDI="G03"{extra}/>'
	"</cfdi:Comprobante>"
)


def _xml(
	erfc=CO_RFC,
	enom="Empresa SA",
	ereg="601",
	rrfc="CUS010101AAA",
	rnom="Cliente Uno",
	rreg="612",
	rcp="06000",
	cp="64000",
	residencia="",
	numreg="",
):
	extra = ""
	if residencia:
		extra += f' ResidenciaFiscal="{residencia}"'
	if numreg:
		extra += f' NumRegIdTrib="{numreg}"'
	return _TPL.format(
		cp=cp, erfc=erfc, enom=enom, ereg=ereg, rrfc=rrfc, rnom=rnom, rreg=rreg, rcp=rcp, extra=extra
	).encode("utf-8")


# ── parseo ────────────────────────────────────────────────────────────────────


class TestParse(unittest.TestCase):
	def test_extrae_partes(self):
		d = P.parse_partes_cfdi(_xml())
		self.assertEqual(d["emisor_rfc"], CO_RFC)
		self.assertEqual(d["receptor_rfc"], "CUS010101AAA")
		self.assertEqual(d["receptor_regimen"], "612")
		self.assertEqual(d["receptor_cp"], "06000")
		self.assertEqual(d["lugar_expedicion"], "64000")

	def test_extranjero_residencia_numreg(self):
		d = P.parse_partes_cfdi(_xml(rrfc="XEXX010101000", residencia="USA", numreg="US99"))
		self.assertEqual(d["receptor_residencia"], "USA")
		self.assertEqual(d["receptor_numreg"], "US99")

	def test_parse_error(self):
		with self.assertRaises(Exception):
			P.parse_partes_cfdi(b"<not-cfdi/>")


# ── rol + contraparte ─────────────────────────────────────────────────────────


class TestRole(unittest.TestCase):
	def setUp(self):
		self.corfc = {CO_RFC: "Test Co"}

	def test_venta_es_customer(self):
		d = P.parse_partes_cfdi(_xml())
		res = P._role_and_counterparty(d, self.corfc)
		self.assertEqual(res["role"], "Customer")
		self.assertEqual(res["party"]["rfc"], "CUS010101AAA")
		self.assertEqual(res["party"]["cp"], "06000")  # DomicilioFiscalReceptor

	def test_compra_es_supplier(self):
		# receptor = company -> compra; contraparte = emisor
		d = P.parse_partes_cfdi(_xml(erfc="PRO010101AAA", enom="Prov SA", rrfc=CO_RFC))
		res = P._role_and_counterparty(d, self.corfc)
		self.assertEqual(res["role"], "Supplier")
		self.assertEqual(res["party"]["rfc"], "PRO010101AAA")
		self.assertEqual(res["party"]["cp"], "64000")  # LugarExpedicion

	def test_ninguno_es_company(self):
		d = P.parse_partes_cfdi(_xml(erfc="OTR010101AAA", rrfc="CUS010101AAA"))
		res = P._role_and_counterparty(d, self.corfc)
		self.assertEqual(res["error"], "ERROR_COMPANY_RFC")

	def test_ambos_company_es_ambiguo(self):
		d = P.parse_partes_cfdi(_xml(erfc=CO_RFC, rrfc=CO_RFC))
		res = P._role_and_counterparty(d, self.corfc)
		self.assertEqual(res["error"], "ERROR_AMBIGUO")


# ── dedupe / extranjero ───────────────────────────────────────────────────────


class TestDedupe(unittest.TestCase):
	def _party(self, **o):
		p = {
			"role": "Customer",
			"rfc": "CUS010101AAA",
			"nombre": "Cliente",
			"regimen": "",
			"cp": "",
			"residencia": "",
			"numreg": "",
		}
		p.update(o)
		return p

	def test_nacional_por_rfc(self):
		self.assertEqual(P._dedupe_key(self._party()), ("Customer", "CUS010101AAA"))

	def test_extranjero_por_numreg(self):
		k = P._dedupe_key(self._party(rfc="XEXX010101000", residencia="USA", numreg="US1"))
		self.assertEqual(k, ("Customer", "XEXX", "TIN:US1"))

	def test_extranjero_sin_numreg_por_nombre(self):
		k = P._dedupe_key(self._party(rfc="XEXX010101000", residencia="USA", numreg="", nombre="Foreign LLC"))
		self.assertEqual(k, ("Customer", "XEXX", "NAME:FOREIGN LLC", "USA"))

	def test_extranjero_sin_evidencia_es_none(self):
		self.assertIsNone(
			P._dedupe_key(self._party(rfc="XEXX010101000", residencia="USA", numreg="", nombre=""))
		)

	def test_sin_rfc_es_none(self):
		self.assertIsNone(P._dedupe_key(self._party(rfc="")))


# ── existencia (read-only, mockeada) ──────────────────────────────────────────


class TestExistencia(unittest.TestCase):
	def _p(self, role="Customer", **o):
		p = {"role": role, "rfc": "CUS010101AAA", "nombre": "X", "residencia": "", "numreg": ""}
		p.update(o)
		return p

	def test_customer_existente(self):
		with patch.object(P.frappe, "get_all", return_value=[frappe._dict(name="C-1")]):
			self.assertEqual(P._customer_exists(self._p())[0], "EXISTENTE")

	def test_customer_a_crear(self):
		with patch.object(P.frappe, "get_all", return_value=[]):
			self.assertEqual(P._customer_exists(self._p())[0], "A_CREAR_CUSTOMER")

	def test_customer_ambiguo(self):
		with patch.object(P.frappe, "get_all", return_value=[frappe._dict(name="A"), frappe._dict(name="B")]):
			self.assertEqual(P._customer_exists(self._p())[0], "ERROR_AMBIGUO")

	def test_customer_extranjero_por_numreg(self):
		with (
			patch.object(P.frappe.db, "has_column", return_value=True),
			patch.object(P.frappe, "get_all", return_value=[]),
		):
			p = self._p(rfc="XEXX010101000", residencia="USA", numreg="US7")
			self.assertEqual(P._customer_exists(p)[0], "A_CREAR_CUSTOMER")

	def test_customer_extranjero_sin_numreg_insuficiente(self):
		with patch.object(P.frappe.db, "has_column", return_value=True):
			p = self._p(rfc="XEXX010101000", residencia="USA", numreg="")
			self.assertEqual(P._customer_exists(p)[0], "DATOS_INSUFICIENTES")

	def test_supplier_a_crear(self):
		with patch.object(P.frappe, "get_all", return_value=[]):
			self.assertEqual(
				P._supplier_exists(self._p(role="Supplier", rfc="PRO010101AAA"))[0], "A_CREAR_SUPPLIER"
			)

	def test_supplier_extranjero_insuficiente(self):
		p = self._p(role="Supplier", rfc="XEXX010101000", residencia="USA", numreg="US7")
		self.assertEqual(P._supplier_exists(p)[0], "DATOS_INSUFICIENTES")


# ── corrida completa (e2e con lookups mockeados) ──────────────────────────────


def _fake_get_all(doctype, filters=None, fields=None, **kwargs):
	filters = filters or {}
	if doctype == "Customer":
		return []  # ningún customer existe
	if doctype == "Supplier":
		if filters.get("tax_id") == "PRO010101AAA":
			return [frappe._dict(name="SUP-1")]  # proveedor existente
		return []
	return []


class TestRunE2E(unittest.TestCase):
	def test_run_genera_csv_y_estados(self):
		src = tempfile.mkdtemp()
		out = tempfile.mkdtemp()
		# venta -> customer nuevo
		with open(os.path.join(src, "venta.xml"), "wb") as fh:
			fh.write(_xml(rrfc="CUS010101AAA", rnom="Cliente Uno"))
		# compra -> supplier existente
		with open(os.path.join(src, "compra.xml"), "wb") as fh:
			fh.write(_xml(erfc="PRO010101AAA", enom="Proveedor Uno", rrfc=CO_RFC))
		# venta extranjera -> customer nuevo por NumRegIdTrib
		with open(os.path.join(src, "ext.xml"), "wb") as fh:
			fh.write(_xml(rrfc="XEXX010101000", rnom="Foreign LLC", residencia="USA", numreg="US123"))

		with (
			patch.object(P, "load_company_rfcs", return_value={CO_RFC: "Test Co"}),
			patch.object(P.frappe, "get_all", side_effect=_fake_get_all),
			patch.object(P.frappe.db, "has_column", return_value=True),
		):
			res = P.run(source_dir=src, report_dir=out)

		# 2 customers a crear (nacional + extranjero), 1 supplier existente
		self.assertEqual(res["resumen_terceros"]["A_CREAR_CUSTOMER"], 2)
		self.assertEqual(res["resumen_terceros"]["EXISTENTE"], 1)
		self.assertEqual(res["resumen_terceros"].get("A_CREAR_SUPPLIER", 0), 0)

		# CSV de customers faltantes con columnas Data-Import y el TIN del extranjero
		cust_csv = [f for f in os.listdir(out) if f.endswith("_customers_faltantes.csv")]
		self.assertEqual(len(cust_csv), 1)
		with open(os.path.join(out, cust_csv[0]), encoding="utf-8") as fh:
			rows = list(csv.DictReader(fh))
		self.assertEqual(
			set(rows[0].keys()),
			{
				"customer_name",
				"tax_id",
				"fm_tax_regime",
				"fm_num_reg_id_trib",
				"codigo_postal_fiscal",
				"residencia_fiscal",
			},
		)
		ext = [r for r in rows if r["tax_id"] == "XEXX010101000"]
		self.assertEqual(ext[0]["fm_num_reg_id_trib"], "US123")
		self.assertEqual(ext[0]["residencia_fiscal"], "USA")
		# no debe existir CSV de suppliers faltantes (el único proveedor ya existe)
		self.assertEqual([f for f in os.listdir(out) if f.endswith("_suppliers_faltantes.csv")], [])


if __name__ == "__main__":
	unittest.main()
