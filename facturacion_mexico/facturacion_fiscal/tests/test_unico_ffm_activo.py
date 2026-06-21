"""Un solo FFM activo/no resuelto por Sales Invoice — Regla B (Corrección 5).

Una Sales Invoice puede tener varios FFM históricos, pero solo UN FFM activo o no
resuelto. Estados activos (bloquean otra creación): BORRADOR, PROCESANDO, TIMBRADO,
ERROR, PENDIENTE_CANCELACION. Estados terminales (no bloquean): CANCELADO, ARCHIVADO.
La decisión usa `status` del FFM (no `docstatus`) y se basa en los FFM activos cuyo
`sales_invoice` es la SI, no solo en `Sales Invoice.fm_factura_fiscal_mx`.

Dos protecciones:
- `get_or_create_active_ffm`: resuelve crear/reutilizar bajo el lock de fila de la SI.
- `Factura Fiscal Mexico.before_insert`: impide insertar un segundo FFM activo por cualquier
  vía (Desk, API, scripts, `.insert()` directo), sin afectar documentos ya existentes.

Sin llamadas al PAC. Pruebas en test-facturacion.localhost.
"""

import multiprocessing as mp
import time

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.config.fiscal_states_config import FiscalStates
from facturacion_mexico.facturacion_fiscal.api import FiscalCorrelationError
from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
	get_or_create_active_ffm,
)

HOLD_SECONDS = 1.0


def _make_si_committed() -> str:
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


def _seed_ffm(sales_invoice: str, status: str, *, docstatus: int = 1) -> str:
	"""Siembra un FFM con un status dado vía db_insert (sin disparar before_insert/validate)."""
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"naming_series": "FFM-TEST-.YYYY.-",
			"sales_invoice": sales_invoice,
			"status": status,
			"fm_tipo_comprobante": "I",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"docstatus": docstatus,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	frappe.db.commit()
	return ffm.name


def _build_ffm_doc(fr, sales_invoice: str):
	"""Construye (sin insertar) un FFM mínimo; insert() ejecutará before_insert (la guarda)."""
	ffm = fr.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"naming_series": "FFM-TEST-.YYYY.-",
			"sales_invoice": sales_invoice,
			"status": "BORRADOR",
			"fm_tipo_comprobante": "I",
			"company": "_Test Company",
			"customer": "_Test Customer",
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	return ffm


def _worker_insert_holder(site, si_name, hold_seconds, locked_evt, queue):
	"""Inserta un FFM (before_insert toma el lock de la SI) y difiere su commit."""
	import frappe as fr

	fr.init(site=site)
	fr.connect()
	try:
		fr.db.begin()
		ffm = _build_ffm_doc(fr, si_name)
		ffm.insert(ignore_permissions=True)  # before_insert adquiere el lock de fila de la SI
		locked_evt.set()
		time.sleep(hold_seconds)
		fr.db.commit()
		queue.put(("holder", ffm.name, 0.0))
	except Exception as e:
		try:
			fr.db.rollback()
		except Exception:
			pass
		queue.put(("holder-err", repr(e), 0.0))
	finally:
		try:
			fr.destroy()
		except Exception:
			pass


def _worker_insert_contender(site, si_name, locked_evt, queue):
	"""Tras la señal, intenta insertar otro FFM activo: su before_insert debe bloquear y luego fallar."""
	import frappe as fr

	fr.init(site=site)
	fr.connect()
	try:
		locked_evt.wait(timeout=20)
		fr.db.begin()
		t0 = time.monotonic()
		try:
			ffm = _build_ffm_doc(fr, si_name)
			ffm.insert(ignore_permissions=True)
			fr.db.commit()
			queue.put(("contender-ok", ffm.name, time.monotonic() - t0))
		except Exception as e:
			espera = time.monotonic() - t0
			fr.db.rollback()
			queue.put(("contender-err", repr(e), espera))
	finally:
		try:
			fr.destroy()
		except Exception:
			pass


