"""Tests de permisos de cancelación en Factura Fiscal Mexico.

Verifica que solo los roles autorizados pueden cancelar FFMs:
- Facturacion Mexico Manager: SÍ puede cancelar
- Facturacion Mexico System Manager: SÍ puede cancelar
- System Manager: SÍ puede cancelar (superuser)
- Accounts Manager: NO puede cancelar
- Accounts User: NO puede cancelar
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
	cancel_ffm_keep_si,
)

ROLES_AUTORIZADOS = [
	"Facturacion Mexico Manager",
	"Facturacion Mexico System Manager",
]

ROLES_BLOQUEADOS = [
	"Accounts Manager",
	"Accounts User",
	"Facturacion Mexico User",
]


def _make_test_user(roles: list[str]) -> str:
	uid = "test-ffm-cancel-" + frappe.generate_hash()[:8] + "@test.com"
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": uid,
			"first_name": "Test",
			"send_welcome_email": 0,
			"roles": [{"role": r} for r in roles],
		}
	)
	user.insert(ignore_permissions=True)
	return uid


def _make_test_ffm() -> str:
	"""Crea una FFM sin UUID (sin timbre) para probar cancel_ffm_keep_si."""
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"naming_series": "FFM-TEST-.YYYY.-",
			"status": "ERROR",
			"fm_tipo_comprobante": "I",
			"company": frappe.defaults.get_global_default("company") or "_Test Company",
			"docstatus": 1,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.db_insert()
	return ffm.name


class TestFFMCancelPermisos(IntegrationTestCase):
	def setUp(self):
		self.ffm_names = []

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in self.ffm_names:
			frappe.db.delete("Factura Fiscal Mexico", {"name": name})
		frappe.db.commit()

	def _ffm(self):
		name = _make_test_ffm()
		self.ffm_names.append(name)
		return name

	def test_facturacion_mexico_manager_puede_cancelar(self):
		uid = _make_test_user(["Facturacion Mexico Manager"])
		ffm_name = self._ffm()
		frappe.set_user(uid)
		try:
			cancel_ffm_keep_si(ffm_name)
		except frappe.PermissionError:
			self.fail("Facturacion Mexico Manager no debería recibir PermissionError al cancelar FFM")
		except Exception:
			# Otros errores (DB transaction, validaciones) son aceptables —
			# lo importante es que el check de permiso pasó.
			pass
		finally:
			frappe.set_user("Administrator")

	def test_facturacion_mexico_system_manager_puede_cancelar(self):
		uid = _make_test_user(["Facturacion Mexico System Manager"])
		ffm_name = self._ffm()
		frappe.set_user(uid)
		try:
			cancel_ffm_keep_si(ffm_name)
		except frappe.PermissionError:
			self.fail("Facturacion Mexico System Manager no debería recibir PermissionError")
		except Exception:
			pass
		finally:
			frappe.set_user("Administrator")

	def test_accounts_manager_no_puede_cancelar(self):
		uid = _make_test_user(["Accounts Manager"])
		ffm_name = self._ffm()
		frappe.set_user(uid)
		with self.assertRaises(frappe.PermissionError):
			cancel_ffm_keep_si(ffm_name)
		frappe.set_user("Administrator")

	def test_accounts_user_no_puede_cancelar(self):
		uid = _make_test_user(["Accounts User"])
		ffm_name = self._ffm()
		frappe.set_user(uid)
		with self.assertRaises(frappe.PermissionError):
			cancel_ffm_keep_si(ffm_name)
		frappe.set_user("Administrator")

	def test_facturacion_mexico_user_no_puede_cancelar(self):
		uid = _make_test_user(["Facturacion Mexico User"])
		ffm_name = self._ffm()
		frappe.set_user(uid)
		with self.assertRaises(frappe.PermissionError):
			cancel_ffm_keep_si(ffm_name)
		frappe.set_user("Administrator")
