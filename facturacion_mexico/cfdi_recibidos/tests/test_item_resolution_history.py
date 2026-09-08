"""Tests del aprendizaje histórico de Items en CFDI Recibidos (_resolve_by_history).

Dos capas:
  - Unit (mock de fronteras frappe/validate): algoritmo, gate, ranking determinista,
    filtrado por validate_expense_item, alternativas, presencia de filtros en el SQL.
  - Integración (IntegrationTestCase, BD real): semántica de la query — scope por company,
    no_procesar, exclusión de autoasignaciones "Historial", anti-autocontaminación —
    más el batch y la conversión Historial→Manual en assign_item_to_concepto.

Gate: HIST_MIN_PREV=2, HIST_MIN_SHARE=0.80. Solo el Item top puede autoasignarse.
"""

import types
import unittest
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

ENGINE = "facturacion_mexico.cfdi_recibidos.services.item_resolution_engine"
VALIDATOR = "facturacion_mexico.cfdi_recibidos.services.item_validator.validate_expense_item"


def _iteminfo(name="Item X", group="FM Hist"):
	return types.SimpleNamespace(item_name=name, item_group=group)


# ───────────────────────── Unit: algoritmo / gate / ranking ─────────────────────────


class TestResolveByHistoryUnit(unittest.TestCase):
	def _run(self, rows, valid=True):
		"""Ejecuta _resolve_by_history con frappe.db.sql y validate mockeados.

		rows: lista de item_code (simula filas ya filtradas por la query).
		valid: True/False global o dict item->bool.
		"""
		from facturacion_mexico.cfdi_recibidos.services import item_resolution_engine as eng

		def _val(ic):
			ok = valid[ic] if isinstance(valid, dict) else valid
			return (ok, "")

		with patch(f"{ENGINE}.frappe") as mf, patch(VALIDATOR, side_effect=_val):
			mf.db.sql.return_value = [{"item_code": ic} for ic in rows]
			mf.db.get_value.side_effect = lambda *a, **k: _iteminfo()
			out = eng._resolve_by_history("Co", "RFC", "SAT", "cur", set())
		return out, mf

	def test_sin_antecedentes_retorna_vacio(self):
		out, _ = self._run([])
		self.assertEqual(out, [])

	def test_gate_prev1_no_autoasigna(self):
		out, _ = self._run(["A"])  # 1 previo
		self.assertEqual(out[0]["item_code"], "A")
		self.assertFalse(out[0]["auto_assignable"])
		self.assertEqual(out[0]["item_resolution"], "Historial")

	def test_gate_prev2_share100_autoasigna(self):
		out, _ = self._run(["A", "A"])
		self.assertTrue(out[0]["auto_assignable"])
		self.assertEqual(out[0]["match_confidence"], "Alta")

	def test_gate_share080_autoasigna(self):
		out, _ = self._run(["A", "A", "A", "A", "B"])  # 4/5 = 0.80
		self.assertEqual(out[0]["item_code"], "A")
		self.assertTrue(out[0]["auto_assignable"])

	def test_gate_share079_no_autoasigna_pero_conserva_alternativas(self):
		out, _ = self._run(["A", "A", "A", "B", "C"])  # 3/5 = 0.60
		self.assertEqual(out[0]["item_code"], "A")
		self.assertFalse(out[0]["auto_assignable"])
		items = {o["item_code"] for o in out}
		self.assertEqual(items, {"A", "B", "C"})  # alternativas conservadas

	def test_top80_autoasigna_aunque_exista_otro_item(self):
		out, _ = self._run(["A", "A", "A", "A", "A", "A", "A", "A", "A", "B"])  # 9/10
		self.assertEqual(out[0]["item_code"], "A")
		self.assertTrue(out[0]["auto_assignable"])
		self.assertIn("B", {o["item_code"] for o in out})
		self.assertFalse(next(o for o in out if o["item_code"] == "B")["auto_assignable"])

	def test_alternativas_solo_top_autoassignable(self):
		out, _ = self._run(["A", "A", "A", "B"])
		top = out[0]
		self.assertEqual(top["item_code"], "A")
		for alt in out[1:]:
			self.assertFalse(alt["auto_assignable"])

	def test_gasto_participa_igual(self):
		out, _ = self._run(["GASTO-X", "GASTO-X", "GASTO-X"])
		self.assertEqual(out[0]["item_code"], "GASTO-X")
		self.assertTrue(out[0]["auto_assignable"])

	def test_ranking_determinista_empate_por_item_code(self):
		out, _ = self._run(["B", "A"])  # empate 1-1 -> ordena por item_code asc
		self.assertEqual([o["item_code"] for o in out], ["A", "B"])

	def test_item_invalido_no_participa_en_count_share(self):
		# BAD inválido: no cuenta; A queda 2/2 -> autoasigna
		out, _ = self._run(["A", "A", "BAD", "BAD", "BAD"], valid={"A": True, "BAD": False})
		self.assertEqual([o["item_code"] for o in out], ["A"])
		self.assertTrue(out[0]["auto_assignable"])

	def test_top_invalido_recalcula_con_validos(self):
		# BAD sería top (3) pero inválido; A válido (2) -> nuevo top A
		out, _ = self._run(["BAD", "BAD", "BAD", "A", "A"], valid={"A": True, "BAD": False})
		self.assertEqual(out[0]["item_code"], "A")

	def test_todos_invalidos_retorna_vacio(self):
		out, _ = self._run(["BAD", "BAD"], valid=False)
		self.assertEqual(out, [])

	def test_query_incluye_filtros_criticos(self):
		_, mf = self._run(["A", "A"])
		sql = mf.db.sql.call_args[0][0]
		params = mf.db.sql.call_args[0][1]
		self.assertIn("p.company = %(co)s", sql)
		self.assertIn("p.supplier_rfc = %(rfc)s", sql)
		self.assertIn("c.sat_product_key = %(sat)s", sql)
		self.assertIn("c.name != %(cur)s", sql)  # anti-autocontaminación
		self.assertIn("COALESCE(p.no_procesar, 0) = 0", sql)
		self.assertIn("COALESCE(c.item_resolution, '') != 'Historial'", sql)  # anti auto-refuerzo
		self.assertEqual(params["co"], "Co")

	def test_sin_company_o_sat_retorna_vacio(self):
		from facturacion_mexico.cfdi_recibidos.services import item_resolution_engine as eng

		with patch(f"{ENGINE}.frappe") as mf, patch(VALIDATOR, return_value=(True, "")):
			self.assertEqual(eng._resolve_by_history("", "RFC", "SAT", "c", set()), [])
			self.assertEqual(eng._resolve_by_history("Co", "RFC", "", "c", set()), [])
			mf.db.sql.assert_not_called()


