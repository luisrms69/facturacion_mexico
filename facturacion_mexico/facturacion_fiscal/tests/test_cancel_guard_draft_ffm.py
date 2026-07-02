"""Regresión: `cancelar_si_post_fiscal` ignora la FFM BORRADOR nunca timbrada (duplicado huérfano).

Caso real (ACC-SINV-2026-02932): una FFM válida `CANCELADO` (submitted, con UUID/facturapi_id) y
una segunda FFM BORRADOR (docstatus=0, sin UUID ni facturapi_id) ligadas a la misma SI. La draft NO
debe bloquear la cancelación de la SI, y NO debe eliminarse, modificarse ni desvincularse; su
Response Log debe permanecer intacto. El guard sigue bloqueando cualquier FFM fiscalmente activa.

Solo se simula el boundary de ERPNext (`Document.cancel`, que hace GL) — cero PAC real.
"""

import unittest.mock as mock

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.api.fiscal_operations import (
	_es_ffm_borrador_sin_timbrar,
	cancelar_si_post_fiscal,
)


def _seed_si():
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"net_total": 100,
			"grand_total": 116,
			"posting_date": frappe.utils.today(),
			"docstatus": 1,
			"fm_fiscal_status": "CANCELADO",
		}
	)
	si.flags.ignore_validate = True
	si.flags.ignore_mandatory = True
	si.flags.ignore_links = True
	si.db_insert()
	return si.name


def _seed_ffm(sales_invoice, status, docstatus, *, uuid=None, facturapi_id=None):
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"sales_invoice": sales_invoice,
			"status": status,
			"docstatus": docstatus,
			"fm_uuid": uuid,
			"facturapi_id": facturapi_id,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	return ffm.name


class TestEsFfmBorradorSinTimbrar(IntegrationTestCase):
	"""Predicado puro: qué FFM es 'borrador sin timbrar' (no fiscalmente activa)."""

	def test_draft_sin_timbrar_es_true(self):
		self.assertTrue(
			_es_ffm_borrador_sin_timbrar(
				{"name": "FFM-A", "docstatus": 0, "status": "BORRADOR", "fm_uuid": None, "facturapi_id": None}
			)
		)
		self.assertTrue(
			_es_ffm_borrador_sin_timbrar(
				{"name": "FFM-A", "docstatus": 0, "status": "BORRADOR", "fm_uuid": "", "facturapi_id": ""}
			)
		)

	def test_con_uuid_o_facturapi_o_submitted_es_false(self):
		self.assertFalse(  # tiene UUID
			_es_ffm_borrador_sin_timbrar(
				{
					"name": "FFM-A",
					"docstatus": 0,
					"status": "BORRADOR",
					"fm_uuid": "U-1",
					"facturapi_id": None,
				}
			)
		)
		self.assertFalse(  # tiene facturapi_id
			_es_ffm_borrador_sin_timbrar(
				{
					"name": "FFM-A",
					"docstatus": 0,
					"status": "BORRADOR",
					"fm_uuid": None,
					"facturapi_id": "FA-1",
				}
			)
		)
		self.assertFalse(  # submitted
			_es_ffm_borrador_sin_timbrar(
				{"name": "FFM-A", "docstatus": 1, "status": "BORRADOR", "fm_uuid": None, "facturapi_id": None}
			)
		)

	def test_status_no_borrador_es_false(self):
		# PROCESANDO/PENDIENTE (posible operación en curso ante el PAC) NO es "borrador sin timbrar"
		self.assertFalse(
			_es_ffm_borrador_sin_timbrar(
				{
					"name": "FFM-A",
					"docstatus": 0,
					"status": "PROCESANDO",
					"fm_uuid": None,
					"facturapi_id": None,
				}
			)
		)
		self.assertFalse(
			_es_ffm_borrador_sin_timbrar(
				{
					"name": "FFM-A",
					"docstatus": 0,
					"status": "PENDIENTE",
					"fm_uuid": None,
					"facturapi_id": None,
				}
			)
		)

	def test_ffm_activa_de_la_si_es_false(self):
		# Aunque sea un borrador sin timbrar, si es la FFM que la SI reconoce como activa NO se ignora
		self.assertFalse(
			_es_ffm_borrador_sin_timbrar(
				{
					"name": "FFM-ACTIVA",
					"docstatus": 0,
					"status": "BORRADOR",
					"fm_uuid": None,
					"facturapi_id": None,
				},
				active_ffm_name="FFM-ACTIVA",
			)
		)


