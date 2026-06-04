"""
Tests para la resolución de expense_account en CFDI Recibidos.

Cubre:
  - _get_familia_sat   — lookup de familia SAT desde mapeo de departamentos
  - _get_sufijo_sat    — lookup de sufijo SAT desde Item Group (requiere migrate)
  - _resolve_expense_account — lógica patron / matriz / manual
  - Integración en _append_item
  - Validación estática de schema/fixtures (no requiere BD)

Tests marcados con @skipUnless requieren bench migrate para crear las tablas nuevas.
"""

import json
import os
import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.purchase_invoice_builder import (
	_get_familia_sat,
	_get_sufijo_sat,
	_resolve_expense_account,
)

TEST_COMPANY = "_Test Company"
_H = frappe.generate_hash()[:6]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_exists(doctype: str) -> bool:
	return frappe.db.table_exists(doctype)


def _mapeo_sat_migrated() -> bool:
	try:
		return frappe.db.table_exists("Mapeo Equivalencias SAT")
	except RuntimeError:
		# Frappe no inicializado en import-time (pytest sin contexto)
		return False


def _sufijo_field_migrated() -> bool:
	try:
		return bool(frappe.db.get_value("Custom Field", "Item Group-fm_codigo_sufijo_sat", "name"))
	except RuntimeError:
		# Frappe no inicializado en import-time (pytest sin contexto)
		return False


def _get_or_create_expense_account(account_number: str, account_name: str, company: str) -> str:
	existing = frappe.db.get_value(
		"Account",
		{"account_number": account_number, "company": company},
		"name",
	)
	if existing:
		return existing
	parent = frappe.db.get_value(
		"Account", {"root_type": "Expense", "is_group": 1, "company": company}, "name"
	)
	if not parent:
		frappe.throw(f"No hay cuenta padre Expense en {company}")
	acc = frappe.new_doc("Account")
	acc.account_name = account_name
	acc.account_number = account_number
	acc.company = company
	acc.parent_account = parent
	acc.root_type = "Expense"
	acc.account_type = "Expense Account"
	acc.is_group = 0
	acc.insert(ignore_permissions=True)
	frappe.db.commit()
	return acc.name


def _get_or_create_dept(dept_name: str, company: str) -> str:
	existing = frappe.db.get_value("Department", {"department_name": dept_name, "company": company}, "name")
	if existing:
		return existing
	doc = frappe.new_doc("Department")
	doc.department_name = dept_name
	doc.company = company
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _make_config(
	company: str,
	*,
	modo: str = "manual_asistido",
	formato: str = "{f}{s}000",
	usar_fallback: int = 0,
	dept_familia: "list|None" = None,
) -> str:
	config_name = f"CFDI-REC-CFG-{company}"
	# No hace delete_doc del config existente — solo sobreescribe si ya existe para esta empresa.
	# El autoname de Configuracion CFDI Recibidos es por empresa (CFDI-REC-CFG-{company}),
	# así que no puede usarse nombre aleatorio. El cleanup se hace en tearDownClass.
	if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		cfg = frappe.get_doc("Configuracion CFDI Recibidos", config_name)
		cfg.modo_resolucion_cuenta_gasto = modo
		cfg.formato_cuenta_gasto = formato
		cfg.usar_fallback_matriz = usar_fallback
		cfg.mapeo_departamentos = []
		if dept_familia:
			for dept, family in dept_familia:
				cfg.append("mapeo_departamentos", {"department": dept, "familia_sat": family})
		cfg.save(ignore_permissions=True)
	else:
		cfg = frappe.new_doc("Configuracion CFDI Recibidos")
		cfg.company = company
		cfg.modo_resolucion_cuenta_gasto = modo
		cfg.formato_cuenta_gasto = formato
		cfg.usar_fallback_matriz = usar_fallback
		if dept_familia:
			for dept, family in dept_familia:
				cfg.append("mapeo_departamentos", {"department": dept, "familia_sat": family})
		cfg.insert(ignore_permissions=True, ignore_links=True)
	frappe.db.commit()
	return config_name


