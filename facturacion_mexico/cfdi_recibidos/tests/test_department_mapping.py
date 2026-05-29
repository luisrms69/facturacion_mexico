"""
Tests para mapeo Department → familia SAT en Configuracion CFDI Recibidos.

Valida:
- guardado correcto de mapeo
- auto-populate con todos los departamentos de la empresa
- no duplicar el mismo department
- cuatro familias SAT válidas
- rechazo de familia SAT inválida
- sin impacto en Purchase Invoice ni Accounting Dimensions
"""

import unittest

import frappe

_FAMILIAS_VALIDAS = [
	"601 Gastos generales",
	"602 Gastos de venta",
	"603 Gastos de administración",
	"604 Gastos de fabricación",
]


def _get_or_create_company() -> str:
	company = frappe.defaults.get_global_default("company")
	if company and frappe.db.exists("Company", company):
		return company
	name = frappe.db.get_value("Company", {}, "name")
	if name:
		return name
	co = frappe.new_doc("Company")
	co.company_name = "_Test FM Dept"
	co.abbr = "_TFD"
	co.default_currency = "MXN"
	co.country = "Mexico"
	co.insert(ignore_permissions=True)
	return co.name


def _create_test_department(suffix: str, company: str) -> str:
	dept = frappe.new_doc("Department")
	dept.department_name = f"_TestDept-{suffix}-{frappe.generate_hash()[:4]}"
	dept.company = company
	dept.insert(ignore_permissions=True)
	return dept.name


def _get_or_create_config(company: str) -> str:
	config_name = f"CFDI-REC-CFG-{company}"
	if not frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		cfg = frappe.new_doc("Configuracion CFDI Recibidos")
		cfg.company = company
		cfg.insert(ignore_permissions=True)
	return config_name


class TestDepartmentMapping(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _get_or_create_company()
		cls.config_name = _get_or_create_config(cls.company)

		cls.dept_a = _create_test_department("A", cls.company)
		cls.dept_b = _create_test_department("B", cls.company)
		cls.dept_c = _create_test_department("C", cls.company)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Limpiar filas del mapeo antes de borrar departamentos para evitar broken links en el next run
		for dept in [cls.dept_a, cls.dept_b, cls.dept_c]:
			frappe.db.delete("Mapeo Departamento CFDI Recibido", {"department": dept})
			if frappe.db.exists("Department", dept):
				frappe.delete_doc("Department", dept, force=True)
		frappe.db.commit()
		super().tearDownClass()

	def _clean_config(self):
		"""Limpia familia_sat de todos los departamentos de prueba y retorna config fresco."""
		cfg = frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)
		for row in cfg.mapeo_departamentos:
			if row.department in (self.dept_a, self.dept_b, self.dept_c):
				row.familia_sat = ""
		cfg.save(ignore_permissions=True)
		frappe.db.commit()
		return frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)

	def _set_familia_sat(self, cfg, department: str, familia_sat: str):
		"""Actualiza familia_sat de una fila existente en el mapeo."""
		for row in cfg.mapeo_departamentos:
			if row.department == department:
				row.familia_sat = familia_sat
				return
		frappe.throw(f"Departamento {department} no encontrado en mapeo — auto-populate falló")

	def test_auto_popula_departamentos_en_guardar(self):
		cfg = frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)
		dept_names = {r.department for r in cfg.mapeo_departamentos}
		self.assertIn(self.dept_a, dept_names, "dept_a debe estar en el mapeo tras auto-populate")
		self.assertIn(self.dept_b, dept_names, "dept_b debe estar en el mapeo tras auto-populate")
		self.assertIn(self.dept_c, dept_names, "dept_c debe estar en el mapeo tras auto-populate")

	def test_no_duplica_departamentos_existentes(self):
		cfg = frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)
		count_before = len(cfg.mapeo_departamentos)
		cfg.save(ignore_permissions=True)
		frappe.db.commit()
		cfg_after = frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)
		self.assertEqual(len(cfg_after.mapeo_departamentos), count_before)

	def test_preserva_familia_sat_al_repoblar(self):
		cfg = self._clean_config()
		self._set_familia_sat(cfg, self.dept_a, "602 Gastos de venta")
		cfg.save(ignore_permissions=True)
		frappe.db.commit()

		cfg2 = frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)
		cfg2.save(ignore_permissions=True)
		frappe.db.commit()

		cfg3 = frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)
		dept_a_rows = [r for r in cfg3.mapeo_departamentos if r.department == self.dept_a]
		self.assertEqual(len(dept_a_rows), 1)
		self.assertEqual(dept_a_rows[0].familia_sat, "602 Gastos de venta")

	def test_guarda_mapeo_department_familia_sat(self):
		cfg = self._clean_config()
		self._set_familia_sat(cfg, self.dept_a, "601 Gastos generales")
		cfg.save(ignore_permissions=True)
		frappe.db.commit()

		saved = frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)
		dept_a_rows = [r for r in saved.mapeo_departamentos if r.department == self.dept_a]
		self.assertEqual(len(dept_a_rows), 1)
		self.assertEqual(dept_a_rows[0].familia_sat, "601 Gastos generales")

	def test_acepta_cuatro_familias_sat_validas(self):
		depts = [self.dept_a, self.dept_b, self.dept_c]
		for i, familia in enumerate(_FAMILIAS_VALIDAS[:3]):
			cfg = self._clean_config()
			self._set_familia_sat(cfg, depts[i], familia)
			cfg.save(ignore_permissions=True)
			frappe.db.commit()
			saved = frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)
			rows = [r for r in saved.mapeo_departamentos if r.department == depts[i]]
			self.assertEqual(rows[0].familia_sat, familia, f"Familia no guardada: {familia}")

		cfg = self._clean_config()
		self._set_familia_sat(cfg, self.dept_c, "604 Gastos de fabricación")
		cfg.save(ignore_permissions=True)
		frappe.db.commit()
		saved = frappe.get_doc("Configuracion CFDI Recibidos", self.config_name)
		rows = [r for r in saved.mapeo_departamentos if r.department == self.dept_c]
		self.assertEqual(rows[0].familia_sat, "604 Gastos de fabricación")

	def test_rechaza_familia_sat_invalida(self):
		cfg = self._clean_config()
		self._set_familia_sat(cfg, self.dept_a, "999 Gastos inventados")
		with self.assertRaises(frappe.ValidationError):
			cfg.save(ignore_permissions=True)

	def test_no_toca_purchase_invoice(self):
		pi_count_antes = frappe.db.count("Purchase Invoice")
		cfg = self._clean_config()
		self._set_familia_sat(cfg, self.dept_a, "601 Gastos generales")
		cfg.save(ignore_permissions=True)
		frappe.db.commit()
		self.assertEqual(frappe.db.count("Purchase Invoice"), pi_count_antes)

	def test_no_crea_accounting_dimensions(self):
		ad_count_antes = frappe.db.count("Accounting Dimension")
		cfg = self._clean_config()
		self._set_familia_sat(cfg, self.dept_b, "603 Gastos de administración")
		cfg.save(ignore_permissions=True)
		frappe.db.commit()
		self.assertEqual(frappe.db.count("Accounting Dimension"), ad_count_antes)
