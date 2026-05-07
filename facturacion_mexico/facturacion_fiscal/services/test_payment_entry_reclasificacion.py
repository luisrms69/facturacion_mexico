# Copyright (c) 2026, Buzola and contributors
# For license information, please see license.txt

"""
Tests: cargar_impuestos_en_payment_entry y _calcular_grupos_desde_doc

Estrategia:
- Tests de _calcular_grupos_desde_doc: mockean frappe.get_doc en el módulo destino
- Tests de cargar_impuestos_en_payment_entry: mockean _calcular_grupos_desde_doc
  para aislar la lógica de carga de filas sin depender de inserción de SI/PE

Fórmula verificada:
  monto_reclasificar = tax_amount * (allocated_amount / grand_total)
  rate = monto_reclasificar / paid_amount * 100
"""

import unittest
from unittest import mock

import frappe
from frappe.utils import flt

from facturacion_mexico.facturacion_fiscal.services import payment_entry_reclasificacion
from facturacion_mexico.facturacion_fiscal.services.payment_entry_reclasificacion import (
	_RECLAS_MARKER,
	_calcular_grupos_desde_doc,
	cargar_impuestos_en_payment_entry,
)

_COMPANY = "_Test Company"
_TAX_PARENT = "Source of Funds (Liabilities) - _TC"
_MODULE = "facturacion_mexico.facturacion_fiscal.services.payment_entry_reclasificacion"


def _ensure_test_prerequisites():
	"""Crea estructura mínima requerida para los tests: empresa y cuenta padre."""
	if not frappe.db.exists("Company", _COMPANY):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test Company",
				"abbr": "_TC",
				"default_currency": "MXN",
				"country": "Mexico",
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit

	if not frappe.db.exists("Account", _TAX_PARENT):
		parent = frappe.db.get_value(
			"Account",
			{"company": _COMPANY, "root_type": "Liability", "is_group": 1},
			"name",
			order_by="lft asc",
		)
		if parent:
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "Source of Funds (Liabilities)",
					"is_group": 1,
					"company": _COMPANY,
					"parent_account": parent,
					"root_type": "Liability",
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit


def _ensure_account(name, account_name):
	if not frappe.db.exists("Account", name):
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"account_type": "Tax",
				"is_group": 0,
				"company": _COMPANY,
				"parent_account": _TAX_PARENT,
				"root_type": "Liability",
			}
		).insert(ignore_permissions=True)
	return name


def _ensure_mapeo(origen, destino, company=_COMPANY):
	existing = frappe.db.get_value(
		"Mapeo Reclasificacion Fiscal Payment Entry",
		{"company": company, "tipo_operacion": "Cobro", "cuenta_origen": origen, "activo": 1},
		"name",
	)
	if existing:
		return existing
	doc = frappe.new_doc("Mapeo Reclasificacion Fiscal Payment Entry")
	doc.company = company
	doc.tipo_operacion = "Cobro"
	doc.cuenta_origen = origen
	doc.cuenta_destino = destino
	doc.activo = 1
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_pe_mock(paid_amount=1160.0, si_name="MOCK-SI-001", allocated=None, grand_total=None):
	"""PE en memoria con referencias ficticias. No inserta en BD."""
	if allocated is None:
		allocated = paid_amount
	if grand_total is None:
		grand_total = paid_amount
	ref = frappe._dict(
		reference_doctype="Sales Invoice",
		reference_name=si_name,
		allocated_amount=allocated,
		outstanding_amount=grand_total,
	)
	pe = frappe._dict(company=_COMPANY, payment_type="Receive", paid_amount=paid_amount)
	pe["references"] = [ref]
	pe["taxes"] = []
	pe["apply_taxes"] = lambda: None
	pe.get = lambda field, default=None: pe[field] if field in pe else default
	pe.append = lambda table, row: pe["taxes"].append(frappe._dict(row))
	return pe


def _make_si_mock(grand_total=1160.0, tax_amount=160.0, account_head=None, origen=None):
	"""SI ficticia con los datos mínimos para _calcular_grupos_desde_doc."""
	ah = account_head or origen
	tax_row = frappe._dict(account_head=ah, tax_amount=tax_amount, description="IVA Test")
	si = frappe._dict(grand_total=grand_total, outstanding_amount=grand_total)
	si["taxes"] = [tax_row]
	si.get = lambda field, default=None: si[field] if field in si else default
	return si


