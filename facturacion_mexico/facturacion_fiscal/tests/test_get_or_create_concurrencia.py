"""Concurrencia de get_or_create_active_ffm — lock de fila con FOR UPDATE (Corrección 4).

Dos solicitudes concurrentes para la misma Sales Invoice deben devolver el MISMO FFM
y persistir un solo documento. Se usa el lock de fila transaccional adquirido por
`frappe.get_doc("Sales Invoice", name, for_update=True)`: la segunda transacción espera
al commit de la primera y, al releer bajo el lock, reutiliza el FFM ya vinculado.

La concurrencia se prueba con PROCESOS independientes (multiprocessing, contexto "spawn"),
cada uno con su propio `frappe.init` + `frappe.connect` + transacción. El commit de cada
proceso representa el fin de un request simulado — NO es un commit del código productivo.

Coordinación determinista: el proceso "holder" adquiere el lock vía la función bajo prueba
y lo mantiene unos segundos (su commit se difiere); el proceso "contender" entra a su
`for_update` mientras el lock está tomado, por lo que necesariamente se serializa. Así la
prueba no depende del azar de una barrera. Sin sleeps inyectados en el código productivo:
la espera está SOLO en el proceso de prueba que simula un request en curso.

Sin llamadas al PAC. Pruebas en test-facturacion.localhost.
"""

import multiprocessing as mp
import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
	get_or_create_active_ffm,
)

# Segundos que el "holder" mantiene el lock de fila tomado (con su transacción abierta)
# para garantizar que el "contender" entre a su FOR UPDATE mientras el lock está activo.
HOLD_SECONDS = 2.0
# Umbral para considerar que el contender SE SERIALIZÓ (esperó al holder).
SERIALIZADO_MIN = 1.0


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


def _worker_holder(site: str, si_name: str, hold_seconds: float, locked_evt, queue) -> None:
	"""Proceso independiente que ADQUIERE el lock y lo MANTIENE.

	Abre su transacción, llama a la función bajo prueba (que toma el FOR UPDATE de la SI),
	avisa que el lock está tomado y difiere su commit `hold_seconds` segundos para forzar
	la serialización del contender. Su commit representa el fin del request simulado.
	"""
	import frappe as fr

	fr.init(site=site)
	fr.connect()
	try:
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			get_or_create_active_ffm as _goc,
		)

		fr.db.begin()
		name = _goc(si_name)  # adquiere el lock de fila de la SI
		locked_evt.set()  # avisar: lock tomado, contender puede intentar
		time.sleep(hold_seconds)  # mantener la transacción (request en curso simulado)
		fr.db.commit()  # fin del request → libera el lock
		queue.put(("holder", name, 0.0))
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


def _worker_contender(site: str, si_name: str, locked_evt, queue) -> None:
	"""Proceso independiente que intenta entrar DESPUÉS de que el holder tomó el lock.

	Espera la señal del holder, abre su transacción y llama a la función bajo prueba.
	Si compite por la misma SI, su `for_update` BLOQUEA hasta el commit del holder; mide
	cuánto esperó. Al desbloquearse relee bajo el lock y debe reutilizar el FFM vinculado.
	"""
	import frappe as fr

	fr.init(site=site)
	fr.connect()
	try:
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			get_or_create_active_ffm as _goc,
		)

		locked_evt.wait(timeout=20)  # esperar a que el holder tenga el lock
		fr.db.begin()
		t0 = time.monotonic()
		name = _goc(si_name)  # bloquea hasta el commit del holder si es la misma SI
		espera = time.monotonic() - t0
		fr.db.commit()  # fin del request simulado
		queue.put(("contender", name, espera))
	except Exception as e:
		try:
			fr.db.rollback()
		except Exception:
			pass
		queue.put(("contender-err", repr(e), 0.0))
	finally:
		try:
			fr.destroy()
		except Exception:
			pass


