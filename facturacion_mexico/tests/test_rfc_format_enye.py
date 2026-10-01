"""Regresión: la validación de formato de RFC acepta Ñ y & en la porción de nombre.

Bug: las regex `^[A-Z]{3,4}[0-9]{6}[A-Z0-9]{3}$` en `catalogos_sat.api._validate_rfc_format`
y en `validaciones.hooks_handlers.customer_validate.validate_rfc_format` usaban `[A-Z]`
(solo ASCII), rechazando RFC válidos del SAT que contienen Ñ o & en la porción de nombre.
El fix alinea ambas al patrón canónico `[A-ZÑ&]` ya usado en
`facturacion_fiscal.validations` y `validaciones.api`. RFC ficticios en los datos de prueba.
"""

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.catalogos_sat.api import _validate_rfc_format
from facturacion_mexico.validaciones.hooks_handlers.customer_validate import validate_rfc_format

# RFC ficticio persona moral con Ñ (Ñ es carácter legal en el nombre del RFC del SAT).
_RFC_ENYE = "AÑA950101AB1"
# RFC ficticio persona moral con & en el nombre.
_RFC_AMP = "A&A950101AB1"
# RFC ficticios persona moral y física normales (sin caracteres especiales).
_RFC_MORAL_OK = "ABC100809G80"
_RFC_FISICA_OK = "ABCD800101XY1"


class TestRFCFormatEnyeAmpersand(FrappeTestCase):
	"""Cubre `_validate_rfc_format` (función pura) y el hook `validate_rfc_format`."""

	# --- función pura _validate_rfc_format (catalogos_sat/api.py) ---
	def test_pure_acepta_enye(self):
		"""RFC persona moral con Ñ debe ser válido."""
		self.assertTrue(_validate_rfc_format(_RFC_ENYE))

	def test_pure_acepta_ampersand(self):
		"""RFC con & en el nombre debe ser válido."""
		self.assertTrue(_validate_rfc_format(_RFC_AMP))

	def test_pure_acepta_rfc_normales(self):
		"""RFC normales (moral y física, sin especiales) siguen aceptándose."""
		self.assertTrue(_validate_rfc_format(_RFC_MORAL_OK))
		self.assertTrue(_validate_rfc_format(_RFC_FISICA_OK))

	def test_pure_rechaza_invalidos(self):
		"""RFC claramente inválidos siguen rechazándose."""
		self.assertFalse(_validate_rfc_format("AÑA950101A"))  # 10 chars (corto)
		self.assertFalse(_validate_rfc_format("1ÑA950101AB1"))  # empieza con dígito
		self.assertFalse(_validate_rfc_format("A-A950101AB1"))  # carácter no permitido (-)
		self.assertFalse(_validate_rfc_format("aña950101ab1"))  # minúsculas (el caller debe upper())

	# --- hook validate_rfc_format (customer_validate.py) ---
	def _run_hook(self, tax_id):
		"""Ejecuta el hook con in_test desactivado (si no, retorna temprano)."""
		doc = frappe._dict(tax_id=tax_id)
		with mock.patch.object(frappe.flags, "in_test", False):
			validate_rfc_format(doc, method="validate")
		return doc

	def test_hook_acepta_enye_sin_throw(self):
		"""El hook del Customer NO debe lanzar con un RFC con Ñ y deja tax_id normalizado."""
		doc = self._run_hook(_RFC_ENYE)
		self.assertEqual(doc.tax_id, _RFC_ENYE)

	def test_hook_acepta_ampersand_sin_throw(self):
		"""El hook del Customer NO debe lanzar con & en el nombre."""
		doc = self._run_hook(_RFC_AMP)
		self.assertEqual(doc.tax_id, _RFC_AMP)

	def test_hook_rechaza_invalido(self):
		"""El hook sigue bloqueando un RFC con formato inválido."""
		with self.assertRaises(frappe.exceptions.ValidationError):
			self._run_hook("A-A950101AB1")
