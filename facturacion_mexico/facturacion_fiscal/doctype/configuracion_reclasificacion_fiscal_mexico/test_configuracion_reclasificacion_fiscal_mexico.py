"""
Tests: Configuracion Reclasificacion Fiscal Mexico (CRFM)

Cubre:
- cargar_reglas(): reconstruye tabla desde CFM + MRFPE, preserva cuenta_destino previa
- aplicar(): crea, actualiza o deja sin cambios los MRFPE según cuenta_destino
"""

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

_COMPANY = "_Test Company CRFM"
_MODULE = "facturacion_mexico.facturacion_fiscal.doctype.configuracion_reclasificacion_fiscal_mexico.configuracion_reclasificacion_fiscal_mexico"

_CUENTA_IVA = "2101-IVA Cobrable"
_CUENTA_IVA_DESTINO = "2103-IVA Cobrado"
_CUENTA_IVA_DESTINO_NUEVA = "2199-IVA Cobrado Nuevo"


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_crfm(reglas=None):
	doc = frappe.new_doc("Configuracion Reclasificacion Fiscal Mexico")
	doc.company = _COMPANY
	doc.reglas = reglas or []
	return doc


def _make_regla(**kwargs):
	defaults = {
		"source_type": "Ingresos / CFM",
		"tipo_operacion": "Cobro",
		"rol_fiscal": "IVA por Pagar (Nacional)",
		"cuenta_origen": _CUENTA_IVA,
		"cuenta_destino": "",
		"mrfpe_ref": "",
	}
	defaults.update(kwargs)
	return frappe._dict(defaults)


def _make_cfm_row(**kwargs):
	defaults = {
		"rol_fiscal": "IVA por Pagar (Nacional)",
		"cuenta_impuesto": _CUENTA_IVA,
		"estado_validacion": "Válido",
	}
	defaults.update(kwargs)
	return frappe._dict(defaults)


def _make_cfm_mock(rows):
	cfm = frappe._dict(mapeo_cuentas=rows)
	return cfm


# ── Tests: cargar_reglas() ─────────────────────────────────────────────────


