"""Creación centralizada de FFM en servidor (Corrección 3).

La creación del FFM deja de hacerse desde JavaScript (`frappe.client.insert` +
`set_value`) y se concentra en `get_or_create_active_ffm(sales_invoice)`.

ADVERTENCIA: esta corrección NO agrega lock. La condición de carrera (dos
llamadas concurrentes con `fm_factura_fiscal_mx` vacío) sigue abierta y será
resuelta por la Corrección 4. La prueba de concurrencia documenta la ventana,
no la corrige.

Sin llamadas al PAC. Pruebas en test-facturacion.localhost.
"""

import os
import re

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
	get_or_create_active_ffm,
)

_JS = os.path.join(os.path.dirname(__file__), "..", "..", "public", "js", "sales_invoice.js")


def _make_si() -> str:
	"""Crea una Sales Invoice mínima y submitted en BD (db_insert).

	docstatus=1 porque el FFM exige que la SI esté submitted (igual que el botón real,
	que solo aparece en SIs submitted). db_insert evita el setup de stock/GL.
	"""
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"net_total": 100,
			"grand_total": 116,
			"posting_date": frappe.utils.today(),
			"docstatus": 1,
		}
	)
	si.flags.ignore_validate = True
	si.flags.ignore_mandatory = True
	si.flags.ignore_links = True
	si.db_insert()
	frappe.db.commit()
	return si.name


def _add_tax_rows(si_name: str, rows: list[tuple[str, float]]) -> None:
	"""Inserta filas hijas de 'Sales Taxes and Charges' para una Sales Invoice.

	Cada fila es (account_head, tax_amount). Se usa db_insert sobre la child table
	para no disparar el recálculo de ERPNext (probamos solo la clasificación del FFM).
	"""
	for i, (account_head, amount) in enumerate(rows, start=1):
		row = frappe.get_doc(
			{
				"doctype": "Sales Taxes and Charges",
				"parent": si_name,
				"parenttype": "Sales Invoice",
				"parentfield": "taxes",
				"idx": i,
				"charge_type": "Actual",
				"account_head": account_head,
				"description": account_head,
				"tax_amount": amount,
			}
		)
		row.flags.ignore_validate = True
		row.flags.ignore_mandatory = True
		row.flags.ignore_links = True
		row.db_insert()
	frappe.db.commit()


