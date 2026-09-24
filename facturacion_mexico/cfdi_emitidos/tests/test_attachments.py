"""Tests — adjuntos XML/PDF del importador `cfdi_emitidos`.

Cubre:
  1. XML + PDF -> se detecta el PDF hermano (mismo stem + directorio).
  2. Solo XML -> sin PDF, no es error.
  3. Reejecución -> `_attach_file` es idempotente (no duplica el mismo adjunto).
  4. PDF huérfano -> `_scan_source` lo reporta y NO lo trata como XML (no genera SI).

La asociación XML<->PDF es determinista (stem+directorio), sin fuzzy matching.

`_find_pdf_for` / `_scan_source` son puros de filesystem (tempdir). `_attach_file`
se prueba con `frappe` mockeado -> sin BD ni red. `unittest.TestCase`.
"""

import os
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from facturacion_mexico.cfdi_emitidos import importer

# ── 1 y 2: emparejamiento determinista XML<->PDF ──────────────────────────────


class TestFindPdfFor(unittest.TestCase):
	def test_xml_con_pdf_hermano(self):
		with tempfile.TemporaryDirectory() as d:
			xml = os.path.join(d, "UUID-1.xml")
			pdf = os.path.join(d, "UUID-1.pdf")
			open(xml, "w").close()
			open(pdf, "w").close()
			self.assertEqual(importer._find_pdf_for(xml), pdf)

	def test_solo_xml_sin_pdf_no_es_error(self):
		with tempfile.TemporaryDirectory() as d:
			xml = os.path.join(d, "UUID-2.xml")
			open(xml, "w").close()
			self.assertIsNone(importer._find_pdf_for(xml))

	def test_pdf_igual_stem_en_otro_directorio_no_empareja(self):
		# Determinismo: solo cuenta el MISMO directorio, no otro con igual stem.
		with tempfile.TemporaryDirectory() as d:
			os.mkdir(os.path.join(d, "a"))
			os.mkdir(os.path.join(d, "b"))
			xml = os.path.join(d, "a", "U.xml")
			open(xml, "w").close()
			open(os.path.join(d, "b", "U.pdf"), "w").close()
			self.assertIsNone(importer._find_pdf_for(xml))

	def test_extension_pdf_mayuscula(self):
		with tempfile.TemporaryDirectory() as d:
			xml = os.path.join(d, "U.xml")
			pdf = os.path.join(d, "U.PDF")
			open(xml, "w").close()
			open(pdf, "w").close()
			self.assertEqual(importer._find_pdf_for(xml), pdf)


# ── 4: escaneo del directorio y PDF huérfanos ─────────────────────────────────


class TestScanSource(unittest.TestCase):
	def test_clasifica_xml_pdf_y_reporta_huerfanos(self):
		with tempfile.TemporaryDirectory() as d:
			open(os.path.join(d, "A.xml"), "w").close()  # par XML+PDF
			open(os.path.join(d, "A.pdf"), "w").close()
			open(os.path.join(d, "B.xml"), "w").close()  # solo XML
			open(os.path.join(d, "C.pdf"), "w").close()  # PDF huérfano
			scan = importer._scan_source(d)
			self.assertEqual(sorted(os.path.basename(x) for x in scan["xml"]), ["A.xml", "B.xml"])
			self.assertEqual([os.path.basename(x) for x in scan["orphan_pdf"]], ["C.pdf"])

	def test_huerfano_no_se_trata_como_xml(self):
		with tempfile.TemporaryDirectory() as d:
			open(os.path.join(d, "C.pdf"), "w").close()
			scan = importer._scan_source(d)
			self.assertEqual(scan["xml"], [])  # ningún XML -> no genera SI
			self.assertEqual([os.path.basename(x) for x in scan["orphan_pdf"]], ["C.pdf"])

	def test_cancelado_con_pdf_no_es_huerfano(self):
		with tempfile.TemporaryDirectory() as d:
			open(os.path.join(d, "X_Cancelado.xml"), "w").close()
			open(os.path.join(d, "X_Cancelado.pdf"), "w").close()
			scan = importer._scan_source(d)
			self.assertEqual(scan["orphan_pdf"], [])


