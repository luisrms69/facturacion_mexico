#!/usr/bin/env python3
"""
Script de migración de datos: Sales Invoice → Factura Fiscal Mexico
Migra datos existentes de campos fm_* sin perder información
"""

import frappe
from frappe import _


def migrate_existing_data():
	"""Migrar datos existentes de Sales Invoice a Factura Fiscal Mexico"""

	print("🔄 INICIANDO MIGRACIÓN DE DATOS...")

	# Campos a migrar (solo los que creamos)
	fields_to_migrate = [
		"fm_cfdi_use",
		"fm_fiscal_status",
		"fm_uuid_fiscal",
		"fm_payment_method_sat",
		"fm_forma_pago_timbrado",
		"fm_serie_folio",
		"fm_lugar_expedicion",
	]

	# Obtener todos los Sales Invoice que tienen fm_factura_fiscal_mx
	invoices = frappe.db.sql(
		"""
		SELECT name, fm_factura_fiscal_mx, {fields}
		FROM `tabSales Invoice`
		WHERE fm_factura_fiscal_mx IS NOT NULL
		AND fm_factura_fiscal_mx != ''
	""".format(fields=", ".join(fields_to_migrate)),
		as_dict=True,
	)

	print(f"📋 Encontradas {len(invoices)} facturas con Factura Fiscal Mexico")

	migrated = 0
	created = 0
	errors = 0

	for invoice in invoices:
		try:
			factura_fiscal_name = invoice["fm_factura_fiscal_mx"]

			# Verificar si existe la Factura Fiscal Mexico
			if not frappe.db.exists("Factura Fiscal Mexico", factura_fiscal_name):
				print(f"⚠️  Factura Fiscal {factura_fiscal_name} no existe, creando...")

				# Crear Factura Fiscal Mexico básica
				fiscal_doc = frappe.get_doc(
					{
						"doctype": "Factura Fiscal Mexico",
						"name": factura_fiscal_name,
						"sales_invoice": invoice["name"],
						"status": "draft",
					}
				)
				fiscal_doc.insert()
				created += 1

			# Preparar datos para actualizar
			update_data = {}
			for field in fields_to_migrate:
				if invoice.get(field):
					update_data[field] = invoice[field]

			if update_data:
				# Actualizar Factura Fiscal Mexico con los datos
				frappe.db.set_value("Factura Fiscal Mexico", factura_fiscal_name, update_data)
				migrated += 1
				print(f"✅ Migrado: {invoice['name']} → {factura_fiscal_name}")

		except Exception as e:
			print(f"❌ Error migrando {invoice['name']}: {e!s}")
			errors += 1

	# Commit cambios
	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required for data migration script to persist all changes atomically

	print("\n" + "=" * 60)
	print("📊 RESUMEN MIGRACIÓN DE DATOS:")
	print(f"   Facturas procesadas: {len(invoices)}")
	print(f"   Datos migrados: {migrated}")
	print(f"   Facturas fiscales creadas: {created}")
	print(f"   Errores: {errors}")
	print("=" * 60)

	return {"processed": len(invoices), "migrated": migrated, "created": created, "errors": errors}


if __name__ == "__main__":
	frappe.init("facturacion.dev")
	frappe.connect()
	migrate_existing_data()