class TestCRFMCargarReglas(FrappeTestCase):
	"""cargar_reglas reconstruye la tabla desde CFM y MRFPE."""

	def _doc(self):
		doc = _make_crfm()
		return doc

	def test_sin_company_lanza_error(self):
		doc = frappe.new_doc("Configuracion Reclasificacion Fiscal Mexico")
		doc.company = ""
		doc.reglas = []
		with self.assertRaises(frappe.exceptions.ValidationError):
			doc.cargar_reglas()

	def test_sin_cfm_lanza_error(self):
		doc = self._doc()
		with (
			mock.patch(f"{_MODULE}.frappe.db.exists", return_value=None),
			mock.patch(f"{_MODULE}.frappe.throw", side_effect=frappe.exceptions.ValidationError),
		):
			with self.assertRaises(frappe.exceptions.ValidationError):
				doc.cargar_reglas()

	def test_carga_cuenta_sin_mrfpe(self):
		"""Cuenta sin MRFPE → cuenta_destino vacía."""
		doc = self._doc()
		cfm_mock = _make_cfm_mock([_make_cfm_row()])

		with (
			mock.patch(f"{_MODULE}.frappe.db.exists", return_value=f"CFM-{_COMPANY}"),
			mock.patch(f"{_MODULE}.frappe.get_doc", return_value=cfm_mock),
			mock.patch(f"{_MODULE}.frappe.get_all", return_value=[]),
			mock.patch.object(doc, "append", side_effect=lambda t, d: doc.reglas.append(frappe._dict(d))),
			mock.patch.object(doc, "save"),
		):
			doc.cargar_reglas()

		self.assertEqual(len(doc.reglas), 1)
		self.assertEqual(doc.reglas[0].cuenta_origen, _CUENTA_IVA)
		self.assertEqual(doc.reglas[0].cuenta_destino, "")
		self.assertIsNone(doc.reglas[0].mrfpe_ref)

	def test_carga_cuenta_con_mrfpe_existente(self):
		"""Cuenta con MRFPE → cuenta_destino cargada del mapeo actual."""
		doc = self._doc()
		cfm_mock = _make_cfm_mock([_make_cfm_row()])
		mrfpe_existente = [frappe._dict(name="MRFPE-0001", cuenta_destino=_CUENTA_IVA_DESTINO)]

		with (
			mock.patch(f"{_MODULE}.frappe.db.exists", return_value=f"CFM-{_COMPANY}"),
			mock.patch(f"{_MODULE}.frappe.get_doc", return_value=cfm_mock),
			mock.patch(f"{_MODULE}.frappe.get_all", return_value=mrfpe_existente),
			mock.patch.object(doc, "append", side_effect=lambda t, d: doc.reglas.append(frappe._dict(d))),
			mock.patch.object(doc, "save"),
		):
			doc.cargar_reglas()

		self.assertEqual(len(doc.reglas), 1)
		self.assertEqual(doc.reglas[0].cuenta_destino, _CUENTA_IVA_DESTINO)
		self.assertEqual(doc.reglas[0].mrfpe_ref, "MRFPE-0001")

	def test_preserva_cuenta_destino_previa(self):
		"""Si el usuario ya llenó cuenta_destino y no hay MRFPE, se preserva."""
		doc = _make_crfm(reglas=[_make_regla(cuenta_destino=_CUENTA_IVA_DESTINO, mrfpe_ref="")])
		cfm_mock = _make_cfm_mock([_make_cfm_row()])

		with (
			mock.patch(f"{_MODULE}.frappe.db.exists", return_value=f"CFM-{_COMPANY}"),
			mock.patch(f"{_MODULE}.frappe.get_doc", return_value=cfm_mock),
			mock.patch(f"{_MODULE}.frappe.get_all", return_value=[]),
			mock.patch.object(doc, "append", side_effect=lambda t, d: doc.reglas.append(frappe._dict(d))),
			mock.patch.object(doc, "save"),
		):
			doc.cargar_reglas()

		self.assertEqual(doc.reglas[0].cuenta_destino, _CUENTA_IVA_DESTINO)

	def test_ignora_filas_invalidas_cfm(self):
		"""Filas de CFM sin cuenta_impuesto o sin estado Válido se ignoran."""
		doc = self._doc()
		cfm_mock = _make_cfm_mock(
			[
				_make_cfm_row(cuenta_impuesto=""),
				_make_cfm_row(estado_validacion="Error"),
			]
		)

		with (
			mock.patch(f"{_MODULE}.frappe.db.exists", return_value=f"CFM-{_COMPANY}"),
			mock.patch(f"{_MODULE}.frappe.get_doc", return_value=cfm_mock),
			mock.patch(f"{_MODULE}.frappe.get_all", return_value=[]),
			mock.patch.object(doc, "append", side_effect=lambda t, d: doc.reglas.append(frappe._dict(d))),
			mock.patch.object(doc, "save"),
		):
			doc.cargar_reglas()

		self.assertEqual(len(doc.reglas), 0)

	def test_reconstruye_tabla_en_segunda_llamada(self):
		"""Segunda llamada reconstruye desde cero, no duplica filas."""
		doc = _make_crfm(reglas=[_make_regla()])
		cfm_mock = _make_cfm_mock([_make_cfm_row()])

		with (
			mock.patch(f"{_MODULE}.frappe.db.exists", return_value=f"CFM-{_COMPANY}"),
			mock.patch(f"{_MODULE}.frappe.get_doc", return_value=cfm_mock),
			mock.patch(f"{_MODULE}.frappe.get_all", return_value=[]),
			mock.patch.object(doc, "append", side_effect=lambda t, d: doc.reglas.append(frappe._dict(d))),
			mock.patch.object(doc, "save"),
		):
			doc.cargar_reglas()

		self.assertEqual(len(doc.reglas), 1)


# ── Tests: aplicar() ───────────────────────────────────────────────────────