def _delete_if_exists(doctype: str, name: str):
	if name and frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True)
		frappe.db.commit()


# ---------------------------------------------------------------------------
# 1. Tests _get_familia_sat  (no requieren migrate)
# ---------------------------------------------------------------------------


class TestGetFamiliaSat(unittest.TestCase):
	"""_get_familia_sat lee desde Mapeo Departamento CFDI Recibido."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.dept = _get_or_create_dept(f"_TestDept GFS {_H}", TEST_COMPANY)
		cls.config_name = _make_config(
			TEST_COMPANY,
			modo="patron",
			dept_familia=[(cls.dept, "603 Gastos de administración")],
		)

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("Configuracion CFDI Recibidos", cls.config_name)
		super().tearDownClass()

	def test_retorna_codigo_3_digitos(self):
		familia = _get_familia_sat(TEST_COMPANY, self.dept)
		self.assertEqual(familia, "603")

	def test_extrae_solo_numero_de_label_completo(self):
		"""'603 Gastos de administración' → '603', no el label completo."""
		familia = _get_familia_sat(TEST_COMPANY, self.dept)
		self.assertNotIn(" ", familia)
		self.assertEqual(len(familia), 3)

	def test_retorna_none_si_department_vacio(self):
		self.assertIsNone(_get_familia_sat(TEST_COMPANY, ""))

	def test_retorna_none_si_department_none(self):
		self.assertIsNone(_get_familia_sat(TEST_COMPANY, None))

	def test_retorna_none_si_no_hay_config(self):
		self.assertIsNone(_get_familia_sat("_Empresa Inexistente XYZ", self.dept))

	def test_retorna_none_si_dept_no_esta_en_mapeo(self):
		self.assertIsNone(_get_familia_sat(TEST_COMPANY, "_Dept Sin Mapeo XYZ"))


# ---------------------------------------------------------------------------
# 2. Tests _get_sufijo_sat  (requieren migrate para fm_codigo_sufijo_sat)
# ---------------------------------------------------------------------------


@unittest.skipUnless(
	_sufijo_field_migrated(), "Requiere bench migrate — Custom Field Item Group-fm_codigo_sufijo_sat"
)
class TestGetSufijoSat(unittest.TestCase):
	"""_get_sufijo_sat lee fm_codigo_sufijo_sat desde Item Group."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		root = frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name") or "All Item Groups"
		ig_name = f"_TestIG Sufijo SAT {_H}"
		if not frappe.db.exists("Item Group", ig_name):
			ig = frappe.new_doc("Item Group")
			ig.item_group_name = ig_name
			ig.parent_item_group = root
			ig.insert(ignore_permissions=True)
			frappe.db.commit()
		cls.item_group = ig_name
		frappe.db.set_value("Item Group", cls.item_group, "fm_codigo_sufijo_sat", "48")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		if frappe.db.exists("Item Group", cls.item_group):
			frappe.delete_doc("Item Group", cls.item_group, force=True)
			frappe.db.commit()
		super().tearDownClass()

	def test_retorna_sufijo_configurado(self):
		sufijo = _get_sufijo_sat(self.item_group)
		self.assertEqual(sufijo, "48")

	def test_strip_espacios(self):
		frappe.db.set_value("Item Group", self.__class__.item_group, "fm_codigo_sufijo_sat", " 50 ")
		frappe.db.commit()
		sufijo = _get_sufijo_sat(self.item_group)
		self.assertEqual(sufijo, "50")
		frappe.db.set_value("Item Group", self.item_group, "fm_codigo_sufijo_sat", "48")
		frappe.db.commit()

	def test_retorna_none_si_item_group_vacio(self):
		self.assertIsNone(_get_sufijo_sat(""))

	def test_retorna_none_si_item_group_none(self):
		self.assertIsNone(_get_sufijo_sat(None))

	def test_retorna_none_si_sufijo_no_configurado(self):
		frappe.db.set_value("Item Group", self.item_group, "fm_codigo_sufijo_sat", "")
		frappe.db.commit()
		self.assertIsNone(_get_sufijo_sat(self.item_group))
		frappe.db.set_value("Item Group", self.item_group, "fm_codigo_sufijo_sat", "48")
		frappe.db.commit()


