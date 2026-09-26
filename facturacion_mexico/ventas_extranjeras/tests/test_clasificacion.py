"""Tests unitarios — clasificación territorial (nacional vs extranjero).

Funciones puras de resolución: se mockean `frappe.db.get_value` y `frappe.get_all`
(sin red, sin BD). Datos FICTICIOS. Cubre la prioridad aprobada:
XEXX (fuerte) → país de Address vs Company → Territory fallback → INDETERMINADO.
"""

import unittest
from unittest.mock import patch

from frappe import _dict

from facturacion_mexico.ventas_extranjeras import clasificacion
from facturacion_mexico.ventas_extranjeras.clasificacion import (
	EXTRANJERA,
	INDETERMINADO,
	NACIONAL,
	clasificar_desde_cfdi,
	clasificar_territorialidad,
)

XEXX = "XEXX010101000"

# ── Dataset en memoria (FICTICIO) ─────────────────────────────────────────────
_COMPANY_COUNTRY = {"MI EMPRESA": "Mexico"}

ROW = "Rest Of The World"  # catch-all estándar de ERPNext: NO clasifica por sí solo

# Customer -> atributos
_CUSTOMERS = {
	"NAC": _dict(tax_id="ABC010101AAA", customer_primary_address="ADDR-MX", territory="Nacional"),
	"EXT-ADDR": _dict(tax_id="ABC010101AAA", customer_primary_address="ADDR-CO", territory="Nacional"),
	"EXT-XEXX": _dict(tax_id=XEXX, customer_primary_address="ADDR-MX", territory="Nacional"),
	"INDET": _dict(tax_id="ABC010101AAA", customer_primary_address=None, territory="All Territories"),
	"EXT-DLINK": _dict(tax_id="ABC010101AAA", customer_primary_address=None, territory="Nacional"),
	# Casos con Territory "Rest Of The World" (ya NO es fuente de clasificación):
	"XAXX-TERR": _dict(tax_id="XAXX010101000", customer_primary_address=None, territory=ROW),
	"NORMAL-TERR": _dict(tax_id="ABC010101AAA", customer_primary_address=None, territory=ROW),
	"XEXX-TERR": _dict(tax_id=XEXX, customer_primary_address=None, territory=ROW),
	"ADDR-EXT-TERR": _dict(tax_id="ABC010101AAA", customer_primary_address="ADDR-US", territory=ROW),
	"ADDR-NAC-TERR": _dict(tax_id="ABC010101AAA", customer_primary_address="ADDR-MX", territory=ROW),
}
_ADDR_COUNTRY = {"ADDR-MX": "Mexico", "ADDR-CO": "Colombia", "ADDR-EC": "Ecuador", "ADDR-US": "United States"}
# Direcciones vinculadas por Customer (Dynamic Link)
_CUST_ADDR_LINKS = {"EXT-DLINK": ["ADDR-US"]}


def _fake_get_value(doctype, name, field, *args, **kwargs):
	if doctype == "Company" and field == "country":
		return _COMPANY_COUNTRY.get(name)
	if doctype == "Customer":
		return _CUSTOMERS.get(name, _dict()).get(field)
	if doctype == "Address" and field == "country":
		return _ADDR_COUNTRY.get(name)
	return None


def _fake_get_all(doctype, filters=None, fields=None):
	if doctype == "Dynamic Link":
		cust = (filters or {}).get("link_name")
		return [_dict(parent=a) for a in _CUST_ADDR_LINKS.get(cust, [])]
	return []


def _clasificar(customer, customer_address=None, company="MI EMPRESA"):
	doc = _dict(company=company, customer=customer, customer_address=customer_address)
	with (
		patch.object(clasificacion.frappe.db, "get_value", side_effect=_fake_get_value),
		patch.object(clasificacion.frappe, "get_all", side_effect=_fake_get_all),
	):
		return clasificar_territorialidad(doc)


