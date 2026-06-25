"""Ubicación de los custom fields fiscales de Customer — incidente "Uso CFDI por Defecto".

Contexto: ERPNext 16.24.0 invirtió el orden nativo `tax_withholding_category`/`tax_withholding_group`,
lo que descolocó `fm_uso_cfdi_default` a la pestaña "Fiscal México". El fix re-ancla la cadena a campos
propios para no depender del orden de campos nativos de ERPNext.

Dos tests (solo Customer, alcance del PR del incidente):
A) Estático — la cadena `insert_after` del fixture (no depende de `idx`, no toca BD).
B) Efectivo — tras migrate, la pestaña efectiva y el orden relativo (se camina `meta.fields`; NO se usa
   `.tab`/`.section` server-side, que no son contractuales).
"""

import json

import frappe
from frappe.tests import IntegrationTestCase


def _customer_custom_fields_from_fixture() -> dict:
	"""Lee el fixture custom_field.json y devuelve {name: entry} de los campos de Customer."""
	path = frappe.get_app_path("facturacion_mexico", "fixtures", "custom_field.json")
	with open(path, encoding="utf-8") as fh:
		data = json.load(fh)
	return {c["name"]: c for c in data if isinstance(c, dict) and c.get("dt") == "Customer"}


class TestCustomerUsoCfdiLayout(IntegrationTestCase):
	# ---------- A) cadena insert_after en el fixture (estático) ----------
	def test_fixture_insert_after_chain(self):
		"""La cadena de Customer NO debe depender del orden relativo de los nativos de impuestos:
		el campo ancla a `tax_withholding_group` y el Tab Break a un campo PROPIO."""
		cf = _customer_custom_fields_from_fixture()
		expected = {
			"Customer-fm_uso_cfdi_default": "tax_withholding_group",
			"Customer-fm_validacion_sat_section": "fm_uso_cfdi_default",
			"Customer-fm_fiscal_mexico_tab": "fm_lista_69b_status",
			"Customer-fm_envio_email_cliente": "fm_fiscal_mexico_tab",
		}
		for name, anchor in expected.items():
			self.assertIn(name, cf, f"Falta {name} en el fixture custom_field.json")
			self.assertEqual(
				cf[name].get("insert_after"),
				anchor,
				f"{name}.insert_after debe ser {anchor!r} (cadena propia, robusta a ERPNext)",
			)

	# ---------- B) ubicación efectiva tras migrate ----------
	def _effective_tab_and_order(self):
		"""Camina el meta NO cacheado de Customer y deriva la pestaña efectiva de cada campo.
		NO se usa `df.tab`/`df.section` (no son propiedades contractuales server-side)."""
		frappe.clear_cache(doctype="Customer")
		meta = frappe.get_meta("Customer", cached=False)
		tab_of = {}
		order = []
		current_tab = None
		for f in meta.fields:
			if f.fieldtype == "Tab Break":
				current_tab = f.label or f.fieldname
			tab_of[f.fieldname] = current_tab
			order.append(f.fieldname)
		return tab_of, order

	def test_effective_layout(self):
		tab_of, order = self._effective_tab_and_order()

		# Orden relativo (independiente de idx absoluto)
		seq = [
			"tax_withholding_group",
			"fm_uso_cfdi_default",
			"fm_validacion_sat_section",
			"fm_lista_69b_status",
			"fm_fiscal_mexico_tab",
			"fm_envio_email_cliente",
		]
		for fn in seq:
			self.assertIn(fn, order, f"{fn} no está en el meta de Customer")
		positions = [order.index(fn) for fn in seq]
		self.assertEqual(
			positions,
			sorted(positions),
			f"Orden relativo roto en Customer: {list(zip(seq, positions, strict=True))}",
		)

		# Pestaña efectiva
		self.assertEqual(tab_of.get("fm_uso_cfdi_default"), "Tax", "Uso CFDI por Defecto debe estar en Tax")
		self.assertEqual(tab_of.get("fm_validacion_sat_section"), "Tax")
		self.assertEqual(tab_of.get("fm_lista_69b_status"), "Tax")
		self.assertEqual(
			tab_of.get("fm_envio_email_cliente"),
			"Fiscal México",
			"El bloque posterior al Tab Break debe quedar en Fiscal México",
		)
