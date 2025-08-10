#!/usr/bin/env python3
"""Script para debuggear CI dentro de la app"""

import frappe
from frappe.test_runner import get_dependencies


def debug_doctype_dependencies():
	"""Debug específico para encontrar el DocType que causa None"""
	print("=== DEBUG DOCTYPE DEPENDENCIES CI ===")

	try:
		# Listar DocTypes de facturacion_mexico
		doctypes = frappe.get_all("DocType", filters={"module": "Facturacion Mexico"}, fields=["name"])

		print(f"DocTypes a procesar: {[dt.name for dt in doctypes]}")

		for dt in doctypes:
			print(f"\n🔍 Procesando: {dt.name}")
			try:
				# Simular exactamente lo que hace get_dependencies
				meta = frappe.get_meta(dt.name)
				link_fields = meta.get_link_fields()
				print(f"   📋 Link fields: {[f.fieldname for f in link_fields]}")

				# El problema está aquí:
				table_fields = meta.get_table_fields()
				print(f"   📋 Table fields: {[f.fieldname for f in table_fields]}")

				for df in table_fields:
					print(f'      - {df.fieldname} -> options: "{df.options}"')
					if df.options:
						try:
							child_meta = frappe.get_meta(df.options)
							child_links = child_meta.get_link_fields()
							print(f"        ✅ Child {df.options}: {len(child_links)} link fields")
						except Exception as child_error:
							print(f"        ❌ ERROR en child {df.options}: {child_error}")
					else:
						print(f"        🚨 PROBLEMA: options vacío en {df.fieldname}!")
						# Esto causaría frappe.get_meta(None)

			except Exception as e:
				print(f"   ❌ ERROR en {dt.name}: {e}")
				import traceback

				traceback.print_exc()
				break

	except Exception as e:
		print(f"ERROR GENERAL: {e}")
		import traceback

		traceback.print_exc()


if __name__ == "__main__":
	debug_doctype_dependencies()