class TestGetOrCreateActiveFFM(IntegrationTestCase):
	def setUp(self):
		self.si_names = []
		self.ffm_names = []
		self.user_ids = []
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		for n in self.ffm_names:
			frappe.db.delete("Factura Fiscal Mexico", {"name": n})
		for n in self.si_names:
			frappe.db.delete("Sales Invoice", {"name": n})
		for u in self.user_ids:
			frappe.db.delete("User", {"name": u})
		frappe.db.commit()

	def _si(self):
		name = _make_si()
		self.si_names.append(name)
		return name

	def _track_ffm(self, name):
		if name and name not in self.ffm_names:
			self.ffm_names.append(name)
		return name

	# 1 — SI sin FFM: crea, vincula, devuelve nombre
	def test_si_sin_ffm_crea_vincula_y_devuelve(self):
		si = self._si()
		ffm = self._track_ffm(get_or_create_active_ffm(si))
		self.assertTrue(ffm)
		# Vinculado en la SI
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"), ffm)
		# El FFM apunta a la SI
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "sales_invoice"), si)

	# 2 — SI con fm_factura_fiscal_mx válido: devuelve el mismo, no crea otro
	def test_si_con_ffm_valido_reutiliza(self):
		si = self._si()
		ffm1 = self._track_ffm(get_or_create_active_ffm(si))
		ffm2 = get_or_create_active_ffm(si)
		self.assertEqual(ffm1, ffm2)
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 1)

	# 3 — dos llamadas secuenciales: mismo FFM, un documento
	def test_dos_llamadas_secuenciales_mismo_ffm(self):
		si = self._si()
		a = self._track_ffm(get_or_create_active_ffm(si))
		b = self._track_ffm(get_or_create_active_ffm(si))
		self.assertEqual(a, b)
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 1)

	# 4 — Sales Invoice inexistente: error controlado, no crea
	def test_si_inexistente_error_controlado(self):
		with self.assertRaises(frappe.ValidationError):
			get_or_create_active_ffm("SI-QUE-NO-EXISTE-XYZ")
		self.assertEqual(
			frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": "SI-QUE-NO-EXISTE-XYZ"}), 0
		)

	# 5 — usuario sin permisos: error, no crea
	def test_usuario_sin_permisos_error(self):
		si = self._si()
		uid = "test-ffm-create-" + frappe.generate_hash()[:8] + "@test.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": uid,
				"first_name": "Sin Permisos",
				"send_welcome_email": 0,
				# Sin roles: no puede leer Sales Invoice ni crear Factura Fiscal Mexico.
			}
		)
		user.insert(ignore_permissions=True)
		self.user_ids.append(uid)
		frappe.db.commit()

		frappe.set_user(uid)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_or_create_active_ffm(si)
		finally:
			frappe.set_user("Administrator")
		# No se creó FFM
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 0)

	# 6 — el JS ya no usa frappe.client.insert para crear el FFM
	def test_js_sin_client_insert(self):
		with open(os.path.abspath(_JS), encoding="utf-8") as f:
			js = f.read()
		# No debe quedar un insert de Factura Fiscal Mexico vía client.insert
		self.assertNotIn('method: "frappe.client.insert"', js)

	# 7 — el JS ya no hace un set_value separado para vincular el FFM
	def test_js_sin_set_value_separado(self):
		with open(os.path.abspath(_JS), encoding="utf-8") as f:
			js = f.read()
		self.assertNotIn('method: "frappe.client.set_value"', js)

	# 8 — el cliente usa la función servidor y su nombre devuelto
	def test_js_usa_funcion_servidor(self):
		with open(os.path.abspath(_JS), encoding="utf-8") as f:
			js = f.read()
		self.assertIn("get_or_create_active_ffm", js)
		# usa el nombre devuelto (r.message) para navegar
		self.assertTrue(re.search(r"const ffm_name = r\.message", js))

	# 9 — cero referencias al cliente del PAC en este módulo de prueba
	def test_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "cancel_invoice", "requests"):
			self.assertNotIn(simbolo, g)

	# Concurrencia (documenta la ventana abierta; NO la corrige) —
	# se prueba que, simulando el campo aún vacío en una segunda lectura, se crearía
	# un segundo FFM. Esto evidencia que SIN LOCK la carrera sigue posible (Corrección 4).
	def test_documenta_ventana_concurrente_sin_lock(self):
		si = self._si()
		ffm1 = self._track_ffm(get_or_create_active_ffm(si))

		# Simular que una segunda llamada entra antes de que la SI refleje el vínculo:
		# forzamos el campo a vacío justo antes de la segunda invocación.
		frappe.db.set_value("Sales Invoice", si, "fm_factura_fiscal_mx", None)
		frappe.db.commit()

		ffm2 = self._track_ffm(get_or_create_active_ffm(si))
		# Sin lock, se crea un segundo FFM (ventana abierta — la Corrección 4 lo impedirá).
		self.assertNotEqual(ffm1, ffm2)
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 2)

	# =========================================================================
	# REGRESIÓN DEL CÁLCULO DE IMPUESTOS (equivalencia con el comportamiento JS)
	#
	# El JS original clasificaba: toda cuenta cuyo account_head contiene "IVA"
	# (tras .toUpperCase()) suma a si_iva; el resto suma a si_otros_impuestos.
	# Estas pruebas demuestran que el cálculo en servidor conserva EXACTAMENTE esa
	# clasificación. Los valores esperados se escriben directamente (sin oráculo).
	#
	# NOTA: clasificar cualquier cuenta que contenga "IVA" como IVA — incluido el
	# "IVA Retenido" — conserva la lógica previa, pero NO constituye una validación
	# de que esa clasificación fiscal sea la ideal; solo demuestra equivalencia.
	# =========================================================================

	def _ffm_tax_totals(self, si):
		# Confirmar que las filas hijas se cargaron al recargar la SI desde servidor.
		si_doc = frappe.get_doc("Sales Invoice", si)
		num_rows = len(si_doc.get("taxes") or [])
		ffm = self._track_ffm(get_or_create_active_ffm(si))
		d = frappe.db.get_value("Factura Fiscal Mexico", ffm, ["si_iva", "si_otros_impuestos"], as_dict=True)
		return num_rows, flt(d["si_iva"], 2), flt(d["si_otros_impuestos"], 2)

	# 1 — IVA y otros impuestos combinados
	# IVA 16% = 160.00 ; IVA retenido = -40.00 ; IEPS = 25.00 ; ISR retenido = -10.00
	def test_calculo_iva_combinado(self):
		si = self._si()
		_add_tax_rows(
			si,
			[
				("IVA 16% - _TC", 160.00),
				("IVA Retenido - _TC", -40.00),
				("IEPS - _TC", 25.00),
				("ISR Retenido - _TC", -10.00),
			],
		)
		num_rows, si_iva, si_otros = self._ffm_tax_totals(si)
		self.assertEqual(num_rows, 4)  # filas hijas realmente cargadas
		self.assertEqual(si_iva, 120.00)  # 160.00 + (-40.00)
		self.assertEqual(si_otros, 15.00)  # 25.00 + (-10.00)

	# 2 — solo IVA
	def test_calculo_solo_iva(self):
		si = self._si()
		_add_tax_rows(si, [("IVA - _TC", 160.00)])
		num_rows, si_iva, si_otros = self._ffm_tax_totals(si)
		self.assertEqual(num_rows, 1)
		self.assertEqual(si_iva, 160.00)
		self.assertEqual(si_otros, 0.00)

	# 3 — solo otros impuestos
	def test_calculo_solo_otros(self):
		si = self._si()
		_add_tax_rows(si, [("IEPS - _TC", 30.00), ("ISR Retenido - _TC", -10.00)])
		num_rows, si_iva, si_otros = self._ffm_tax_totals(si)
		self.assertEqual(num_rows, 2)
		self.assertEqual(si_iva, 0.00)
		self.assertEqual(si_otros, 20.00)  # 30.00 + (-10.00)

	# 4 — sin impuestos
	def test_calculo_sin_impuestos(self):
		si = self._si()
		num_rows, si_iva, si_otros = self._ffm_tax_totals(si)
		self.assertEqual(num_rows, 0)
		self.assertEqual(si_iva, 0.00)
		self.assertEqual(si_otros, 0.00)

	# 5 — clasificación insensible a mayúsculas/minúsculas (JS usaba .toUpperCase())
	def test_calculo_iva_minusculas(self):
		si = self._si()
		_add_tax_rows(si, [("iva trasladado - _TC", 80.00), ("ieps - _TC", 12.00)])
		num_rows, si_iva, si_otros = self._ffm_tax_totals(si)
		self.assertEqual(num_rows, 2)
		self.assertEqual(si_iva, 80.00)  # "iva" en minúsculas clasifica como IVA
		self.assertEqual(si_otros, 12.00)
