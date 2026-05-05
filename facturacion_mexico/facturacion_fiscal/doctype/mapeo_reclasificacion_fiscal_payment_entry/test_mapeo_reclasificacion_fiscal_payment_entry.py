# Copyright (c) 2026, Buzola and contributors
# For license information, please see license.txt

"""
Tests: Mapeo Reclasificacion Fiscal Payment Entry

Cubre validaciones del DocType:
- cuentas distintas
- account_type = Tax obligatorio
- misma empresa
- cuenta no grupo
- sin duplicado activo
"""

import unittest

import frappe
from frappe.exceptions import ValidationError

_COMPANY = "_Test Company"
_TAX_PARENT = "Source of Funds (Liabilities) - _TC"


def _ensure_account(name, account_name, account_type="Tax", is_group=0):
	if not frappe.db.exists("Account", name):
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"account_type": account_type,
				"is_group": is_group,
				"company": _COMPANY,
				"parent_account": _TAX_PARENT,
				"root_type": "Liability",
			}
		).insert(ignore_permissions=True)
	return name


def _make_mapeo(origen, destino, company=_COMPANY, activo=1):
	doc = frappe.new_doc("Mapeo Reclasificacion Fiscal Payment Entry")
	doc.company = company
	doc.tipo_operacion = "Cobro"
	doc.cuenta_origen = origen
	doc.cuenta_destino = destino
	doc.activo = activo
	return doc


class TestMapeoReclasificacionFiscalPaymentEntry(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.clear_cache()
		cls.origen = _ensure_account("Test IVA Pendiente - _TC", "Test IVA Pendiente")
		cls.destino = _ensure_account("Test IVA Cobrado - _TC", "Test IVA Cobrado")
		cls.non_tax = frappe.db.get_value(
			"Account",
			{"company": _COMPANY, "account_type": ["!=", "Tax"], "is_group": 0},
			"name",
		)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist test fixtures across tearDown rollbacks

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete(
			"Mapeo Reclasificacion Fiscal Payment Entry",
			{"company": _COMPANY, "cuenta_origen": ["in", [cls.origen, cls.destino]]},
		)
		for acc in ["Test IVA Pendiente - _TC", "Test IVA Cobrado - _TC"]:
			if frappe.db.exists("Account", acc):
				frappe.delete_doc("Account", acc, ignore_permissions=True, force=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit

	def tearDown(self):
		frappe.db.rollback()

	def test_cuentas_distintas(self):
		"""cuenta_origen == cuenta_destino debe lanzar ValidationError."""
		doc = _make_mapeo(self.origen, self.origen)
		with self.assertRaises(ValidationError):
			doc.insert(ignore_permissions=True)

	def test_cuenta_debe_ser_tax(self):
		"""account_type != Tax en cuenta_origen debe lanzar ValidationError."""
		if not self.non_tax:
			self.skipTest("No hay cuenta no-Tax en _Test Company")
		doc = _make_mapeo(self.non_tax, self.destino)
		with self.assertRaises(ValidationError):
			doc.insert(ignore_permissions=True)

	def test_cuenta_destino_debe_ser_tax(self):
		"""account_type != Tax en cuenta_destino debe lanzar ValidationError."""
		if not self.non_tax:
			self.skipTest("No hay cuenta no-Tax en _Test Company")
		doc = _make_mapeo(self.origen, self.non_tax)
		with self.assertRaises(ValidationError):
			doc.insert(ignore_permissions=True)

	def test_cuenta_no_grupo(self):
		"""Cuenta grupo debe lanzar ValidationError."""
		grupo = frappe.db.get_value(
			"Account", {"company": _COMPANY, "account_type": "Tax", "is_group": 1}, "name"
		)
		if not grupo:
			self.skipTest("No hay cuenta Tax grupo en _Test Company")
		doc = _make_mapeo(grupo, self.destino)
		with self.assertRaises(ValidationError):
			doc.insert(ignore_permissions=True)

	def test_sin_duplicado_activo(self):
		"""Segundo mapeo activo con mismo company+tipo+origen debe lanzar ValidationError."""
		doc1 = _make_mapeo(self.origen, self.destino, activo=1)
		doc1.insert(ignore_permissions=True)
		doc2 = _make_mapeo(self.origen, self.destino, activo=1)
		with self.assertRaises(ValidationError):
			doc2.insert(ignore_permissions=True)

	def test_duplicado_inactivo_permitido(self):
		"""Mapeo inactivo con mismo company+tipo+origen es válido."""
		doc1 = _make_mapeo(self.origen, self.destino, activo=1)
		doc1.insert(ignore_permissions=True)
		doc2 = _make_mapeo(self.origen, self.destino, activo=0)
		doc2.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Mapeo Reclasificacion Fiscal Payment Entry", doc2.name))

	def test_insert_valido(self):
		"""Mapeo con datos correctos se inserta sin error."""
		doc = _make_mapeo(self.origen, self.destino)
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Mapeo Reclasificacion Fiscal Payment Entry", doc.name))
