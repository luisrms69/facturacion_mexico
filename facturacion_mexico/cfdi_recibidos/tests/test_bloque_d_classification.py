"""
Tests de Bloque D — clasificación automática de conceptos (UI/API).

Valida:
1. propose_item nivel 3: retorna item_code e item_resolution "Genérico"
2. classify_all_concepts: actualiza status a "Clasificado" cuando todos reciben item_code
3. validate(): auto-deriva item_group cuando item_code está presente y item_group vacío
4. classify_all_concepts: no sobreescribe conceptos que ya tienen item_code
5. classify_all_concepts: rechaza ítems con is_sales_item=1 o is_stock_item=1
6-14. validate_expense_item: cobertura completa de condiciones de rechazo y aceptación
"""

import unittest
from unittest.mock import patch

import frappe

TEST_COMPANY = "_Test Company"
_UUID_BASE = "BLOQ-D-0001-0001-"

_CONCEPTO_BASE = {
	"sat_product_key": "80111500",
	"description": "Servicio test Bloque D",
	"quantity": 1,
	"unit_key": "E48",
	"unit": "Servicio",
	"unit_price": 100,
	"amount": 100,
	"discount": 0,
	"tax_object": "02",
	"taxes_json": "{}",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_gastos_group() -> str:
	if not frappe.db.exists("Item Group", "Gastos"):
		root = frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name") or "All Item Groups"
		g = frappe.new_doc("Item Group")
		g.item_group_name = "Gastos"
		g.parent_item_group = root
		g.insert(ignore_permissions=True)
		frappe.db.commit()
	return "Gastos"


def _get_or_create_supplier(tax_id="BLDTEST001RFC") -> str:
	existing = frappe.db.get_value("Supplier", {"tax_id": tax_id}, "name")
	if existing:
		return existing
	sg = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	if not sg:
		g = frappe.new_doc("Supplier Group")
		g.supplier_group_name = "_Test SG BLD"
		g.insert(ignore_permissions=True)
		frappe.db.commit()
		sg = g.name
	sup = frappe.new_doc("Supplier")
	sup.supplier_name = "Proveedor Test BLD"
	sup.supplier_group = sg
	sup.tax_id = tax_id
	sup.insert(ignore_permissions=True)
	frappe.db.commit()
	return sup.name


def _get_or_create_dept() -> str:
	existing = frappe.db.get_value(
		"Department", {"department_name": "_Test Dept BLD", "company": TEST_COMPANY}, "name"
	)
	if existing:
		return existing
	doc = frappe.new_doc("Department")
	doc.department_name = "_Test Dept BLD"
	doc.company = TEST_COMPANY
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _get_or_create_item_group(name: str) -> str:
	"""Crea o retorna un Item Group hoja bajo el árbol 'Gastos'. Reparenta si es necesario."""
	_ensure_gastos_group()
	existing = frappe.db.get_value("Item Group", {"item_group_name": name}, "name")
	if existing:
		gastos = frappe.db.get_value("Item Group", "Gastos", ["lft", "rgt"], as_dict=True)
		ig_data = frappe.db.get_value("Item Group", existing, ["lft", "rgt"], as_dict=True)
		if not (ig_data.lft > gastos.lft and ig_data.rgt < gastos.rgt):
			doc = frappe.get_doc("Item Group", existing)
			doc.parent_item_group = "Gastos"
			doc.save(ignore_permissions=True)
			frappe.db.commit()
		return existing
	doc = frappe.new_doc("Item Group")
	doc.item_group_name = name
	doc.parent_item_group = "Gastos"
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _get_or_create_item_group_outside_gastos(name: str) -> str:
	"""Crea un Item Group fuera del árbol 'Gastos' (bajo root). Solo para tests de rechazo."""
	if frappe.db.exists("Item Group", name):
		return name
	root = frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name") or "All Item Groups"
	doc = frappe.new_doc("Item Group")
	doc.item_group_name = name
	doc.parent_item_group = root
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return name


def _get_or_create_item(
	item_code: str,
	item_group: str,
	is_stock_item=0,
	is_sales_item=0,
	is_purchase_item=None,
) -> str:
	computed_purchase = 0 if is_sales_item else 1
	if is_purchase_item is None:
		is_purchase_item = computed_purchase
	if frappe.db.exists("Item", item_code):
		# Actualizar flags si difieren (idempotente para reruns del test suite)
		frappe.db.set_value(
			"Item",
			item_code,
			{
				"is_stock_item": is_stock_item,
				"is_sales_item": is_sales_item,
				"is_purchase_item": is_purchase_item,
				"stock_uom": "H87 - Pieza",
			},
		)
		frappe.db.commit()
		return item_code
	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = item_code
	doc.item_group = item_group
	doc.is_stock_item = is_stock_item
	doc.is_sales_item = is_sales_item
	doc.is_purchase_item = is_purchase_item
	doc.stock_uom = "H87 - Pieza"
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _make_cfdi(uuid_suffix: str, supplier: str, department: str, conceptos=None) -> str:
	doc = frappe.new_doc("CFDI Recibido")
	doc.company = TEST_COMPANY
	doc.uuid = f"{_UUID_BASE}{uuid_suffix}"
	doc.supplier_rfc = "BLDTEST001RFC"
	doc.supplier_name = "Proveedor Test BLD"
	doc.supplier = supplier
	doc.department = department
	doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
	doc.status = "Falta clasificación"
	doc.cfdi_type = "I"
	doc.xml_hash = frappe.generate_hash()[:64]
	for c in conceptos or []:
		doc.append("conceptos", c)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _cleanup(uuid_suffix: str):
	name = frappe.db.get_value("CFDI Recibido", {"uuid": f"{_UUID_BASE}{uuid_suffix}"}, "name")
	if name:
		frappe.delete_doc("CFDI Recibido", name, force=True)
		frappe.db.commit()


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestProposeItemEndpoint(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = _get_or_create_supplier()
		cls.dept = _get_or_create_dept()
		cls.ig = _get_or_create_item_group("_Test IG BLD Proponer")
		cls.item = _get_or_create_item("GASTO-BLD-PROP-001", cls.ig)

	def setUp(self):
		_cleanup("PRP01")

	def tearDown(self):
		_cleanup("PRP01")

	def test_propose_item_nivel3_retorna_propuesta(self):
		"""propose_item retorna item_code e item_resolution 'Genérico' por nivel 3."""
		from facturacion_mexico.cfdi_recibidos.api import propose_item

		name = _make_cfdi("PRP01", self.supplier, self.dept)

		result = propose_item(
			cfdi_recibido=name,
			sat_product_key="80111500",
			no_identificacion="",
			item_group=self.ig,
		)

		self.assertEqual(result["item_code"], self.item)
		self.assertEqual(result["item_resolution"], "Genérico")


class TestClassifyAllConcepts(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = _get_or_create_supplier()
		cls.dept = _get_or_create_dept()
		cls.ig = _get_or_create_item_group("_Test IG BLD ClassAll")
		cls.item = _get_or_create_item("GASTO-BLD-CLSA-001", cls.ig)

	def setUp(self):
		for s in ["CA01", "CA02", "CA03"]:
			_cleanup(s)

	def tearDown(self):
		for s in ["CA01", "CA02", "CA03"]:
			_cleanup(s)

	def test_classify_all_actualiza_status_a_clasificado(self):
		"""classify_all_concepts asigna item_code y cambia status a 'Clasificado'."""
		from facturacion_mexico.cfdi_recibidos.api import classify_all_concepts

		name = _make_cfdi(
			"CA01",
			self.supplier,
			self.dept,
			conceptos=[{**_CONCEPTO_BASE, "item_group": self.ig}],
		)

		result = classify_all_concepts(cfdi_recibido=name)

		self.assertEqual(result["actualizados"], 1)
		self.assertEqual(result["sin_match"], 0)
		self.assertEqual(result["nuevo_status"], "Clasificado")

		doc = frappe.get_doc("CFDI Recibido", name)
		self.assertEqual(doc.conceptos[0].item_code, self.item)
		self.assertEqual(doc.conceptos[0].item_resolution, "Genérico")

	def test_classify_all_no_sobrescribe_item_code_existente(self):
		"""classify_all_concepts no toca conceptos que ya tienen item_code."""
		from facturacion_mexico.cfdi_recibidos.api import classify_all_concepts

		name = _make_cfdi(
			"CA02",
			self.supplier,
			self.dept,
			conceptos=[{**_CONCEPTO_BASE, "item_group": self.ig, "item_code": self.item}],
		)

		result = classify_all_concepts(cfdi_recibido=name)

		self.assertEqual(result["actualizados"], 0)

		doc = frappe.get_doc("CFDI Recibido", name)
		self.assertEqual(doc.conceptos[0].item_code, self.item)

	def test_classify_all_rechaza_item_ventas(self):
		"""classify_all_concepts no asigna ítems con is_sales_item=1."""
		from facturacion_mexico.cfdi_recibidos.api import classify_all_concepts
		from facturacion_mexico.cfdi_recibidos.services import item_resolver as ir_module

		ig_sales = _get_or_create_item_group("_Test IG BLD Sales")
		sales_item = _get_or_create_item("GASTO-BLD-SALES-D01", ig_sales, is_sales_item=1)

		name = _make_cfdi(
			"CA03",
			self.supplier,
			self.dept,
			conceptos=[{**_CONCEPTO_BASE, "item_group": ig_sales}],
		)

		with patch.object(
			ir_module.ItemResolver,
			"propose",
			return_value={"item_code": sales_item, "item_resolution": "Genérico"},
		):
			result = classify_all_concepts(cfdi_recibido=name)

		self.assertEqual(result["actualizados"], 0)
		self.assertEqual(result["sin_match"], 1)

		doc = frappe.get_doc("CFDI Recibido", name)
		self.assertFalse(doc.conceptos[0].item_code)


class TestValidateDerivesItemGroup(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = _get_or_create_supplier()
		cls.dept = _get_or_create_dept()
		cls.ig = _get_or_create_item_group("_Test IG BLD Derive")
		cls.item = _get_or_create_item("GASTO-BLD-DERV-001", cls.ig)

	def setUp(self):
		for s in ["DRV01", "DRV02"]:
			_cleanup(s)

	def tearDown(self):
		for s in ["DRV01", "DRV02"]:
			_cleanup(s)

	def test_validate_deriva_item_group_cuando_esta_vacio(self):
		"""validate() auto-asigna item_group desde item.item_group cuando estaba vacío."""
		name = _make_cfdi(
			"DRV01",
			self.supplier,
			self.dept,
			conceptos=[
				{
					**_CONCEPTO_BASE,
					"item_code": self.item,
					# item_group vacío a propósito
				}
			],
		)

		doc = frappe.get_doc("CFDI Recibido", name)
		self.assertEqual(doc.conceptos[0].item_group, self.ig)

	def test_validate_sobrescribe_item_group_diferente(self):
		"""validate() sobreescribe item_group con el del Item, sin lanzar error."""
		ig_otro = _get_or_create_item_group("_Test IG BLD DeriveOtro")

		name = _make_cfdi(
			"DRV02",
			self.supplier,
			self.dept,
			conceptos=[
				{
					**_CONCEPTO_BASE,
					"item_code": self.item,
					"item_group": ig_otro,  # diferente al item_group del item
				}
			],
		)

		doc = frappe.get_doc("CFDI Recibido", name)
		# item_group debe ser el del Item, no el que se pasó
		self.assertEqual(doc.conceptos[0].item_group, self.ig)


class TestValidateExpenseItem(unittest.TestCase):
	"""Cobertura completa de validate_expense_item (services/item_validator.py)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.ig_valid = _get_or_create_item_group("_Test IG BLD ValidHelper")
		cls.item_valid = _get_or_create_item("GASTO-BLD-VLD-001", cls.ig_valid)
		cls.item_stock = _get_or_create_item("GASTO-BLD-VLD-002", cls.ig_valid, is_stock_item=1)
		cls.item_no_purchase = _get_or_create_item("GASTO-BLD-VLD-003", cls.ig_valid, is_purchase_item=0)
		# Item con is_purchase_item=1 y is_sales_item=1 para testear rechazo por ventas
		cls.item_ventas = _get_or_create_item(
			"GASTO-BLD-VLD-004", cls.ig_valid, is_sales_item=1, is_purchase_item=1
		)
		cls.ig_out = _get_or_create_item_group_outside_gastos("_Test IG BLD OutGastos")
		cls.item_out = _get_or_create_item("GASTO-BLD-VLD-005", cls.ig_out)

		# Grupo padre (is_group=1): set explícito — Frappe no lo propaga automáticamente
		_ensure_gastos_group()
		if not frappe.db.exists("Item Group", "_Test IG BLD ParentVld"):
			pg = frappe.new_doc("Item Group")
			pg.item_group_name = "_Test IG BLD ParentVld"
			pg.parent_item_group = "Gastos"
			pg.is_group = 1
			pg.insert(ignore_permissions=True)
			frappe.db.commit()
		else:
			frappe.db.set_value("Item Group", "_Test IG BLD ParentVld", "is_group", 1)
			frappe.db.commit()
		cls.ig_parent = "_Test IG BLD ParentVld"
		cls.item_in_parent = _get_or_create_item("GASTO-BLD-VLD-006", cls.ig_parent)

	def setUp(self):
		_cleanup("VLD08")
		_cleanup("VLD09")

	def tearDown(self):
		_cleanup("VLD08")
		_cleanup("VLD09")

	def _vi(self, item_code):
		from facturacion_mexico.cfdi_recibidos.services.item_validator import validate_expense_item

		return validate_expense_item(item_code)

	def test_item_inexistente_retorna_false(self):
		ok, msg = self._vi("ITEM-NO-EXISTE-XXXXXX")
		self.assertFalse(ok)
		self.assertIn("no existe", msg)

	def test_item_stock_retorna_false(self):
		ok, msg = self._vi(self.item_stock)
		self.assertFalse(ok)
		self.assertIn("inventario", msg)

	def test_item_no_purchase_retorna_false(self):
		ok, msg = self._vi(self.item_no_purchase)
		self.assertFalse(ok)
		self.assertIn("no es de compra", msg)

	def test_item_ventas_retorna_false(self):
		ok, msg = self._vi(self.item_ventas)
		self.assertFalse(ok)
		self.assertIn("venta", msg.lower())

	def test_grupo_padre_retorna_false(self):
		ok, msg = self._vi(self.item_in_parent)
		self.assertFalse(ok)
		self.assertIn("padre", msg.lower())

	def test_grupo_fuera_gastos_retorna_false(self):
		ok, msg = self._vi(self.item_out)
		self.assertFalse(ok)
		self.assertIn("Gastos", msg)

	def test_item_valido_retorna_true(self):
		ok, msg = self._vi(self.item_valid)
		self.assertTrue(ok)
		self.assertEqual(msg, "")

	def test_validate_lanza_error_por_item_invalido(self):
		"""validate() lanza ValidationError si item_code no pasa validate_expense_item."""
		supplier = _get_or_create_supplier()
		dept = _get_or_create_dept()
		with self.assertRaises(frappe.ValidationError):
			_make_cfdi(
				"VLD08",
				supplier,
				dept,
				conceptos=[{**_CONCEPTO_BASE, "item_code": self.item_stock}],
			)

	def test_classify_all_rechaza_item_no_purchase(self):
		"""classify_all_concepts no asigna ítems con is_purchase_item=0."""
		from facturacion_mexico.cfdi_recibidos.api import classify_all_concepts
		from facturacion_mexico.cfdi_recibidos.services import item_resolver as ir_module

		supplier = _get_or_create_supplier()
		dept = _get_or_create_dept()
		name = _make_cfdi("VLD09", supplier, dept, conceptos=[_CONCEPTO_BASE])

		with patch.object(
			ir_module.ItemResolver,
			"propose",
			return_value={"item_code": self.item_no_purchase, "item_resolution": "Genérico"},
		):
			result = classify_all_concepts(cfdi_recibido=name)

		self.assertEqual(result["actualizados"], 0)
		self.assertEqual(result["sin_match"], 1)