class TestCRFMAplicar(FrappeTestCase):
	"""aplicar crea, actualiza o deja sin cambios los MRFPE."""

	def _doc_con_regla(self, cuenta_destino=_CUENTA_IVA_DESTINO, mrfpe_ref=""):
		return _make_crfm(reglas=[_make_regla(cuenta_destino=cuenta_destino, mrfpe_ref=mrfpe_ref)])

	def test_sin_company_lanza_error(self):
		doc = frappe.new_doc("Configuracion Reclasificacion Fiscal Mexico")
		doc.company = ""
		doc.reglas = [_make_regla(cuenta_destino=_CUENTA_IVA_DESTINO)]
		with self.assertRaises(frappe.exceptions.ValidationError):
			doc.aplicar()

	def test_crea_mrfpe_cuando_no_existe(self):
		"""Sin MRFPE existente + cuenta_destino → crea nuevo."""
		doc = self._doc_con_regla()
		mrfpe_mock = frappe._dict(name="MRFPE-NEW")
		mrfpe_mock.insert = mock.MagicMock()

		with (
			mock.patch(f"{_MODULE}.frappe.db.get_value", return_value=None),
			mock.patch(f"{_MODULE}.frappe.get_all", return_value=[]),
			mock.patch(f"{_MODULE}.frappe.new_doc", return_value=mrfpe_mock),
			mock.patch.object(doc, "save"),
		):
			resultado = doc.aplicar()

		mrfpe_mock.insert.assert_called_once()
		self.assertEqual(resultado["creados"], 1)
		self.assertEqual(resultado["actualizados"], 0)

	def test_sin_cambio_no_actualiza(self):
		"""MRFPE existe con misma cuenta_destino → sin cambios."""
		doc = self._doc_con_regla(mrfpe_ref="MRFPE-0001")

		with (
			mock.patch(f"{_MODULE}.frappe.db.get_value", return_value=_CUENTA_IVA_DESTINO),
			mock.patch(f"{_MODULE}.frappe.db.set_value") as mock_set,
			mock.patch(f"{_MODULE}.frappe.new_doc") as mock_new,
			mock.patch.object(doc, "save"),
		):
			resultado = doc.aplicar()

		mock_set.assert_not_called()
		mock_new.assert_not_called()
		self.assertEqual(resultado["creados"], 0)
		self.assertEqual(resultado["actualizados"], 0)

	def test_actualiza_cuando_cuenta_destino_cambia(self):
		"""MRFPE existe con distinta cuenta_destino → actualiza."""
		doc = self._doc_con_regla(cuenta_destino=_CUENTA_IVA_DESTINO_NUEVA, mrfpe_ref="MRFPE-0001")

		with (
			mock.patch(f"{_MODULE}.frappe.db.get_value", return_value=_CUENTA_IVA_DESTINO),
			mock.patch(f"{_MODULE}.frappe.db.set_value") as mock_set,
			mock.patch(f"{_MODULE}.frappe.new_doc") as mock_new,
			mock.patch.object(doc, "save"),
		):
			resultado = doc.aplicar()

		mock_new.assert_not_called()
		mock_set.assert_called_once_with(
			"Mapeo Reclasificacion Fiscal Payment Entry",
			"MRFPE-0001",
			"cuenta_destino",
			_CUENTA_IVA_DESTINO_NUEVA,
		)
		self.assertEqual(resultado["actualizados"], 1)

	def test_salta_filas_sin_cuenta_destino(self):
		"""Filas sin cuenta_destino no generan MRFPE."""
		doc = _make_crfm(reglas=[_make_regla(cuenta_destino="")])

		with (
			mock.patch(f"{_MODULE}.frappe.db.get_value", return_value=None),
			mock.patch(f"{_MODULE}.frappe.new_doc") as mock_new,
			mock.patch.object(doc, "save"),
		):
			resultado = doc.aplicar()

		mock_new.assert_not_called()
		self.assertEqual(resultado["creados"], 0)

	def test_mrfpe_creado_con_datos_correctos(self):
		"""El MRFPE se crea con company, tipo_operacion y cuentas correctas."""
		doc = self._doc_con_regla()
		mrfpe_mock = frappe._dict(name="MRFPE-NEW")
		mrfpe_mock.insert = mock.MagicMock()

		with (
			mock.patch(f"{_MODULE}.frappe.db.get_value", return_value=None),
			mock.patch(f"{_MODULE}.frappe.get_all", return_value=[]),
			mock.patch(f"{_MODULE}.frappe.new_doc", return_value=mrfpe_mock),
			mock.patch.object(doc, "save"),
		):
			doc.aplicar()

		self.assertEqual(mrfpe_mock.company, _COMPANY)
		self.assertEqual(mrfpe_mock.tipo_operacion, "Cobro")
		self.assertEqual(mrfpe_mock.cuenta_origen, _CUENTA_IVA)
		self.assertEqual(mrfpe_mock.cuenta_destino, _CUENTA_IVA_DESTINO)
		self.assertEqual(mrfpe_mock.activo, 1)
