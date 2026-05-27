"""
Tests de Bloque B — clasificación de Items en CFDI Recibido Concepto.

Valida:
- item_group inconsistente con item.item_group → frappe.throw() al guardar
- item_group consistente → guarda sin error
- compute_stage: conceptos sin item_code → "Falta clasificación"
- compute_stage: todos los conceptos con item_code → "Clasificado"
- compute_stage: sin conceptos + dept → "Clasificado" (vacuously true)
"""

import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.status_manager import compute_stage

TEST_COMPANY = "_Test Company"
_UUID_BASE = "ITEM-CLSF-0001-0001-"
_TEST_ITEM_GROUP_NAME = "_Test IG Bloque B"


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _get_or_create_supplier() -> str:
	existing = frappe.db.get_value("Supplier", {"tax_id": "IBTEST001RFC"}, "name")
	if existing:
		return existing
	sg = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	if not sg:
		g = frappe.new_doc("Supplier Group")
		g.supplier_group_name = "_Test SG IB"
		g.insert(ignore_permissions=True)
		sg = g.name
	sup = frappe.new_doc("Supplier")
	sup.supplier_name = "Proveedor Test IB"
	sup.supplier_group = sg
	sup.tax_id = "IBTEST001RFC"
	sup.insert(ignore_permissions=True)
	frappe.db.commit()
	return sup.name


def _get_or_create_dept() -> str:
	existing = frappe.db.get_value(
		"Department", {"department_name": "_Test Dept IB", "company": TEST_COMPANY}, "name"
	)
	if existing:
		return existing
	doc = frappe.new_doc("Department")
	doc.department_name = "_Test Dept IB"
	doc.company = TEST_COMPANY
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _ensure_gastos_group() -> str:
	if not frappe.db.exists("Item Group", "Gastos"):
		root = frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name") or "All Item Groups"
		g = frappe.new_doc("Item Group")
		g.item_group_name = "Gastos"
		g.parent_item_group = root
		g.insert(ignore_permissions=True)
		frappe.db.commit()
	return "Gastos"


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


def _get_or_create_item(item_code: str, item_group: str) -> str:
	if frappe.db.exists("Item", item_code):
		return item_code
	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = item_code
	doc.item_group = item_group
	doc.is_stock_item = 0
	doc.is_purchase_item = 1
	doc.is_sales_item = 0
	doc.stock_uom = frappe.db.get_value("Stock Settings", None, "stock_uom") or "Nos"
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _make_cfdi(uuid_suffix: str, supplier: str, department: str, conceptos: list | None = None) -> str:
	doc = frappe.new_doc("CFDI Recibido")
	doc.company = TEST_COMPANY
	doc.uuid = f"{_UUID_BASE}{uuid_suffix}"
	doc.supplier_rfc = "IBTEST001RFC"
	doc.supplier_name = "Proveedor Test IB"
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


# ─── FakeDoc para tests de compute_stage sin BD ───────────────────────────────


class _FakeDoc:
	def __init__(self, supplier=None, department=None, conceptos=None):
		self.supplier = supplier
		self.department = department
		self.conceptos = conceptos or []
		self.company = TEST_COMPANY
		self.supplier_rfc = ""


class _FakeConceptoConItem:
	item_code = "SOME-ITEM-001"


class _FakeConceptoSinItem:
	pass  # sin item_code → getattr retorna None


# ─── Tests compute_stage (sin BD) ────────────────────────────────────────────


class TestComputeStageItemCode(unittest.TestCase):
	def test_sin_conceptos_retorna_clasificado(self):
		doc = _FakeDoc(supplier="PROV-001", department="IT", conceptos=[])
		self.assertEqual(compute_stage(doc), "Clasificado")

	def test_concepto_sin_item_code_retorna_falta_clasificacion(self):
		doc = _FakeDoc(supplier="PROV-001", department="IT", conceptos=[_FakeConceptoSinItem()])
		self.assertEqual(compute_stage(doc), "Falta clasificación")

	def test_concepto_con_item_code_retorna_clasificado(self):
		doc = _FakeDoc(supplier="PROV-001", department="IT", conceptos=[_FakeConceptoConItem()])
		self.assertEqual(compute_stage(doc), "Clasificado")

	def test_mezcla_retorna_falta_clasificacion(self):
		"""Un concepto sin item_code es suficiente para "Falta clasificación"."""
		doc = _FakeDoc(
			supplier="PROV-001",
			department="IT",
			conceptos=[_FakeConceptoConItem(), _FakeConceptoSinItem()],
		)
		self.assertEqual(compute_stage(doc), "Falta clasificación")


