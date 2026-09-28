"""Tests — validación multimoneda de Complemento Pago MX.validate_documentos_relacionados.

Cuadre SAT en MonedaP: importe_MonedaP = ImpPagado / EquivalenciaDR (Decimal). Cubre
MXN/MXN, USD/USD, Pago USD/doc MXN, Pago MXN/doc USD, EquivalenciaDR faltante/negativa,
redondeos multi-documento. Se llama el método desligado sobre un objeto duck-typed (sin BD/PAC).
"""

import types
import unittest

import frappe

from facturacion_mexico.complementos_pago.doctype.complemento_pago_mx.complemento_pago_mx import (
	ComplementoPagoMX,
)


def _doc(imp, moneda_dr, eq, idd="D1", pago_idx=1):
	return frappe._dict(
		imp_pagado=imp, moneda_dr=moneda_dr, equivalencia_dr=eq, id_documento=idd, idx=1, pago_idx=pago_idx
	)


def _pg(pago_idx, moneda_p, monto_p):
	return frappe._dict(pago_idx=pago_idx, moneda_p=moneda_p, monto_p=monto_p)


def _comp(moneda_p, monto_p, docs, pagos=None):
	c = frappe._dict(moneda_p=moneda_p, monto_p=monto_p, documentos_relacionados=docs)
	if pagos is not None:
		c.pagos = pagos
	return c


def _validate(comp):
	# Se invoca el método desligado sobre un doble duck-typed; se inyecta el helper enlazado.
	comp._validar_cuadre_pago = types.MethodType(ComplementoPagoMX._validar_cuadre_pago, comp)
	ComplementoPagoMX.validate_documentos_relacionados(comp)


class TestValidateMultimoneda(unittest.TestCase):
	# ── casos válidos ──
	def test_mxn_mxn(self):
		_validate(_comp("MXN", 1160.0, [_doc(1160.0, "MXN", 1)]))  # no raise

	def test_usd_usd(self):
		_validate(_comp("USD", 100.0, [_doc(100.0, "USD", 1)]))

	def test_pago_usd_doc_mxn(self):
		# MonedaP=USD, MonedaDR=MXN, EquivalenciaDR=20 (MXN por USD) → 2000/20 = 100 USD == Monto
		_validate(_comp("USD", 100.0, [_doc(2000.0, "MXN", 20)]))

	def test_pago_mxn_doc_usd(self):
		# MonedaP=MXN, MonedaDR=USD, EquivalenciaDR=0.05 (USD por MXN) → 100/0.05 = 2000 MXN == Monto
		_validate(_comp("MXN", 2000.0, [_doc(100.0, "USD", 0.05)]))

	def test_equivalencia_1_misma_moneda_vacia_ok(self):
		# EquivalenciaDR vacía permitida como 1 cuando MonedaDR == MonedaP
		_validate(_comp("MXN", 500.0, [_doc(500.0, "MXN", None)]))

	def test_redondeo_multidoc(self):
		# 3 docs, tolerancia 0.01 * 3; suma exacta 100.00
		docs = [_doc(33.33, "MXN", 1, "A"), _doc(33.33, "MXN", 1, "B"), _doc(33.34, "MXN", 1, "C")]
		_validate(_comp("MXN", 100.0, docs))

	# ── casos que deben fallar ──
	def test_equivalencia_faltante_distinta_moneda(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_comp("USD", 100.0, [_doc(2000.0, "MXN", None)]))

	def test_equivalencia_negativa(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_comp("MXN", 100.0, [_doc(100.0, "MXN", -1)]))

	def test_suma_incorrecta(self):
		with self.assertRaises(frappe.ValidationError):
			_validate(_comp("MXN", 1000.0, [_doc(500.0, "MXN", 1)]))

	def test_multimoneda_sin_conversion_falla(self):
		# Pago USD, doc MXN, EquivalenciaDR=1 (incorrecto) → 2000 MXN tratado como 2000 USD ≠ 100
		with self.assertRaises(frappe.ValidationError):
			_validate(_comp("USD", 100.0, [_doc(2000.0, "MXN", 1)]))

	# ── canónico: validación por nodo Pago (pago_idx) ──
	def test_multi_pago_cada_grupo_cuadra(self):
		docs = [_doc(1000.0, "MXN", 1, "A", pago_idx=1), _doc(2000.0, "MXN", 1, "B", pago_idx=2)]
		pagos = [_pg(1, "MXN", 1000.0), _pg(2, "MXN", 2000.0)]
		_validate(_comp("MXN", 1000.0, docs, pagos=pagos))  # no raise (cada Pago cuadra su grupo)

	def test_multi_pago_grupo_no_cuadra_falla(self):
		# Pago 2: docs suman 2000 pero monto_p=1500 → falla solo ese grupo
		docs = [_doc(1000.0, "MXN", 1, "A", pago_idx=1), _doc(2000.0, "MXN", 1, "B", pago_idx=2)]
		pagos = [_pg(1, "MXN", 1000.0), _pg(2, "MXN", 1500.0)]
		with self.assertRaises(frappe.ValidationError):
			_validate(_comp("MXN", 1000.0, docs, pagos=pagos))


if __name__ == "__main__":
	unittest.main()
