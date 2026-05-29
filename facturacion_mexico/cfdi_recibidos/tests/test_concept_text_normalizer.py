"""Tests del normalizador de texto para resolucion de Items CFDI."""

import unittest


class TestNormalize(unittest.TestCase):
	def setUp(self):
		from facturacion_mexico.cfdi_recibidos.services.concept_text_normalizer import normalize

		self.normalize = normalize

	def test_empty_string_returns_empty(self):
		self.assertEqual(self.normalize(""), "")

	def test_none_returns_empty(self):
		self.assertEqual(self.normalize(None), "")

	def test_lowercase(self):
		result = self.normalize("MANTENIMIENTO PREVENTIVO")
		self.assertIn("mantenimiento", result)
		self.assertIn("preventivo", result)

	def test_removes_accents(self):
		result = self.normalize("Reparacion de equipos")
		self.assertIn("reparacion", result)

	def test_removes_accent_in_original(self):
		result = self.normalize("Reparación de equipos")
		self.assertNotIn("ó", result)
		self.assertIn("reparacion", result)

	def test_removes_stopword_de(self):
		result = self.normalize("servicio de mantenimiento")
		words = result.split()
		self.assertNotIn("de", words)

	def test_removes_short_tokens(self):
		result = self.normalize("a B c servicio")
		words = result.split()
		for w in words:
			self.assertGreaterEqual(len(w), 2)

	def test_expands_mto(self):
		result = self.normalize("mto preventivo")
		self.assertIn("mantenimiento", result)

	def test_expands_serv(self):
		result = self.normalize("serv tecnico")
		self.assertIn("servicio", result)

	def test_expands_adm(self):
		result = self.normalize("gastos adm")
		self.assertIn("administracion", result)

	def test_preserves_non_abbrev(self):
		result = self.normalize("papeleria oficina")
		self.assertIn("papeleria", result)
		self.assertIn("oficina", result)

	def test_punctuation_split(self):
		result = self.normalize("renta/arrendamiento local")
		self.assertIn("renta", result)
		self.assertIn("arrendamiento", result)
		self.assertIn("local", result)


class TestKeywordsMatch(unittest.TestCase):
	def setUp(self):
		from facturacion_mexico.cfdi_recibidos.services.concept_text_normalizer import keywords_match

		self.keywords_match = keywords_match

	def test_empty_text_returns_false(self):
		self.assertFalse(self.keywords_match("", "mantenimiento"))

	def test_empty_keywords_returns_false(self):
		self.assertFalse(self.keywords_match("mantenimiento preventivo", ""))

	def test_single_keyword_match(self):
		self.assertTrue(self.keywords_match("Mantenimiento Preventivo", "mantenimiento"))

	def test_single_keyword_no_match(self):
		self.assertFalse(self.keywords_match("Reparacion de equipos", "mantenimiento"))

	def test_all_keywords_must_be_present(self):
		self.assertTrue(
			self.keywords_match("Mantenimiento preventivo de equipos", "mantenimiento,preventivo")
		)
		self.assertFalse(self.keywords_match("Mantenimiento de equipos", "mantenimiento,preventivo"))

	def test_keywords_with_accented_text(self):
		self.assertTrue(self.keywords_match("Reparación de equipos", "reparacion"))

	def test_keywords_with_spaces_in_csv(self):
		self.assertTrue(self.keywords_match("Servicio tecnico de red", " servicio , tecnico "))

	def test_keywords_expanded_abbreviation(self):
		self.assertTrue(self.keywords_match("servicio de mantenimiento", "serv,mto"))