# ─── Tests validación item_group vs item.item_group ───────────────────────────


class TestItemGroupConsistency(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = _get_or_create_supplier()
		cls.dept = _get_or_create_dept()
		cls.ig_a = _get_or_create_item_group("_Test IG A Bloque B")
		cls.ig_b = _get_or_create_item_group("_Test IG B Bloque B")
		cls.item_in_a = _get_or_create_item("_TEST-ITEM-IG-A", cls.ig_a)

	def setUp(self):
		for s in ["IB01", "IB02"]:
			_cleanup(s)

	def tearDown(self):
		for s in ["IB01", "IB02"]:
			_cleanup(s)

	def test_item_group_diferente_es_sobreescrito(self):
		"""validate() sobreescribe item_group del concepto con el del Item, sin lanzar error."""
		name = _make_cfdi(
			"IB01",
			self.supplier,
			self.dept,
			conceptos=[
				{
					"sat_product_key": "80141600",
					"description": "Servicio X",
					"quantity": 1,
					"unit_key": "E48",
					"unit": "Servicio",
					"unit_price": 100,
					"amount": 100,
					"discount": 0,
					"tax_object": "02",
					"taxes_json": "{}",
					"item_group": self.ig_b,  # diferente al item_group del item
					"item_code": self.item_in_a,  # pertenece a ig_a
				}
			],
		)
		doc = frappe.get_doc("CFDI Recibido", name)
		self.assertEqual(doc.conceptos[0].item_group, self.ig_a)

	def test_item_group_consistente_guarda_ok(self):
		"""item_group del concepto == item_group del Item → guarda sin error."""
		name = _make_cfdi(
			"IB02",
			self.supplier,
			self.dept,
			conceptos=[
				{
					"sat_product_key": "80141600",
					"description": "Servicio Y",
					"quantity": 1,
					"unit_key": "E48",
					"unit": "Servicio",
					"unit_price": 100,
					"amount": 100,
					"discount": 0,
					"tax_object": "02",
					"taxes_json": "{}",
					"item_group": self.ig_a,  # coincide con item_group del item
					"item_code": self.item_in_a,
				}
			],
		)
		self.assertIsNotNone(name)


# ─── Test integración: compute_stage con CFDI real ────────────────────────────


class TestComputeStageBD(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = _get_or_create_supplier()
		cls.dept = _get_or_create_dept()
		cls.ig = _get_or_create_item_group("_Test IG BD Bloque B")
		cls.item = _get_or_create_item("_TEST-ITEM-BD", cls.ig)

	def setUp(self):
		for s in ["IB03", "IB04"]:
			_cleanup(s)

	def tearDown(self):
		for s in ["IB03", "IB04"]:
			_cleanup(s)

	def test_cfdi_sin_item_code_en_bd_retorna_falta_clasificacion(self):
		name = _make_cfdi(
			"IB03",
			self.supplier,
			self.dept,
			conceptos=[
				{
					"sat_product_key": "80141600",
					"description": "Sin item",
					"quantity": 1,
					"unit_key": "E48",
					"unit": "Servicio",
					"unit_price": 50,
					"amount": 50,
					"discount": 0,
					"tax_object": "02",
					"taxes_json": "{}",
				}
			],
		)
		doc = frappe.get_doc("CFDI Recibido", name)
		self.assertEqual(compute_stage(doc), "Falta clasificación")

	def test_cfdi_con_item_code_en_bd_retorna_clasificado(self):
		name = _make_cfdi(
			"IB04",
			self.supplier,
			self.dept,
			conceptos=[
				{
					"sat_product_key": "80141600",
					"description": "Con item",
					"quantity": 1,
					"unit_key": "E48",
					"unit": "Servicio",
					"unit_price": 50,
					"amount": 50,
					"discount": 0,
					"tax_object": "02",
					"taxes_json": "{}",
					"item_group": self.ig,
					"item_code": self.item,
				}
			],
		)
		doc = frappe.get_doc("CFDI Recibido", name)
		self.assertEqual(compute_stage(doc), "Clasificado")
