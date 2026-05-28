import unittest
from unittest.mock import call, patch

from facturacion_mexico.cfdi_recibidos.services.item_resolver import ItemResolver, _rank_candidates

_BASE = dict(
	sat_product_key="80111500",
	no_identificacion="PROD-001",
	item_group="Honorarios a personas morales residentes nacionales",
	company="Test Company",
	supplier="SUPP-001",
	supplier_rfc="AAA010101AAA",
)


def _gv(mapping=None, item_supplier=None):
	"""side_effect para frappe.db.get_value — despacha por doctype."""

	def _fn(doctype, filters, fieldname, **kwargs):
		if doctype == "CFDI Concepto Mapping":
			return mapping
		if doctype == "Item Supplier":
			return item_supplier
		return None

	return _fn


def _ga_search(expense_groups=None, items=None):
	"""side_effect para frappe.db.get_all en search_candidates."""
	expense_groups = expense_groups or ["Gastos de Servicios"]
	items = items or []

	def _fn(doctype, filters=None, pluck=None, fields=None, **kwargs):
		if doctype == "Item Group":
			return expense_groups
		if doctype == "Item":
			return items
		return []

	return _fn


def _gv_with_item_group(mapping=None, item_supplier=None, item_group_root=None):
	"""side_effect para get_value que incluye Item Group para search_candidates."""

	def _fn(doctype, filters, fieldname, **kwargs):
		if doctype == "CFDI Concepto Mapping":
			return mapping
		if doctype == "Item Supplier":
			return item_supplier
		if doctype == "Item Group":
			return item_group_root
		return None

	return _fn


# ---------------------------------------------------------------------------
# Nivel 1 — Mapeado
# ---------------------------------------------------------------------------


class TestNivel1Mapeado(unittest.TestCase):
	def setUp(self):
		self.r = ItemResolver()

	def test_mapeado_activo_retorna_item(self):
		with patch("frappe.db.get_value", side_effect=_gv("GASTO-SRV-007")):
			result = self.r.propose(**_BASE)
		self.assertEqual(result["item_code"], "GASTO-SRV-007")
		self.assertEqual(result["item_resolution"], "Mapeado")

	def test_mapeado_inactivo_no_retorna_item(self):
		# is_active=0 en BD → filtro is_active=1 no matchea → None en ambos niveles
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			result = self.r.propose(**_BASE)
		self.assertIsNone(result["item_code"])
		self.assertIsNone(result["item_resolution"])

	def test_expense_account_no_retorna_como_mapeado(self):
		# target_type='ExpenseAccount' no matchea filtro target_type='Item'
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			result = self.r.propose(**_BASE)
		self.assertNotEqual(result.get("item_resolution"), "Mapeado")

	def test_nivel1_gana_nivel2_no_se_consulta(self):
		with patch("frappe.db.get_value", side_effect=_gv("GASTO-SRV-007")) as mock_gv:
			result = self.r.propose(**_BASE)
		calls_item_supplier = [c for c in mock_gv.call_args_list if c[0][0] == "Item Supplier"]
		self.assertEqual(len(calls_item_supplier), 0, "Item Supplier no debe consultarse si hay Mapeado")
		self.assertEqual(result["item_code"], "GASTO-SRV-007")
		self.assertEqual(result["item_resolution"], "Mapeado")


# ---------------------------------------------------------------------------
# Nivel 2 — Específico
# ---------------------------------------------------------------------------


class TestNivel2Especifico(unittest.TestCase):
	def setUp(self):
		self.r = ItemResolver()

	def test_especifico_por_no_identificacion(self):
		with patch("frappe.db.get_value", side_effect=_gv(None, "ITEM-ESPECIFICO")):
			result = self.r.propose(**_BASE)
		self.assertEqual(result["item_code"], "ITEM-ESPECIFICO")
		self.assertEqual(result["item_resolution"], "Específico")

	def test_salta_si_no_identificacion_vacio(self):
		kwargs = {**_BASE, "no_identificacion": ""}
		with patch("frappe.db.get_value", side_effect=_gv(None, None)) as mock_gv:
			result = self.r.propose(**kwargs)
		calls_item_supplier = [c for c in mock_gv.call_args_list if c[0][0] == "Item Supplier"]
		self.assertEqual(
			len(calls_item_supplier), 0, "Item Supplier no debe consultarse si no_identificacion está vacío"
		)
		self.assertIsNone(result["item_code"])
		self.assertIsNone(result["item_resolution"])


