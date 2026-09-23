"""CFDI externo (V3) — timbrado fuera de este ERP, representado como FFM autoritativa.

Cubre el diseño acordado:
- `fm_creation_source = "CFDI externo"` desactiva la derivación de status desde FacturAPI Response
  Log; `FFM.status` es la fuente de verdad (poblada por `registrar_cfdi_externo`).
- Evidencia mínima (UUID válido + fecha_timbrado + XML) antes de TIMBRADO/CANCELADO.
- Sin `facturapi_id`, sin Response Log sintético, sin llamadas al PAC.
- CANCELADO externo NO cascada a la Sales Invoice.
- Idempotencia por (SI, UUID); fail-closed ante conflictos.
- El flujo FacturAPI normal NO cambia.

Sin llamadas al PAC. Pruebas en test-facturacion.localhost.
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
	CFDI_EXTERNO,
	get_or_create_active_ffm,
	registrar_cfdi_externo,
)

_XML = b"<cfdi:Comprobante xmlns:cfdi='http://www.sat.gob.mx/cfd/4'>historico</cfdi:Comprobante>"


def _uuid(suffix: str) -> str:
	"""UUID válido (8-4-4-4-12) determinista por sufijo hex de 12."""
	return f"AAAAAAAA-BBBB-CCCC-DDDD-{suffix}"


def _make_si() -> str:
	"""Sales Invoice mínima submitted (db_insert, sin líneas → sin dependencia de clave SAT)."""
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


class TestCFDIExterno(IntegrationTestCase):
	def setUp(self):
		self.si_names = []
		self.ffm_names = []

	def tearDown(self):
		frappe.set_user("Administrator")
		for n in self.ffm_names:
			frappe.db.delete("File", {"attached_to_doctype": "Factura Fiscal Mexico", "attached_to_name": n})
			frappe.db.set_value("Factura Fiscal Mexico", n, "docstatus", 0)
			frappe.db.delete("Factura Fiscal Mexico", {"name": n})
		for n in self.si_names:
			frappe.db.delete("Sales Invoice", {"name": n})
		frappe.db.commit()

	def _si(self):
		name = _make_si()
		self.si_names.append(name)
		return name

	def _track(self, ffm_name):
		if ffm_name and ffm_name not in self.ffm_names:
			self.ffm_names.append(ffm_name)
		return ffm_name

	def _registrar(self, si, uuid, **kw):
		kw.setdefault("uso_cfdi", "G03")
		return self._track(
			registrar_cfdi_externo(
				si,
				uuid,
				_XML,
				fecha_timbrado=frappe.utils.now_datetime(),
				serie="CFDI",
				folio="1001",
				total_fiscal=116,
				**kw,
			)
		)

	# 1 — Externo TIMBRADO se conserva tras save/submit y ciclo de recálculo/reconciliación
	def test_externo_timbrado_persiste(self):
		si = self._si()
		ffm = self._registrar(si, _uuid("000000000001"))
		doc = frappe.get_doc("Factura Fiscal Mexico", ffm)
		self.assertEqual(doc.status, "TIMBRADO")
		self.assertEqual(doc.fm_creation_source, CFDI_EXTERNO)
		self.assertEqual(doc.docstatus, 1)
		self.assertFalse(doc.get("facturapi_id"))
		self.assertTrue(doc.get("xml_file"))

		# El recálculo por logs NO revierte (guard externo): la función es la que corre en on_update.
		doc.calculate_fiscal_status_from_logs()
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")

		# La reconciliación programada omite externos (sin facturapi_id) y no altera el estado.
		from facturacion_mexico.facturacion_fiscal.services.ffm_reconciliation import reconcile_ffm

		res = reconcile_ffm(ffm)
		self.assertEqual(res.get("outcome"), "skipped")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")

		# Snapshot proyectado a la SI.
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_fiscal_status"), "TIMBRADO")
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"), ffm)

	# 2 — Externo CANCELADO se conserva y NO cancela la Sales Invoice
	def test_externo_cancelado_sin_cascada(self):
		si = self._si()
		ffm = self._registrar(si, _uuid("000000000002"), external_status="CANCELADO", motivo_cancelacion="02")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "CANCELADO")
		# La SI NO se cancela (docstatus sigue 1), sin reversión contable.
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_fiscal_status"), "CANCELADO")

	# 3 — Idempotencia: misma SI + mismo UUID reutiliza la misma FFM
	def test_idempotente_misma_si_mismo_uuid(self):
		si = self._si()
		u = _uuid("000000000003")
		ffm1 = self._registrar(si, u)
		ffm2 = self._registrar(si, u)
		self.assertEqual(ffm1, ffm2)

	# 4a — Misma SI con UUID distinto → falla cerrado
	def test_conflicto_uuid_misma_si(self):
		si = self._si()
		self._registrar(si, _uuid("00000000004a"))
		with self.assertRaises(frappe.ValidationError):
			self._registrar(si, _uuid("00000000004b"))

	# 4b — Mismo UUID en otra SI → falla cerrado
	def test_conflicto_uuid_otra_si(self):
		si_a = self._si()
		si_b = self._si()
		u = _uuid("000000000005")
		self._registrar(si_a, u)
		with self.assertRaises(frappe.ValidationError):
			self._registrar(si_b, u)

	# 5 — Operaciones FacturAPI rechazadas para externos (guards servidor, sin depender de la UI)
	def test_operaciones_facturapi_rechazadas(self):
		from facturacion_mexico.facturacion_fiscal.timbrado_api import (
			cancelar_factura,
			create_substitution_si,
			descargar_archivos_cfdi,
			timbrar_factura,
		)

		si = self._si()
		ffm = self._registrar(si, _uuid("000000000006"))
		with self.assertRaises(frappe.ValidationError):
			timbrar_factura(si)
		with self.assertRaises(frappe.ValidationError):
			cancelar_factura(sales_invoice=si, motivo="02")
		with self.assertRaises(frappe.ValidationError):
			descargar_archivos_cfdi(ffm)
		with self.assertRaises(frappe.ValidationError):
			create_substitution_si(si)

	# 6 — PPD: una FFM externa TIMBRADO expone UUID + snapshots usables por el complemento
	def test_ppd_consumible(self):
		si = self._si()
		ffm = self._registrar(si, _uuid("000000000007"))
		# Marcar la SI como PPD (lo haría el importador desde el XML).
		frappe.db.set_value("Sales Invoice", si, "fm_es_ppd", 1)
		# Los cuatro insumos que exige el flujo de complemento están presentes.
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_fiscal_status"), "TIMBRADO")
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"), ffm)
		self.assertTrue(frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_uuid"))
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "fm_es_ppd"), 1)

	# 7 — FFM normal FacturAPI: comportamiento intacto (status se deriva de logs → BORRADOR sin logs)
	def test_ffm_normal_no_afectada(self):
		si = self._si()
		ffm = self._track(get_or_create_active_ffm(si))
		doc = frappe.get_doc("Factura Fiscal Mexico", ffm)
		self.assertNotEqual(doc.fm_creation_source, CFDI_EXTERNO)
		self.assertEqual(doc.status, "BORRADOR")
		# El recálculo por logs sigue activo para no-externos y mantiene BORRADOR (sin logs de timbrado).
		doc.calculate_fiscal_status_from_logs()
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "BORRADOR")

	# 8 — Sin evidencia no se acepta TIMBRADO externo (anti-atajo)
	def test_evidencia_insuficiente_bloquea(self):
		si = self._si()
		ffm_name = self._track(get_or_create_active_ffm(si))
		doc = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		doc.fm_creation_source = CFDI_EXTERNO
		doc.fm_cfdi_use = "G03"  # uso válido: el fallo debe ser por evidencia, no por uso
		doc.status = "TIMBRADO"  # sin UUID/fecha/XML
		with self.assertRaisesRegex(frappe.ValidationError, "[Ee]videncia"):
			doc.save()
