"""
Tests para la resolución de expense_account en CFDI Recibidos.

Cubre:
  - Modo Automatico CoA SAT: éxito, cero cuentas, múltiples cuentas,
    cuenta grupo, cuenta deshabilitada, sin código SAT en item_group
  - Modo Manual: éxito, concepto sin cuenta, cuenta grupo, cuenta deshabilitada
  - _build_prefix: formatos válidos e inválido
  - _get_familia_sat: con mapeo, sin mapeo, sin departamento
"""

import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.purchase_invoice_builder import (
	_build_prefix,
	_get_familia_sat,
	_resolve_one,
)

TEST_COMPANY = "_Test Company"
_H = frappe.generate_hash()[:6]
_CONFIG_NAME = f"CFDI-REC-CFG-{TEST_COMPANY}"


def _get_or_create_account(account_name: str, company: str, is_group: int = 0, disabled: int = 0) -> str:
	existing = frappe.db.get_value("Account", {"account_name": account_name, "company": company}, "name")
	if existing:
		return existing
	parent = frappe.db.get_value(
		"Account", {"root_type": "Expense", "is_group": 1, "company": company}, "name"
	) or frappe.db.get_value("Account", {"is_group": 1, "company": company}, "name")
	acc = frappe.new_doc("Account")
	acc.account_name = account_name
	acc.company = company
	acc.parent_account = parent
	acc.account_type = "Expense Account"
	acc.is_group = is_group
	acc.disabled = disabled
	acc.insert(ignore_permissions=True)
	frappe.db.commit()
	return acc.name


def _ensure_config(mode: str, formato: str = "") -> None:
	if frappe.db.exists("Configuracion CFDI Recibidos", _CONFIG_NAME):
		frappe.db.set_value(
			"Configuracion CFDI Recibidos",
			_CONFIG_NAME,
			{"modo_resolucion_contable": mode, "formato_coa": formato},
		)
	else:
		doc = frappe.new_doc("Configuracion CFDI Recibidos")
		doc.company = TEST_COMPANY
		doc.modo_resolucion_contable = mode
		doc.formato_coa = formato
		doc.insert(ignore_permissions=True)
	frappe.db.commit()


def _set_dept_mapping(department: str, familia: str) -> None:
	frappe.db.delete("Mapeo Departamento CFDI Recibido", {"parent": _CONFIG_NAME})
	frappe.db.sql(
		"INSERT INTO `tabMapeo Departamento CFDI Recibido` "
		"(name, parent, parenttype, parentfield, department, familia_sat) "
		"VALUES (%s, %s, 'Configuracion CFDI Recibidos', 'mapeo_departamentos', %s, %s)",
		(frappe.generate_hash()[:10], _CONFIG_NAME, department, familia),
	)
	frappe.db.commit()


def _concepto(item_group: str = "", expense_account: str = "", item_code: str = "ITEM") -> object:
	return frappe._dict(
		item_code=item_code,
		description=f"Test {_H}",
		item_group=item_group,
		expense_account=expense_account,
	)


class TestBuildPrefix(unittest.TestCase):
	def test_guiones(self):
		self.assertEqual(_build_prefix("###-##-###", "603", "50"), "603-50-")

	def test_puntos(self):
		self.assertEqual(_build_prefix("###.##.###", "603", "50"), "603.50.")

	def test_sin_separador(self):
		self.assertEqual(_build_prefix("########", "603", "50"), "60350")

	def test_zero_padding(self):
		self.assertEqual(_build_prefix("###-##-###", "603", "5"), "603-05-")

	def test_formato_invalido(self):
		with self.assertRaises(frappe.ValidationError):
			_build_prefix("XXX", "603", "50")


