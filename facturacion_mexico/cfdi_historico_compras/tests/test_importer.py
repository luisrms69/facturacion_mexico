"""Tests — importador masivo histórico de CFDI de compra -> Purchase Invoice (Draft).

Verifica la orquestación del módulo `cfdi_historico_compras` SIN tocar `cfdi_recibidos`:
- dry_run es 100% READ-ONLY (nunca llama `ingest_xml`/`build_purchase_invoice`);
- fail-closed de proveedor (no se llama al pipeline si falta Supplier → no auto-crea);
- idempotencia por UUID (PI existente, incl. cancelada, se reporta sin recrear);
- apply reutiliza el pipeline real y clasifica los ValidationError de fail-closed.

Boundary mockeado (parser + pipeline + lookups frappe). Funciones puras -> `unittest.TestCase`.
"""

import os
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.cfdi_historico_compras import importer

UUID = "11111111-1111-4111-8111-111111111111"


def _cfg(rfc="XAXX010101000"):
	return types.SimpleNamespace(company="_Test Co", company_rfc=rfc)


def _data(**over):
	d = {
		"uuid": UUID,
		"supplier_rfc": "PRO010101AAA",
		"receiver_rfc": "XAXX010101000",
		"cfdi_type": "I",
		"supplier_name": "Proveedor Test SA",
		"supplier_tax_regime": "601",
		"serie": "A",
		"folio": "1",
		"total": 100.0,
	}
	d.update(over)
	return d


def _tmpxml():
	d = tempfile.mkdtemp()
	p = os.path.join(d, "cfdi.xml")
	with open(p, "wb") as fh:
		fh.write(b"<xml/>")
	return p


def _parser_ok(data):
	# importer llama CFDIRecibidoParser(raw).parse()
	return lambda raw: types.SimpleNamespace(parse=lambda: data)


def _fake_get_value(pi_by_uuid=None, pi_by_name=None, cfdi_name=None):
	def gv(doctype, filters, field=None, as_dict=False):
		if doctype == "Purchase Invoice":
			# filtro dict -> pre-check por UUID; nombre str -> lookup docstatus (rama recovered)
			return pi_by_uuid if isinstance(filters, dict) else pi_by_name
		if doctype == "CFDI Recibido":
			return cfdi_name
		return None

	return gv


def _process(
	path,
	cfg,
	dry_run,
	*,
	data=None,
	supplier_rows=None,
	pi_by_uuid=None,
	pi_by_name=None,
	cfdi_name=None,
	ingest=None,
	build=None,
):
	"""Ejecuta _process_file con todo el boundary mockeado. Retorna (entry, ingest_mock, build_mock)."""
	data = data if data is not None else _data()
	ingest = ingest or MagicMock(
		return_value={"status": "Clasificado", "cfdi_recibido": "CR-1", "message": ""}
	)
	build = build or MagicMock(return_value={"status": "ok", "purchase_invoice": "PI-1", "recovered": False})
	with (
		patch.object(importer, "CFDIRecibidoParser", _parser_ok(data)),
		patch.object(importer, "ingest_xml", ingest),
		patch.object(importer, "build_purchase_invoice", build),
		patch.object(
			importer, "_classify_conceptos_doc", MagicMock(return_value={"total": 0, "clasificados": 0})
		),
		patch.object(
			importer.frappe,
			"get_all",
			return_value=supplier_rows if supplier_rows is not None else [frappe._dict(name="SUP-1")],
		),
		patch.object(
			importer.frappe.db, "get_value", side_effect=_fake_get_value(pi_by_uuid, pi_by_name, cfdi_name)
		),
		patch.object(importer.frappe.db, "savepoint", MagicMock()),
		patch.object(importer.frappe.db, "rollback", MagicMock()),
		patch.object(importer.frappe.db, "commit", MagicMock()),
	):
		entry = importer._process_file(path, cfg, dry_run, 0)
	return entry, ingest, build


# ── funciones puras ───────────────────────────────────────────────────────────


class TestMapBuildError(unittest.TestCase):
	def test_item(self):
		self.assertEqual(importer._map_build_error("2 concepto(s) sin item_code"), "ERROR_ITEM")

	def test_account(self):
		self.assertEqual(importer._map_build_error("Cuenta de Gasto vacía"), "ERROR_ACCOUNT")

	def test_tax(self):
		self.assertEqual(importer._map_build_error("no existe regla de impuesto"), "ERROR_TAX")

	def test_total(self):
		self.assertEqual(importer._map_build_error("grand_total difiere del XML"), "ERROR_TOTAL")

	def test_other(self):
		self.assertEqual(importer._map_build_error("algo inesperado"), "ERROR_OTHER")


