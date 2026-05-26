"""
Tests para asignación de Department a CFDI Recibidos (C.2).

Valida:
- compute_stage retorna "Falta departamento" cuando supplier OK, conceptos OK, sin dept
- compute_stage retorna "Listo" cuando supplier + conceptos + dept OK
- get_department_candidates incluye CFDI con supplier pero sin dept
- get_department_candidates excluye: sin supplier, con dept, no_procesar, terminales
- assign_departments asigna dept válido y recalcula status
- assign_departments omite CFDI con dept ya asignado
- assign_departments omite dept no registrado en Configuracion CFDI Recibidos
- assign_departments retorna contadores correctos
"""

import json
import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.api import assign_departments, get_department_candidates
from facturacion_mexico.cfdi_recibidos.services.status_manager import compute_stage

TEST_COMPANY = "_Test Company"
_UUID_BASE = "DEPT-ASIG-0001-0001-"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get_or_create_supplier(rfc: str) -> str:
	existing = frappe.db.get_value("Supplier", {"tax_id": rfc}, "name")
	if existing:
		return existing
	sg = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	if not sg:
		g = frappe.new_doc("Supplier Group")
		g.supplier_group_name = "_Test SG Dept"
		g.insert(ignore_permissions=True)
		sg = g.name
	sup = frappe.new_doc("Supplier")
	sup.supplier_name = f"Proveedor {rfc}"
	sup.supplier_group = sg
	sup.tax_id = rfc
	sup.insert(ignore_permissions=True)
	frappe.db.commit()
	return sup.name


def _make_cfdi(
	uuid_suffix: str,
	company: str = TEST_COMPANY,
	supplier: str | None = None,
	department: str | None = None,
	status: str = "Falta proveedor",
	no_procesar: int = 0,
) -> str:
	doc = frappe.new_doc("CFDI Recibido")
	doc.company = company
	doc.uuid = f"{_UUID_BASE}{uuid_suffix}"
	doc.supplier_rfc = "TEST_RFC_DA00"
	doc.supplier_name = "Proveedor Test DA"
	doc.receiver_rfc = frappe.db.get_value("Company", company, "tax_id") or "RFC000000000"
	doc.status = status
	doc.cfdi_type = "I"
	doc.xml_hash = frappe.generate_hash()[:64]
	doc.no_procesar = no_procesar
	if supplier:
		doc.supplier = supplier
	if department:
		doc.department = department
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _cleanup(uuid_suffix: str):
	name = frappe.db.get_value("CFDI Recibido", {"uuid": f"{_UUID_BASE}{uuid_suffix}"}, "name")
	if name:
		frappe.delete_doc("CFDI Recibido", name, force=True)
		frappe.db.commit()


def _get_or_create_dept(dept_name: str, company: str) -> str:
	"""Crea o recupera un Department por department_name + company."""
	existing = frappe.db.get_value("Department", {"department_name": dept_name, "company": company}, "name")
	if existing:
		return existing
	doc = frappe.new_doc("Department")
	doc.department_name = dept_name
	doc.company = company
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _get_or_create_config(company: str) -> str:
	config_name = f"CFDI-REC-CFG-{company}"
	if not frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		cfg = frappe.new_doc("Configuracion CFDI Recibidos")
		cfg.company = company
		cfg.insert(ignore_permissions=True)
		frappe.db.commit()
	return config_name


def _add_dept_to_config(config_name: str, dept_name: str):
	"""Agrega un departamento al mapeo de Configuracion CFDI Recibidos si aún no está."""
	cfg = frappe.get_doc("Configuracion CFDI Recibidos", config_name)
	existing = {row.department for row in cfg.mapeo_departamentos}
	if dept_name not in existing:
		cfg.append("mapeo_departamentos", {"department": dept_name})
		cfg.save(ignore_permissions=True)
		frappe.db.commit()


# ─── Mock doc para tests de compute_stage ────────────────────────────────────


class _FakeDoc:
	def __init__(self, supplier=None, department=None, conceptos=None):
		self.supplier = supplier
		self.department = department
		self.conceptos = conceptos or []
		self.company = TEST_COMPANY
		self.supplier_rfc = ""


# ─── Tests compute_stage ─────────────────────────────────────────────────────


class TestComputeStageConDepartamento(unittest.TestCase):
	def test_sin_supplier_retorna_falta_proveedor(self):
		doc = _FakeDoc(supplier=None, department=None)
		self.assertEqual(compute_stage(doc), "Falta proveedor")

	def test_con_supplier_sin_dept_sin_conceptos_retorna_falta_departamento(self):
		doc = _FakeDoc(supplier="PROV-001", department=None, conceptos=[])
		# Sin conceptos no hay Falta clasificación → pasa a chequear dept
		self.assertEqual(compute_stage(doc), "Falta departamento")

	def test_con_supplier_con_dept_sin_conceptos_retorna_listo(self):
		doc = _FakeDoc(supplier="PROV-001", department="IT", conceptos=[])
		self.assertEqual(compute_stage(doc), "Listo")

	def test_con_supplier_con_dept_con_concepto_sin_regla_retorna_falta_clasificacion(self):
		"""Dept asignado pero concepto sin regla → sigue siendo Falta clasificación."""

		class FakeConcepto:
			sat_product_key = "99999999-NOEXISTE-TEST"

		doc = _FakeDoc(supplier="PROV-001", department="IT", conceptos=[FakeConcepto()])
		result = compute_stage(doc)
		# La clave inexistente no tiene regla → "Falta clasificación"
		self.assertEqual(result, "Falta clasificación")

	def test_con_supplier_sin_dept_con_concepto_sin_regla_retorna_falta_departamento(self):
		"""Department tiene prioridad sobre clasificación: si falta dept, no se evalúan conceptos."""

		class FakeConcepto:
			sat_product_key = "99999999-NOEXISTE-TEST"

		doc = _FakeDoc(supplier="PROV-001", department=None, conceptos=[FakeConcepto()])
		self.assertEqual(compute_stage(doc), "Falta departamento")


