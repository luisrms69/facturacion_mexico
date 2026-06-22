"""Prueba estática del registro del motor de reconciliación en scheduler_events (Paso 4).

Verifica que run_auto_reconciliation esté en `hourly_long`, una sola vez, y NO en ningún otro
evento. Es estática (inspecciona hooks.scheduler_events); no ejecuta el scheduler ni el PAC.
"""

from frappe.tests import IntegrationTestCase

from facturacion_mexico import hooks

_RECON = "facturacion_mexico.facturacion_fiscal.services.ffm_reconciliation.run_auto_reconciliation"


def _count_in_event(value, target):
	"""Cuenta apariciones de `target` en un valor de scheduler_events (lista o dict de listas)."""
	if isinstance(value, list):
		return value.count(target)
	if isinstance(value, dict):
		return sum(tasks.count(target) for tasks in value.values() if isinstance(tasks, list))
	return 0


class TestSchedulerHooks(IntegrationTestCase):
	def test_hourly_long_existe_con_motor(self):
		se = hooks.scheduler_events
		self.assertIn("hourly_long", se)
		self.assertIn(_RECON, se["hourly_long"])

	def test_motor_no_en_otros_eventos(self):
		se = hooks.scheduler_events
		for evento, value in se.items():
			if evento == "hourly_long":
				continue
			self.assertEqual(
				_count_in_event(value, _RECON), 0, f"El motor no debe estar en el evento '{evento}'"
			)

	def test_motor_no_duplicado(self):
		se = hooks.scheduler_events
		# Exactamente una vez en hourly_long y una vez en total (todos los eventos).
		self.assertEqual(se["hourly_long"].count(_RECON), 1)
		total = sum(_count_in_event(value, _RECON) for value in se.values())
		self.assertEqual(total, 1)
