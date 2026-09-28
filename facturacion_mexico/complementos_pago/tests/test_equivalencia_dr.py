"""Tests — _equivalencia_dr del flujo saliente (complementos_pago/api.py).

EquivalenciaDR SAT = unidades de MonedaDR por 1 de MonedaP = (MonedaP→MXN)/(MonedaDR→MXN).
Casos: factura USD/pago USD, factura MXN/pago USD, factura USD/pago MXN, misma moneda MXN.
Función pura → `unittest.TestCase`, sin BD ni PAC.
"""

import unittest

from facturacion_mexico.complementos_pago.api import _equivalencia_dr


class TestEquivalenciaDR(unittest.TestCase):
	def test_mxn_mxn(self):
		# MonedaDR=MXN (→MXN=1), MonedaP=MXN (→MXN=1) → 1
		self.assertEqual(_equivalencia_dr("MXN", "MXN", 1.0, 1.0), 1.0)

	def test_usd_usd(self):
		# misma moneda → 1 (regla SAT), sin importar el conversion_rate
		self.assertEqual(_equivalencia_dr("USD", "USD", 17.0, 17.0), 1.0)

	def test_factura_mxn_pago_usd(self):
		# MonedaDR=MXN (→MXN=1), MonedaP=USD (→MXN=17) → EquivalenciaDR = 17 (MXN por USD)
		self.assertEqual(_equivalencia_dr("MXN", "USD", 1.0, 17.0), 17.0)

	def test_factura_usd_pago_mxn(self):
		# MonedaDR=USD (→MXN=20), MonedaP=MXN (→MXN=1) → EquivalenciaDR = 1/20 = 0.05 (USD por MXN)
		self.assertEqual(_equivalencia_dr("USD", "MXN", 20.0, 1.0), 0.05)

	def test_rates_faltantes_default_1(self):
		# tasas None → 1.0 cada una, distinta moneda → 1/1 = 1
		self.assertEqual(_equivalencia_dr("USD", "MXN", None, None), 1.0)


if __name__ == "__main__":
	unittest.main()