# ─────────────── Unit: precedencia en get_resolution_options (flag operativo) ───────────────


class TestHistoryPrecedenceUnit(unittest.TestCase):
	"""auto_assignable describe capacidad operativa en el resultado FINAL: si una fuente de mayor
	precedencia (manual/determinista) ocupó el primary, el histórico queda como alternativa y
	pierde auto_assignable, aunque hubiera pasado el gate."""

	@patch(VALIDATOR, return_value=(True, ""))
	@patch(f"{ENGINE}.frappe")
	def test_regla_manual_gana_historial_alternativa_no_autoassignable(self, mf, _val):
		# Regla MANUAL nivel 2 (rfc+sat, sin company) -> gana el primary como "Mapeado".
		manual_rule = {
			"name": "R1",
			"company": "",
			"supplier_rfc": "RFC",
			"sat_product_key": "SAT",
			"keywords": "",
			"target_item": "ITEM-MANUAL",
			"match_reason": "Regla manual",
			"priority": 10,
		}
		mf.get_all.side_effect = [
			[manual_rule],  # paso 1: reglas manuales
			[],  # paso 4: reglas auto
			[],  # item groups (dentro de _resolve_by_text)
			[],  # candidatos Item (texto)
		]
		# Historial pasa el gate holgadamente: 3x ITEM-HIST (share 1.0).
		mf.db.sql.return_value = [{"item_code": "ITEM-HIST"}] * 3

		def _gv(doctype, name, *a, **k):
			if doctype == "Item Group":
				return types.SimpleNamespace(lft=1, rgt=10)
			return _iteminfo(name=name)

		mf.db.get_value.side_effect = _gv

		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import (
			get_resolution_options,
		)

		res = get_resolution_options(
			{"sat_product_key": "SAT", "no_identificacion": "", "description": "servicio", "item_group": ""},
			{"company": "Co", "supplier": "Prov", "supplier_rfc": "RFC"},
		)

		# primary = regla manual, no el histórico
		self.assertEqual(res["primary"]["item_code"], "ITEM-MANUAL")
		self.assertEqual(res["primary"]["item_resolution"], "Mapeado")

		# el histórico aparece en alternatives...
		hist = [a for a in res["alternatives"] if a.get("source") == "Historial"]
		self.assertEqual(len(hist), 1)
		self.assertEqual(hist[0]["item_code"], "ITEM-HIST")
		# ...pero SIN capacidad operativa de autoasignación
		self.assertFalse(hist[0]["auto_assignable"])
		# conserva confianza y motivo (solo pierde auto_assignable)
		self.assertEqual(hist[0]["match_confidence"], "Alta")
		self.assertIn("Historial", hist[0]["match_reason"])


