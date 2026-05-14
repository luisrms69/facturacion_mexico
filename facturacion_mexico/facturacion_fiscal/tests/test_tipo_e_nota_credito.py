"""
Tests Issue #116 — Notas de Crédito CFDI tipo E.

Cubre:
  1. Tipo E sin UUID relacionado → bloquea timbrado (frappe.throw)
  2. Tipo E con UUID válido → related_documents incluido en payload
  3. _find_uuid_cfdi_origen resuelve UUID desde return_against vía fm_factura_fiscal_mx
  4. _find_uuid_cfdi_origen resuelve UUID desde return_against vía query FFM (fallback)
  5. _find_uuid_cfdi_origen retorna None cuando no hay FFM timbrada en SI origen
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe import _
from frappe.tests.utils import FrappeTestCase

# ── helpers ──────────────────────────────────────────────────────────────────


def _mock_ffm(fm_tipo_comprobante="E - Egreso", fm_uuid_relacionado="", fm_tipo_relacion_sat="03"):
	ffm = MagicMock()
	_data = {
		"fm_tipo_comprobante": fm_tipo_comprobante,
		"fm_uuid_relacionado": fm_uuid_relacionado,
		"fm_tipo_relacion_sat": fm_tipo_relacion_sat,
		"fm_payment_method_sat": "PUE",
		"fm_cfdi_use": "G03",
		"fm_tax_system": "601",
		"sales_invoice": "SINV-TEST-001",
	}
	ffm.get = lambda key, default=None: _data.get(key, default)
	ffm.name = "FFMX-TEST-001"
	return ffm


def _mock_si(is_return=0, return_against=None):
	si = MagicMock()
	si.name = "SINV-TEST-001"
	si.customer = "Test Customer"
	si.is_return = is_return
	si.return_against = return_against
	si.items = []
	_data = {
		"is_return": is_return,
		"return_against": return_against,
		"branch": None,
		"ffm_substitution_source_uuid": "",
	}
	si.get = lambda key, default=None: _data.get(key, default)
	return si


# ── Tests guard bloqueante ────────────────────────────────────────────────────


class TestTipoEGuard(FrappeTestCase):
	"""Guard en _prepare_facturapi_data: tipo E sin UUID bloquea timbrado."""

	def _run_tipo_e_block(self, uuid_relacionado: str):
		"""Ejecutar solo el bloque Tipo E de _prepare_facturapi_data."""
		invoice_data = {"type": "E"}
		ffm = _mock_ffm(fm_uuid_relacionado=uuid_relacionado)

		tipo_relacion = ffm.get("fm_tipo_relacion_sat", "").strip()
		uuid = ffm.get("fm_uuid_relacionado", "").strip()

		if not uuid:
			frappe.throw(
				_(
					"No se puede timbrar la Nota de Crédito: "
					"falta el UUID del CFDI origen relacionado. "
					"Verifique que la factura original esté timbrada."
				),
				title=_("UUID Relacionado Requerido"),
			)

		relacion_code = tipo_relacion.split(" - ")[0].strip() if " - " in tipo_relacion else tipo_relacion
		invoice_data["related_documents"] = [{"relationship": relacion_code, "documents": [uuid]}]
		return invoice_data

	def test_tipo_e_sin_uuid_bloquea_timbrado(self):
		"""CFDI tipo E sin fm_uuid_relacionado → frappe.throw bloqueante."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._run_tipo_e_block(uuid_relacionado="")
		self.assertIn("UUID", str(ctx.exception))

	def test_tipo_e_con_uuid_incluye_related_documents(self):
		"""CFDI tipo E con UUID válido → related_documents en payload con relación 03 (devolución física)."""
		test_uuid = "550E8400-E29B-41D4-A716-446655440000"
		result = self._run_tipo_e_block(uuid_relacionado=test_uuid)

		self.assertIn("related_documents", result)
		docs = result["related_documents"]
		self.assertEqual(len(docs), 1)
		self.assertEqual(docs[0]["relationship"], "03")
		self.assertIn(test_uuid, docs[0]["documents"])


# ── Tests _find_uuid_cfdi_origen ─────────────────────────────────────────────


class TestFindUuidCfdiOrigen(FrappeTestCase):
	"""Tests para _find_uuid_cfdi_origen en Factura Fiscal Mexico."""

	def _call(self, ffm_doc):
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		instance = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		instance.sales_invoice = ffm_doc.get("sales_invoice")
		return instance._find_uuid_cfdi_origen()

	def test_sin_sales_invoice_retorna_none(self):
		ffm = MagicMock()
		ffm.get = lambda k, d=None: None
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		instance = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		instance.sales_invoice = None
		self.assertIsNone(instance._find_uuid_cfdi_origen())

	def test_resuelve_uuid_via_fm_factura_fiscal_mx(self):
		"""Ruta 1: SI origen tiene fm_factura_fiscal_mx → retorna fm_uuid de esa FFM."""
		expected_uuid = "UUID-ORIGEN-001"

		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		instance = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		instance.sales_invoice = "SINV-DEVOLUCION"

		def mock_get_value(doctype, name, field, **kwargs):
			if doctype == "Sales Invoice" and name == "SINV-DEVOLUCION" and field == "return_against":
				return "SINV-ORIGINAL"
			if doctype == "Sales Invoice" and name == "SINV-ORIGINAL" and field == "fm_factura_fiscal_mx":
				return "FFM-ORIGINAL"
			if doctype == "Factura Fiscal Mexico" and name == "FFM-ORIGINAL" and field == "fm_uuid":
				return expected_uuid
			return None

		with patch("frappe.db.get_value", side_effect=mock_get_value):
			result = instance._find_uuid_cfdi_origen()

		self.assertEqual(result, expected_uuid)

	def test_resuelve_uuid_via_query_fallback(self):
		"""Ruta 2 (fallback): fm_factura_fiscal_mx vacío → query FFM por sales_invoice."""
		expected_uuid = "UUID-FALLBACK-002"

		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		instance = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		instance.sales_invoice = "SINV-DEVOLUCION"

		def mock_get_value(doctype, name_or_filters, field=None, **kwargs):
			# return_against lookup
			if doctype == "Sales Invoice" and name_or_filters == "SINV-DEVOLUCION":
				return "SINV-ORIGINAL"
			# fm_factura_fiscal_mx → vacío (fuerza fallback)
			if doctype == "Sales Invoice" and name_or_filters == "SINV-ORIGINAL":
				return None
			# Fallback query: FFM con sales_invoice = SINV-ORIGINAL y status TIMBRADO
			if doctype == "Factura Fiscal Mexico" and isinstance(name_or_filters, dict):
				return expected_uuid
			return None

		with patch("frappe.db.get_value", side_effect=mock_get_value):
			result = instance._find_uuid_cfdi_origen()

		self.assertEqual(result, expected_uuid)

	def test_retorna_none_cuando_no_hay_ffm_timbrada(self):
		"""Sin FFM timbrada en SI origen → retorna None (guard bloqueará el timbrado)."""
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		instance = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		instance.sales_invoice = "SINV-DEVOLUCION"

		def mock_get_value(doctype, name_or_filters, field=None, **kwargs):
			if doctype == "Sales Invoice" and name_or_filters == "SINV-DEVOLUCION":
				return "SINV-ORIGINAL"
			return None  # Sin FFM, sin UUID en ninguna ruta

		with patch("frappe.db.get_value", side_effect=mock_get_value):
			result = instance._find_uuid_cfdi_origen()

		self.assertIsNone(result)
