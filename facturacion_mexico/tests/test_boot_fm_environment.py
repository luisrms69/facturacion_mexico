"""Tests del boot del indicador de ambiente fiscal (issue #171).

Verifican que `boot_session` publique en `frappe.boot.fm_environment` el valor devuelto por la
única fuente de verdad (`get_fm_environment`, #215), para production / sandbox / ausente.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico import boot


class TestBootFmEnvironment(FrappeTestCase):
	def _boot_value(self, environment):
		bootinfo = frappe._dict()
		with patch("facturacion_mexico.boot.get_fm_environment", return_value=environment):
			boot.add_fiscal_environment_to_boot(bootinfo)
		return bootinfo.get("fm_environment")

	def test_boot_production(self):
		self.assertEqual(self._boot_value("production"), "production")

	def test_boot_sandbox(self):
		self.assertEqual(self._boot_value("sandbox"), "sandbox")

	def test_boot_ausente(self):
		self.assertEqual(self._boot_value(""), "")