# ── 3: idempotencia de attachments en reejecución ─────────────────────────────


class TestAttachFileIdempotente(unittest.TestCase):
	def _attach(self, existing_rows):
		"""Ejecuta _attach_file con frappe mockeado. `existing_rows` = lo que devuelve
		el get_all de File (vacío = no existe; con fila = ya adjunto)."""
		calls = {"insert": 0}
		fake_file = MagicMock()
		fake_file.file_url = "/private/files/CFDI-x.xml"

		def fake_insert():
			calls["insert"] += 1

		fake_file.insert.side_effect = fake_insert

		def fake_get_all(doctype, filters=None, fields=None, limit=None):
			return existing_rows

		with (
			patch.object(importer.frappe, "get_all", side_effect=fake_get_all),
			patch.object(importer.frappe, "new_doc", return_value=fake_file),
		):
			url, created = importer._attach_file("SI-0001", "CFDI-x.xml", b"data")
		return url, created, calls

	def test_primera_vez_crea_el_adjunto(self):
		_url, created, calls = self._attach(existing_rows=[])
		self.assertTrue(created)
		self.assertEqual(calls["insert"], 1)

	def test_reejecucion_no_duplica(self):
		existente = [importer.frappe._dict(file_url="/private/files/CFDI-x.xml")]
		url, created, calls = self._attach(existing_rows=existente)
		self.assertFalse(created)
		self.assertEqual(calls["insert"], 0)
		self.assertEqual(url, "/private/files/CFDI-x.xml")


# ── PDF sin reparseo: filesystem + copy_from_existing_file (evita pdf_contains_js) ──


class _FileRec:
	"""File espía: registra qué atributos se asignan y expone `flags`."""

	def __init__(self):
		object.__setattr__(self, "asignados", set())
		object.__setattr__(self, "flags", types.SimpleNamespace(ignore_permissions=False))
		object.__setattr__(self, "file_url", None)
		object.__setattr__(self, "inserted", False)

	def __setattr__(self, k, v):
		self.asignados.add(k)
		object.__setattr__(self, k, v)

	def insert(self):
		object.__setattr__(self, "inserted", True)


class TestAttachPdfSinReparseo(unittest.TestCase):
	def _attach(self, file_name, use_filesystem):
		rec = _FileRec()
		saved = {"file_name": file_name, "file_url": f"/private/files/{file_name}"}
		with (
			patch.object(importer.frappe, "get_all", return_value=[]),
			patch.object(importer.frappe, "new_doc", return_value=rec),
			patch("frappe.utils.file_manager.save_file_on_filesystem", return_value=saved) as sfs,
		):
			url, created = importer._attach_file(
				"SI-0001", file_name, b"%PDF-1.4 data", use_filesystem=use_filesystem
			)
		return rec, url, created, sfs

	def test_pdf_via_filesystem_no_pasa_content_y_referencia_url(self):
		rec, url, created, sfs = self._attach("CFDI-x.pdf", use_filesystem=True)
		self.assertTrue(created)
		self.assertTrue(rec.inserted)
		# El blob se escribió por el escritor nativo (no se reparsea el PDF).
		sfs.assert_called_once()
		# Se referencia por file_url + copy_from_existing_file (before_insert retorna
		# antes de write_file()/check_content()/pdf_contains_js()).
		self.assertEqual(url, "/private/files/CFDI-x.pdf")
		self.assertTrue(rec.flags.copy_from_existing_file)
		# NUNCA se asigna `.content` (eso dispararía el parseo con PyPDF2).
		self.assertNotIn("content", rec.asignados)

	def test_xml_por_content_no_usa_filesystem(self):
		rec, _url, created, sfs = self._attach("CFDI-x.xml", use_filesystem=False)
		self.assertTrue(created)
		sfs.assert_not_called()
		# Ruta por content (XML: file_type != PDF -> check_content no parsea nada).
		self.assertIn("content", rec.asignados)
		self.assertFalse(getattr(rec.flags, "copy_from_existing_file", False))


if __name__ == "__main__":
	unittest.main()