class TestGetFamiliaSat(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_config("Manual")

	def test_extrae_codigo_numerico(self):
		_set_dept_mapping("_Test Department", "603 Gastos de administración")
		self.assertEqual(_get_familia_sat(TEST_COMPANY, "_Test Department"), "603")

	def test_sin_mapeo_retorna_none(self):
		frappe.db.delete("Mapeo Departamento CFDI Recibido", {"parent": _CONFIG_NAME})
		frappe.db.commit()
		self.assertIsNone(_get_familia_sat(TEST_COMPANY, "_Test Department"))

	def test_departamento_vacio_retorna_none(self):
		self.assertIsNone(_get_familia_sat(TEST_COMPANY, ""))


class TestAutoResolve(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_config("Automatico CoA SAT", "###-##-###")

		# Item Group con código SAT 50
		ig_name = f"_Test IG {_H}"
		if not frappe.db.exists("Item Group", ig_name):
			ig = frappe.new_doc("Item Group")
			ig.item_group_name = ig_name
			ig.parent_item_group = frappe.db.get_value("Item Group", {"is_group": 1}, "name")
			ig.is_group = 0
			ig.insert(ignore_permissions=True)
		frappe.db.set_value("Item Group", ig_name, "fm_codigo_sufijo_sat", "50")
		frappe.db.commit()
		cls.ig = ig_name

		# Cuenta única bajo prefijo 603-50-
		cls.acc = _get_or_create_account(f"_Test Tel {_H}", TEST_COMPANY)
		frappe.db.set_value("Account", cls.acc, "account_number", f"603-50-{_H[:3]}")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		try:
			frappe.delete_doc("Account", cls.acc, force=True)
		except Exception:
			pass
		try:
			frappe.delete_doc("Item Group", cls.ig, force=True)
		except Exception:
			pass
		frappe.db.commit()
		super().tearDownClass()

	def test_resuelve_cuenta_unica(self):
		c = _concepto(item_group=self.ig)
		self.assertEqual(_resolve_one(c, TEST_COMPANY, "Automatico CoA SAT", "603", "###-##-###"), self.acc)

	def test_falla_cero_cuentas(self):
		c = _concepto(item_group=self.ig)
		with self.assertRaises(frappe.ValidationError) as ctx:
			_resolve_one(c, TEST_COMPANY, "Automatico CoA SAT", "601", "###-##-###")
		self.assertIn("No se pudo resolver", str(ctx.exception))

	def test_falla_multiples_cuentas(self):
		acc2 = _get_or_create_account(f"_Test Tel2 {_H}", TEST_COMPANY)
		frappe.db.set_value("Account", acc2, "account_number", f"603-50-{_H[:2]}9")
		frappe.db.commit()
		try:
			c = _concepto(item_group=self.ig)
			with self.assertRaises(frappe.ValidationError) as ctx:
				_resolve_one(c, TEST_COMPANY, "Automatico CoA SAT", "603", "###-##-###")
			self.assertIn("cuentas con account_number", str(ctx.exception))
		finally:
			try:
				frappe.delete_doc("Account", acc2, force=True)
				frappe.db.commit()
			except Exception:
				pass

	def test_falla_sin_codigo_sat(self):
		frappe.db.set_value("Item Group", self.ig, "fm_codigo_sufijo_sat", "")
		frappe.db.commit()
		try:
			c = _concepto(item_group=self.ig)
			with self.assertRaises(frappe.ValidationError) as ctx:
				_resolve_one(c, TEST_COMPANY, "Automatico CoA SAT", "603", "###-##-###")
			self.assertIn("fm_codigo_sufijo_sat", str(ctx.exception))
		finally:
			frappe.db.set_value("Item Group", self.ig, "fm_codigo_sufijo_sat", "50")
			frappe.db.commit()

	def test_cuenta_deshabilitada_falla(self):
		frappe.db.set_value("Account", self.acc, "disabled", 1)
		frappe.db.commit()
		try:
			c = _concepto(item_group=self.ig)
			with self.assertRaises(frappe.ValidationError) as ctx:
				_resolve_one(c, TEST_COMPANY, "Automatico CoA SAT", "603", "###-##-###")
			self.assertIn("No se pudo resolver", str(ctx.exception))
		finally:
			frappe.db.set_value("Account", self.acc, "disabled", 0)
			frappe.db.commit()


class TestManualResolve(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.acc = _get_or_create_account(f"_Test Manual {_H}", TEST_COMPANY)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		try:
			frappe.delete_doc("Account", cls.acc, force=True)
			frappe.db.commit()
		except Exception:
			pass
		super().tearDownClass()

	def test_exitoso(self):
		c = _concepto(expense_account=self.acc)
		self.assertEqual(_resolve_one(c, TEST_COMPANY, "Manual", None, ""), self.acc)

	def test_sin_cuenta_lanza_error(self):
		c = _concepto(expense_account="")
		with self.assertRaises(frappe.ValidationError) as ctx:
			_resolve_one(c, TEST_COMPANY, "Manual", None, "")
		self.assertIn("Cuenta de Gasto vacía", str(ctx.exception))

	def test_cuenta_grupo_lanza_error(self):
		acc_grp = _get_or_create_account(f"_Test MG {_H}", TEST_COMPANY, is_group=1)
		frappe.db.commit()
		try:
			c = _concepto(expense_account=acc_grp)
			with self.assertRaises(frappe.ValidationError) as ctx:
				_resolve_one(c, TEST_COMPANY, "Manual", None, "")
			self.assertIn("grupo contable", str(ctx.exception))
		finally:
			try:
				frappe.delete_doc("Account", acc_grp, force=True)
				frappe.db.commit()
			except Exception:
				pass

	def test_cuenta_deshabilitada_lanza_error(self):
		frappe.db.set_value("Account", self.acc, "disabled", 1)
		frappe.db.commit()
		try:
			c = _concepto(expense_account=self.acc)
			with self.assertRaises(frappe.ValidationError) as ctx:
				_resolve_one(c, TEST_COMPANY, "Manual", None, "")
			self.assertIn("deshabilitada", str(ctx.exception))
		finally:
			frappe.db.set_value("Account", self.acc, "disabled", 0)
			frappe.db.commit()