class TestGetOrCreateConcurrencia(IntegrationTestCase):
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

	def _run_holder_contender(self, si_holder, si_contender):
		"""Lanza holder (mantiene el lock) y contender (entra después); devuelve resultados.

		Devuelve un dict con claves de tipo de proceso → (name, espera_segundos).
		"""
		site = frappe.local.site
		ctx = mp.get_context("spawn")
		locked = ctx.Event()
		q = ctx.Queue()
		ph = ctx.Process(target=_worker_holder, args=(site, si_holder, HOLD_SECONDS, locked, q))
		pc = ctx.Process(target=_worker_contender, args=(site, si_contender, locked, q))
		ph.start()
		pc.start()
		ph.join(60)
		pc.join(60)
		out = {}
		for _ in range(2):
			tipo, name, espera = q.get(timeout=10)
			out[tipo] = (name, espera)
		return out

	# 1 + 2 — dos procesos sobre la MISMA SI: el contender se serializa y reutiliza.
	#         Un solo FFM, ambos lo devuelven, la SI apunta a él.
	def test_concurrencia_misma_si_un_solo_ffm(self):
		si = self._si()
		out = self._run_holder_contender(si, si)

		self.assertIn("holder", out, f"El holder debe terminar OK: {out}")
		self.assertIn("contender", out, f"El contender debe terminar OK: {out}")
		holder_name, _ = out["holder"]
		contender_name, espera = out["contender"]

		# El contender SE SERIALIZÓ: esperó al commit del holder (lock efectivo entre procesos).
		self.assertGreaterEqual(
			espera,
			SERIALIZADO_MIN,
			f"El contender debió esperar al holder (~{HOLD_SECONDS}s); esperó {espera:.2f}s",
		)
		# Ambos devuelven el MISMO FFM (el contender reutilizó el vinculado por el holder).
		self.assertEqual(holder_name, contender_name, f"Ambos deben devolver el mismo FFM: {out}")
		# Solo existe un FFM para esa SI.
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 1)
		# La SI apunta a ese FFM.
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"), holder_name)

	# 4 — dos SIs distintas NO se bloquean: el contender no espera y cada una obtiene su FFM.
	def test_sis_distintas_no_se_bloquean(self):
		si_a = self._si()
		si_b = self._si()
		out = self._run_holder_contender(si_a, si_b)

		self.assertIn("holder", out, f"El holder debe terminar OK: {out}")
		self.assertIn("contender", out, f"El contender debe terminar OK: {out}")
		_, espera = out["contender"]

		# El contender opera sobre OTRA fila: no se serializa con el holder.
		self.assertLess(
			espera,
			SERIALIZADO_MIN,
			f"SIs distintas no deben bloquearse; el contender esperó {espera:.2f}s",
		)
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si_a}), 1)
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si_b}), 1)
		ffm_a = frappe.db.get_value("Sales Invoice", si_a, "fm_factura_fiscal_mx")
		ffm_b = frappe.db.get_value("Sales Invoice", si_b, "fm_factura_fiscal_mx")
		self.assertNotEqual(ffm_a, ffm_b)

	# 3 — una excepción dentro de la sección crítica: el rollback libera el lock,
	#     una llamada posterior procede normalmente (no queda lock huérfano).
	def test_rollback_libera_lock(self):
		si = self._si()

		# Capturar la función REAL ANTES de parchear: si se captura dentro del `with patch`,
		# `frappe.get_doc` ya es el mock y la rama "Sales Invoice" recursaría infinitamente
		# (RecursionError, subclase de RuntimeError) → el test pasaría por la razón equivocada
		# sin ejercitar el for_update real ni el fallo en creación del FFM.
		real_get_doc = frappe.get_doc

		# Forzar excepción DESPUÉS de adquirir el for_update (al insertar el FFM).
		with patch(
			"facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico."
			"factura_fiscal_mexico.frappe.get_doc"
		) as _mock:
			# Dejamos pasar la lectura for_update real y rompemos en la creación del FFM.

			def _side(*args, **kwargs):
				if args and args[0] == "Sales Invoice":
					return real_get_doc(*args, **kwargs)  # for_update real
				raise RuntimeError("fallo simulado en creación de FFM")

			_mock.side_effect = _side
			with self.assertRaises(RuntimeError):
				get_or_create_active_ffm(si)
		frappe.db.rollback()  # rollback del request simulado → libera el lock de fila

		# Una llamada posterior procede sin problema (no hay lock huérfano).
		ffm = get_or_create_active_ffm(si)
		frappe.db.commit()
		self.assertTrue(ffm)
		self.assertEqual(frappe.db.count("Factura Fiscal Mexico", {"sales_invoice": si}), 1)

	# 5 — cero referencias al cliente del PAC en este módulo de prueba
	def test_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "cancel_invoice", "requests"):
			self.assertNotIn(simbolo, g)
