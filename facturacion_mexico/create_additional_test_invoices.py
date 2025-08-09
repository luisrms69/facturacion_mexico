"""
Crear 20 Sales Invoices adicionales para pruebas - variaciones de cantidad
Basadas en ACC-SINV-2025-00924 pero con cantidades diferentes
"""

import frappe
from frappe.utils import add_days, today


def create_additional_test_invoices():
	"""Crear 20 Sales Invoices con cantidades variables para pruebas."""
	invoices_created = []

	for i in range(1, 21):  # 20 invoices
		try:
			# Crear Sales Invoice con cantidad variable
			si = frappe.get_doc(
				{
					"doctype": "Sales Invoice",
					"customer": "A&B Tecnología Sustentable S.A. de C.V.",
					"company": "_Test E2E Fiscal Company",
					"currency": "MXN",
					"posting_date": today(),
					"due_date": add_days(today(), 30),
					"items": [
						{
							"item_code": "Servicio E2E Test",
							"qty": i + 5,  # Cantidades de 6 a 25
							"rate": 100,
						}
					],
				}
			)

			# Insertar documento
			si.insert()

			# Submit para que esté listo para timbrado
			si.submit()

			invoices_created.append(si.name)

			if i % 5 == 0:
				print(f"✅ Creados {i} invoices...")

		except Exception as e:
			print(f"❌ Error creando invoice {i}: {e!s}")
			frappe.log_error(f"Error creating additional test invoice {i}: {e!s}", "Additional Test Invoices")

	print(f"\n🎯 RESULTADO: {len(invoices_created)} Sales Invoices adicionales creados")
	print(f"📋 Rango: {invoices_created[0]} a {invoices_created[-1]}")
	print("📊 Cantidades: 6 a 25 unidades")

	return {
		"success": True,
		"count": len(invoices_created),
		"invoices": invoices_created,
		"message": f"Creados {len(invoices_created)} Sales Invoices para pruebas",
	}