class TestCancelarSiPostFiscalIgnoraDraft(IntegrationTestCase):
	def setUp(self):
		self.si = _seed_si()
		# FFM fiscal válida: submitted, CANCELADO, con evidencia fiscal
		self.ffm_valida = _seed_ffm(
			self.si,
			"CANCELADO",
			1,
			uuid=frappe.generate_hash(length=10),
			facturapi_id=frappe.generate_hash(length=10),
		)
		frappe.db.set_value("Sales Invoice", self.si, "fm_factura_fiscal_mx", self.ffm_valida)
		# FFM duplicada BORRADOR: docstatus=0, sin UUID ni facturapi_id
		self.ffm_draft = _seed_ffm(self.si, "BORRADOR", 0)
		# Response Log ligado a la draft (debe permanecer intacto)
		rl = frappe.get_doc(
			{
				"doctype": "FacturAPI Response Log",
				"factura_fiscal_mexico": self.ffm_draft,
				"operation_type": "Solicitud Cancelación",
				"success": 0,
			}
		)
		rl.flags.ignore_validate = True
		rl.flags.ignore_mandatory = True
		rl.flags.ignore_links = True
		rl.db_insert()
		self.response_log = rl.name

	def test_draft_no_bloquea_y_permanece_intacta(self):
		# El cancel de ERPNext (GL) se simula: aislamos el guard/desvinculación.
		with mock.patch("frappe.model.document.Document.cancel") as mocked_cancel:
			result = cancelar_si_post_fiscal(self.si)

		# La cancelación continuó (guard NO bloqueó) y se llamó al cancel de la SI
		self.assertTrue(result.get("ok"))
		self.assertTrue(mocked_cancel.called)

		# La FFM draft NO se tocó: sigue ligada, en borrador, sin cambios
		d = frappe.db.get_value(
			"Factura Fiscal Mexico", self.ffm_draft, ["sales_invoice", "docstatus", "status"], as_dict=True
		)
		self.assertEqual(d.sales_invoice, self.si)  # NO desvinculada
		self.assertEqual(d.docstatus, 0)
		self.assertEqual(d.status, "BORRADOR")

		# El Response Log de la draft permanece
		self.assertTrue(frappe.db.exists("FacturAPI Response Log", self.response_log))

		# La FFM fiscal válida SÍ se desvinculó (para permitir el cancel nativo de la SI)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", self.ffm_valida, "sales_invoice"), "")

	def test_draft_con_uuid_sigue_bloqueando(self):
		# Convertir la draft en una con UUID → vuelve a ser fiscalmente activa y BLOQUEA
		frappe.db.set_value(
			"Factura Fiscal Mexico", self.ffm_draft, "fm_uuid", frappe.generate_hash(length=10)
		)
		with mock.patch("frappe.model.document.Document.cancel"), self.assertRaises(frappe.ValidationError):
			cancelar_si_post_fiscal(self.si)

	def test_ffm_submitted_no_cancelada_sigue_bloqueando(self):
		# Una segunda FFM submitted en TIMBRADO (no CANCELADO) debe bloquear
		_seed_ffm(
			self.si,
			"TIMBRADO",
			1,
			uuid=frappe.generate_hash(length=10),
			facturapi_id=frappe.generate_hash(length=10),
		)
		with mock.patch("frappe.model.document.Document.cancel"), self.assertRaises(frappe.ValidationError):
			cancelar_si_post_fiscal(self.si)

	def test_draft_procesando_sigue_bloqueando(self):
		# Draft en PROCESANDO (sin UUID ni facturapi_id): puede haber operación en curso → BLOQUEA
		_seed_ffm(self.si, "PROCESANDO", 0)
		with mock.patch("frappe.model.document.Document.cancel"), self.assertRaises(frappe.ValidationError):
			cancelar_si_post_fiscal(self.si)

	# Nota: el guard "nunca ignorar la FFM activa de la SI" se cubre por el test directo del
	# predicado (TestEsFfmBorradorSinTimbrar.test_ffm_activa_de_la_si_es_false). Un test de
	# integración que apunte el borrador como FFM activa bloquearía por el guard previo
	# (la FFM activa debe estar CANCELADO), no por este branch — sería engañoso, se omite.