class TestResolveSupplier(unittest.TestCase):
	def test_unico(self):
		with patch.object(importer.frappe, "get_all", return_value=[frappe._dict(name="SUP-1")]):
			self.assertEqual(importer.resolve_supplier_by_rfc("PRO010101AAA"), ("SUP-1", None))

	def test_missing(self):
		with patch.object(importer.frappe, "get_all", return_value=[]):
			self.assertEqual(importer.resolve_supplier_by_rfc("PRO010101AAA"), (None, "missing"))

	def test_ambiguous(self):
		with patch.object(
			importer.frappe, "get_all", return_value=[frappe._dict(name="A"), frappe._dict(name="B")]
		):
			self.assertEqual(importer.resolve_supplier_by_rfc("PRO010101AAA"), (None, "ambiguous"))

	def test_sin_rfc(self):
		self.assertEqual(importer.resolve_supplier_by_rfc(""), (None, "sin_rfc"))


# ── dry_run: 100% READ-ONLY ───────────────────────────────────────────────────


class TestDryRunReadOnly(unittest.TestCase):
	def test_ready_no_llama_pipeline(self):
		entry, ingest, build = _process(_tmpxml(), _cfg(), dry_run=True)
		self.assertEqual(entry["estado"], "READY")
		ingest.assert_not_called()
		build.assert_not_called()

	def test_supplier_missing_genera_payload_y_no_llama_pipeline(self):
		entry, ingest, _build = _process(_tmpxml(), _cfg(), dry_run=True, supplier_rows=[])
		self.assertEqual(entry["estado"], "ERROR_SUPPLIER_MISSING")
		self.assertEqual(entry["_missing_supplier"]["supplier_rfc"], "PRO010101AAA")
		self.assertEqual(entry["_missing_supplier"]["supplier_name"], "Proveedor Test SA")
		ingest.assert_not_called()

	def test_existing_pi_reporta_docstatus_sin_recrear(self):
		# PI existente cancelada (docstatus=2)
		pi_row = frappe._dict(name="PI-9", docstatus=2)
		entry, ingest, build = _process(_tmpxml(), _cfg(), dry_run=True, pi_by_uuid=pi_row)
		self.assertEqual(entry["estado"], "EXISTING_PI")
		self.assertEqual(entry["purchase_invoice"], "PI-9")
		self.assertEqual(entry["docstatus_pi"], 2)
		ingest.assert_not_called()
		build.assert_not_called()

	def test_skip_no_aplicable(self):
		entry, ingest, _ = _process(_tmpxml(), _cfg(), dry_run=True, data=_data(cfdi_type="E"))
		self.assertEqual(entry["estado"], "SKIP_NO_APLICABLE")
		ingest.assert_not_called()

	def test_receptor_mismatch(self):
		entry, ingest, _ = _process(_tmpxml(), _cfg(rfc="XEXX010101000"), dry_run=True)
		self.assertEqual(entry["estado"], "ERROR_RECEPTOR_RFC")
		ingest.assert_not_called()

	def test_parse_error(self):
		def _boom(raw):
			raise ValueError("xml roto")

		with patch.object(importer, "CFDIRecibidoParser", _boom):
			entry = importer._process_file(_tmpxml(), _cfg(), True, 0)
		self.assertEqual(entry["estado"], "ERROR_PARSE")


# ── apply: reutiliza el pipeline real ─────────────────────────────────────────


class TestApply(unittest.TestCase):
	def test_creada_llama_ingest_y_build(self):
		entry, ingest, build = _process(_tmpxml(), _cfg(), dry_run=False)
		self.assertEqual(entry["estado"], "CREADA")
		self.assertEqual(entry["purchase_invoice"], "PI-1")
		self.assertEqual(entry["docstatus_pi"], 0)
		ingest.assert_called_once()
		build.assert_called_once()

	def test_supplier_missing_no_llama_ingest_failclosed(self):
		# Fail-closed: sin Supplier NO se llama al pipeline (no auto-crea).
		entry, ingest, build = _process(_tmpxml(), _cfg(), dry_run=False, supplier_rows=[])
		self.assertEqual(entry["estado"], "ERROR_SUPPLIER_MISSING")
		ingest.assert_not_called()
		build.assert_not_called()

	def test_build_validationerror_item_se_clasifica(self):
		build = MagicMock(side_effect=frappe.ValidationError("3 concepto(s) sin item_code"))
		entry, ingest, _ = _process(_tmpxml(), _cfg(), dry_run=False, build=build)
		self.assertEqual(entry["estado"], "ERROR_ITEM")
		ingest.assert_called_once()

	def test_recovered_reporta_existing_pi(self):
		# Pre-check por UUID no encuentra PI (pi_by_uuid=None) -> corre pipeline;
		# build detecta idempotencia (recovered) -> se reporta EXISTING_PI con docstatus por nombre.
		build = MagicMock(return_value={"status": "ok", "purchase_invoice": "PI-7", "recovered": True})
		entry, _ing, _b = _process(
			_tmpxml(),
			_cfg(),
			dry_run=False,
			build=build,
			pi_by_uuid=None,
			pi_by_name=frappe._dict(docstatus=1),
		)
		self.assertEqual(entry["estado"], "EXISTING_PI")
		self.assertEqual(entry["purchase_invoice"], "PI-7")
		self.assertEqual(entry["docstatus_pi"], 1)


if __name__ == "__main__":
	unittest.main()
