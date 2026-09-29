"""Tests del clasificador determinista ClaveProdServ SAT -> item_code.

Función pura (sin BD) -> `unittest.TestCase`. Verifica la GARANTÍA de cobertura
(nunca retorna item_code vacío), la precedencia por prefijo más largo y el ruteo por
segmento SAT hacia la taxonomía autorizada de Gastos.
"""

import unittest

from facturacion_mexico.cfdi_historico_compras.clasificador import (
	classify_many,
	resolve_item_code,
)


class TestResolveItemCode(unittest.TestCase):
	def test_mapping_definido_resuelve(self):
		for clave in ("80101507", "01010101", "43211508"):
			code, motivo = resolve_item_code(clave)
			self.assertTrue(code, f"item_code vacío para {clave!r}")
			self.assertIsInstance(motivo, str)

	def test_sin_mapping_queda_sin_resolver(self):
		# Sin fallback: clave desconocida o vacía -> item_code vacío (provoca ERROR_ITEM).
		for clave in ("99999999", "", None, "  ", "07"):
			code, motivo = resolve_item_code(clave)
			self.assertEqual(code, "", f"no debería resolver {clave!r}")
			self.assertEqual(motivo, "sin_mapping")

	def test_precedencia_prefijo_mas_largo(self):
		# 8116xxxx (software) gana al segmento 81 (servicios)
		self.assertEqual(resolve_item_code("81161700")[0], "GASTO-OPR-008")
		self.assertEqual(resolve_item_code("81111811")[0], "GASTO-SRV-001")  # segmento 81
		# 8310 (energía) gana al segmento 83 (telecom)
		self.assertEqual(resolve_item_code("83101800")[0], "GASTO-OPR-003")
		self.assertEqual(resolve_item_code("83111603")[0], "GASTO-OPR-001")  # segmento 83
		# 6 dígitos gana a 4/2
		self.assertEqual(resolve_item_code("841216 00".replace(" ", ""))[0], "GASTO-VNT-002")

	def test_ruteo_por_segmento_representativo(self):
		casos = {
			"80101507": "GASTO-SRV-001",  # servicios profesionales
			"84141602": "GASTO-FIN-001",  # comisiones bancarias
			"78131806": "GASTO-ARR-002",  # renta storage (781318)
			"84131602": "GASTO-SEG-001",  # seguros (8413)
			"85101701": "GASTO-NOM-026",  # IMSS (851017)
			"90101501": "GASTO-MOV-002",  # alimentos/viáticos
			"95111602": "GASTO-MOV-010",  # peaje (exacto)
			"43211508": "INFRA-0002",  # hardware (43)
			"80141600": "GASTO-VNT-001",  # publicidad (8014)
			"84111500": "GASTO-SRV-017",  # honorarios contables (8411)
			"72101507": "GASTO-OPR-006",  # mantenimiento (72)
			"15101514": "GASTO-MOV-003",  # combustible (15)
		}
		for clave, esperado in casos.items():
			self.assertEqual(resolve_item_code(clave)[0], esperado, f"clave {clave}")

	def test_classify_many_definidos_sin_item_cero(self):
		# Muestra amplia de segmentos DEFINIDOS: ninguno debe quedar sin item.
		claves = [
			"80101507",
			"81161700",
			"82101800",
			"83111603",
			"84141602",
			"85121800",
			"86101601",
			"90101501",
			"78102201",
			"72101507",
			"94131603",
			"93161700",
			"15101514",
			"10121506",
			"50202203",
			"52161500",
			"43231505",
			"44103124",
			"14111815",
			"26101700",
			"32131000",
			"60111400",
			"49101609",
			"01010101",
			"95111602",
			"56101700",
		]
		_out, sin_item = classify_many(claves)
		self.assertEqual(sin_item, 0)

	def test_classify_many_cuenta_sin_mapping(self):
		_out, sin_item = classify_many(["80101507", "99999999", ""])
		self.assertEqual(sin_item, 2)


if __name__ == "__main__":
	unittest.main()
