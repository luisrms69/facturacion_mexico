"""
Tests para _ensure_manual_template en wizard_cfdi_recibidos.

Verifica que el wizard genera Purchase Taxes and Charges Templates porcentuales
(On Net Total) para cada regla de traslado con tipo_factor=Tasa.
"""

import unittest

import frappe
from frappe.utils import flt

from facturacion_mexico.cfdi_recibidos.services.wizard_cfdi_recibidos import (
    _ensure_manual_template,
)

TEST_COMPANY = "_Test Company"
_H = frappe.generate_hash()[:6]


def _get_or_create_tax_account(account_name: str, company: str) -> str:
    existing = frappe.db.get_value("Account", {"account_name": account_name, "company": company}, "name")
    if existing:
        return existing
    parent = frappe.db.get_value("Account", {"account_type": "Tax", "is_group": 1, "company": company}, "name") or frappe.db.get_value("Account", {"root_type": "Liability", "is_group": 1, "company": company}, "name")
    acc = frappe.new_doc("Account")
    acc.account_name = account_name
    acc.company = company
    acc.parent_account = parent
    acc.account_type = "Tax"
    acc.insert(ignore_permissions=True)
    frappe.db.commit()
    return acc.name


def _make_config(company: str, reglas: list) -> object:
    config_name = f"CFDI-REC-CFG-{company}"
    if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
        frappe.delete_doc("Configuracion CFDI Recibidos", config_name, force=True)
    config = frappe.new_doc("Configuracion CFDI Recibidos")
    config.company = company
    config.wizard_completado = 0
    for r in reglas:
        config.append("reglas_impuesto", r)
    config.insert(ignore_permissions=True, ignore_links=True)
    frappe.db.commit()
    return frappe.get_doc("Configuracion CFDI Recibidos", config_name)


def _cleanup_templates(company: str, suffix: str):
    names = frappe.get_all(
        "Purchase Taxes and Charges Template",
        filters={"company": company, "title": ["like", f"%{suffix}%"]},
        pluck="name",
    )
    for name in names:
        frappe.delete_doc("Purchase Taxes and Charges Template", name, force=True)
    frappe.db.commit()


class TestEnsureManualTemplate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.acc_iva = _get_or_create_tax_account(f"_Test IVA WMT {_H}", TEST_COMPANY)
        cls.acc_iva8 = _get_or_create_tax_account(f"_Test IVA8 WMT {_H}", TEST_COMPANY)
        cls.acc_ieps = _get_or_create_tax_account(f"_Test IEPS WMT {_H}", TEST_COMPANY)

    @classmethod
    def tearDownClass(cls):
        _cleanup_templates(TEST_COMPANY, f"WMT {_H}")
        for acc in [cls.acc_iva, cls.acc_iva8, cls.acc_ieps]:
            try:
                frappe.delete_doc("Account", acc, force=True)
            except Exception:
                pass
        config_name = f"CFDI-REC-CFG-{TEST_COMPANY}"
        if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
            frappe.delete_doc("Configuracion CFDI Recibidos", config_name, force=True)
        frappe.db.commit()
        super().tearDownClass()

    def tearDown(self):
        _cleanup_templates(TEST_COMPANY, f"WMT {_H}")

    def _regla(self, impuesto, tasa, cuenta, *, es_retencion=False, tipo_factor="Tasa", activo=1):
        return {
            "impuesto_sat": impuesto,
            "tipo_factor": tipo_factor,
            "tasa_cuota": tasa,
            "descripcion": f"Test {impuesto} {_H}",
            "es_retencion": 1 if es_retencion else 0,
            "cuenta_impuesto": cuenta,
            "activo": activo,
        }

    def test_genera_template_iva_16(self):
        config = _make_config(TEST_COMPANY, [self._regla("002", 0.16, self.acc_iva)])
        result = _ensure_manual_template(config)
        self.assertTrue(result)
        tmpl = frappe.get_doc("Purchase Taxes and Charges Template", result)
        self.assertEqual(len(tmpl.taxes), 1)
        self.assertEqual(tmpl.taxes[0].charge_type, "On Net Total")
        self.assertAlmostEqual(flt(tmpl.taxes[0].rate), 16.0, places=1)
        self.assertEqual(tmpl.is_default, 1)
        self.assertIn("002", tmpl.title)
        self.assertIn("IVA", tmpl.title)

    def test_genera_un_template_por_tasa_iva(self):
        config = _make_config(TEST_COMPANY, [
            self._regla("002", 0.16, self.acc_iva),
            self._regla("002", 0.08, self.acc_iva8),
        ])
        result = _ensure_manual_template(config)
        self.assertTrue(result)
        templates = frappe.get_all(
            "Purchase Taxes and Charges Template",
            filters={"company": TEST_COMPANY, "title": ["like", f"%{TEST_COMPANY}%IVA%"]},
            fields=["name", "is_default", "title"],
        )
        # Verificar que se generaron 2 templates
        titulos = [t.title for t in templates]
        has_16 = any("16" in t for t in titulos)
        has_8 = any("8" in t for t in titulos)
        self.assertTrue(has_16 and has_8)
        # Solo uno es default
        defaults = [t for t in templates if t.is_default]
        self.assertEqual(len(defaults), 1)
        # El default es el de mayor tasa (16%)
        self.assertIn("16", defaults[0].title)

    def test_excluye_cuota(self):
        """Reglas con tipo_factor=Cuota no generan template On Net Total."""
        config = _make_config(TEST_COMPANY, [
            self._regla("003", 0.0, self.acc_ieps, tipo_factor="Cuota"),
        ])
        result = _ensure_manual_template(config)
        self.assertEqual(result, "")

    def test_excluye_retenciones(self):
        """Retenciones no generan template porcentual."""
        config = _make_config(TEST_COMPANY, [
            self._regla("002", 0.1067, self.acc_iva, es_retencion=True),
        ])
        result = _ensure_manual_template(config)
        self.assertEqual(result, "")

    def test_excluye_reglas_sin_cuenta(self):
        """Reglas sin cuenta_impuesto no generan template (validate auto-activa si hay cuenta)."""
        config = _make_config(TEST_COMPANY, [
            {
                "impuesto_sat": "002",
                "tipo_factor": "Tasa",
                "tasa_cuota": 0.16,
                "descripcion": f"Test sin cuenta {_H}",
                "es_retencion": 0,
                "cuenta_impuesto": "",
                "activo": 0,
            }
        ])
        result = _ensure_manual_template(config)
        self.assertEqual(result, "")

    def test_incluye_ieps_tasa(self):
        """IEPS con tipo_factor=Tasa sí genera template (es un porcentaje válido)."""
        config = _make_config(TEST_COMPANY, [
            self._regla("003", 0.265, self.acc_ieps, tipo_factor="Tasa"),
        ])
        result = _ensure_manual_template(config)
        self.assertTrue(result)
        tmpl = frappe.get_doc("Purchase Taxes and Charges Template", result)
        self.assertEqual(tmpl.taxes[0].charge_type, "On Net Total")
        self.assertIn("003", tmpl.title)
        self.assertIn("IEPS", tmpl.title)

    def test_idempotente(self):
        """Re-ejecutar no duplica templates."""
        config = _make_config(TEST_COMPANY, [self._regla("002", 0.16, self.acc_iva)])
        _ensure_manual_template(config)
        _ensure_manual_template(config)
        count = frappe.db.count(
            "Purchase Taxes and Charges Template",
            {"company": TEST_COMPANY, "title": ["like", f"%{TEST_COMPANY}%002%IVA%16%"]},
        )
        self.assertEqual(count, 1)
