#!/usr/bin/env python3
"""
Testing utilities for SHADOW MODE data creation
Usando métodos oficiales Frappe para TAREA 2.0

TODO: Tests deberán incluir monitoreo de estado correcto del campo "Estado Fiscal"
en Factura Fiscal Mexico. Validar que siempre use estados arquitectura (BORRADOR,
TIMBRADO, ERROR, etc.) y nunca estados legacy (Pendiente, Timbrada, etc.)
"""

import frappe


def create_shadow_mode_invoices():
	"""Crear 20 Sales Invoices con clientes mexicanos para SHADOW MODE"""

	# Clientes mexicanos disponibles (excluyendo Cliente E2E Test y Performance Test Customer)
	mexican_customers = [
		"A&B Tecnología Sustentable S.A. de C.V.",
		"América Móvil, S.A.B. de C.V.",
		"Empresa de Pruebas Fiscales S.A. de C.V.",
		"Grupo Bimbo S.A.B. de C.V.",
		"Liverpool S.A. de C.V.",
		"Nueva Wal mart de México, S. de R.L. de C.V.",
		"Nueva Walmart de México Test Error CP",
		"Telmex S.A.B. de C.V.",
	]

	# Datos base
	base_company = "_Test E2E Fiscal Company"
	base_item = "Servicio E2E Test"
	base_rate = 100

	print("🚀 Iniciando creación de 20 Sales Invoices para SHADOW MODE...")
	created_invoices = []

	for i in range(1, 21):
		try:
			# Seleccionar cliente mexicano (rotar entre los 8 disponibles)
			customer = mexican_customers[i % len(mexican_customers)]

			# Crear Sales Invoice usando método oficial Frappe
			si = frappe.get_doc(
				{
					"doctype": "Sales Invoice",
					"customer": customer,
					"company": base_company,
					"currency": "MXN",
					"posting_date": frappe.utils.today(),
					"due_date": frappe.utils.add_days(frappe.utils.today(), 30),
					"items": [
						{
							"item_code": base_item,
							"qty": i,  # Cantidad de 1 a 20
							"rate": base_rate,  # Precio 100
							"amount": base_rate * i,
						}
					],
				}
			)

			# Guardar usando método oficial
			si.insert()

			print(f"📋 Creado {si.name}: {customer}, Qty: {i}, Total: {base_rate * i}")
			created_invoices.append({"name": si.name, "customer": customer, "qty": i, "total": base_rate * i})

		except Exception as e:
			print(f"❌ Error creando invoice {i}: {e}")
			continue

	print(f"\n✅ Creados {len(created_invoices)} Sales Invoices exitosamente")

	# Aplicar diferentes escenarios
	apply_scenarios(created_invoices)

	return created_invoices


def apply_scenarios(invoices):
	"""Aplicar diferentes escenarios a los invoices creados"""

	total = len(invoices)
	if total < 20:
		print(f"⚠️ Solo se crearon {total} invoices, ajustando escenarios...")

	# Dividir en 4 escenarios de 5 invoices cada uno
	scenario_size = max(1, total // 4)

	scenarios = {
		"draft": invoices[0:scenario_size],
		"submitted_unpaid": invoices[scenario_size : scenario_size * 2],
		"submitted_paid": invoices[scenario_size * 2 : scenario_size * 3],
		"testing": invoices[scenario_size * 3 :],
	}

	print("\n🎭 Aplicando escenarios SHADOW MODE:")

	# Escenario 1: Dejar en Draft (ya están en draft)
	print(f"📝 Escenario Draft: {len(scenarios['draft'])} invoices")

	# Escenario 2: Submitted pero sin pago
	print(f"📤 Escenario Submitted Unpaid: {len(scenarios['submitted_unpaid'])} invoices")
	for inv in scenarios["submitted_unpaid"]:
		try:
			doc = frappe.get_doc("Sales Invoice", inv["name"])
			doc.submit()
			print(f"   ✅ Submitted: {inv['name']}")
		except Exception as e:
			print(f"   ❌ Error submitting {inv['name']}: {e}")

	# Escenario 3: Testing mixto (simplified - no payment entries for now)
	print(f"🧪 Escenario Testing: {len(scenarios['submitted_paid']) + len(scenarios['testing'])} invoices")
	remaining = scenarios["submitted_paid"] + scenarios["testing"]
	for i, inv in enumerate(remaining):
		try:
			doc = frappe.get_doc("Sales Invoice", inv["name"])
			if i % 2 == 0:
				doc.submit()
				print(f"   ✅ Testing Submitted: {inv['name']}")
			else:
				print(f"   📝 Testing Draft: {inv['name']}")
		except Exception as e:
			print(f"   ❌ Error in testing scenario {inv['name']}: {e}")

	print("\n🎯 RESUMEN FINAL:")
	print(f"- {len(scenarios['draft'])} invoices en Draft")
	print(f"- {len(scenarios['submitted_unpaid'])} invoices Submitted")
	print(f"- {len(remaining)} invoices para testing mixto")
	print("\n✅ Datos de prueba listos para SHADOW MODE")
