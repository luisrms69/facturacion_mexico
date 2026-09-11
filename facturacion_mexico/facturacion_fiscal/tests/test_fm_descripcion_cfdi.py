"""Tests Issue #237 — Descripción fiscal editable por línea (`fm_descripcion_cfdi`).

Cubre:
  - `sanitize_cfdi_description`: HTML→texto plano, entidades, espacios/saltos, límite 1000.
  - `populate_fm_descripcion_cfdi` (auto-llenado en validate): vacío→description; description vacío→
    item_name; valor de usuario conservado y saneado; HTML→texto plano.
  - `resolve_concepto_description`: usa `fm_descripcion_cfdi`; fallback histórico; NC/relación 01.
  - Meta: el campo existe en `Sales Invoice Item` con las propiedades esperadas.

Sin red. Sin sandbox FacturAPI. Funciones puras + meta del DocType.
unittest.TestCase (no FrappeTestCase): son pruebas de funciones puras + lectura de meta; no
requieren transacciones ni preload de test-records (evita el flake de bootstrap de ERPNext).
"""

import unittest

import frappe
from frappe import _dict

from facturacion_mexico.facturacion_fiscal.timbrado_api import resolve_concepto_description
from facturacion_mexico.facturacion_fiscal.utils import sanitize_cfdi_description
from facturacion_mexico.hooks_handlers.sales_invoice_automated_tax import (
	populate_fm_descripcion_cfdi,
)

# ── sanitize_cfdi_description ──────────────────────────────────────────────────


class TestSanitizeCfdiDescription(unittest.TestCase):
	def test_html_a_texto_plano(self):
		self.assertEqual(sanitize_cfdi_description("<div>Llanta <b>205</b></div>"), "Llanta 205")

	def test_entidades_decodificadas(self):
		self.assertEqual(sanitize_cfdi_description("Tornillo &amp; tuerca"), "Tornillo & tuerca")

	def test_nbsp_y_saltos_colapsados(self):
		self.assertEqual(
			sanitize_cfdi_description("Servicio&nbsp;de\n\n  limpieza\t mensual"),
			"Servicio de limpieza mensual",
		)

	def test_espacios_extremos_trim(self):
		self.assertEqual(sanitize_cfdi_description("   Producto X   "), "Producto X")

	def test_limite_1000_caracteres(self):
		out = sanitize_cfdi_description("A" * 1500)
		self.assertEqual(len(out), 1000)

	def test_vacio_y_none(self):
		self.assertEqual(sanitize_cfdi_description(""), "")
		self.assertEqual(sanitize_cfdi_description(None), "")


# ── populate_fm_descripcion_cfdi (auto-llenado en validate) ────────────────────


class TestPopulateFmDescripcionCfdi(unittest.TestCase):
	def _doc(self, *rows):
		return _dict({"items": [_dict(r) for r in rows]})

	def test_vacio_toma_description(self):
		doc = self._doc({"fm_descripcion_cfdi": "", "description": "Llanta 205", "item_name": "LLANTA-A"})
		populate_fm_descripcion_cfdi(doc)
		self.assertEqual(doc["items"][0].fm_descripcion_cfdi, "Llanta 205")

	def test_description_vacia_usa_item_name(self):
		doc = self._doc({"fm_descripcion_cfdi": "", "description": "", "item_name": "ACELGA PZA"})
		populate_fm_descripcion_cfdi(doc)
		self.assertEqual(doc["items"][0].fm_descripcion_cfdi, "ACELGA PZA")

	def test_valor_usuario_se_conserva_saneado(self):
		doc = self._doc(
			{"fm_descripcion_cfdi": "  <b>MI TEXTO</b> fiscal ", "description": "otro", "item_name": "X"}
		)
		populate_fm_descripcion_cfdi(doc)
		self.assertEqual(doc["items"][0].fm_descripcion_cfdi, "MI TEXTO fiscal")

	def test_html_en_description_se_sanea(self):
		doc = self._doc(
			{"fm_descripcion_cfdi": "", "description": "<p>Rin&nbsp;16</p>", "item_name": "RIN-B"}
		)
		populate_fm_descripcion_cfdi(doc)
		self.assertEqual(doc["items"][0].fm_descripcion_cfdi, "Rin 16")

	def test_cap_1000_en_autollenado(self):
		doc = self._doc({"fm_descripcion_cfdi": "", "description": "B" * 1200, "item_name": "X"})
		populate_fm_descripcion_cfdi(doc)
		self.assertEqual(len(doc["items"][0].fm_descripcion_cfdi), 1000)


