"""
Tests para _resolver_forma_pago_sat (issue #161).

Usa documentos reales de Mode of Payment y Forma Pago SAT del fixture del app.
No mockea frappe.db.* ni frappe.get_doc (RG-003).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.complementos_pago.api import _PATRON_MOP_SAT, _resolver_forma_pago_sat


class TestResolverFormaPagoSAT(FrappeTestCase):
	"""Tests para _resolver_forma_pago_sat usando documentos reales."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		suffix = frappe.generate_hash()[:6]

		# MoP deshabilitado — para test de disabled
		cls.mop_disabled = f"TEST-MOP-DIS-{suffix}"
		frappe.get_doc(
			{
				"doctype": "Mode of Payment",
				"mode_of_payment": cls.mop_disabled,
				"enabled": 0,
				"type": "General",
			}
		).insert(ignore_permissions=True)

		# MoP con formato SAT pero código "55" que no existe en Forma Pago SAT
		cls.mop_fake_sat = f"55 TEST-{suffix}"
		frappe.get_doc(
			{
				"doctype": "Mode of Payment",
				"mode_of_payment": cls.mop_fake_sat,
				"enabled": 1,
				"type": "General",
			}
		).insert(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		frappe.db.delete("Mode of Payment", cls.mop_disabled)
		frappe.db.delete("Mode of Payment", cls.mop_fake_sat)
		frappe.db.commit()

	# -- Casos válidos con fixtures reales --

	def test_resuelve_transferencia_electronica(self):
		"""MoP SAT '03 Transferencia...' del fixture → código '03'."""
		result = _resolver_forma_pago_sat("03 Transferencia electrónica de fondos")
		self.assertEqual(result, "03")

	def test_resuelve_efectivo(self):
		"""MoP SAT '01 Efectivo' del fixture → código '01'."""
		result = _resolver_forma_pago_sat("01 Efectivo")
		self.assertEqual(result, "01")

	def test_resuelve_por_definir_99(self):
		"""MoP SAT '99 Por definir' del fixture → código '99'."""
		result = _resolver_forma_pago_sat("99 Por definir")
		self.assertEqual(result, "99")

	# -- Casos de bloqueo --

	def test_bloquea_mop_vacio_none(self):
		"""None → ValidationError."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			_resolver_forma_pago_sat(None)
		self.assertIn("Forma de Pago", str(ctx.exception))

	def test_bloquea_mop_string_vacio(self):
		"""String vacío → ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			_resolver_forma_pago_sat("")

	def test_bloquea_mop_inexistente_en_bd(self):
		"""MoP que no existe en BD → ValidationError."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			_resolver_forma_pago_sat("MOP-FANTASMA-XYZ-99999")
		self.assertIn("no existe", str(ctx.exception))

	def test_bloquea_mop_deshabilitado(self):
		"""MoP con enabled=0 → ValidationError."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			_resolver_forma_pago_sat(self.mop_disabled)
		self.assertIn("deshabilitado", str(ctx.exception))

	def test_bloquea_cash(self):
		"""MoP nativo 'Cash' no cumple patrón → ValidationError."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			_resolver_forma_pago_sat("Cash")
		self.assertIn("catálogo SAT", str(ctx.exception))

	def test_bloquea_wire_transfer(self):
		"""MoP nativo 'Wire Transfer' no cumple patrón → ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			_resolver_forma_pago_sat("Wire Transfer")

	def test_bloquea_check(self):
		"""MoP nativo 'Check' → ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			_resolver_forma_pago_sat("Check")

	def test_bloquea_credit_card(self):
		"""MoP nativo 'Credit Card' → ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			_resolver_forma_pago_sat("Credit Card")

	def test_bloquea_patron_sin_espacio(self):
		"""Nombre sin espacio separador no cumple patrón → ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			_resolver_forma_pago_sat("01Efectivo")

	def test_bloquea_formato_canonico_con_guion(self):
		"""Formato canónico '01 - Efectivo' (con guion) no existe en BD → ValidationError.

		El estándar del app es '01 Efectivo' (sin guion). El formato con guion
		no corresponde a ningún registro del fixture y debe fallar.
		"""
		with self.assertRaises(frappe.ValidationError) as ctx:
			_resolver_forma_pago_sat("01 - Efectivo")
		# Falla porque "01 - Efectivo" no existe en BD (fixture usa "01 Efectivo")
		self.assertIn("no existe", str(ctx.exception))

	def test_bloquea_letras_en_prefijo(self):
		"""Prefijo con letras 'AB Algo' → ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			_resolver_forma_pago_sat("AB Algo")

	def test_bloquea_codigo_no_en_catalogo_sat(self):
		"""MoP con formato correcto pero código '55' no en Forma Pago SAT → ValidationError."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			_resolver_forma_pago_sat(self.mop_fake_sat)
		self.assertIn("catálogo SAT", str(ctx.exception))

	# -- Verificación del patrón regex --

	def test_patron_acepta_formatos_validos(self):
		"""El patrón regex acepta nombres válidos del fixture."""
		validos = [
			"01 Efectivo",
			"03 Transferencia electrónica de fondos",
			"99 Por definir",
			"28 Tarjeta de débito",
		]
		for v in validos:
			self.assertIsNotNone(_PATRON_MOP_SAT.match(v), f"Debería aceptar: {v}")

	def test_patron_rechaza_formatos_invalidos(self):
		"""El patrón regex rechaza nombres no SAT."""
		invalidos = [
			"Cash",
			"Wire Transfer",
			"Check",
			"Credit Card",
			"Bank Draft",
			"Cheque",
			"1 Solo un dígito",  # un solo dígito
			"01 - Efectivo",  # formato con guion — no es el estándar del app
		]
		for v in invalidos:
			self.assertIsNone(_PATRON_MOP_SAT.match(v), f"Debería rechazar: {v}")