# ---------------------------------------------------------------------------
# propose() sin match — nunca asigna GASTO-* automáticamente
# ---------------------------------------------------------------------------


class TestProposeSinMatch(unittest.TestCase):
	def setUp(self):
		self.r = ItemResolver()

	def test_sin_match_retorna_none(self):
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			result = self.r.propose(**_BASE)
		self.assertIsNone(result["item_code"])
		self.assertIsNone(result["item_resolution"])

	def test_no_consulta_get_all(self):
		# propose() ya no llama _try_generico → get_all no debe ejecutarse
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			with patch("frappe.db.get_all") as mock_ga:
				result = self.r.propose(**_BASE)
		mock_ga.assert_not_called()
		self.assertIsNone(result["item_code"])

	def test_sin_supplier_ni_no_identificacion_retorna_none(self):
		kwargs = {**_BASE, "supplier": "", "no_identificacion": "", "supplier_rfc": ""}
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			result = self.r.propose(**kwargs)
		self.assertIsNone(result["item_code"])
		self.assertIsNone(result["item_resolution"])


# ---------------------------------------------------------------------------
# suggest_generic_fallback — explícito, no automático
# ---------------------------------------------------------------------------


class TestSuggestGenericFallback(unittest.TestCase):
	def setUp(self):
		self.r = ItemResolver()

	def test_unico_candidato_retorna_generico(self):
		with patch("frappe.db.get_all", return_value=["GASTO-SRV-007"]):
			result = self.r.suggest_generic_fallback("Honorarios a personas morales residentes nacionales")
		self.assertEqual(result["item_code"], "GASTO-SRV-007")
		self.assertEqual(result["item_resolution"], "Genérico")

	def test_multiples_candidatos_no_elige(self):
		with patch("frappe.db.get_all", return_value=["GASTO-SRV-007", "GASTO-SRV-008"]):
			result = self.r.suggest_generic_fallback("Honorarios")
		self.assertIsNone(result)

	def test_item_group_vacio_retorna_none(self):
		result = self.r.suggest_generic_fallback("")
		self.assertIsNone(result)

	def test_sin_candidatos_retorna_none(self):
		with patch("frappe.db.get_all", return_value=[]):
			result = self.r.suggest_generic_fallback("Gastos Generales")
		self.assertIsNone(result)


# ---------------------------------------------------------------------------
# search_candidates — búsqueda asistida
# ---------------------------------------------------------------------------


