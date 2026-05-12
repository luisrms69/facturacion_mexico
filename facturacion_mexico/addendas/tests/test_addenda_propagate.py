"""
Tests para propagate_addenda_from_customer — Fase 3 Issue #129.

Cubre:
  1. Cliente sin addenda → SI no cambia
  2. Cliente con addenda → SI recibe fm_addenda_required=1 y fm_addenda_type
  3. SI con fm_addenda_required=1 ya seteado → no se sobrescribe (override manual)
  4. SI con fm_addenda_type ya seteado → no se sobrescribe (override manual)
  5. SI sin customer → no hace nada
  6. Draft se puede guardar aunque falten datos (no frappe.throw)
  7. Hook registrado en hooks.py en Sales Invoice.validate
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


def _make_si_doc(
	customer=None,
	fm_addenda_required=0,
	fm_addenda_type=None,
):
	"""Simular un documento Sales Invoice para tests."""
	doc = MagicMock()
	doc.customer = customer
	_fields = {
		"fm_addenda_required": fm_addenda_required,
		"fm_addenda_type": fm_addenda_type,
	}
	doc.get = lambda key, default=None: _fields.get(key, default)

	# Permitir asignación directa como atributo (doc.fm_addenda_required = 1)
	def _setattr(name, value):
		if name in _fields:
			_fields[name] = value
		else:
			object.__setattr__(doc, name, value)

	doc.__class__.__setattr__ = lambda self, name, value: (
		_fields.__setitem__(name, value) if name in _fields else object.__setattr__(self, name, value)
	)
	doc._fields = _fields
	return doc


class TestAddendaPropagate(FrappeTestCase):
	def _call(self, doc):
		from facturacion_mexico.addendas.hooks_handlers.sales_invoice_addenda_propagate import (
			propagate_addenda_from_customer,
		)

		propagate_addenda_from_customer(doc)

	# ── Sin customer ─────────────────────────────────────────────────────────

	def test_no_customer_does_nothing(self):
		doc = _make_si_doc(customer=None)
		self._call(doc)
		self.assertEqual(doc._fields["fm_addenda_required"], 0)
		self.assertIsNone(doc._fields["fm_addenda_type"])

	# ── Cliente sin addenda ──────────────────────────────────────────────────

	def test_customer_without_addenda_leaves_si_unchanged(self):
		doc = _make_si_doc(customer="TEST-CUSTOMER", fm_addenda_required=0, fm_addenda_type=None)

		with patch("frappe.db.get_value") as mock_get:
			mock_get.side_effect = lambda dt, name, field: 0 if field == "fm_requires_addenda" else ""
			self._call(doc)

		self.assertEqual(doc._fields["fm_addenda_required"], 0)
		self.assertIsNone(doc._fields["fm_addenda_type"])

	# ── Cliente con addenda ──────────────────────────────────────────────────

	def test_customer_with_addenda_propagates_to_empty_si(self):
		"""Cliente con addenda → SI recibe required=1 y tipo del cliente."""
		doc = _make_si_doc(customer="TEST-CUSTOMER", fm_addenda_required=0, fm_addenda_type=None)

		with patch("frappe.db.get_value") as mock_get:
			mock_get.side_effect = lambda dt, name, field: 1 if field == "fm_requires_addenda" else "WALMART"
			self._call(doc)

		self.assertEqual(doc._fields["fm_addenda_required"], 1)
		self.assertEqual(doc._fields["fm_addenda_type"], "WALMART")

	def test_customer_with_addenda_required_propagates_required_flag(self):
		"""fm_addenda_required se propaga cuando SI está en 0."""
		doc = _make_si_doc(customer="C1", fm_addenda_required=0)

		with patch("frappe.db.get_value") as mock_get:
			mock_get.side_effect = lambda dt, name, field: 1 if field == "fm_requires_addenda" else ""
			self._call(doc)

		self.assertEqual(doc._fields["fm_addenda_required"], 1)

	def test_customer_with_type_propagates_type(self):
		"""fm_addenda_type se propaga cuando SI no tiene tipo."""
		doc = _make_si_doc(customer="C1", fm_addenda_type=None)

		with patch("frappe.db.get_value") as mock_get:
			mock_get.side_effect = lambda dt, name, field: 0 if field == "fm_requires_addenda" else "SAP"
			self._call(doc)

		self.assertEqual(doc._fields["fm_addenda_type"], "SAP")

	# ── Overrides manuales — no sobrescribir ─────────────────────────────────

	def test_si_with_manual_required_1_not_overwritten(self):
		"""Si SI ya tiene fm_addenda_required=1 (override), no cambiar."""
		doc = _make_si_doc(customer="C1", fm_addenda_required=1, fm_addenda_type=None)

		with patch("frappe.db.get_value") as mock_get:
			mock_get.side_effect = lambda dt, name, field: 0 if field == "fm_requires_addenda" else ""
			self._call(doc)

		# Ya tenía 1, debe seguir en 1 aunque cliente diga 0
		self.assertEqual(doc._fields["fm_addenda_required"], 1)

	def test_si_with_manual_type_not_overwritten(self):
		"""Si SI ya tiene fm_addenda_type configurado (override), no cambiar."""
		doc = _make_si_doc(customer="C1", fm_addenda_required=0, fm_addenda_type="OXXO")

		with patch("frappe.db.get_value") as mock_get:
			mock_get.side_effect = lambda dt, name, field: 1 if field == "fm_requires_addenda" else "WALMART"
			self._call(doc)

		# Tipo manual "OXXO" se preserva, no se sobrescribe con "WALMART"
		self.assertEqual(doc._fields["fm_addenda_type"], "OXXO")

	def test_si_with_both_overrides_not_overwritten(self):
		"""SI con ambos campos manuales — ninguno se sobrescribe."""
		doc = _make_si_doc(customer="C1", fm_addenda_required=1, fm_addenda_type="FEMSA")

		with patch("frappe.db.get_value") as mock_get:
			mock_get.side_effect = lambda dt, name, field: 1 if field == "fm_requires_addenda" else "WALMART"
			self._call(doc)

		self.assertEqual(doc._fields["fm_addenda_required"], 1)
		self.assertEqual(doc._fields["fm_addenda_type"], "FEMSA")

	# ── Draft sin datos — no bloquear ────────────────────────────────────────

	def test_no_frappe_throw_when_draft_missing_addenda_data(self):
		"""Draft con addenda requerida pero sin datos → NO lanza excepción."""
		doc = _make_si_doc(customer="C1", fm_addenda_required=0, fm_addenda_type=None)

		# Simula cliente con addenda requerida (tipo vacío → faltarían datos)
		with patch("frappe.db.get_value") as mock_get:
			mock_get.side_effect = lambda dt, name, field: 1 if field == "fm_requires_addenda" else ""
			# No debe lanzar frappe.ValidationError
			try:
				self._call(doc)
			except frappe.ValidationError:
				self.fail("propagate_addenda_from_customer lanzó ValidationError en draft")

	# ── Hook registrado ──────────────────────────────────────────────────────

	def test_hook_registered_in_hooks_py(self):
		"""El hook debe estar registrado en doc_events['Sales Invoice']['validate']."""
		from facturacion_mexico.hooks import doc_events

		si_events = doc_events.get("Sales Invoice", {})
		validate = si_events.get("validate", [])

		# Puede ser string o lista
		if isinstance(validate, str):
			validate = [validate]

		registered = any(
			"sales_invoice_addenda_propagate.propagate_addenda_from_customer" in v for v in validate
		)
		self.assertTrue(
			registered,
			"Hook propagate_addenda_from_customer no está registrado en Sales Invoice.validate",
		)
