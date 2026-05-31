"""
Tests para send_notifications — Factura Global.

Cubre:
  1. No envía si notify_global_generation = 0
  2. Envía si notify_global_generation = 1 y hay emails
  3. No lee Facturacion Mexico Settings
  4. Maneja lista separada por comas (trim, vacíos ignorados)
  5. Log de error claro si falta Company Settings
  6. Log de error claro si notify=1 pero sin emails ni creador
"""

from unittest.mock import MagicMock, call, patch

import frappe
from frappe.tests.utils import FrappeTestCase


def _mock_doc(company="Test Company", created_by="user@test.com"):
	doc = MagicMock()
	doc.company = company
	doc.created_by = created_by
	doc.name = "FG-Test-2026-01-0001"
	doc.periodo_inicio = frappe.utils.getdate("2026-01-01")
	doc.periodo_fin = frappe.utils.getdate("2026-01-31")
	doc.total_periodo = 1000.0
	doc.cantidad_receipts = 5
	doc.uuid = "ABCD-1234"
	doc.folio = "001"
	doc.processing_time = 1.5
	return doc


def _mock_cs(notify=1, emails="admin@empresa.com, contabilidad@empresa.com"):
	return frappe._dict({"notify_global_generation": notify, "global_notification_emails": emails})


class TestSendNotifications(FrappeTestCase):
	def _run(self, doc=None, cs=None, cs_exists=True):
		from facturacion_mexico.facturas_globales.hooks_handlers.factura_global_submit import (
			send_notifications,
		)

		doc = doc or _mock_doc()
		db_return = cs if cs_exists else None

		with patch("frappe.db.get_value", return_value=db_return):
			with patch("frappe.sendmail") as mock_mail:
				with patch(
					"facturacion_mexico.facturas_globales.hooks_handlers.factura_global_submit.get_notification_template",
					return_value="<html>test</html>",
				):
					send_notifications(doc)
		return mock_mail

	# ── no envía si notify = 0 ────────────────────────────────────────────────

	def test_no_send_if_notify_off(self):
		"""notify_global_generation=0 → no se envía email."""
		mock_mail = self._run(cs=_mock_cs(notify=0))
		mock_mail.assert_not_called()

	# ── envía si notify = 1 y hay emails ─────────────────────────────────────

	def test_sends_if_notify_on_with_emails(self):
		"""notify=1 y emails configurados → frappe.sendmail llamado."""
		mock_mail = self._run(cs=_mock_cs(notify=1, emails="a@test.com"))
		mock_mail.assert_called_once()

	def test_recipients_include_creator(self):
		"""El usuario creador siempre está en la lista."""
		doc = _mock_doc(created_by="creador@test.com")
		mock_mail = self._run(doc=doc, cs=_mock_cs(notify=1, emails="a@test.com"))
		recipients = mock_mail.call_args.kwargs["recipients"]
		self.assertIn("creador@test.com", recipients)

	# ── no lee Facturacion Mexico Settings ───────────────────────────────────

	def test_does_not_read_single_settings(self):
		"""No llama frappe.get_single('Facturacion Mexico Settings')."""
		with patch("frappe.get_single") as mock_single:
			with patch("frappe.db.get_value", return_value=_mock_cs(notify=0)):
				from facturacion_mexico.facturas_globales.hooks_handlers.factura_global_submit import (
					send_notifications,
				)

				send_notifications(_mock_doc())
		mock_single.assert_not_called()

	# ── maneja lista de emails separada por comas ────────────────────────────

	def test_comma_separated_emails_trimmed(self):
		"""Emails separados por coma con espacios → todos incluidos, sin espacios."""
		cs = _mock_cs(notify=1, emails="  a@test.com , b@test.com ,  c@test.com  ")
		mock_mail = self._run(cs=cs)
		recipients = mock_mail.call_args.kwargs["recipients"]
		self.assertIn("a@test.com", recipients)
		self.assertIn("b@test.com", recipients)
		self.assertIn("c@test.com", recipients)

	def test_empty_entries_in_emails_ignored(self):
		"""Entradas vacías en la lista de emails se ignoran."""
		cs = _mock_cs(notify=1, emails="a@test.com,,  ,b@test.com")
		mock_mail = self._run(cs=cs)
		recipients = mock_mail.call_args.kwargs["recipients"]
		self.assertNotIn("", recipients)
		self.assertNotIn(" ", recipients)

	def test_duplicate_emails_deduped(self):
		"""Emails duplicados se deducan."""
		doc = _mock_doc(created_by="a@test.com")
		cs = _mock_cs(notify=1, emails="a@test.com,b@test.com")
		mock_mail = self._run(doc=doc, cs=cs)
		recipients = mock_mail.call_args.kwargs["recipients"]
		self.assertEqual(recipients.count("a@test.com"), 1)

	# ── falla claro si falta Company Settings ────────────────────────────────

	def test_logs_error_if_no_company_settings(self):
		"""Sin Company Settings → log de error, no excepción."""
		with patch("frappe.db.get_value", return_value=None):
			with patch("frappe.log_error") as mock_log:
				with patch("frappe.sendmail") as mock_mail:
					from facturacion_mexico.facturas_globales.hooks_handlers.factura_global_submit import (
						send_notifications,
					)

					send_notifications(_mock_doc())
		mock_mail.assert_not_called()
		mock_log.assert_called()

	# ── log claro si notify=1 pero sin emails ────────────────────────────────

	def test_logs_error_if_notify_on_but_no_emails_no_creator(self):
		"""notify=1 pero emails vacíos y sin creador → log de error."""
		doc = _mock_doc(created_by=None)
		cs = _mock_cs(notify=1, emails="")
		with patch("frappe.db.get_value", return_value=cs):
			with patch("frappe.log_error") as mock_log:
				with patch("frappe.sendmail") as mock_mail:
					with patch(
						"facturacion_mexico.facturas_globales.hooks_handlers.factura_global_submit.get_notification_template",
						return_value="",
					):
						from facturacion_mexico.facturas_globales.hooks_handlers.factura_global_submit import (
							send_notifications,
						)

						send_notifications(doc)
		mock_mail.assert_not_called()
		mock_log.assert_called()