class TestSearchCandidates(unittest.TestCase):
	def setUp(self):
		self.r = ItemResolver()

	def _setup_mocks(self, items, expense_groups=None):
		expense_groups = expense_groups or ["Gastos de Servicios", "Honorarios"]
		gv_fn = _gv_with_item_group(item_group_root={"lft": 1, "rgt": 100})
		ga_fn = _ga_search(expense_groups=expense_groups, items=items)
		return gv_fn, ga_fn

	def test_retorna_candidatos_validos(self):
		items = [
			{
				"name": "SERV-001",
				"item_name": "Servicio de consultoría",
				"item_group": "Honorarios",
				"stock_uom": "E48 - Unidad de servicio",
			},
			{
				"name": "SERV-002",
				"item_name": "Servicios profesionales",
				"item_group": "Honorarios",
				"stock_uom": "E48 - Unidad de servicio",
			},
		]
		gv_fn, ga_fn = self._setup_mocks(items)
		with patch("frappe.db.get_value", side_effect=gv_fn):
			with patch("frappe.db.get_all", side_effect=ga_fn):
				result = self.r.search_candidates("Consultoría de sistemas", "80111500", "_Test Company")
		self.assertEqual(len(result), 2)

	def test_sin_items_retorna_lista_vacia(self):
		gv_fn, ga_fn = self._setup_mocks([])
		with patch("frappe.db.get_value", side_effect=gv_fn):
			with patch("frappe.db.get_all", side_effect=ga_fn):
				result = self.r.search_candidates("Servicio", "80111500", "_Test Company")
		self.assertEqual(result, [])

	def test_sin_gastos_root_no_filtra_por_grupo(self):
		# Si no existe el grupo "Gastos", retorna candidatos sin filtro de grupo
		items = [
			{
				"name": "SERV-001",
				"item_name": "Servicio",
				"item_group": "Servicios",
				"stock_uom": "E48 - Unidad de servicio",
			},
		]

		def _gv_no_root(doctype, filters, fieldname, **kwargs):
			return None  # Item Group no encontrado

		def _ga_fn(doctype, filters=None, pluck=None, fields=None, **kwargs):
			if doctype == "Item":
				return items
			return []

		with patch("frappe.db.get_value", side_effect=_gv_no_root):
			with patch("frappe.db.get_all", side_effect=_ga_fn):
				result = self.r.search_candidates("Servicio", "80111500", "_Test Company")
		self.assertEqual(len(result), 1)

	def test_ranking_por_coincidencia_descripcion(self):
		items = [
			{
				"name": "ITEM-A",
				"item_name": "Servicio de internet y telecomunicaciones",
				"item_group": "Telecomunicaciones",
				"stock_uom": "E48 - Unidad de servicio",
			},
			{
				"name": "ITEM-B",
				"item_name": "Renta de equipo de oficina",
				"item_group": "Renta",
				"stock_uom": "MON - Mes",
			},
			{
				"name": "ITEM-C",
				"item_name": "Servicio de telefonía celular",
				"item_group": "Telecomunicaciones",
				"stock_uom": "E48 - Unidad de servicio",
			},
		]
		gv_fn, ga_fn = self._setup_mocks(items)
		with patch("frappe.db.get_value", side_effect=gv_fn):
			with patch("frappe.db.get_all", side_effect=ga_fn):
				result = self.r.search_candidates("Servicio de internet", "83111600", "_Test Company")
		# ITEM-A: "servicio"+"de"+"internet" → 3 coincidencias
		# ITEM-C: "servicio"+"de" → 2 coincidencias
		# ITEM-B: "de" → 1 coincidencia
		self.assertEqual(result[0]["name"], "ITEM-A")
		self.assertEqual(result[1]["name"], "ITEM-C")

	def test_maximo_20_resultados(self):
		items = [
			{
				"name": f"ITEM-{i:03d}",
				"item_name": f"Servicio {i}",
				"item_group": "Servicios",
				"stock_uom": "E48 - Unidad de servicio",
			}
			for i in range(30)
		]
		gv_fn, ga_fn = self._setup_mocks(items)
		with patch("frappe.db.get_value", side_effect=gv_fn):
			with patch("frappe.db.get_all", side_effect=ga_fn):
				result = self.r.search_candidates("Servicio", "80111500", "_Test Company")
		self.assertLessEqual(len(result), 20)


# ---------------------------------------------------------------------------
# _rank_candidates — función auxiliar de ranking
# ---------------------------------------------------------------------------


class TestRankCandidates(unittest.TestCase):
	def test_orden_por_coincidencia(self):
		candidates = [
			{"name": "A", "item_name": "Servicio de limpieza"},
			{"name": "B", "item_name": "Servicio de internet y telecomunicaciones"},
			{"name": "C", "item_name": "Renta mensual"},
		]
		result = _rank_candidates(candidates, "Servicio de internet")
		self.assertEqual(result[0]["name"], "B")  # 3 palabras coinciden

	def test_descripcion_vacia_retorna_sin_crash(self):
		candidates = [{"name": "A", "item_name": "Servicio"}]
		result = _rank_candidates(candidates, "")
		self.assertEqual(len(result), 1)

	def test_candidatos_vacios_retorna_lista_vacia(self):
		result = _rank_candidates([], "Servicio de consultoría")
		self.assertEqual(result, [])