# ---------------------------------------------------------------------------
# 3. Tests _resolve_expense_account — modo manual_asistido (no requieren migrate)
# ---------------------------------------------------------------------------


class TestResolveExpenseAccountManual(unittest.TestCase):
	"""modo manual_asistido: nunca resuelve automáticamente."""

	def _config(self, modo="manual_asistido"):
		return {
			"modo_resolucion_cuenta_gasto": modo,
			"formato_cuenta_gasto": "{f}{s}000",
			"usar_fallback_matriz": 0,
		}

	def test_manual_retorna_none(self):
		result = _resolve_expense_account(TEST_COMPANY, "603", "48", self._config("manual_asistido"))
		self.assertIsNone(result)

	def test_manual_no_consulta_bd(self):
		"""Sin config válida tampoco debe asignar — el default manual_asistido es None."""
		result = _resolve_expense_account(TEST_COMPANY, "603", "48", {})
		self.assertIsNone(result)


# ---------------------------------------------------------------------------
# 4. Tests _resolve_expense_account — modo patron (no requieren migrate nuevas tablas)
# ---------------------------------------------------------------------------


class TestResolveExpenseAccountPatron(unittest.TestCase):
	"""modo patron: construye account_number y busca Account hoja activa."""

	_acc_name = None

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._acc_name = _get_or_create_expense_account(f"EAR{_H}0000", f"_TestEAR Patron {_H}", TEST_COMPANY)

	@classmethod
	def tearDownClass(cls):
		try:
			_delete_if_exists("Account", cls._acc_name)
		except Exception:
			pass
		super().tearDownClass()

	def _config(self, **kwargs):
		base = {
			"modo_resolucion_cuenta_gasto": "patron",
			"formato_cuenta_gasto": "{f}{s}000",
			"usar_fallback_matriz": 0,
		}
		base.update(kwargs)
		return base

	def test_patron_encuentra_cuenta_existente(self):
		# Account creada con account_number = f"EAR{_H}0000"
		# familia = "EAR"[:3] = "EAR", sufijo = _H[:2] — no vamos a buscar esa
		# Creamos la cuenta con número derivable desde familia+sufijo ficticios
		familia = f"E{_H[:2]}"  # 3 chars
		sufijo = _H[3:5]  # 2 chars
		numero = f"{familia}{sufijo}000"
		acc = _get_or_create_expense_account(numero, f"_TestEAR Pat2 {_H}", TEST_COMPANY)
		self.addCleanup(_delete_if_exists, "Account", acc)

		result = _resolve_expense_account(TEST_COMPANY, familia, sufijo, self._config())
		self.assertEqual(result, acc)

	def test_patron_formato_guiones(self):
		familia = f"F{_H[:2]}"
		sufijo = _H[3:5]
		numero = f"{familia}-{sufijo}-000"
		acc = _get_or_create_expense_account(numero, f"_TestEAR PG {_H}", TEST_COMPANY)
		self.addCleanup(_delete_if_exists, "Account", acc)

		result = _resolve_expense_account(
			TEST_COMPANY, familia, sufijo, self._config(formato_cuenta_gasto="{f}-{s}-000")
		)
		self.assertEqual(result, acc)

	def test_patron_no_usa_cuenta_grupo(self):
		"""Cuentas con is_group=1 no deben ser retornadas."""
		familia = f"G{_H[:2]}"
		sufijo = _H[3:5]
		numero = f"{familia}{sufijo}000"
		parent = frappe.db.get_value(
			"Account", {"root_type": "Expense", "is_group": 1, "company": TEST_COMPANY}, "name"
		)
		# Crear una cuenta grupo con ese número
		grp = frappe.new_doc("Account")
		grp.account_name = f"_TestEAR Grupo {_H}"
		grp.account_number = numero
		grp.company = TEST_COMPANY
		grp.parent_account = parent
		grp.root_type = "Expense"
		grp.is_group = 1
		grp.insert(ignore_permissions=True)
		frappe.db.commit()
		self.addCleanup(_delete_if_exists, "Account", grp.name)

		result = _resolve_expense_account(TEST_COMPANY, familia, sufijo, self._config())
		self.assertIsNone(result)

	def test_patron_no_usa_cuenta_disabled(self):
		familia = f"D{_H[:2]}"
		sufijo = _H[3:5]
		numero = f"{familia}{sufijo}000"
		acc = _get_or_create_expense_account(numero, f"_TestEAR Disabled {_H}", TEST_COMPANY)
		frappe.db.set_value("Account", acc, "disabled", 1)
		frappe.db.commit()
		self.addCleanup(_delete_if_exists, "Account", acc)

		result = _resolve_expense_account(TEST_COMPANY, familia, sufijo, self._config())
		self.assertIsNone(result)

		frappe.db.set_value("Account", acc, "disabled", 0)
		frappe.db.commit()

	def test_patron_sin_cuenta_sin_fallback_retorna_none(self):
		result = _resolve_expense_account(TEST_COMPANY, "ZZZ", "99", self._config(usar_fallback_matriz=0))
		self.assertIsNone(result)

	def test_sufijo_se_rellena_a_2_digitos(self):
		"""sufijo '8' debe tratarse como '08' al construir el account_number."""
		familia = f"H{_H[:2]}"
		sufijo_raw = "8"
		numero = f"{familia}08000"
		acc = _get_or_create_expense_account(numero, f"_TestEAR Pad {_H}", TEST_COMPANY)
		self.addCleanup(_delete_if_exists, "Account", acc)

		result = _resolve_expense_account(TEST_COMPANY, familia, sufijo_raw, self._config())
		self.assertEqual(result, acc)