# ─── Tests get_department_candidates ─────────────────────────────────────────


class TestGetDepartmentCandidates(unittest.TestCase):
	_RFC = "GTCAND001AAAA"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = _get_or_create_supplier(cls._RFC)

	def setUp(self):
		for s in ["GC01", "GC02", "GC03", "GC04", "GC05"]:
			_cleanup(s)

	def tearDown(self):
		for s in ["GC01", "GC02", "GC03", "GC04", "GC05"]:
			_cleanup(s)

	def _candidate_names(self, company=""):
		return {c["name"] for c in get_department_candidates(company)}

	def test_incluye_cfdi_con_supplier_sin_dept(self):
		cfdi = _make_cfdi("GC01", supplier=self.supplier, status="Proveedor encontrado")
		self.assertIn(cfdi, self._candidate_names())

	def test_excluye_cfdi_sin_supplier(self):
		cfdi = _make_cfdi("GC02", status="Falta proveedor")
		self.assertNotIn(cfdi, self._candidate_names())

	def test_excluye_cfdi_con_dept_asignado(self):
		dept_name = _get_or_create_dept("_TestDept GTC01", TEST_COMPANY)
		cfdi = _make_cfdi("GC03", supplier=self.supplier, department=dept_name, status="Listo")
		self.assertNotIn(cfdi, self._candidate_names())

	def test_excluye_no_procesar(self):
		cfdi = _make_cfdi("GC04", supplier=self.supplier, status="Proveedor encontrado", no_procesar=1)
		self.assertNotIn(cfdi, self._candidate_names())

	def test_filtro_por_empresa(self):
		cfdi = _make_cfdi("GC05", supplier=self.supplier, status="Proveedor encontrado")
		# Filtro con empresa correcta: incluye
		self.assertIn(cfdi, self._candidate_names(TEST_COMPANY))
		# Filtro con empresa distinta: excluye
		self.assertNotIn(cfdi, self._candidate_names("_Empresa Inexistente XYZ"))


# ─── Tests assign_departments ─────────────────────────────────────────────────


class TestAssignDepartments(unittest.TestCase):
	_RFC = "ASSIGNDEPT001A"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = _get_or_create_supplier(cls._RFC)
		cls.dept_valido = _get_or_create_dept("_TestDept Valido AD", TEST_COMPANY)
		cls.dept_invalido = "_TestDept Inexistente En Config XYZ"
		cls.config_name = _get_or_create_config(TEST_COMPANY)
		_add_dept_to_config(cls.config_name, cls.dept_valido)

	def setUp(self):
		for s in ["AD01", "AD02", "AD03", "AD04", "AD05"]:
			_cleanup(s)

	def tearDown(self):
		for s in ["AD01", "AD02", "AD03", "AD04", "AD05"]:
			_cleanup(s)

	def _assign(self, mapping: dict) -> dict:
		"""Llama assign_departments con el dict serializado como JSON (como lo haría la API HTTP)."""
		return assign_departments(json.dumps(mapping))

	def test_asigna_dept_valido_y_actualiza_status(self):
		cfdi = _make_cfdi("AD01", supplier=self.supplier, status="Falta departamento")
		result = self._assign({cfdi: self.dept_valido})

		self.assertEqual(result["asignados"], 1)
		self.assertEqual(result["omitidos"], 0)

		dept_en_doc = frappe.db.get_value("CFDI Recibido", cfdi, "department")
		self.assertEqual(dept_en_doc, self.dept_valido)

		# Sin conceptos + dept asignado → Listo
		status = frappe.db.get_value("CFDI Recibido", cfdi, "status")
		self.assertEqual(status, "Listo")

	def test_omite_cfdi_con_dept_ya_asignado(self):
		cfdi = _make_cfdi(
			"AD02",
			supplier=self.supplier,
			department=self.dept_valido,
			status="Listo",
		)
		result = self._assign({cfdi: self.dept_valido})
		self.assertEqual(result["asignados"], 0)
		self.assertEqual(result["omitidos"], 1)

	def test_omite_dept_no_en_config(self):
		cfdi = _make_cfdi("AD03", supplier=self.supplier, status="Falta departamento")
		result = self._assign({cfdi: self.dept_invalido})
		self.assertEqual(result["asignados"], 0)
		self.assertEqual(result["omitidos"], 1)
		dept_en_doc = frappe.db.get_value("CFDI Recibido", cfdi, "department")
		self.assertIn(dept_en_doc, [None, ""])

	def test_omite_dept_vacio(self):
		cfdi = _make_cfdi("AD04", supplier=self.supplier, status="Falta departamento")
		result = self._assign({cfdi: ""})
		self.assertEqual(result["asignados"], 0)
		self.assertEqual(result["omitidos"], 1)

	def test_resultado_contiene_campos_correctos(self):
		cfdi = _make_cfdi("AD05", supplier=self.supplier, status="Falta departamento")
		result = self._assign({cfdi: self.dept_valido})
		for key in ["asignados", "omitidos", "errores"]:
			self.assertIn(key, result)
		self.assertIsInstance(result["errores"], list)
