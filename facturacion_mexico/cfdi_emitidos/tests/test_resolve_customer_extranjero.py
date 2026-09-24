"""Tests — resolución de Customer en el importador `cfdi_emitidos`.

Cubre la resolución genérica de receptores EXTRANJEROS (RFC genérico
`XEXX010101000`), que no pueden distinguirse por `tax_id` porque todos lo
comparten. La resolución usa la evidencia del CFDI (NumRegIdTrib,
ResidenciaFiscal, Nombre) contra los datos reales del Customer.

Escenario (datos FICTICIOS): 3 masters extranjeros con el mismo RFC genérico
—uno en Colombia, uno en Ecuador, uno con dirección mal etiquetada como México—
y confirma que cada receptor resuelve al master correcto por Nombre, con la
Residencia solo como desempate.

Sin red, sin BD: se mockean `frappe.get_all` y `frappe.db.get_value`. Funciones
puras de resolución -> `unittest.TestCase` (no FrappeTestCase).
"""

import unittest
from unittest.mock import patch

from frappe import _dict

from facturacion_mexico.cfdi_emitidos import importer

# ── Dataset en memoria (FICTICIO) ─────────────────────────────────────────────

XEXX = "XEXX010101000"

# Customers: (name, customer_name, tax_id)
_CUSTOMERS = [
	_dict(name="EXT-COL", customer_name="EMPRESA EXTERIOR COLOMBIA SA", tax_id=XEXX),
	_dict(name="EXT-ECU", customer_name="CONSORCIO EXTERIOR ECUADOR S.A. TESTECU", tax_id=XEXX),
	_dict(name="EXT-USA", customer_name="FOREIGN CORP USA INC", tax_id=XEXX),
	# nacionales
	_dict(name="NAC-UNO", customer_name="PROVEEDOR NACIONAL UNO SA", tax_id="AAA010101AA1"),
	_dict(name="DUP-1", customer_name="PROVEEDOR DUPLICADO SA", tax_id="BBB020202BB2"),
	_dict(name="DUP-2", customer_name="PROVEEDOR DUPLICADO SA", tax_id="BBB020202BB2"),
]

# Address.country por Customer (vía Dynamic Link)
_ADDR_COUNTRY = {
	"EXT-COL": "Colombia",
	"EXT-ECU": "Ecuador",
	"EXT-USA": "Mexico",  # dirección mal etiquetada: el país NO debe ser requisito
}


def _fake_get_all(doctype, filters=None, fields=None):
	filters = filters or {}
	fields = fields or []
	if doctype == "Customer":
		res = [c for c in _CUSTOMERS if all(c.get(k) == v for k, v in filters.items())]
		return [_dict({f: c.get(f) for f in fields}) for c in res]
	if doctype == "Dynamic Link":
		# Modelamos 1 Address por Customer, con parent = "ADDR::<customer>".
		name = filters.get("link_name")
		if name in _ADDR_COUNTRY:
			return [_dict(parent=f"ADDR::{name}")]
		return []
	return []


def _fake_get_value(doctype, name, field):
	if doctype == "Address" and field == "country" and name.startswith("ADDR::"):
		return _ADDR_COUNTRY.get(name[len("ADDR::") :])
	return None


def _rc(rfc, receptor=None):
	with (
		patch.object(importer.frappe, "get_all", side_effect=_fake_get_all),
		patch.object(importer.frappe.db, "get_value", side_effect=_fake_get_value),
	):
		return importer.resolve_customer(rfc, receptor)


def _receptor(nombre="", num_reg="", residencia=""):
	return {
		"receptor_nombre": nombre,
		"receptor_num_reg_id_trib": num_reg,
		"receptor_residencia_fiscal": residencia,
	}


# ── Nacionales: comportamiento actual por tax_id ──────────────────────────────