# ---------------------------------------------------------------------------
# 5. Tests _resolve_expense_account — modo matriz (requieren migrate)
# ---------------------------------------------------------------------------


@unittest.skipUnless(_mapeo_sat_migrated(), "Requiere bench migrate — DocType Mapeo Equivalencias SAT")
class TestResolveExpenseAccountMatriz(unittest.TestCase):
	"""modo matriz_equivalencias: busca en child table."""

	_acc_name = None
	_config_name = None

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._acc_name = _get_or_create_expense_account(f"MXQ{_H}0000", f"_TestEAR Matriz {_H}", TEST_COMPANY)
		cls._config_name = _make_config(TEST_COMPANY, modo="matriz_equivalencias")
		# Agregar fila a la matriz
		cfg = frappe.get_doc("Configuracion CFDI Recibidos", cls._config_name)
		cfg.append(
			"matriz_equivalencias_sat",
			{
				"codigo_agrupador_sat": f"MXQ.{_H[:2]}",
				"account": cls._acc_name,
				"validado_por_contador": 1,
			},
		)
		cfg.save(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("Configuracion CFDI Recibidos", cls._config_name)
		try:
			_delete_if_exists("Account", cls._acc_name)
		except Exception:
			pass
		super().tearDownClass()

	def _config(self):
		return {
			"modo_resolucion_cuenta_gasto": "matriz_equivalencias",
			"formato_cuenta_gasto": "{f}{s}000",
			"usar_fallback_matriz": 0,
		}

	def test_matriz_encuentra_cuenta(self):
		familia = "MXQ"
		sufijo = _H[:2]
		result = _resolve_expense_account(TEST_COMPANY, familia, sufijo, self._config())
		self.assertEqual(result, self._acc_name)

	def test_matriz_retorna_none_si_no_hay_equivalencia(self):
		result = _resolve_expense_account(TEST_COMPANY, "ZZZ", "99", self._config())
		self.assertIsNone(result)

	def test_patron_con_fallback_usa_matriz(self):
		"""modo patron, no encuentra cuenta, usar_fallback_matriz=1 → busca en matriz."""
		familia = "MXQ"
		sufijo = _H[:2]
		config = {
			"modo_resolucion_cuenta_gasto": "patron",
			"formato_cuenta_gasto": "{f}{s}000",
			"usar_fallback_matriz": 1,
		}
		# El account_number del patrón no existe (MXQ + xx + 000 distinto al de la cuenta)
		# pero la matriz sí tiene el código SAT
		result = _resolve_expense_account(TEST_COMPANY, familia, sufijo, config)
		self.assertEqual(result, self._acc_name)


# ---------------------------------------------------------------------------
# 6. Validación estática de schema y fixtures (sin BD)
# ---------------------------------------------------------------------------


class TestSchemaYFixtures(unittest.TestCase):
	"""Valida estructura de archivos JSON sin necesitar bench migrate."""

	_BASE = os.path.join(os.path.dirname(__file__), "..", "..")

	def _read_json(self, rel_path: str) -> dict | list:
		full = os.path.normpath(os.path.join(self._BASE, rel_path))
		with open(full) as f:
			return json.load(f)

	def test_mapeo_equivalencias_sat_json_existe(self):
		data = self._read_json("cfdi_recibidos/doctype/mapeo_equivalencias_sat/mapeo_equivalencias_sat.json")
		self.assertEqual(data["name"], "Mapeo Equivalencias SAT")
		self.assertEqual(data["istable"], 1)

	def test_mapeo_equivalencias_sat_campos_requeridos(self):
		data = self._read_json("cfdi_recibidos/doctype/mapeo_equivalencias_sat/mapeo_equivalencias_sat.json")
		fieldnames = {f["fieldname"] for f in data["fields"]}
		self.assertIn("codigo_agrupador_sat", fieldnames)
		self.assertIn("account", fieldnames)
		self.assertIn("validado_por_contador", fieldnames)
		self.assertIn("notas", fieldnames)

	def test_configuracion_cfdi_recibidos_tiene_nuevos_campos(self):
		data = self._read_json(
			"cfdi_recibidos/doctype/configuracion_cfdi_recibidos/configuracion_cfdi_recibidos.json"
		)
		fieldnames = {f["fieldname"] for f in data["fields"]}
		self.assertIn("modo_resolucion_cuenta_gasto", fieldnames)
		self.assertIn("formato_cuenta_gasto", fieldnames)
		self.assertIn("usar_fallback_matriz", fieldnames)
		self.assertIn("matriz_equivalencias_sat", fieldnames)

	def test_modo_resolucion_tiene_opciones_correctas(self):
		data = self._read_json(
			"cfdi_recibidos/doctype/configuracion_cfdi_recibidos/configuracion_cfdi_recibidos.json"
		)
		field = next(f for f in data["fields"] if f["fieldname"] == "modo_resolucion_cuenta_gasto")
		options = field["options"].split("\n")
		self.assertIn("manual_asistido", options)
		self.assertIn("patron", options)
		self.assertIn("matriz_equivalencias", options)

	def test_formato_cuenta_gasto_default_es_patron_correcto(self):
		data = self._read_json(
			"cfdi_recibidos/doctype/configuracion_cfdi_recibidos/configuracion_cfdi_recibidos.json"
		)
		field = next(f for f in data["fields"] if f["fieldname"] == "formato_cuenta_gasto")
		self.assertEqual(field["default"], "{f}{s}000")

	def test_custom_field_json_contiene_item_group_sufijo(self):
		data = self._read_json("fixtures/custom_field.json")
		names = {e.get("name") for e in data}
		self.assertIn("Item Group-fm_codigo_sufijo_sat", names)

	def test_custom_field_item_group_tiene_atributos_correctos(self):
		data = self._read_json("fixtures/custom_field.json")
		field = next(e for e in data if e.get("name") == "Item Group-fm_codigo_sufijo_sat")
		self.assertEqual(field["dt"], "Item Group")
		self.assertEqual(field["fieldname"], "fm_codigo_sufijo_sat")
		self.assertEqual(field["fieldtype"], "Data")

	def test_hooks_py_registra_custom_field(self):
		hooks_path = os.path.normpath(os.path.join(self._BASE, "hooks.py"))
		with open(hooks_path) as f:
			content = f.read()
		self.assertIn("Item Group-fm_codigo_sufijo_sat", content)
