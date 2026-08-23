"""Prueba estática del modal de éxito de timbrado (issue #56).

El botón "Cerrar" del modal de éxito era un `primary_action` con
`client_action: "frappe.hide_msgprint()"`. Frappe resuelve `client_action`
como ruta de propiedades (no evalúa código), por lo que `hide_msgprint()` con
paréntesis quedaba en `undefined` → clic no-op. El cierre nativo del modal
(X / Escape) siempre funcionó, así que la corrección mínima fue ELIMINAR ese
`primary_action` roto, sin tocar el `try/except` de la FASE 3.

Esta prueba es estática (lee el source) — no abre formularios, no ejecuta JS,
no llama al PAC. Verifica estructuralmente que:
  - el modal de éxito sigue existiendo (se sigue notificando el timbrado);
  - ya no contiene el `primary_action` / `client_action` / `hide_msgprint` roto.
"""

import os
import unittest

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TIMBRADO_API = os.path.join(APP_ROOT, "facturacion_fiscal", "timbrado_api.py")


class TestTimbradoSuccessModalClose(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		with open(TIMBRADO_API, encoding="utf-8") as f:
			cls.src = f.read()

	def _bloque_modal_exito(self) -> str:
		"""Aísla el bloque del `frappe.msgprint(...)` de éxito de timbrado.

		Anclado en la cadena única del modal de éxito ("Factura Timbrada
		Exitosamente"): desde el `frappe.msgprint(` que la precede hasta el
		`base_result` que le sigue (frontera real del bloque en el source).
		"""
		idx = self.src.find("Factura Timbrada Exitosamente")
		self.assertNotEqual(idx, -1, "No se encontró el modal de éxito de timbrado en timbrado_api.py")
		start = self.src.rfind("frappe.msgprint(", 0, idx)
		self.assertNotEqual(start, -1, "No se encontró la llamada frappe.msgprint del modal de éxito")
		end = self.src.find("base_result", idx)
		self.assertNotEqual(end, -1, "No se encontró la frontera 'base_result' tras el modal de éxito")
		bloque = self.src[start:end]
		self.assertIn("Timbrado Exitoso", bloque, "El bloque aislado no es el modal de éxito esperado")
		return bloque

	def test_modal_exito_se_conserva(self):
		"""El modal de éxito debe seguir presentándose tras un timbrado exitoso."""
		bloque = self._bloque_modal_exito()
		self.assertIn("Factura Timbrada Exitosamente", bloque)
		self.assertIn('indicator="green"', bloque)

	def test_sin_primary_action_roto(self):
		"""No debe quedar el `primary_action`/`client_action`/`hide_msgprint` roto."""
		bloque = self._bloque_modal_exito()
		self.assertNotIn("primary_action", bloque)
		self.assertNotIn("client_action", bloque)
		self.assertNotIn("hide_on_success", bloque)
		self.assertNotIn("hide_msgprint", bloque)

	def test_ningun_client_action_en_todo_el_modulo(self):
		"""Salvaguarda global: el patrón inválido no reaparece en el módulo de timbrado."""
		self.assertNotIn("client_action", self.src)
		self.assertNotIn("frappe.hide_msgprint()", self.src)