# ───────────────────────── Integración: semántica de la query en BD ─────────────────────────


class TestResolveByHistoryDB(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = "_Test Company"
		# UOM SAT válida
		if not frappe.db.exists("UOM", "E48 - Servicio"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "E48 - Servicio"}).insert(ignore_permissions=True)
		# Árbol de grupos: Gastos (raíz) + hoja de prueba
		if not frappe.db.exists("Item Group", "All Item Groups"):
			frappe.get_doc(
				{"doctype": "Item Group", "item_group_name": "All Item Groups", "is_group": 1}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Item Group", "Gastos"):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": "Gastos",
					"is_group": 1,
					"parent_item_group": "All Item Groups",
				}
			).insert(ignore_permissions=True)
		cls.leaf = "FM Hist Test Group"
		if not frappe.db.exists("Item Group", cls.leaf):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": cls.leaf,
					"is_group": 0,
					"parent_item_group": "Gastos",
				}
			).insert(ignore_permissions=True)
		# Items de gasto válidos
		for code in ("ITEM-HIST-A", "ITEM-HIST-B", "GASTO-HIST-001"):
			if not frappe.db.exists("Item", code):
				frappe.get_doc(
					{
						"doctype": "Item",
						"item_code": code,
						"item_name": code,
						"item_group": cls.leaf,
						"stock_uom": "E48 - Servicio",
						"is_purchase_item": 1,
						"is_stock_item": 0,
						"is_sales_item": 0,
					}
				).insert(ignore_permissions=True)

	def setUp(self):
		self.tid = frappe.generate_hash(length=6)
		self.rfc = "HST" + frappe.generate_hash(length=8).upper()

	def _cfdi(self, company=None, no_procesar=0):
		doc = frappe.get_doc(
			{
				"doctype": "CFDI Recibido",
				"company": company or self.company,
				"supplier_rfc": self.rfc,
				"no_procesar": no_procesar,
			}
		)
		doc.flags.ignore_validate = True
		doc.flags.ignore_mandatory = True
		doc.flags.ignore_links = True
		doc.db_insert()
		return doc.name

	def _concepto(self, parent, sat, item_code, resolution="Manual"):
		row = frappe.get_doc(
			{
				"doctype": "CFDI Recibido Concepto",
				"name": f"{self.tid}-{frappe.generate_hash(length=6)}",
				"parent": parent,
				"parenttype": "CFDI Recibido",
				"parentfield": "conceptos",
				"idx": 1,
				"sat_product_key": sat,
				"description": "concepto",
				"item_code": item_code,
				"item_resolution": resolution,
			}
		)
		row.flags.ignore_validate = True
		row.flags.ignore_mandatory = True
		row.flags.ignore_links = True
		row.db_insert()
		return row.name

	def _hist(self, sat, current="cur", company=None):
		from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import (
			_resolve_by_history,
		)

		return _resolve_by_history(company or self.company, self.rfc, sat, current, set())

	def test_autoasigna_con_dos_antecedentes_reales(self):
		c = self._cfdi()
		self._concepto(c, "SAT001", "ITEM-HIST-A")
		self._concepto(c, "SAT001", "ITEM-HIST-A")
		out = self._hist("SAT001")
		self.assertEqual(out[0]["item_code"], "ITEM-HIST-A")
		self.assertTrue(out[0]["auto_assignable"])

	def test_historial_no_alimenta_historial(self):
		# 2 humanos ITEM-A + 10 autoasignaciones "Historial" -> count=2, no 12
		c = self._cfdi()
		self._concepto(c, "SAT002", "ITEM-HIST-A", resolution="Manual")
		self._concepto(c, "SAT002", "ITEM-HIST-A", resolution="Manual")
		for _ in range(10):
			self._concepto(c, "SAT002", "ITEM-HIST-A", resolution="Historial")
		out = self._hist("SAT002")
		self.assertIn("2/2", out[0]["match_reason"])  # count real = 2

	def test_company_a_no_alimenta_company_b(self):
		ca = self._cfdi(company="_Test Company")
		self._concepto(ca, "SAT003", "ITEM-HIST-A")
		self._concepto(ca, "SAT003", "ITEM-HIST-A")
		# Consulta desde otra company -> sin evidencia
		out = self._hist("SAT003", company="_Test Company 1")
		self.assertEqual(out, [])

	def test_no_procesar_no_alimenta(self):
		c = self._cfdi(no_procesar=1)
		self._concepto(c, "SAT004", "ITEM-HIST-A")
		self._concepto(c, "SAT004", "ITEM-HIST-A")
		self.assertEqual(self._hist("SAT004"), [])

	def test_excluye_el_propio_concepto(self):
		c = self._cfdi()
		n1 = self._concepto(c, "SAT005", "ITEM-HIST-A")
		self._concepto(c, "SAT005", "ITEM-HIST-A")
		# al resolver n1, no debe contarse a sí mismo (quedaría 1 previo -> no auto)
		out = self._hist("SAT005", current=n1)
		self.assertFalse(out[0]["auto_assignable"])

	def test_gasto_autoasigna_desde_historial(self):
		c = self._cfdi()
		for _ in range(3):
			self._concepto(c, "SAT006", "GASTO-HIST-001")
		out = self._hist("SAT006")
		self.assertEqual(out[0]["item_code"], "GASTO-HIST-001")
		self.assertTrue(out[0]["auto_assignable"])

	def test_assign_confirmacion_historial_se_persiste_como_manual(self):
		from facturacion_mexico.cfdi_recibidos.api import assign_item_to_concepto

		c = self._cfdi()
		n = self._concepto(c, "SAT007", "", resolution="Pendiente")
		assign_item_to_concepto(n, "ITEM-HIST-A", "Historial", match_reason="Historial rfc+sat: 3/3")
		self.assertEqual(frappe.db.get_value("CFDI Recibido Concepto", n, "item_resolution"), "Manual")
		# y la evidencia histórica se conserva
		self.assertIn(
			"Historial", frappe.db.get_value("CFDI Recibido Concepto", n, "item_match_reason") or ""
		)