class TestPaymentEntryReclasificacion(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.clear_cache()
		_ensure_test_prerequisites()
		cls.origen = _ensure_account("Test IVA Pendiente - _TC", "Test IVA Pendiente")
		cls.destino = _ensure_account("Test IVA Cobrado - _TC", "Test IVA Cobrado")
		cls.otro = _ensure_account("Test IVA Sin Mapeo - _TC", "Test IVA Sin Mapeo")
		_ensure_mapeo(cls.origen, cls.destino)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist test fixtures

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete(
			"Mapeo Reclasificacion Fiscal Payment Entry",
			{"company": _COMPANY, "cuenta_origen": ["in", [cls.origen, cls.otro]]},
		)
		for acc in ["Test IVA Pendiente - _TC", "Test IVA Cobrado - _TC", "Test IVA Sin Mapeo - _TC"]:
			if frappe.db.exists("Account", acc):
				frappe.delete_doc("Account", acc, ignore_permissions=True, force=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit

	def tearDown(self):
		frappe.db.rollback()

	# -----------------------------------------------------------------------
	# Tests de _calcular_grupos_desde_doc
	# Mockean frappe.get_doc en el módulo de producción
	# -----------------------------------------------------------------------

	def test_calcular_grupos_retorna_monto_correcto(self):
		"""_calcular_grupos_desde_doc retorna el monto proporcional correcto."""
		grand_total, tax_amount, allocated = 1160.0, 160.0, 1160.0
		si_mock = _make_si_mock(grand_total, tax_amount, origen=self.origen)
		pe = _make_pe_mock(allocated, grand_total=grand_total)

		with mock.patch.object(payment_entry_reclasificacion.frappe, "get_doc", return_value=si_mock):
			grupos = _calcular_grupos_desde_doc(pe)

		key = (self.origen, self.destino, "Cobro")
		self.assertIn(key, grupos)
		self.assertAlmostEqual(grupos[key], tax_amount, places=2)

	def test_calcular_grupos_proporcion_parcial(self):
		"""_calcular_grupos_desde_doc calcula monto proporcional para pago parcial."""
		grand_total, tax_amount, allocated = 1160.0, 160.0, 580.0
		si_mock = _make_si_mock(grand_total, tax_amount, origen=self.origen)
		pe = _make_pe_mock(allocated, allocated=allocated, grand_total=grand_total)

		with mock.patch.object(payment_entry_reclasificacion.frappe, "get_doc", return_value=si_mock):
			grupos = _calcular_grupos_desde_doc(pe)

		key = (self.origen, self.destino, "Cobro")
		expected = round(tax_amount * (allocated / grand_total), 6)
		self.assertAlmostEqual(grupos[key], expected, places=4)

	def test_calcular_grupos_sin_mapeo_retorna_vacio(self):
		"""SI con account_head sin mapeo activo retorna grupos vacíos."""
		si_mock = _make_si_mock(1160.0, 160.0, origen=self.otro)
		pe = _make_pe_mock(1160.0, grand_total=1160.0)

		with mock.patch.object(payment_entry_reclasificacion.frappe, "get_doc", return_value=si_mock):
			grupos = _calcular_grupos_desde_doc(pe)

		self.assertEqual(len(grupos), 0)

	def test_calcular_grupos_impuesto_cero_ignorado(self):
		"""tax_amount=0 no genera grupo."""
		si_mock = _make_si_mock(1000.0, 0.0, origen=self.origen)
		pe = _make_pe_mock(1000.0, grand_total=1000.0)

		with mock.patch.object(payment_entry_reclasificacion.frappe, "get_doc", return_value=si_mock):
			grupos = _calcular_grupos_desde_doc(pe)

		self.assertEqual(len(grupos), 0)

	# -----------------------------------------------------------------------
	# Tests de cargar_impuestos_en_payment_entry
	# Mockean _calcular_grupos_desde_doc para aislar la lógica de filas
	# -----------------------------------------------------------------------

	def _run_cargar(self, grand_total=1160.0, tax_amount=160.0, allocated=None, grupos_override=None):
		"""Helper: corre cargar_impuestos con grupos mockeados."""
		if allocated is None:
			allocated = grand_total
		pe = _make_pe_mock(allocated, grand_total=grand_total)
		monto = tax_amount * (allocated / grand_total)
		grupos = (
			grupos_override if grupos_override is not None else {(self.origen, self.destino, "Cobro"): monto}
		)
		with mock.patch(f"{_MODULE}._calcular_grupos_desde_doc", return_value=grupos):
			cargar_impuestos_en_payment_entry(pe)
		return pe

	def test_carga_filas_en_validate(self):
		"""cargar_impuestos agrega exactamente 2 filas de reclasificación."""
		pe = self._run_cargar()
		reclas = [t for t in pe["taxes"] if _RECLAS_MARKER in (t.get("description") or "")]
		self.assertEqual(len(reclas), 2)

	def test_rate_pago_total(self):
		"""rate = tax_amount / grand_total * 100 para pago total."""
		grand_total, tax_amount = 1160.0, 160.0
		pe = self._run_cargar(grand_total, tax_amount, allocated=grand_total)
		expected_rate = round(tax_amount / grand_total * 100, 6)
		destino_row = next(
			t
			for t in pe["taxes"]
			if _RECLAS_MARKER in (t.get("description") or "") and t.account_head == self.destino
		)
		self.assertAlmostEqual(destino_row.rate, expected_rate, places=4)

	def test_rate_pago_parcial(self):
		"""
		Pago parcial — verifica fórmula exacta:
		  monto_reclasificar = tax_amount * (allocated_amount / grand_total)
		  rate = monto_reclasificar / paid_amount * 100
		"""
		grand_total, tax_amount, allocated = 1160.0, 160.0, 580.0
		pe = self._run_cargar(grand_total, tax_amount, allocated=allocated)

		monto_reclasificar = tax_amount * (allocated / grand_total)
		expected_rate = round(monto_reclasificar / allocated * 100, 6)

		destino_row = next(
			t
			for t in pe["taxes"]
			if _RECLAS_MARKER in (t.get("description") or "") and t.account_head == self.destino
		)
		self.assertAlmostEqual(destino_row.rate, expected_rate, places=4)
		self.assertAlmostEqual(destino_row.tax_amount, round(monto_reclasificar, 2), places=1)

	def test_filas_limpian_en_re_validate(self):
		"""Re-ejecutar cargar_impuestos no duplica filas."""
		pe = self._run_cargar()
		count_antes = len([t for t in pe["taxes"] if _RECLAS_MARKER in (t.get("description") or "")])

		monto = 160.0
		grupos = {(self.origen, self.destino, "Cobro"): monto}
		with mock.patch(f"{_MODULE}._calcular_grupos_desde_doc", return_value=grupos):
			cargar_impuestos_en_payment_entry(pe)

		count_despues = len([t for t in pe["taxes"] if _RECLAS_MARKER in (t.get("description") or "")])
		self.assertEqual(count_antes, count_despues)

	def test_sin_mapeo_no_carga_filas(self):
		"""Grupos vacíos → PE sin filas de reclasificación."""
		pe = self._run_cargar(grupos_override={})
		reclas = [t for t in pe["taxes"] if _RECLAS_MARKER in (t.get("description") or "")]
		self.assertEqual(len(reclas), 0)

	def test_included_in_paid_amount_1(self):
		"""Todas las filas tienen included_in_paid_amount = 1."""
		pe = self._run_cargar()
		reclas = [t for t in pe["taxes"] if _RECLAS_MARKER in (t.get("description") or "")]
		for fila in reclas:
			self.assertEqual(fila.included_in_paid_amount, 1)

	def test_destino_rate_positivo_origen_negativo(self):
		"""Destino rate > 0, origen rate < 0, misma magnitud."""
		pe = self._run_cargar()
		reclas = [t for t in pe["taxes"] if _RECLAS_MARKER in (t.get("description") or "")]
		destino = next(t for t in reclas if t.account_head == self.destino)
		origen = next(t for t in reclas if t.account_head == self.origen)
		self.assertGreater(destino.rate, 0)
		self.assertLess(origen.rate, 0)
		self.assertAlmostEqual(abs(destino.rate), abs(origen.rate), places=4)

	def test_rates_se_anulan(self):
		"""Suma de rates = 0 → total_taxes_and_charges no cambia."""
		pe = self._run_cargar()
		reclas = [t for t in pe["taxes"] if _RECLAS_MARKER in (t.get("description") or "")]
		total_rates = sum(t.rate for t in reclas)
		self.assertAlmostEqual(total_rates, 0.0, places=4)

	def test_impuesto_cero_ignorado(self):
		"""Grupos vacíos por tax_amount=0 → no hay filas."""
		pe = self._run_cargar(tax_amount=0.0, grupos_override={})
		reclas = [t for t in pe["taxes"] if _RECLAS_MARKER in (t.get("description") or "")]
		self.assertEqual(len(reclas), 0)
