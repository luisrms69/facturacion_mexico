"""
Tests MVP Complemento Pago MX — PR #94

Sin red. Sin sandbox FacturAPI. Mocks solo en boundary externo.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestComplementoStatusSchema(FrappeTestCase):
	"""Verifica que el campo status existe y complement_status no se usa."""

	def test_campo_status_existe_en_doctype(self):
		meta = frappe.get_meta("Complemento Pago MX")
		field_names = [f.fieldname for f in meta.fields]
		self.assertIn("status", field_names)

	def test_complement_status_no_en_doctype(self):
		meta = frappe.get_meta("Complemento Pago MX")
		field_names = [f.fieldname for f in meta.fields]
		self.assertNotIn("complement_status", field_names)

	def test_status_opciones_validas(self):
		meta = frappe.get_meta("Complemento Pago MX")
		field = next(f for f in meta.fields if f.fieldname == "status")
		opciones = [o.strip() for o in field.options.strip().split("\n") if o.strip()]
		for estado in ["Pendiente", "Timbrado", "Pendiente Cancelación", "Cancelado", "Error"]:
			self.assertIn(estado, opciones, f"Estado '{estado}' no encontrado en opciones")

	def test_states_configurados_en_doctype(self):
		states = frappe.get_all(
			"DocType State",
			filters={"parent": "Complemento Pago MX"},
			fields=["title", "color"],
		)
		titulos = [s.title for s in states]
		self.assertIn("Timbrado", titulos, "Estado 'Timbrado' no configurado en states")
		self.assertIn("Cancelado", titulos, "Estado 'Cancelado' no configurado en states")

	def test_fm_ultimo_response_log_existe(self):
		meta = frappe.get_meta("Complemento Pago MX")
		field_names = [f.fieldname for f in meta.fields]
		self.assertIn("fm_ultimo_response_log", field_names)

	def test_complement_status_no_en_codigo_activo(self):
		"""complement_status no debe aparecer en api.py ni en hooks_handlers activos."""
		import ast
		import os

		archivos = [
			"facturacion_mexico/complementos_pago/api.py",
			"facturacion_mexico/complementos_pago/hooks_handlers/payment_entry_cancel.py",
			"facturacion_mexico/api/complemento_summary.py",
		]
		base = frappe.get_app_path("facturacion_mexico", "..")
		for archivo in archivos:
			ruta = os.path.join(base, archivo)
			if not os.path.exists(ruta):
				continue
			with open(ruta) as f:
				contenido = f.read()
			self.assertNotIn(
				"complement_status",
				contenido,
				f"'complement_status' encontrado en {archivo}",
			)


class TestBloqueoPaymentEntry(FrappeTestCase):
	"""Verifica que el PE se bloquea/desbloquea según el estado del complemento."""

	def _make_pe_doc(self, comp_name):
		doc = MagicMock()
		doc.name = "ACC-PAY-TEST"
		doc.fm_complemento_pago = comp_name
		return doc

	def _assert_bloquea(self, status):
		from facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_cancel import (
			block_cancel_if_complemento_activo,
		)

		comp_name = f"COMP-TEST-{status[:4].upper()}"
		doc = self._make_pe_doc(comp_name)

		with patch("frappe.db.get_value", return_value=status):
			with self.assertRaises(frappe.ValidationError):
				block_cancel_if_complemento_activo(doc)

	def _assert_permite(self, status):
		from facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_cancel import (
			block_cancel_if_complemento_activo,
		)

		comp_name = f"COMP-TEST-{status[:4].upper()}"
		doc = self._make_pe_doc(comp_name)

		with patch("frappe.db.get_value", return_value=status):
			block_cancel_if_complemento_activo(doc)  # no debe lanzar

	def test_bloquea_con_timbrado(self):
		self._assert_bloquea("Timbrado")

	def test_bloquea_con_pendiente_cancelacion(self):
		self._assert_bloquea("Pendiente Cancelación")

	def test_bloquea_con_pendiente(self):
		self._assert_bloquea("Pendiente")

	def test_bloquea_con_error(self):
		self._assert_bloquea("Error")

	def test_permite_con_cancelado(self):
		self._assert_permite("Cancelado")

	def test_permite_sin_complemento(self):
		from facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_cancel import (
			block_cancel_if_complemento_activo,
		)

		doc = MagicMock()
		doc.get.return_value = None  # doc.get("fm_complemento_pago") retorna None
		block_cancel_if_complemento_activo(doc)  # no debe lanzar


class TestHookRegistrado(FrappeTestCase):
	"""Verifica que el hook before_cancel está registrado en Payment Entry."""

	def test_before_cancel_hook_registrado(self):
		from facturacion_mexico import hooks

		doc_events = getattr(hooks, "doc_events", {})
		pe_hooks = doc_events.get("Payment Entry", {})
		before_cancel = pe_hooks.get("before_cancel", "")
		self.assertIn(
			"block_cancel_if_complemento_activo",
			before_cancel,
			"Hook before_cancel no registrado en Payment Entry",
		)


class TestResponseLogOperationTypes(FrappeTestCase):
	"""Verifica que los operation_type del Response Log existen en el DocType."""

	def test_operation_types_complemento_existen(self):
		meta = frappe.get_meta("FacturAPI Response Log")
		field = next(f for f in meta.fields if f.fieldname == "operation_type")
		opciones = [o.strip() for o in field.options.strip().split("\n") if o.strip()]
		for op in [
			"Timbrado Complemento Pago",
			"Cancelación Complemento Pago",
			"Consulta Estado Complemento Pago",
		]:
			self.assertIn(op, opciones, f"operation_type '{op}' no encontrado")

	def test_campo_complemento_pago_mx_en_log(self):
		meta = frappe.get_meta("FacturAPI Response Log")
		field_names = [f.fieldname for f in meta.fields]
		self.assertIn("complemento_pago_mx", field_names)


class TestInterpretarRespuestaCancelacion(FrappeTestCase):
	"""Verifica la lógica de interpretación de respuesta PAC."""

	def setUp(self):
		from facturacion_mexico.complementos_pago.api import _interpretar_respuesta_cancelacion

		self.interpretar = _interpretar_respuesta_cancelacion

	def test_accepted_da_cancelado(self):
		status, estatus_sat = self.interpretar({"cancellation_status": "accepted"})
		self.assertEqual(status, "Cancelado")
		self.assertEqual(estatus_sat, "Cancelado")

	def test_status_canceled_da_cancelado(self):
		status, estatus_sat = self.interpretar({"status": "canceled"})
		self.assertEqual(status, "Cancelado")
		self.assertEqual(estatus_sat, "Cancelado")

	def test_pending_da_pendiente_cancelacion(self):
		status, estatus_sat = self.interpretar({"cancellation_status": "pending"})
		self.assertEqual(status, "Pendiente Cancelación")
		self.assertEqual(estatus_sat, "Pendiente Cancelación")

	def test_rejected_da_timbrado(self):
		status, estatus_sat = self.interpretar({"cancellation_status": "rejected"})
		self.assertEqual(status, "Timbrado")
		self.assertEqual(estatus_sat, "Vigente")

	def test_desconocido_fallback_conservador(self):
		status, estatus_sat = self.interpretar({})
		self.assertEqual(status, "Pendiente Cancelación")

	def test_accepted_libera_pe(self):
		"""_aplicar_cancelacion limpia PE cuando status=Cancelado."""
		from facturacion_mexico.complementos_pago.api import _aplicar_cancelacion

		comp_doc = MagicMock()
		comp_doc.flags = MagicMock()

		with patch("frappe.db.set_value") as mock_set, patch("frappe.get_doc", return_value=comp_doc):
			_aplicar_cancelacion("COMP-TEST", "ACC-PAY-TEST", "Cancelado", "Cancelado")

			# Verificar que PE fue liberado
			calls = [str(c) for c in mock_set.call_args_list]
			pe_call = next((c for c in calls if "ACC-PAY-TEST" in c), None)
			self.assertIsNotNone(pe_call, "PE no fue actualizado en cancelación accepted")

	def test_pending_no_libera_pe(self):
		"""_aplicar_cancelacion NO limpia PE cuando status=Pendiente Cancelación."""
		from facturacion_mexico.complementos_pago.api import _aplicar_cancelacion

		with patch("frappe.db.set_value") as mock_set, patch("frappe.get_doc") as mock_get:
			_aplicar_cancelacion(
				"COMP-TEST", "ACC-PAY-TEST", "Pendiente Cancelación", "Pendiente Cancelación"
			)

			# get_doc no debe llamarse (no hay cancel ni liberación de PE)
			mock_get.assert_not_called()


class TestAmendBloqueado(FrappeTestCase):
	"""Verifica que before_cancel bloquea cancel directo (protege también el amend)."""

	def test_before_cancel_bloquea_sin_flag(self):
		from facturacion_mexico.complementos_pago.doctype.complemento_pago_mx.complemento_pago_mx import (
			ComplementoPagoMX,
		)

		doc = MagicMock(spec=ComplementoPagoMX)
		doc.flags = MagicMock()
		doc.flags.allow_fiscal_cancel = False
		type(doc.flags).allow_fiscal_cancel = property(lambda self: False)

		instance = ComplementoPagoMX.__new__(ComplementoPagoMX)
		instance.flags = MagicMock()
		instance.flags.allow_fiscal_cancel = False

		with self.assertRaises(frappe.ValidationError):
			instance.before_cancel()

	def test_before_cancel_permite_con_flag(self):
		from facturacion_mexico.complementos_pago.doctype.complemento_pago_mx.complemento_pago_mx import (
			ComplementoPagoMX,
		)

		instance = ComplementoPagoMX.__new__(ComplementoPagoMX)
		instance.flags = MagicMock()
		instance.flags.allow_fiscal_cancel = True

		instance.before_cancel()  # no debe lanzar
