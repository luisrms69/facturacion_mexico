#!/usr/bin/env python3
"""
Script para crear cliente Volaris con datos fiscales reales del SAT
Información verificada: RFC CVA041027H80
"""

import frappe


def create_volaris_customer():
	"""Crear cliente Volaris con datos fiscales oficiales del SAT."""

	frappe.init(site="facturacion.dev")
	frappe.connect()

	try:
		# Datos oficiales de Volaris registrados en SAT
		customer_data = {
			"doctype": "Customer",
			"customer_name": "Concesionaria Vuela Compañía de Aviación SAPI de CV",
			"customer_type": "Company",
			"customer_group": "Commercial",
			"territory": "Mexico",
			"tax_id": "CVA041027H80",  # RFC oficial SAT
			"is_frozen": 0,
			"disabled": 0,
			"country": "Mexico",
			"default_currency": "MXN",
			"language": "es",
			# Campos fiscales específicos de México
			"fm_rfc": "CVA041027H80",
			"custom_regimen_fiscal": "601",  # General de Ley Personas Morales
		}

		# Verificar si ya existe
		existing_customer = frappe.db.exists("Customer", {"tax_id": "CVA041027H80"})
		if existing_customer:
			print(f"✅ Cliente Volaris ya existe: {existing_customer}")
			customer = frappe.get_doc("Customer", existing_customer)
		else:
			# Crear nuevo customer
			customer = frappe.new_doc("Customer")
			customer.update(customer_data)
			customer.insert()
			print(f"✅ Cliente Volaris creado: {customer.name}")

		# Crear dirección fiscal oficial
		address_data = {
			"doctype": "Address",
			"address_title": "Volaris - Oficinas Corporativas",
			"address_type": "Billing",
			"address_line1": "Antonio Dovali Jaime No. 70, Torre B, Piso 13",
			"city": "México",
			"state": "Ciudad de México",
			"country": "Mexico",
			"pincode": "01210",
			"is_primary_address": 1,
			"is_shipping_address": 0,
		}

		# Verificar si ya existe la dirección
		existing_address = frappe.db.exists(
			"Address", {"address_line1": address_data["address_line1"], "pincode": "01210"}
		)

		if existing_address:
			print(f"✅ Dirección Volaris ya existe: {existing_address}")
			address = frappe.get_doc("Address", existing_address)
		else:
			# Crear nueva dirección
			address = frappe.new_doc("Address")
			address.update(address_data)
			address.insert()
			print(f"✅ Dirección Volaris creada: {address.name}")

		# Vincular dirección con customer
		existing_link = frappe.db.exists(
			"Dynamic Link", {"parent": address.name, "link_doctype": "Customer", "link_name": customer.name}
		)

		if not existing_link:
			# Crear vínculo
			address.append("links", {"link_doctype": "Customer", "link_name": customer.name})
			address.save()
			print("✅ Dirección vinculada con customer")

		# Actualizar customer con dirección primaria
		if not customer.customer_primary_address:
			customer.customer_primary_address = address.name
			customer.save()
			print("✅ Dirección primaria configurada")

		frappe.db.commit()

		print("\n🎉 CLIENTE VOLARIS CONFIGURADO EXITOSAMENTE")
		print(f"📋 Customer: {customer.name}")
		print(f"🏢 Razón Social: {customer.customer_name}")
		print(f"💰 RFC: {customer.tax_id}")
		print(f"📍 Dirección: {address.name}")
		print(f"🏠 Ubicación: {address.address_line1}, CP {address.pincode}")

		return {
			"customer": customer.name,
			"customer_name": customer.customer_name,
			"rfc": customer.tax_id,
			"address": address.name,
		}

	except Exception as e:
		print(f"❌ Error creando cliente Volaris: {e!s}")
		frappe.db.rollback()
		raise

	finally:
		frappe.destroy()


if __name__ == "__main__":
	result = create_volaris_customer()
	print("\n📋 RESULTADO:")
	for key, value in result.items():
		print(f"  {key}: {value}")
