"""Tests — receptor extranjero en el payload de timbrado + guard histórico STCT.

Bloque fiscal 1 (correcto en cualquier escenario, sin tocar el IVA):
  - `receptor_tax_id_payload`: nacional → RFC; extranjero → NumRegIdTrib o se omite (nunca XEXX).
  - `es_receptor_extranjero`: reutiliza la clasificación territorial.
  - `_set_stct_by_branch`: no impone STCT cuando el CFDI ya trae `fm_folio_fiscal` (histórico/externo).

Unit (mock), sin red ni BD.
"""

import unittest
from unittest.mock import patch

from frappe import _dict

from facturacion_mexico.facturacion_fiscal.timbrado_api import (
	es_receptor_extranjero,
	receptor_tax_id_payload,
)
from facturacion_mexico.hooks_handlers import sales_invoice_automated_tax
from facturacion_mexico.ventas_extranjeras.clasificacion import EXTRANJERA, NACIONAL

XEXX = "XEXX010101000"


class TestReceptorTaxId(unittest.TestCase):
	def test_nacional_usa_rfc(self):
		cust = _dict(tax_id="XAXX010101000", fm_num_reg_id_trib=None)
		self.assertEqual(receptor_tax_id_payload(cust, es_extranjera=False), "XAXX010101000")

	def test_nacional_rfc_normal(self):
		cust = _dict(tax_id="ABC010101AAA", fm_num_reg_id_trib="US999")
		# nacional: aunque tenga TIN, se usa el RFC
		self.assertEqual(receptor_tax_id_payload(cust, es_extranjera=False), "ABC010101AAA")

	def test_extranjero_con_tin_envia_tin(self):
		cust = _dict(tax_id=XEXX, fm_num_reg_id_trib="US123456789")
		self.assertEqual(receptor_tax_id_payload(cust, es_extranjera=True), "US123456789")

	def test_extranjero_sin_tin_se_omite(self):
		cust = _dict(tax_id=XEXX, fm_num_reg_id_trib=None)
		self.assertIsNone(receptor_tax_id_payload(cust, es_extranjera=True))

	def test_extranjero_tin_vacio_se_omite(self):
		cust = _dict(tax_id=XEXX, fm_num_reg_id_trib="   ")
		self.assertIsNone(receptor_tax_id_payload(cust, es_extranjera=True))

	def test_xexx_nunca_se_envia_como_tax_id_extranjero(self):
		# Aunque tax_id interno sea XEXX (señal territorial), NO se transmite como tax_id extranjero.
		cust = _dict(tax_id=XEXX, fm_num_reg_id_trib=None)
		self.assertNotEqual(receptor_tax_id_payload(cust, es_extranjera=True), XEXX)


class TestEsReceptorExtranjero(unittest.TestCase):
	# `es_receptor_extranjero` importa clasificar_territorialidad perezosamente desde el módulo
	# clasificacion; se parchea ahí.
	def test_extranjera(self):
		with patch(
			"facturacion_mexico.ventas_extranjeras.clasificacion.clasificar_territorialidad",
			return_value=EXTRANJERA,
		):
			self.assertTrue(es_receptor_extranjero(_dict(company="C", customer="X")))

	def test_nacional(self):
		with patch(
			"facturacion_mexico.ventas_extranjeras.clasificacion.clasificar_territorialidad",
			return_value=NACIONAL,
		):
			self.assertFalse(es_receptor_extranjero(_dict(company="C", customer="X")))


class TestGuardImportadorSTCT(unittest.TestCase):
	def test_flag_importador_no_toca_taxes(self):
		# Flag transitorio del importador (cfdi_emitidos) → _set_stct_by_branch retorna sin tocar taxes.
		# Con branch presente: sin el guard intentaría cargar STCT (tocaría taxes / haría db calls).
		doc = _dict(flags=_dict(fm_from_cfdi_emitidos=True), company="C", taxes=["SENTINEL"])
		res = sales_invoice_automated_tax._set_stct_by_branch(doc, "Sucursal X")
		self.assertIsNone(res)
		self.assertEqual(doc.taxes, ["SENTINEL"])  # taxes del XML intactos

	def test_sin_flag_no_corta_en_el_guard_del_importador(self):
		# Sin el flag y sin branch → retorna por el guard de branch (no por el del importador). No lanza.
		doc = _dict(flags=_dict(), company="C", taxes=[])
		self.assertIsNone(sales_invoice_automated_tax._set_stct_by_branch(doc, None))


if __name__ == "__main__":
	unittest.main()