class TestClasificacionTerritorial(unittest.TestCase):
	def test_nacional_por_address(self):
		self.assertEqual(_clasificar("NAC"), NACIONAL)

	def test_extranjero_por_address(self):
		self.assertEqual(_clasificar("EXT-ADDR"), EXTRANJERA)

	def test_xexx_resuelve_extranjero_pese_a_address_mexico(self):
		# tax_id XEXX + dirección Mexico inconsistente -> XEXX gana (señal fuerte).
		self.assertEqual(_clasificar("EXT-XEXX"), EXTRANJERA)

	def test_indeterminado_sin_evidencia(self):
		# RFC mexicano normal, sin address, sin Territory útil -> no adivinar
		self.assertEqual(_clasificar("INDET"), INDETERMINADO)

	# ── Territory "Rest Of The World" ya NO clasifica (Opción A) ───────────────
	def test_row_xaxx_sin_address_es_indeterminado(self):
		# (1) XAXX + sin Address.country + RoW -> INDETERMINADO (no extranjero por Territory)
		self.assertEqual(_clasificar("XAXX-TERR"), INDETERMINADO)

	def test_row_rfc_normal_sin_address_es_indeterminado(self):
		# (2) RFC normal + sin Address.country + RoW -> INDETERMINADO
		self.assertEqual(_clasificar("NORMAL-TERR"), INDETERMINADO)

	def test_row_con_xexx_es_extranjero(self):
		# (3) XEXX + RoW -> EXTRANJERA (gana la señal fuerte XEXX)
		self.assertEqual(_clasificar("XEXX-TERR"), EXTRANJERA)

	def test_row_con_address_extranjero_es_extranjero(self):
		# (4) Address.country extranjero + RoW -> EXTRANJERA (gana Address)
		self.assertEqual(_clasificar("ADDR-EXT-TERR"), EXTRANJERA)

	def test_row_con_address_nacional_es_nacional(self):
		# (5) Address.country == Company.country + RoW -> NACIONAL (gana Address)
		self.assertEqual(_clasificar("ADDR-NAC-TERR"), NACIONAL)

	def test_customer_address_del_doc_tiene_prioridad(self):
		# doc.customer_address (Ecuador) debe pesar más que la primaria (Mexico) de NAC.
		self.assertEqual(_clasificar("NAC", customer_address="ADDR-EC"), EXTRANJERA)

	def test_dynamic_link_como_ultimo_recurso(self):
		# sin customer_address ni primaria, pero hay dirección vinculada (US) -> EXTRANJERA
		self.assertEqual(_clasificar("EXT-DLINK"), EXTRANJERA)

	def test_sin_customer_es_indeterminado(self):
		self.assertEqual(_clasificar(None), INDETERMINADO)

	def test_rfc_mexicano_normal_no_basta_para_nacional(self):
		# INDET tiene RFC mexicano válido pero sin evidencia territorial -> INDETERMINADO, no NACIONAL
		self.assertNotEqual(_clasificar("INDET"), NACIONAL)


# ── Evidencia del CFDI histórico (fuente de verdad) ───────────────────────────
class _DocConFlags:
	"""Doc mínimo con .get y .flags para probar la precedencia de la evidencia CFDI."""

	def __init__(self, evidencia, **campos):
		self._d = campos
		self.flags = _dict(fm_cfdi_territorial=evidencia)

	def get(self, key, default=None):
		return self._d.get(key, default)


class TestClasificacionDesdeCFDI(unittest.TestCase):
	def test_xexx_es_extranjero(self):
		self.assertEqual(clasificar_desde_cfdi({"receptor_rfc": XEXX}), EXTRANJERA)

	def test_residencia_fiscal_es_extranjero(self):
		self.assertEqual(
			clasificar_desde_cfdi({"receptor_rfc": "ABC010101AAA", "receptor_residencia_fiscal": "USA"}),
			EXTRANJERA,
		)

	def test_num_reg_id_trib_es_extranjero(self):
		self.assertEqual(
			clasificar_desde_cfdi({"receptor_rfc": "ABC010101AAA", "receptor_num_reg_id_trib": "US123"}),
			EXTRANJERA,
		)

	def test_rfc_nacional_sin_señales_es_nacional(self):
		self.assertEqual(clasificar_desde_cfdi({"receptor_rfc": "ABC010101AAA"}), NACIONAL)

	def test_evidencia_cfdi_tiene_precedencia_sobre_maestro(self):
		# El XML dice extranjero (residencia) aunque no pasemos datos maestros -> EXTRANJERA.
		doc = _DocConFlags({"receptor_rfc": "ABC010101AAA", "receptor_residencia_fiscal": "COL"})
		with (
			patch.object(clasificacion.frappe.db, "get_value", side_effect=_fake_get_value),
			patch.object(clasificacion.frappe, "get_all", side_effect=_fake_get_all),
		):
			self.assertEqual(clasificar_territorialidad(doc), EXTRANJERA)

	def test_evidencia_cfdi_nacional_no_reinterpreta_como_extranjero(self):
		# El XML dice nacional; aunque el maestro tuviera señales, el XML manda -> NACIONAL.
		doc = _DocConFlags({"receptor_rfc": "ABC010101AAA"}, customer="EXT-XEXX", company="MI EMPRESA")
		with (
			patch.object(clasificacion.frappe.db, "get_value", side_effect=_fake_get_value),
			patch.object(clasificacion.frappe, "get_all", side_effect=_fake_get_all),
		):
			self.assertEqual(clasificar_territorialidad(doc), NACIONAL)


if __name__ == "__main__":
	unittest.main()
