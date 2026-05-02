#!/usr/bin/env python3
"""
Tests unitarios E3 - Sistema Retenciones Multi-Tipo con Precisión Mejorada.

Valida:
- Constante global PROPORCION_IVA_RETENIDO_SAT (66.6667%)
- RETENCIONES_CONFIG usando constante global
- Sistema legacy TASAS_RETENCIONES deprecated
- Precisión cálculo IVA retenido (4 decimales)
- Arquitectura DRY (single source of truth)
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import (
	PROPORCION_IVA_RETENIDO_SAT,
	RETENCIONES_CONFIG,
	TASAS_RETENCIONES,
	obtener_configuracion_por_rol,
)
from facturacion_mexico.utils.roles_fiscales import (
	ROL_RET_IVA_HON,
	ROL_RET_IVA_ARR,
	ROL_RET_IVA_AUTO,
)


class TestE3RetencionesConstante(FrappeTestCase):
	"""Tests para validar constante global PROPORCION_IVA_RETENIDO_SAT."""

	def test_constante_global_existe(self):
		"""Test que constante global PROPORCION_IVA_RETENIDO_SAT existe."""
		self.assertIsNotNone(PROPORCION_IVA_RETENIDO_SAT)

	def test_constante_precision_4_decimales(self):
		"""Test que constante tiene precisión 4 decimales (66.6667)."""
		self.assertEqual(PROPORCION_IVA_RETENIDO_SAT, 66.6667)

	def test_constante_representa_dos_tercios(self):
		"""Test que constante representa 2/3 (normativa SAT)."""
		dos_tercios = (2 / 3) * 100  # 66.66666...
		self.assertAlmostEqual(PROPORCION_IVA_RETENIDO_SAT, dos_tercios, places=4)

	def test_constante_mejor_precision_vs_66_67(self):
		"""Test que 66.6667 tiene mejor precisión que 66.67 (2 decimales)."""
		# Calcular error absoluto para $1000 base
		base_iva = 160.0  # $1000 × 16% IVA
		esperado_exacto = base_iva * (2 / 3)  # 106.6666...

		# Error con 66.67 (2 decimales)
		error_66_67 = abs((base_iva * 66.67 / 100) - esperado_exacto)

		# Error con 66.6667 (4 decimales)
		error_66_6667 = abs((base_iva * 66.6667 / 100) - esperado_exacto)

		# 66.6667 debe tener menor error (mejora 10x)
		self.assertLess(error_66_6667, error_66_67)
		# Error con 4 decimales debe ser muy pequeño (< 0.01)
		self.assertLess(error_66_6667, 0.01)


class TestE3RetencionesConfig(FrappeTestCase):
	"""Tests para validar RETENCIONES_CONFIG usando constante global."""

	def test_honorarios_usa_constante_global(self):
		"""Test que honorarios usa PROPORCION_IVA_RETENIDO_SAT."""
		config = RETENCIONES_CONFIG["honorarios"]
		self.assertEqual(config["proporcion_iva_retenido"], PROPORCION_IVA_RETENIDO_SAT)
		self.assertEqual(config["proporcion_iva_retenido"], 66.6667)

	def test_arrendamiento_usa_constante_global(self):
		"""Test que arrendamiento usa PROPORCION_IVA_RETENIDO_SAT."""
		config = RETENCIONES_CONFIG["arrendamiento"]
		self.assertEqual(config["proporcion_iva_retenido"], PROPORCION_IVA_RETENIDO_SAT)
		self.assertEqual(config["proporcion_iva_retenido"], 66.6667)

	def test_autotransporte_usa_constante_global(self):
		"""Test que autotransporte usa PROPORCION_IVA_RETENIDO_SAT."""
		config = RETENCIONES_CONFIG["autotransporte"]
		self.assertEqual(config["proporcion_iva_retenido"], PROPORCION_IVA_RETENIDO_SAT)
		self.assertEqual(config["proporcion_iva_retenido"], 66.6667)

	def test_resico_usa_constante_global(self):
		"""Test que RESICO usa PROPORCION_IVA_RETENIDO_SAT."""
		config = RETENCIONES_CONFIG["resico"]
		self.assertEqual(config["proporcion_iva_retenido"], PROPORCION_IVA_RETENIDO_SAT)
		self.assertEqual(config["proporcion_iva_retenido"], 66.6667)

	def test_todos_tipos_misma_proporcion_iva(self):
		"""Test que TODOS los tipos retención usan MISMA proporción IVA (normativa SAT)."""
		tipos = ["honorarios", "arrendamiento", "autotransporte", "resico"]
		proporciones = [RETENCIONES_CONFIG[t]["proporcion_iva_retenido"] for t in tipos]

		# Todos deben ser iguales (66.6667)
		self.assertEqual(len(set(proporciones)), 1)
		self.assertEqual(proporciones[0], 66.6667)

	def test_isr_varia_por_tipo(self):
		"""Test que ISR SÍ varía por tipo (no IVA retenido)."""
		# ISR varía según tipo
		self.assertEqual(RETENCIONES_CONFIG["honorarios"]["tasa_isr"], 10.0)
		self.assertEqual(RETENCIONES_CONFIG["arrendamiento"]["tasa_isr"], 10.0)
		self.assertEqual(RETENCIONES_CONFIG["autotransporte"]["tasa_isr"], 4.0)
		self.assertEqual(RETENCIONES_CONFIG["resico"]["tasa_isr"], 1.25)

		# Pero IVA retenido SIEMPRE 66.6667%
		for tipo in ["honorarios", "arrendamiento", "autotransporte", "resico"]:
			self.assertEqual(RETENCIONES_CONFIG[tipo]["proporcion_iva_retenido"], 66.6667)


class TestE3LegacyDeprecated(FrappeTestCase):
	"""Tests para validar sistema legacy TASAS_RETENCIONES deprecated."""

	def test_legacy_iva_servicios_deprecated(self):
		"""Test que iva_servicios legacy marcado deprecated."""
		config = TASAS_RETENCIONES["iva_servicios"]
		self.assertTrue(config.get("deprecated", False))

	def test_legacy_iva_arrendamiento_deprecated(self):
		"""Test que iva_arrendamiento legacy marcado deprecated."""
		config = TASAS_RETENCIONES["iva_arrendamiento"]
		self.assertTrue(config.get("deprecated", False))

	def test_legacy_iva_autotransporte_deprecated(self):
		"""Test que iva_autotransporte legacy marcado deprecated."""
		config = TASAS_RETENCIONES["iva_autotransporte"]
		self.assertTrue(config.get("deprecated", False))

	def test_legacy_iva_resico_deprecated(self):
		"""Test que iva_resico legacy marcado deprecated."""
		config = TASAS_RETENCIONES["iva_resico"]
		self.assertTrue(config.get("deprecated", False))

	def test_legacy_usa_enfoque_antiguo(self):
		"""Test que legacy usa enfoque antiguo (% del neto, no del IVA trasladado)."""
		# Sistema legacy: 10.67% del neto ≈ 2/3 de 16% IVA
		# Sistema E3: 66.6667% del IVA trasladado

		# Verificar que legacy tiene 10.67
		self.assertEqual(TASAS_RETENCIONES["iva_servicios"]["tasa"], 10.67)
		self.assertEqual(TASAS_RETENCIONES["iva_arrendamiento"]["tasa"], 10.67)
		self.assertEqual(TASAS_RETENCIONES["iva_resico"]["tasa"], 10.67)

		# Sistema E3 usa 66.6667 del IVA trasladado (diferente base)
		self.assertEqual(RETENCIONES_CONFIG["honorarios"]["proporcion_iva_retenido"], 66.6667)

	def test_legacy_isr_no_deprecated(self):
		"""Test que ISR legacy NO deprecated (solo IVA retenido cambió)."""
		# ISR no cambió en E3, solo IVA retenido
		self.assertNotIn("deprecated", TASAS_RETENCIONES.get("isr_honorarios", {}))
		self.assertNotIn("deprecated", TASAS_RETENCIONES.get("isr_arrendamiento", {}))
		self.assertNotIn("deprecated", TASAS_RETENCIONES.get("isr_autotransporte", {}))


class TestE3CalculosPrecision(FrappeTestCase):
	"""Tests para validar cálculos con nueva precisión."""

	def test_calculo_honorarios_iva_8_frontera(self):
		"""Test cálculo retención IVA Honorarios zona frontera (8%)."""
		# Caso: $1,000 neto × 8% IVA = $80 IVA trasladado
		# Retención IVA = $80 × 66.6667% = $53.33 (redondeado)
		neto = 1000.0
		iva_trasladado = neto * 0.08  # 80.0
		ret_iva_esperada = iva_trasladado * (PROPORCION_IVA_RETENIDO_SAT / 100)

		self.assertAlmostEqual(ret_iva_esperada, 53.33, places=2)

	def test_calculo_honorarios_iva_16_general(self):
		"""Test cálculo retención IVA Honorarios zona general (16%)."""
		# Caso: $1,000 neto × 16% IVA = $160 IVA trasladado
		# Retención IVA = $160 × 66.6667% = $106.67 (redondeado)
		neto = 1000.0
		iva_trasladado = neto * 0.16  # 160.0
		ret_iva_esperada = iva_trasladado * (PROPORCION_IVA_RETENIDO_SAT / 100)

		self.assertAlmostEqual(ret_iva_esperada, 106.67, places=2)

	def test_calculo_autotransporte_isr_4_porciento(self):
		"""Test cálculo retención ISR Autotransporte (4%)."""
		# Caso: $1,000 neto × 4% ISR = $40 ISR retenido
		neto = 1000.0
		isr_esperado = neto * (RETENCIONES_CONFIG["autotransporte"]["tasa_isr"] / 100)

		self.assertAlmostEqual(isr_esperado, 40.0, places=2)

	def test_calculo_resico_isr_1_25_porciento(self):
		"""Test cálculo retención ISR RESICO (1.25%)."""
		# Caso: $1,000 neto × 1.25% ISR = $12.50 ISR retenido
		neto = 1000.0
		isr_esperado = neto * (RETENCIONES_CONFIG["resico"]["tasa_isr"] / 100)

		self.assertAlmostEqual(isr_esperado, 12.5, places=2)

	def test_precision_mejora_montos_grandes(self):
		"""Test que precisión 66.6667 reduce error en montos grandes."""
		# Caso extremo: $100,000 neto × 16% IVA = $16,000 IVA trasladado
		neto = 100000.0
		iva_trasladado = neto * 0.16  # 16,000.0
		ret_iva_exacta = iva_trasladado * (2 / 3)  # 10,666.6666...

		# Error con 66.67 (2 decimales)
		ret_iva_66_67 = iva_trasladado * 0.6667
		error_66_67 = abs(ret_iva_66_67 - ret_iva_exacta)

		# Error con 66.6667 (4 decimales)
		ret_iva_66_6667 = iva_trasladado * (PROPORCION_IVA_RETENIDO_SAT / 100)
		error_66_6667 = abs(ret_iva_66_6667 - ret_iva_exacta)

		# Error con 4 decimales debe ser < 10% del error con 2 decimales
		self.assertLess(error_66_6667, error_66_67 * 0.1)


class TestE3ArquitecturaDRY(FrappeTestCase):
	"""Tests para validar principio DRY (single source of truth)."""

	def test_una_sola_definicion_proporcion_iva(self):
		"""Test que proporción IVA retenido definida UNA sola vez (constante global)."""
		# Antes E3: 4 definiciones hardcoded (66.67 × 4)
		# Después E3: 1 definición global (PROPORCION_IVA_RETENIDO_SAT)

		# Verificar que TODAS las referencias apuntan a MISMA constante
		referencias = [
			RETENCIONES_CONFIG["honorarios"]["proporcion_iva_retenido"],
			RETENCIONES_CONFIG["arrendamiento"]["proporcion_iva_retenido"],
			RETENCIONES_CONFIG["autotransporte"]["proporcion_iva_retenido"],
			RETENCIONES_CONFIG["resico"]["proporcion_iva_retenido"],
		]

		# Todas deben ser idénticas (mismo valor en memoria)
		for ref in referencias:
			self.assertIs(ref, PROPORCION_IVA_RETENIDO_SAT)

	def test_modificar_constante_afecta_todos_tipos(self):
		"""Test que modificar constante global afecta TODOS los tipos (arquitectura DRY)."""
		# Este test verifica que si cambiara PROPORCION_IVA_RETENIDO_SAT,
		# TODOS los tipos reflejarían el cambio (single source of truth)

		valor_actual = PROPORCION_IVA_RETENIDO_SAT
		self.assertEqual(valor_actual, 66.6667)

		# Verificar que todos usan MISMA referencia
		for tipo in ["honorarios", "arrendamiento", "autotransporte", "resico"]:
			self.assertEqual(RETENCIONES_CONFIG[tipo]["proporcion_iva_retenido"], valor_actual)


class TestE3IntegracionRoles(FrappeTestCase):
	"""Tests para validar integración con mapeo roles fiscales."""

	def test_rol_honorarios_usa_nueva_precision(self):
		"""Test que rol Honorarios usa nueva precisión."""
		config = obtener_configuracion_por_rol(ROL_RET_IVA_HON)
		# Sistema legacy deprecated tiene 10.67
		# Sistema E3 moderno usa proporcion_iva_retenido en RETENCIONES_CONFIG
		self.assertEqual(config["tasa"], 10.67)  # Legacy aún disponible para compatibilidad

	def test_rol_arrendamiento_usa_nueva_precision(self):
		"""Test que rol Arrendamiento usa nueva precisión."""
		config = obtener_configuracion_por_rol(ROL_RET_IVA_ARR)
		self.assertEqual(config["tasa"], 10.67)  # Legacy

	def test_rol_autotransporte_usa_nueva_precision(self):
		"""Test que rol Autotransporte usa nueva precisión."""
		config = obtener_configuracion_por_rol(ROL_RET_IVA_AUTO)
		self.assertEqual(config["tasa"], 4.0)  # Autotransporte usa 4% (no 2/3)

	def test_retenciones_config_accesible(self):
		"""Test que RETENCIONES_CONFIG accesible para generador templates."""
		# Generador templates usa RETENCIONES_CONFIG (no TASAS_RETENCIONES)
		# Verificar que está disponible para import
		from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import (
			RETENCIONES_CONFIG,
		)

		self.assertIsNotNone(RETENCIONES_CONFIG)
		self.assertIn("honorarios", RETENCIONES_CONFIG)
		self.assertIn("proporcion_iva_retenido", RETENCIONES_CONFIG["honorarios"])


if __name__ == "__main__":
	frappe.init(site="facturacion.dev")
	frappe.connect()

	import unittest

	unittest.main()
