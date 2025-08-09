#!/usr/bin/env python3

import frappe


def migrate_acc_sinv_2025_00956():
	"""Migrar específicamente ACC-SINV-2025-00956 y FFMX-2025-00038 a estados arquitectura."""

	try:
		print("🔄 Migrando registros específicos para testing...")

		# Migrar Factura Fiscal FFMX-2025-00038
		frappe.db.set_value("Factura Fiscal Mexico", "FFMX-2025-00038", "fm_fiscal_status", "BORRADOR")
		print("✅ FFMX-2025-00038: Pendiente → BORRADOR")

		# Migrar Sales Invoice ACC-SINV-2025-00956
		frappe.db.set_value("Sales Invoice", "ACC-SINV-2025-00956", "fm_fiscal_status", "BORRADOR")
		print("✅ ACC-SINV-2025-00956: Pendiente → BORRADOR")

		# Commit cambios
		frappe.db.commit()

		print("🎯 Migración específica completada - Ready for testing")
		return True

	except Exception as e:
		print(f"❌ Error: {e}")
		return False


if __name__ == "__main__":
	migrate_acc_sinv_2025_00956()