# ── resolve_concepto_description: fuente y fallback ────────────────────────────


class TestResolveUsaFmDescripcionCfdi(unittest.TestCase):
	def test_usa_fm_descripcion_cfdi_cuando_existe(self):
		item = _dict(
			{"fm_descripcion_cfdi": "DESCRIPCION FISCAL", "description": "comercial", "item_name": "X"}
		)
		self.assertEqual(resolve_concepto_description(item, es_nota_descuento=False), "DESCRIPCION FISCAL")

	def test_fallback_historico_a_description_saneado(self):
		# Documento histórico sin el campo: usa description saneado.
		item = _dict({"description": "<i>Llanta 205</i>", "item_name": "LLANTA-A"})
		self.assertEqual(resolve_concepto_description(item, es_nota_descuento=False), "Llanta 205")

	def test_fallback_historico_a_item_name(self):
		item = _dict({"description": "", "item_name": "LLANTA-A"})
		self.assertEqual(resolve_concepto_description(item, es_nota_descuento=False), "LLANTA-A")

	def test_nota_credito_01_prefija_sobre_fm_descripcion(self):
		# NC por descuento (TipoRelación 01): 'Descuento - <fm_descripcion_cfdi>'.
		item = _dict({"fm_descripcion_cfdi": "Llanta 205", "description": "x", "item_name": "X"})
		self.assertEqual(resolve_concepto_description(item, es_nota_descuento=True), "Descuento - Llanta 205")

	def test_nota_credito_01_idempotente_con_fm_ya_prefijado(self):
		item = _dict({"fm_descripcion_cfdi": "Descuento - Llanta 205", "item_name": "X"})
		self.assertEqual(resolve_concepto_description(item, es_nota_descuento=True), "Descuento - Llanta 205")

	def test_fm_descripcion_cfdi_se_sanea_en_punto_de_uso_post_submit(self):
		# Camino post-submit: al editar un campo allow_on_submit NO corre `validate`, así que
		# `fm_descripcion_cfdi` puede llegar con HTML y >1000 chars. resolve_concepto_description
		# debe sanearlo igual en el punto final de uso: texto plano y máximo 1000 caracteres.
		item = _dict(
			{"fm_descripcion_cfdi": "<b>" + "A" * 1500 + "</b>", "description": "x", "item_name": "X"}
		)
		out = resolve_concepto_description(item, es_nota_descuento=False)
		self.assertNotIn("<", out)
		self.assertEqual(len(out), 1000)
		self.assertEqual(out, "A" * 1000)


# ── Meta del DocType ──────────────────────────────────────────────────────────


class TestMetaFmDescripcionCfdi(unittest.TestCase):
	def test_campo_existe_con_propiedades(self):
		meta = frappe.get_meta("Sales Invoice Item")
		field = next((f for f in meta.fields if f.fieldname == "fm_descripcion_cfdi"), None)
		self.assertIsNotNone(field, "fm_descripcion_cfdi no existe en Sales Invoice Item")
		self.assertEqual(field.fieldtype, "Small Text")
		self.assertEqual(field.allow_on_submit, 1)
		self.assertEqual(field.in_list_view, 1)
		self.assertEqual(field.insert_after, "description")
