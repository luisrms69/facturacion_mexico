"""
Tests para _resolver_forma_pago_sat (issue #161).

Verifica que el helper rechaza modos de pago no SAT y resuelve
correctamente los del fixture del app.
"""

import re
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.complementos_pago.api import _resolver_forma_pago_sat


def _mock_get_value(enabled_map):
	"""Retorna side_effect para frappe.db.get_value."""

	def side_effect(doctype, name, field):
		if doctype == "Mode of Payment" and field == "enabled":
			return enabled_map.get(name)
		return None

	return side_effect


def _mock_exists(existing):
	"""Retorna side_effect para frappe.db.exists."""

	def side_effect(doctype, name):
		if doctype == "Forma Pago SAT":
			return name in existing
		return False

	return side_effect


class TestResolverFormaPagoSAT(FrappeTestCase):
	"""Tests unitarios para _resolver_forma_pago_sat."""

	# -- Casos válidos --

	def test_resuelve_transferencia_electronica(self):
		"""MoP SAT válido '03 - Transferencia...' → código '03'."""
		mop = "03 - Transferencia electrónica de fondos"
		with (
			patch("frappe.db.get_value", side_effect=_mock_get_value({mop: 1})),
			patch("frappe.db.exists", side_effect=_mock_exists({"03"})),
		):
			self.assertEqual(_resolver_forma_pago_sat(mop), "03")

	def test_resuelve_efectivo(self):
		"""MoP SAT válido '01 - Efectivo' → código '01'."""
		mop = "01 - Efectivo"
		with (
			patch("frappe.db.get_value", side_effect=_mock_get_value({mop: 1})),
			patch("frappe.db.exists", side_effect=_mock_exists({"01"})),
		):
			self.assertEqual(_resolver_forma_pago_sat(mop), "01")

	def test_resuelve_por_definir_99(self):
		"""MoP SAT '99 - Por definir' → código '99'."""
		mop = "99 - Por definir"
		with (
			patch("frappe.db.get_value", side_effect=_mock_get_value({mop: 1})),
			patch("frappe.db.exists", side_effect=_mock_exists({"99"})),
		):
			self.assertEqual(_resolver_forma_pago_sat(mop), "99")

	# -- Casos de bloqueo --

	def test_bloquea_mop_vacio(self):
		"""None → ValidationError 'Forma de Pago Faltante'."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			_resolver_forma_pago_sat(None)
		self.assertIn("Forma de Pago", str(ctx.exception))

	def test_bloquea_string_vacio(self):
		"""String vacío → ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			_resolver_forma_pago_sat("")

	def test_bloquea_cash(self):
		"""MoP nativo 'Cash' no cumple patrón → ValidationError."""
		with patch("frappe.db.get_value", side_effect=_mock_get_value({"Cash": 1})):
			with self.assertRaises(frappe.ValidationError) as ctx:
				_resolver_forma_pago_sat("Cash")
		self.assertIn("catálogo SAT", str(ctx.exception))

	def test_bloquea_wire_transfer(self):
		"""MoP nativo 'Wire Transfer' → ValidationError."""
		with patch("frappe.db.get_value", side_effect=_mock_get_value({"Wire Transfer": 1})):
			with self.assertRaises(frappe.ValidationError):
				_resolver_forma_pago_sat("Wire Transfer")

	def test_bloquea_check(self):
		"""MoP nativo 'Check' → ValidationError."""
		with patch("frappe.db.get_value", side_effect=_mock_get_value({"Check": 1})):
			with self.assertRaises(frappe.ValidationError):
				_resolver_forma_pago_sat("Check")

	def test_bloquea_credit_card(self):
		"""MoP nativo 'Credit Card' → ValidationError (patrón no cumple)."""
		with patch("frappe.db.get_value", side_effect=_mock_get_value({"Credit Card": 1})):
			with self.assertRaises(frappe.ValidationError):
				_resolver_forma_pago_sat("Credit Card")

	def test_bloquea_mop_deshabilitado(self):
		"""MoP con enabled=0 → ValidationError 'Modo de Pago Deshabilitado'."""
		mop = "03 - Transferencia electrónica de fondos"
		with patch("frappe.db.get_value", side_effect=_mock_get_value({mop: 0})):
			with self.assertRaises(frappe.ValidationError) as ctx:
				_resolver_forma_pago_sat(mop)
		self.assertIn("deshabilitado", str(ctx.exception))

	def test_bloquea_mop_inexistente_en_bd(self):
		"""MoP que no existe en BD (get_value devuelve None) → ValidationError."""
		with patch("frappe.db.get_value", return_value=None):
			with self.assertRaises(frappe.ValidationError) as ctx:
				_resolver_forma_pago_sat("55 - Inexistente")
		self.assertIn("no existe", str(ctx.exception))

	def test_bloquea_patron_sin_guion(self):
		"""Nombre sin ' - ' → ValidationError."""
		with patch("frappe.db.get_value", side_effect=_mock_get_value({"01Efectivo": 1})):
			with self.assertRaises(frappe.ValidationError):
				_resolver_forma_pago_sat("01Efectivo")

	def test_bloquea_letras_en_prefijo(self):
		"""Prefijo con letras 'AB - Algo' no cumple patrón \\d{2}."""
		with patch("frappe.db.get_value", side_effect=_mock_get_value({"AB - Algo": 1})):
			with self.assertRaises(frappe.ValidationError):
				_resolver_forma_pago_sat("AB - Algo")

	def test_bloquea_codigo_no_en_catalogo_sat(self):
		"""Nombre cumple patrón pero código no está en Forma Pago SAT → ValidationError."""
		mop = "55 - Inventado"
		with (
			patch("frappe.db.get_value", side_effect=_mock_get_value({mop: 1})),
			patch("frappe.db.exists", side_effect=_mock_exists(set())),
		):
			with self.assertRaises(frappe.ValidationError) as ctx:
				_resolver_forma_pago_sat(mop)
		self.assertIn("catálogo SAT", str(ctx.exception))

	# -- Verificación del patrón regex --

	def test_patron_acepta_formatos_validos(self):
		"""El patrón regex acepta nombres válidos del fixture."""
		from facturacion_mexico.complementos_pago.api import _PATRON_MOP_SAT

		validos = [
			"01 - Efectivo",
			"03 - Transferencia electrónica de fondos",
			"99 - Por definir",
			"28 - Tarjeta de débito",
		]
		for v in validos:
			self.assertIsNotNone(_PATRON_MOP_SAT.match(v), f"Debería aceptar: {v}")

	def test_patron_rechaza_formatos_invalidos(self):
		"""El patrón regex rechaza nombres no SAT."""
		from facturacion_mexico.complementos_pago.api import _PATRON_MOP_SAT

		invalidos = [
			"Cash",
			"Wire Transfer",
			"Check",
			"Credit Card",
			"Bank Draft",
			"Cheque",
			"1 - Solo un dígito",
		]
		for v in invalidos:
			self.assertIsNone(_PATRON_MOP_SAT.match(v), f"Debería rechazar: {v}")
