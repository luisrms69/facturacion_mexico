"""Guarda ESTÁTICA (análisis de código fuente) contra la regresión del patrón vulnerable
de lookups de Customer en el JavaScript del app.

NO es una prueba funcional de navegador: no ejecuta JavaScript, no renderiza el formulario
ni verifica que el botón Timbrar aparezca. Lee los archivos `.js` como texto y valida, por
expresiones regulares, que los call-sites de Customer usen filtros `{ name: ... }` y no el
docname como string suelto.

Complementa a `test_customer_docname_safe_lookup.py` (que prueba el borde del servidor): esa
prueba dinámica quedaría verde aunque alguien revirtiera el JS a `get_value("Customer", frm.doc.customer, …)`.
Esta prueba estática es la que fallaría en ese caso.

Cubre:
  - que NO exista `frappe.db.get_value`/`frappe.client.get_value` sobre Customer pasando el
    nombre como string suelto (en `sales_invoice.js` y `factura_fiscal_mexico.js`);
  - que los call-sites corregidos usen filtro con `name`;
  - que `_check_rfc_and_show_timbrar` consulte `tax_id` y `fm_rfc_validated` en una sola lectura.
"""

import re

import frappe
from frappe.tests.utils import FrappeTestCase

JS_FILES = {
	"sales_invoice.js": ("public", "js", "sales_invoice.js"),
	"factura_fiscal_mexico.js": (
		"facturacion_fiscal",
		"doctype",
		"factura_fiscal_mexico",
		"factura_fiscal_mexico.js",
	),
}

# .get_value("Customer", <arg2>, ...  — captura el 2º argumento (posiblemente multilínea).
DB_GETVALUE_CUSTOMER = re.compile(r'\.get_value\(\s*(["\'])Customer\1\s*,\s*(.+?)\s*,', re.S)
# method: "frappe.client.get_value"
CLIENT_GETVALUE = re.compile(r'method:\s*["\']frappe\.client\.get_value["\']')


def _read(rel_parts):
	path = frappe.get_app_path("facturacion_mexico", *rel_parts)
	with open(path, encoding="utf-8") as fh:
		return fh.read()


def _func_body(src, name):
	m = re.search(r"function\s+" + re.escape(name) + r"\s*\(", src)
	if not m:
		return ""
	nxt = src.find("\nfunction ", m.end())
	return src[m.start() : nxt if nxt != -1 else len(src)]


class TestSalesInvoiceJsCustomerLookups(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.sources = {name: _read(parts) for name, parts in JS_FILES.items()}

	def test_db_get_value_customer_usa_filtro_dict(self):
		"""Todo `frappe.db.get_value("Customer", X, …)` debe pasar X como dict `{ name: … }`,
		nunca como string suelto (que get_safe_filters/orjson mutila para docnames con comillas)."""
		offenders = []
		for fname, src in self.sources.items():
			for m in DB_GETVALUE_CUSTOMER.finditer(src):
				arg2 = m.group(2).strip()
				if not arg2.startswith("{"):
					line = src.count("\n", 0, m.start()) + 1
					offenders.append(f'{fname}:{line} -> get_value("Customer", {arg2!r}, …)')
		self.assertEqual(
			offenders,
			[],
			"Lookups de Customer con nombre como string suelto (usar { name: … }):\n" + "\n".join(offenders),
		)

	def test_client_get_value_customer_usa_filtro_name(self):
		"""Todo `frappe.client.get_value` sobre Customer debe usar `filters: { name: … }`."""
		offenders = []
		for fname, src in self.sources.items():
			for m in CLIENT_GETVALUE.finditer(src):
				block = src[m.start() : m.start() + 600]
				if not re.search(r'doctype:\s*["\']Customer["\']', block):
					continue
				fm = re.search(r"filters:\s*([^\n]+)", block)
				filt = fm.group(1).strip() if fm else "(sin filters)"
				if "{" not in filt or "name" not in filt:
					line = src.count("\n", 0, m.start()) + 1
					offenders.append(f"{fname}:{line} -> filters: {filt}")
		self.assertEqual(
			offenders,
			[],
			"client.get_value sobre Customer sin filtro { name: … }:\n" + "\n".join(offenders),
		)

	def test_check_rfc_lee_tax_id_y_fm_rfc_validated_juntos(self):
		"""`_check_rfc_and_show_timbrar` debe hacer UNA sola lectura del Customer con filtro
		{ name } que traiga `tax_id` y `fm_rfc_validated` — no dos consultas ni string suelto."""
		body = _func_body(self.sources["sales_invoice.js"], "_check_rfc_and_show_timbrar")
		self.assertTrue(body, "No se encontró _check_rfc_and_show_timbrar en sales_invoice.js")

		# Debe existir el get_value sobre Customer con filtro dict { name ... }.
		self.assertRegex(
			body,
			r'get_value\(\s*"Customer"\s*,\s*\{\s*name',
			"_check_rfc_and_show_timbrar no usa filtro { name } sobre Customer",
		)
		# Debe leer ambos campos en la misma llamada.
		self.assertIn("tax_id", body, "_check_rfc_and_show_timbrar no consulta tax_id")
		self.assertIn("fm_rfc_validated", body, "_check_rfc_and_show_timbrar no consulta fm_rfc_validated")
		# Ya no debe depender del doble round-trip vía has_customer_rfc.
		self.assertNotIn(
			"has_customer_rfc(",
			body,
			"_check_rfc_and_show_timbrar sigue llamando has_customer_rfc (doble consulta)",
		)

	def test_callsites_corregidos_usan_name(self):
		"""Los call-sites concretos que se corrigieron deben verse con filtro { name }."""
		si = self.sources["sales_invoice.js"]
		ffm = self.sources["factura_fiscal_mexico.js"]

		expected = [
			(ffm, r'get_value\(\s*"Customer"\s*,\s*\{\s*name:\s*customer\s*\}\s*,\s*"fm_uso_cfdi_default"'),
			(
				ffm,
				r'get_value\(\s*"Customer"\s*,\s*\{\s*name:\s*currentCustomer\s*\}\s*,\s*"fm_allow_generic_rfc"',
			),
			(
				si,
				r'get_value\(\s*"Customer"\s*,\s*\{\s*name:\s*frm\.doc\.customer\s*\}\s*,\s*"default_price_list"',
			),
			(si, r'get_value\(\s*"Customer"\s*,\s*\{\s*name:\s*frm\.doc\.customer\s*\}\s*,\s*\['),
		]
		for src, pattern in expected:
			self.assertRegex(src, pattern, f"No se encontró call-site corregido: {pattern}")