class TestResolveCustomerNacional(unittest.TestCase):
	def test_match_unico(self):
		self.assertEqual(_rc("AAA010101AA1"), ("NAC-UNO", None))

	def test_sin_match(self):
		self.assertEqual(_rc("XXX000000XXX"), (None, "ERROR_CUSTOMER"))

	def test_duplicado_es_ambiguo(self):
		# Dos masters con el mismo tax_id -> AMB (no se compensa en código)
		self.assertEqual(_rc("BBB020202BB2"), (None, "ERROR_CUSTOMER_AMB"))

	def test_rfc_generico_extranjero_no_matchea_por_tax_id(self):
		# Aun con 3 Customers XEXX, la rama nacional no aplica; sin evidencia -> ERROR_CUSTOMER
		self.assertEqual(_rc(XEXX), (None, "ERROR_CUSTOMER"))


# ── Extranjeros: resolución por evidencia del CFDI ────────────────────────────


class TestResolveCustomerExtranjero(unittest.TestCase):
	def test_extranjero_col_por_nombre(self):
		r = _receptor("EMPRESA EXTERIOR COLOMBIA SA", "100000001", "COL")
		self.assertEqual(_rc(XEXX, r), ("EXT-COL", None))

	def test_extranjero_ecu_por_nombre(self):
		r = _receptor("CONSORCIO EXTERIOR ECUADOR S.A. TESTECU", "200000002", "ECU")
		self.assertEqual(_rc(XEXX, r), ("EXT-ECU", None))

	def test_extranjero_por_nombre_aunque_pais_no_coincida(self):
		# ResidenciaFiscal USA vs Address.country Mexico: el nombre resuelve igual.
		r = _receptor("FOREIGN CORP USA INC", "300000003", "USA")
		self.assertEqual(_rc(XEXX, r), ("EXT-USA", None))

	def test_nombre_con_puntuacion_normalizada(self):
		# "S.A." (con puntos) debe normalizar igual que el maestro.
		r = _receptor("Consorcio Exterior Ecuador S.A. TESTECU", "", "ECU")
		self.assertEqual(_rc(XEXX, r), ("EXT-ECU", None))

	def test_sin_nombre_desempata_por_residencia(self):
		# Sin nombre, pero ECU solo coincide con el master de Ecuador -> resuelve por país.
		r = _receptor("", "", "ECU")
		self.assertEqual(_rc(XEXX, r), ("EXT-ECU", None))

	def test_nombre_desconocido_sin_residencia_util_es_error(self):
		# Nombre que no coincide con ninguno y país sin match -> ERROR_CUSTOMER.
		r = _receptor("EMPRESA INEXISTENTE LLC", "", "USA")  # USA no mapea a Mexico
		self.assertEqual(_rc(XEXX, r), (None, "ERROR_CUSTOMER"))

	def test_num_reg_id_trib_como_tax_id_directo(self):
		# Si un cliente registró el id extranjero como tax_id, se resuelve directo.
		extra = _dict(name="EXT_DIRECTO", customer_name="EMPRESA DIRECTA LLC", tax_id="US123456789")
		_CUSTOMERS.append(extra)
		try:
			r = _receptor("EMPRESA DIRECTA LLC", "US123456789", "USA")
			self.assertEqual(_rc(XEXX, r), ("EXT_DIRECTO", None))
		finally:
			_CUSTOMERS.remove(extra)

	def test_sin_evidencia_es_error(self):
		self.assertEqual(_rc(XEXX, None), (None, "ERROR_CUSTOMER"))

	def test_nombre_duplicado_sin_desempate_es_ambiguo(self):
		# Dos masters extranjeros con el mismo nombre y sin país -> AMB.
		dup = _dict(name="EXT-USA-DUP", customer_name="FOREIGN CORP USA INC", tax_id=XEXX)
		_CUSTOMERS.append(dup)
		try:
			r = _receptor("FOREIGN CORP USA INC", "", "")  # sin residencia
			self.assertEqual(_rc(XEXX, r), (None, "ERROR_CUSTOMER_AMB"))
		finally:
			_CUSTOMERS.remove(dup)


if __name__ == "__main__":
	unittest.main()
