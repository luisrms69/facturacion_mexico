#!/usr/bin/env python3
"""
Tests específicos para validación Hito 1 - Constantes Centralizadas.
Solo testing de constantes y generación de templates.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import (
    obtener_tasa,
    obtener_configuracion_por_rol,
    es_impuesto_cascada,
    obtener_roles_por_alcance
)


class TestHito1Constantes(FrappeTestCase):
    """Tests para validar Hito 1 - Constantes centralizadas completamente funcionales."""

    def test_constantes_iva_centralizadas(self):
        """Test que todas las constantes IVA funcionan correctamente."""
        # IVA General 16%
        iva_general = obtener_tasa("iva", "general")
        self.assertEqual(iva_general["tasa"], 16.0)
        self.assertEqual(iva_general["add_deduct_tax"], "Add")
        self.assertEqual(iva_general["charge_type"], "On Net Total")

        # IVA Frontera 8%
        iva_frontera = obtener_tasa("iva", "frontera")
        self.assertEqual(iva_frontera["tasa"], 8.0)
        self.assertEqual(iva_frontera["add_deduct_tax"], "Add")

        # IVA Exportación 0%
        iva_exportacion = obtener_tasa("iva", "exportacion")
        self.assertEqual(iva_exportacion["tasa"], 0.0)

        # IVA Exento
        iva_exento = obtener_tasa("iva", "exento")
        self.assertEqual(iva_exento["tasa"], 0.0)

    def test_constantes_ieps_centralizadas(self):
        """Test que todas las constantes IEPS funcionan (Hito 1 - nuevas)."""
        # IEPS Alcohol 26.5%
        ieps_alcohol = obtener_tasa("ieps", "alcohol")
        self.assertEqual(ieps_alcohol["tasa"], 26.5)
        self.assertTrue(ieps_alcohol["iva_aplicable"])
        self.assertEqual(ieps_alcohol["add_deduct_tax"], "Add")

        # IEPS Azúcar 1.0 peso/litro
        ieps_azucar = obtener_tasa("ieps", "azucar")
        self.assertEqual(ieps_azucar["tasa"], 1.0)
        self.assertTrue(ieps_azucar["iva_aplicable"])

        # IEPS Combustibles 4.58 peso/litro
        ieps_combustibles = obtener_tasa("ieps", "combustibles")
        self.assertEqual(ieps_combustibles["tasa"], 4.58)
        self.assertTrue(ieps_combustibles["iva_aplicable"])

        # IEPS Tabaco 160%
        ieps_tabaco = obtener_tasa("ieps", "tabaco")
        self.assertEqual(ieps_tabaco["tasa"], 160.0)
        self.assertTrue(ieps_tabaco["iva_aplicable"])

    def test_constantes_retenciones_centralizadas(self):
        """Test que todas las constantes retenciones funcionan (Hito 1 - nuevas)."""
        # ISR Honorarios 10%
        isr_honorarios = obtener_tasa("retenciones", "isr_honorarios")
        self.assertEqual(isr_honorarios["tasa"], 10.0)
        self.assertEqual(isr_honorarios["add_deduct_tax"], "Deduct")

        # ISR Arrendamiento 10%
        isr_arrendamiento = obtener_tasa("retenciones", "isr_arrendamiento")
        self.assertEqual(isr_arrendamiento["tasa"], 10.0)
        self.assertEqual(isr_arrendamiento["add_deduct_tax"], "Deduct")

        # ISR Autotransporte 4%
        isr_autotransporte = obtener_tasa("retenciones", "isr_autotransporte")
        self.assertEqual(isr_autotransporte["tasa"], 4.0)
        self.assertEqual(isr_autotransporte["add_deduct_tax"], "Deduct")

        # IVA Retenido Servicios 10.67%
        iva_servicios = obtener_tasa("retenciones", "iva_servicios")
        self.assertEqual(iva_servicios["tasa"], 10.67)
        self.assertEqual(iva_servicios["add_deduct_tax"], "Deduct")

        # IVA Retenido Arrendamiento 10.67%
        iva_arrendamiento = obtener_tasa("retenciones", "iva_arrendamiento")
        self.assertEqual(iva_arrendamiento["tasa"], 10.67)
        self.assertEqual(iva_arrendamiento["add_deduct_tax"], "Deduct")

        # IVA Retenido Autotransporte 4%
        iva_autotransporte = obtener_tasa("retenciones", "iva_autotransporte")
        self.assertEqual(iva_autotransporte["tasa"], 4.0)
        self.assertEqual(iva_autotransporte["add_deduct_tax"], "Deduct")

    def test_mapeo_roles_completo(self):
        """Test que el mapeo de roles fiscales a configuraciones funciona."""
        # Roles IVA
        config_iva16 = obtener_configuracion_por_rol("IVA por Pagar (16%)")
        self.assertEqual(config_iva16["tasa"], 16.0)

        config_iva8 = obtener_configuracion_por_rol("IVA por Pagar (8% frontera)")
        self.assertEqual(config_iva8["tasa"], 8.0)

        config_iva0 = obtener_configuracion_por_rol("IVA por Pagar (0% exportación)")
        self.assertEqual(config_iva0["tasa"], 0.0)

        config_exento = obtener_configuracion_por_rol("IVA Exento")
        self.assertEqual(config_exento["tasa"], 0.0)

        # Roles IEPS
        config_ieps_alcohol = obtener_configuracion_por_rol("IEPS por Pagar (Alcohol)")
        self.assertEqual(config_ieps_alcohol["tasa"], 26.5)

        config_ieps_tabaco = obtener_configuracion_por_rol("IEPS por Pagar (Tabaco)")
        self.assertEqual(config_ieps_tabaco["tasa"], 160.0)

        # Roles Retenciones
        config_isr_hon = obtener_configuracion_por_rol("ISR Retenido (Honorarios)")
        self.assertEqual(config_isr_hon["tasa"], 10.0)
        self.assertEqual(config_isr_hon["add_deduct_tax"], "Deduct")

        config_iva_ret_serv = obtener_configuracion_por_rol("IVA Retenido (Servicios Profesionales)")
        self.assertEqual(config_iva_ret_serv["tasa"], 10.67)
        self.assertEqual(config_iva_ret_serv["add_deduct_tax"], "Deduct")

    def test_deteccion_impuestos_cascada(self):
        """Test que la detección de impuestos en cascada funciona."""
        # IEPS requieren cascada con IVA
        self.assertTrue(es_impuesto_cascada("IEPS por Pagar (Alcohol)"))
        self.assertTrue(es_impuesto_cascada("IEPS por Pagar (Azúcar/Bebidas)"))
        self.assertTrue(es_impuesto_cascada("IEPS por Pagar (Combustibles)"))
        self.assertTrue(es_impuesto_cascada("IEPS por Pagar (Tabaco)"))

        # IVA y retenciones NO requieren cascada
        self.assertFalse(es_impuesto_cascada("IVA por Pagar (16%)"))
        self.assertFalse(es_impuesto_cascada("ISR Retenido (Honorarios)"))
        self.assertFalse(es_impuesto_cascada("IVA Retenido (Servicios Profesionales)"))

    def test_combinaciones_alcance(self):
        """Test que las combinaciones por alcance funcionan."""
        # Alcance básico
        roles_basico = obtener_roles_por_alcance("basico")
        self.assertIn("IVA por Pagar (16%)", roles_basico)
        self.assertIn("IVA por Pagar (0% exportación)", roles_basico)
        self.assertIn("IVA Exento", roles_basico)

        # Alcance frontera
        roles_frontera = obtener_roles_por_alcance("frontera")
        self.assertIn("IVA por Pagar (8% frontera)", roles_frontera)

        # Alcance IEPS alcohol
        roles_ieps_alcohol = obtener_roles_por_alcance("ieps_alcohol")
        self.assertIn("IEPS por Pagar (Alcohol)", roles_ieps_alcohol)
        self.assertIn("IVA por Pagar (16%)", roles_ieps_alcohol)  # Cascada

        # Alcance retenciones honorarios
        roles_ret_honorarios = obtener_roles_por_alcance("retenciones_honorarios")
        self.assertIn("ISR Retenido (Honorarios)", roles_ret_honorarios)
        self.assertIn("IVA Retenido (Servicios Profesionales)", roles_ret_honorarios)

    def test_error_handling_constantes(self):
        """Test que el manejo de errores funciona correctamente."""
        # Categoría inexistente
        with self.assertRaises(ValueError):
            obtener_tasa("categoria_inexistente", "tipo")

        # Tipo inexistente
        with self.assertRaises(ValueError):
            obtener_tasa("iva", "tipo_inexistente")

        # Rol inexistente
        with self.assertRaises(ValueError):
            obtener_configuracion_por_rol("Rol Inexistente")

        # Alcance inexistente
        with self.assertRaises(ValueError):
            obtener_roles_por_alcance("alcance_inexistente")

    def test_cobertura_14_de_14_templates(self):
        """Test que el sistema puede generar los 14/14 templates prometidos."""
        # Este test valida que las constantes permiten generar:
        # - 4 IVA base (16%, 8%, 0%, exento)
        # - 4 IEPS + cascada (alcohol, azúcar, combustibles, tabaco)
        # - 6 retenciones (3 ISR + 3 IVA retenido)
        # = 14 templates totales

        # Verificar IVA (4 tipos)
        tipos_iva = ["general", "frontera", "exportacion", "exento"]
        for tipo in tipos_iva:
            config = obtener_tasa("iva", tipo)
            self.assertIsNotNone(config)
            self.assertIn("tasa", config)

        # Verificar IEPS (4 tipos)
        tipos_ieps = ["alcohol", "azucar", "combustibles", "tabaco"]
        for tipo in tipos_ieps:
            config = obtener_tasa("ieps", tipo)
            self.assertIsNotNone(config)
            self.assertIn("tasa", config)
            self.assertTrue(config["iva_aplicable"])  # Todos requieren cascada

        # Verificar retenciones (6 tipos: 3 ISR + 3 IVA)
        tipos_retenciones = [
            "isr_honorarios", "isr_arrendamiento", "isr_autotransporte",
            "iva_servicios", "iva_arrendamiento", "iva_autotransporte"
        ]
        for tipo in tipos_retenciones:
            config = obtener_tasa("retenciones", tipo)
            self.assertIsNotNone(config)
            self.assertIn("tasa", config)
            self.assertEqual(config["add_deduct_tax"], "Deduct")

        # Total: 4 + 4 + 6 = 14 configuraciones disponibles ✅


if __name__ == "__main__":
    frappe.init(site="facturacion.dev")
    frappe.connect()

    import unittest
    unittest.main()