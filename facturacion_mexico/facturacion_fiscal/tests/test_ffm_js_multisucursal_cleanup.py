"""Prueba estática del cleanup de multi-sucursal en el JS de Factura Fiscal Mexico.

Verifica que la corrección temporal de los errores 403/417 (al abrir/refrescar
una FFM) quedó correctamente aplicada en el cliente, sin tocar la lógica de
timbrado.

Contexto: `control_multisucursal_field_visibility` consultaba campos/métodos
inexistentes en Frappe v16 (`System Settings.multisucursal_enabled` → 403 y
`frappe.utils.get_site_config` → 417). La corrección elimina esas llamadas y
oculta los campos multi-sucursal sin tocar el servidor. La implementación
definitiva de multi-sucursal fiscal está documentada en su issue de raíz.

Esta prueba es estática (lee los archivos) — no abre formularios ni ejecuta JS.
"""

import os
import re
import unittest

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

FFM_JS = os.path.join(
	APP_ROOT,
	"facturacion_fiscal",
	"doctype",
	"factura_fiscal_mexico",
	"factura_fiscal_mexico.js",
)

TIMBRADO_API = os.path.join(APP_ROOT, "facturacion_fiscal", "timbrado_api.py")


def _strip_js_line_comments(source: str) -> str:
	"""Devuelve solo las líneas de código JS, eliminando las de comentario `//`.

	El comentario explicativo del cleanup menciona intencionalmente las cadenas
	eliminadas ("System Settings", "frappe.utils.get_site_config"); esta función
	las descarta para que las aserciones evalúen únicamente código ejecutable.
	"""
	code_lines = []
	for line in source.splitlines():
		if line.strip().startswith("//"):
			continue
		code_lines.append(line)
	return "\n".join(code_lines)


class TestFFMJsMultisucursalCleanup(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		with open(FFM_JS, encoding="utf-8") as f:
			cls.js_raw = f.read()
		cls.js_code = _strip_js_line_comments(cls.js_raw)
		with open(TIMBRADO_API, encoding="utf-8") as f:
			cls.timbrado_src = f.read()

	def test_no_system_settings_en_logica_activa(self):
		"""No debe quedar ninguna consulta a System Settings en código ejecutable."""
		self.assertNotIn(
			"System Settings",
			self.js_code,
			"Quedó una referencia activa a 'System Settings' en el JS de FFM (causa 403).",
		)

	def test_no_get_site_config(self):
		"""No debe quedar ninguna llamada a frappe.utils.get_site_config (causa 417)."""
		self.assertNotIn(
			"frappe.utils.get_site_config",
			self.js_code,
			"Quedó una referencia activa a 'frappe.utils.get_site_config' en el JS de FFM (causa 417).",
		)

	def test_no_existe_check_site_config_multisucursal(self):
		"""La función fallback check_site_config_multisucursal debe estar eliminada."""
		self.assertNotIn(
			"check_site_config_multisucursal",
			self.js_raw,
			"La función 'check_site_config_multisucursal' no fue eliminada del JS.",
		)

	def test_control_visibility_llama_hide(self):
		"""control_multisucursal_field_visibility debe llamar a hide_multisucursal_fields."""
		match = re.search(
			r"function\s+control_multisucursal_field_visibility\s*\(frm\)\s*\{([\s\S]*?)\n\s*\}",
			self.js_raw,
		)
		self.assertIsNotNone(
			match,
			"No se encontró la función control_multisucursal_field_visibility.",
		)
		body = match.group(1)
		self.assertIn(
			"hide_multisucursal_fields(frm)",
			body,
			"control_multisucursal_field_visibility no llama a hide_multisucursal_fields.",
		)
		# No debe hacer llamadas al servidor dentro de esta función.
		body_code = _strip_js_line_comments(body)
		self.assertNotIn(
			"frappe.call",
			body_code,
			"control_multisucursal_field_visibility no debe hacer llamadas al servidor.",
		)

	def test_timbrado_api_serie_intacta(self):
		"""Guard: la lógica de serie en timbrado_api.py no fue modificada."""
		self.assertIn(
			'serie_for_pac = "F"',
			self.timbrado_src,
			"Se modificó la resolución de serie en timbrado_api.py (debe permanecer intacta).",
		)

	def test_timbrado_api_payload_sin_lugar_expedicion(self):
		"""Guard: el payload a FacturAPI sigue sin incluir lugar_expedicion."""
		# Aislar el dict invoice_data principal para no leer comentarios sueltos.
		match = re.search(
			r"invoice_data\s*=\s*\{([\s\S]*?)\n\s*\}",
			self.timbrado_src,
		)
		self.assertIsNotNone(match, "No se encontró el dict invoice_data en timbrado_api.py.")
		self.assertNotIn(
			"lugar_expedicion",
			match.group(1),
			"El payload invoice_data ahora incluye lugar_expedicion (no debe cambiar en esta corrección).",
		)
