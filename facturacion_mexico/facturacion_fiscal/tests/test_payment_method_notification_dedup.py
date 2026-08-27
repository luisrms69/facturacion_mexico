"""Prueba estática de la deduplicación del aviso de método de pago (issue #78).

Un mismo cambio de método de pago disparaba DOS avisos solapados sobre
"99 Por definir": el aviso "Método cambiado a PPD/PUE"
(`show_payment_method_change_notification`) y el aviso "Forma de pago asignada
automáticamente: 99 Por definir" (`handle_payment_form_field_visibility`). La
corrección introduce un guard determinista por transición
(`_should_notify_payment_method`, sobre `frm.__fm_pm_notified === method`) que
hace que solo se muestre un aviso por transición y se re-arme al cambiar a otro
método (una transición nueva legítima vuelve a notificar).

El repo no tiene runner de tests JS, así que esta prueba es estática (lee el
source). La verificación conductual del doble disparo se hace manualmente en el
navegador. Estas aserciones FALLAN con el código previo (sin guard) y PASAN con
el fix.
"""

import os
import unittest

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FFM_JS = os.path.join(
	APP_ROOT, "facturacion_fiscal", "doctype", "factura_fiscal_mexico", "factura_fiscal_mexico.js"
)


class TestPaymentMethodNotificationDedup(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		with open(FFM_JS, encoding="utf-8") as f:
			cls.src = f.read()

	def test_existe_guard_determinista_por_transicion(self):
		"""Debe existir el guard, keyed por método (re-arma), no un debounce temporal."""
		self.assertIn("function _should_notify_payment_method(frm, method) {", self.src)
		self.assertIn("frm.__fm_pm_notified === method", self.src)  # suprime misma transición
		self.assertIn("frm.__fm_pm_notified = method;", self.src)  # re-arma por método
		# No es debounce temporal:
		self.assertNotIn("Date.now()", self.src.split("function _should_notify_payment_method")[1][:400])

	def test_canal1_aviso_metodo_esta_guardado(self):
		"""El aviso 'Método cambiado a PPD/PUE' debe pasar por el guard.

		Esta aserción falla con el código previo (que tenía `if (message) {` sin guard)
		y pasa con el fix.
		"""
		self.assertIn("if (message && _should_notify_payment_method(frm, new_value)) {", self.src)

	def test_canal2_aviso_99_esta_guardado(self):
		"""El aviso 'Forma de pago asignada automáticamente: 99 Por definir' debe pasar por el guard."""
		self.assertIn('_should_notify_payment_method(frm, "PPD")', self.src)

	def test_logica_ppd_99_intacta(self):
		"""La asignación PPD ⇒ 99 (lógica, no aviso) NO se toca."""
		self.assertIn('"fm_forma_pago_timbrado", "99 Por definir"', self.src)

	def test_sin_reejecucion_redundante_del_evento_metodo_pago(self):
		"""El radio handler NO debe re-disparar fm_payment_method_sat.

		`frm.set_value("fm_payment_method_sat", ...)` ya dispara ese evento de formulario
		(que llama a auto_load_payment_method_from_sales_invoice). El `frm.trigger` explícito
		lo ejecutaba una segunda vez -> doble aviso "No se encontró Payment Entry" al cambiar a
		PUE. Esta aserción falla con el código previo y pasa con el fix.
		"""
		self.assertNotIn('frm.trigger("fm_payment_method_sat")', self.src)
