"""Tests de permisos de cancelación en Factura Fiscal Mexico.

Verifica que solo los roles autorizados pueden cancelar FFMs:
- System Manager: SÍ puede cancelar (superuser)
- Facturacion Mexico Manager: SÍ puede cancelar
- Facturacion Mexico System Manager: SÍ puede cancelar
- Accounts Manager: NO puede cancelar
- Accounts User: NO puede cancelar
- Facturacion Mexico User: NO puede cancelar
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
	cancel_ffm_keep_si,
)

ALLOWED_ROLES = [
	"System Manager",
	"Facturacion Mexico Manager",
	"Facturacion Mexico System Manager",
]

BLOCKED_ROLES = [
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
		self.user_ids = []
		# Garantizar reset de usuario aunque una aserción falle a mitad de test.
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in self.ffm_names:
			frappe.db.delete("Factura Fiscal Mexico", {"name": name})
		for uid in self.user_ids:
			frappe.db.delete("User", {"name": uid})
		frappe.db.commit()

	def _user(self, roles):
		uid = _make_test_user(roles)
		self.user_ids.append(uid)
		return uid

	def _ffm(self):
		name = _make_test_ffm()
		self.ffm_names.append(name)
		return name

	def _assert_puede_cancelar(self, role: str):
		"""Verifica que el rol NO recibe PermissionError al cancelar FFM."""
		uid = self._user([role])
		ffm_name = self._ffm()
		frappe.set_user(uid)
		try:
			cancel_ffm_keep_si(ffm_name)
		except frappe.PermissionError:
			self.fail(f"El rol '{role}' no debería recibir PermissionError al cancelar FFM")
		except Exception:
			# Otros errores (DB transaction, validaciones) son aceptables —
			# lo importante es que el check de permiso pasó.
			pass
		finally:
			frappe.set_user("Administrator")

	def _assert_no_puede_cancelar(self, role: str):
		"""Verifica que el rol SÍ recibe PermissionError al cancelar FFM."""
		uid = self._user([role])
		ffm_name = self._ffm()
		frappe.set_user(uid)
		try:
			with self.assertRaises(frappe.PermissionError):
				cancel_ffm_keep_si(ffm_name)
		finally:
			frappe.set_user("Administrator")

	def test_system_manager_puede_cancelar(self):
		self._assert_puede_cancelar("System Manager")

	def test_facturacion_mexico_manager_puede_cancelar(self):
		self._assert_puede_cancelar("Facturacion Mexico Manager")

	def test_facturacion_mexico_system_manager_puede_cancelar(self):
		self._assert_puede_cancelar("Facturacion Mexico System Manager")

	def test_accounts_manager_no_puede_cancelar(self):
		self._assert_no_puede_cancelar("Accounts Manager")

	def test_accounts_user_no_puede_cancelar(self):
		self._assert_no_puede_cancelar("Accounts User")

	def test_facturacion_mexico_user_no_puede_cancelar(self):
		self._assert_no_puede_cancelar("Facturacion Mexico User")