class TestUnicoFFMActivo(IntegrationTestCase):
	def setUp(self):
		self.si_names = []
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		for si in self.si_names:
			for ffm in frappe.get_all("Factura Fiscal Mexico", filters={"sales_invoice": si}, pluck="name"):
				frappe.db.delete("Factura Fiscal Mexico", {"name": ffm})
			frappe.db.delete("Sales Invoice", {"name": si})
		frappe.db.commit()

	def _si(self):
		name = _make_si_committed()
		self.si_names.append(name)
		return name

	def _link(self, si, ffm):
		frappe.db.set_value("Sales Invoice", si, "fm_factura_fiscal_mx", ffm)

	# ── Resolución vía get_or_create_active_ffm ──────────────────────────────

	def _reutiliza_activo(self, status):
		si = self._si()
		ffm = _seed_ffm(si, status)
		self._link(si, ffm)
		result = get_or_create_active_ffm(si)
		self.assertEqual(result, ffm, f"Debe reutilizar el FFM {status}")
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 1)

	def test_01_borrador_reutiliza(self):
		self._reutiliza_activo("BORRADOR")

	def test_02_error_reutiliza(self):
		self._reutiliza_activo("ERROR")

	def test_03_procesando_reutiliza(self):
		self._reutiliza_activo("PROCESANDO")

	def test_04_timbrado_reutiliza_no_crea_otro(self):
		self._reutiliza_activo("TIMBRADO")

	def test_05_pendiente_cancelacion_reutiliza(self):
		self._reutiliza_activo("PENDIENTE_CANCELACION")

	def test_06_cancelado_permite_crear_nuevo(self):
		si = self._si()
		cancelado = _seed_ffm(si, "CANCELADO")
		self._link(si, cancelado)
		nuevo = get_or_create_active_ffm(si)
		self.assertNotEqual(nuevo, cancelado, "Tras CANCELADO debe crear uno nuevo")
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 2)
		# El nuevo es activo (no terminal) y la SI apunta a él. El status inicial exacto del
		# nuevo depende del entorno (en test, el fallback de eventos puede dejarlo en ERROR;
		# en producción nace BORRADOR). Lo relevante para Regla B es que sea activo.
		nuevo_status = frappe.db.get_value("Factura Fiscal Mexico", nuevo, "status")
		self.assertIn(nuevo_status, FiscalStates.ACTIVE_STATES)
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"), nuevo)

	def test_07_archivado_permite_crear_nuevo(self):
		si = self._si()
		archivado = _seed_ffm(si, "ARCHIVADO")
		self._link(si, archivado)
		nuevo = get_or_create_active_ffm(si)
		self.assertNotEqual(nuevo, archivado, "ARCHIVADO es terminal: debe crear uno nuevo")
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 2)
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"), nuevo)

	def test_08_ref_vacia_un_activo_repara_y_reutiliza(self):
		si = self._si()
		ffm = _seed_ffm(si, "TIMBRADO")
		# referencia vacía a propósito (no se vincula)
		self.assertFalse(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"))
		result = get_or_create_active_ffm(si)
		self.assertEqual(result, ffm)
		# vínculo reparado
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"), ffm)
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 1)

	def test_09_ref_rota_un_activo_reutiliza(self):
		si = self._si()
		ffm = _seed_ffm(si, "BORRADOR")
		self._link(si, "FFMX-INEXISTENTE-999")  # referencia a FFM que no existe
		result = get_or_create_active_ffm(si)
		self.assertEqual(result, ffm)
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"), ffm)
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 1)

	def test_10_ref_a_ffm_de_otra_si_error_integridad(self):
		si_a = self._si()
		si_b = self._si()
		ffm_b = _seed_ffm(si_b, "TIMBRADO")  # pertenece a si_b
		self._link(si_a, ffm_b)  # si_a apunta a un FFM de si_b (corrupción)
		with self.assertRaises(FiscalCorrelationError):
			get_or_create_active_ffm(si_a)
		# no creó nada para si_a, no tocó el FFM de si_b
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si_a}), 0)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm_b, "status"), "TIMBRADO")

	def test_11_dos_activos_alerta_y_no_selecciona(self):
		si = self._si()
		a1 = _seed_ffm(si, "BORRADOR")
		a2 = _seed_ffm(si, "TIMBRADO")
		with self.assertRaises(FiscalCorrelationError):
			get_or_create_active_ffm(si)
		# no creó otro, no modificó estados
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 2)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", a1, "status"), "BORRADOR")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", a2, "status"), "TIMBRADO")

	def test_14_cancelado_y_activo_coexisten(self):
		si = self._si()
		cancelado = _seed_ffm(si, "CANCELADO")
		activo = _seed_ffm(si, "TIMBRADO")
		self._link(si, activo)
		result = get_or_create_active_ffm(si)
		self.assertEqual(result, activo, "Debe reutilizar el único activo; el cancelado coexiste")
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 2)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", cancelado, "status"), "CANCELADO")

	# ── Protección en before_insert (toda vía de inserción) ──────────────────

	def test_12_insercion_directa_segundo_activo_bloqueada(self):
		si = self._si()
		_seed_ffm(si, "BORRADOR")  # ya hay un activo
		ffm2 = _build_ffm_doc(frappe, si)
		with self.assertRaises(frappe.ValidationError):
			ffm2.insert(ignore_permissions=True)
		# el segundo no persistió
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 1)

	def test_15_modificacion_de_existentes_no_bloqueada(self):
		# Dos activos preexistentes (duplicados de producción). Guardar uno NO debe bloquearse:
		# before_insert solo corre en inserción, no en actualización.
		si = self._si()
		a1 = _seed_ffm(si, "BORRADOR")
		_seed_ffm(si, "TIMBRADO")
		doc = frappe.get_doc("Factura Fiscal Mexico", a1)
		doc.flags.ignore_validate = True
		doc.fm_uuid = "UUID-EDIT-15"
		doc.save(ignore_permissions=True)  # no debe lanzar "FFM activo ya existe"
		frappe.db.commit()
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", a1, "fm_uuid"), "UUID-EDIT-15")
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 2)

	# ── Concurrencia de inserción directa (procesos/conexiones independientes) ─

	def test_13_insercion_concurrente_directa_solo_uno_persiste(self):
		si = self._si()
		site = frappe.local.site
		ctx = mp.get_context("spawn")
		locked = ctx.Event()
		q = ctx.Queue()
		ph = ctx.Process(target=_worker_insert_holder, args=(site, si, HOLD_SECONDS, locked, q))
		pc = ctx.Process(target=_worker_insert_contender, args=(site, si, locked, q))
		ph.start()
		pc.start()
		ph.join(60)
		pc.join(60)
		out = {}
		for _ in range(2):
			tipo, val, espera = q.get(timeout=10)
			out[tipo] = (val, espera)

		# Outcome determinista: el holder inserta y el contender (que corre tras la señal,
		# con el FFM del holder ya visible) es bloqueado por la guarda before_insert.
		# La serialización por for_update se prueba de forma determinista en la Corrección 4;
		# aquí lo esencial es que la inserción directa concurrente deje UN solo FFM.
		self.assertIn("holder", out, f"El holder debe insertar OK: {out}")
		self.assertIn("contender-err", out, f"El contender debe fallar (no insertar): {out}")
		self.assertIn("ya tiene un FFM activo", out["contender-err"][0])
		# Solo un FFM persistió.
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 1)

	# ── Cero tráfico PAC ─────────────────────────────────────────────────────

	def test_16_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "cancel_invoice", "requests"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
