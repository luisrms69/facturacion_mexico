#!/usr/bin/env python3

import frappe


def diagnose_migration_status():
	"""Diagnosticar estado actual de migración estados fiscales."""

	try:
		print("🔍 DIAGNÓSTICO MIGRACIÓN ESTADOS FISCALES")
		print("=" * 50)

		# 1. Verificar estados en Factura Fiscal Mexico
		ffm_states = frappe.db.sql(
			"""
			SELECT fm_fiscal_status, COUNT(*) as count
			FROM `tabFactura Fiscal Mexico`
			GROUP BY fm_fiscal_status
		""",
			as_dict=True,
		)

		print("📊 ESTADOS EN FACTURA FISCAL MEXICO:")
		for state in ffm_states:
			print(f"   - {state.fm_fiscal_status}: {state.count} registros")

		# 2. Verificar estados en Sales Invoice
		si_states = frappe.db.sql(
			"""
			SELECT fm_fiscal_status, COUNT(*) as count
			FROM `tabSales Invoice`
			WHERE fm_fiscal_status IS NOT NULL
			GROUP BY fm_fiscal_status
		""",
			as_dict=True,
		)

		print("\n📊 ESTADOS EN SALES INVOICE:")
		for state in si_states:
			print(f"   - {state.fm_fiscal_status}: {state.count} registros")

		# 3. Buscar Sales Invoice específico ACC-SINV-2025-00956
		target_invoice = frappe.db.get_value(
			"Sales Invoice",
			"ACC-SINV-2025-00956",
			["name", "fm_fiscal_status", "fm_factura_fiscal_mx"],
			as_dict=True,
		)

		print("\n🎯 SALES INVOICE ACC-SINV-2025-00956:")
		if target_invoice:
			print(f"   - Estado: {target_invoice.fm_fiscal_status}")
			print(f"   - Factura Fiscal: {target_invoice.fm_factura_fiscal_mx}")
		else:
			print("   ❌ No encontrado")

		print("\n✅ Diagnóstico completado")

	except Exception as e:
		print(f"❌ Error en diagnóstico: {e}")
	finally:
		frappe.destroy()


if __name__ == "__main__":
	diagnose_migration_status()
