#!/usr/bin/env python3
"""
Script de Actualización de Referencias a Custom Fields
Proyecto: facturacion_mexico
Función: Actualizar todas las referencias en código de campos antiguos a nuevos con prefijo fm_
"""

import os
import re
import sys
from pathlib import Path

# Mapeo completo de campos antiguos a nuevos
FIELD_MAPPINGS = {
	# Sales Invoice (7 campos)
	"cfdi_use": "fm_cfdi_use",
	"payment_method_sat": "fm_payment_method_sat",
	"fiscal_status": "fm_fiscal_status",
	"uuid_fiscal": "fm_uuid_fiscal",
	"factura_fiscal_mx": "fm_factura_fiscal_mx",
	"informacion_fiscal_mx_section": "fm_informacion_fiscal_section",
	"column_break_fiscal_mx": "fm_column_break_fiscal",
	# Customer (5 campos)
	"rfc": "fm_rfc",
	"regimen_fiscal": "fm_regimen_fiscal",
	"uso_cfdi_default": "fm_uso_cfdi_default",
	"column_break_fiscal_customer": "fm_column_break_fiscal_customer",
	# Item (4 campos)
	"producto_servicio_sat": "fm_producto_servicio_sat",
	"unidad_sat": "fm_unidad_sat",
	"clasificacion_sat_section": "fm_clasificacion_sat_section",
	"column_break_item_sat": "fm_column_break_item_sat",
}

# Mapeo de section breaks que cambiaron de nombre
SECTION_MAPPINGS = {
	# Customer section break - para evitar duplicados
	("Customer", "informacion_fiscal_mx_section"): "fm_informacion_fiscal_section_customer"
}


def update_file(filepath):
	"""Actualizar referencias en un archivo específico"""

	try:
		with open(filepath, encoding="utf-8") as f:
			content = f.read()
	except Exception as e:
		print(f"❌ Error leyendo {filepath}: {e!s}")
		return []

	original_content = content
	changes_made = []

	for old_field, new_field in FIELD_MAPPINGS.items():
		# Patrones múltiples para capturar diferentes formas de referenciar campos
		patterns = [
			# Referencias en strings
			(rf'"{old_field}"', f'"{new_field}"'),
			(rf"'{old_field}'", f"'{new_field}'"),
			# Referencias en attributes/dot notation
			(rf"\.{old_field}\b", f".{new_field}"),
			# Referencias en diccionarios/arrays
			(rf'\["{old_field}"\]', f'["{new_field}"]'),
			(rf"\['{old_field}'\]", f"['{new_field}']"),
			# Referencias en get()
			(rf'get\("{old_field}"', f'get("{new_field}"'),
			(rf"get\('{old_field}'", f"get('{new_field}'"),
			# Referencias en fieldname definiciones
			(rf'fieldname"?\s*:\s*"{old_field}"', f'fieldname": "{new_field}"'),
			(rf"fieldname'?\s*:\s*'{old_field}'", f"fieldname': '{new_field}'"),
			# Referencias en frappe.db.set_value, get_value, etc
			(
				rf'set_value\([^,]+,\s*"{old_field}"',
				lambda m: m.group(0).replace(f'"{old_field}"', f'"{new_field}"'),
			),
			(
				rf"set_value\([^,]+,\s*'{old_field}'",
				lambda m: m.group(0).replace(f"'{old_field}'", f"'{new_field}'"),
			),
			(
				rf'get_value\([^,]+,\s*"{old_field}"',
				lambda m: m.group(0).replace(f'"{old_field}"', f'"{new_field}"'),
			),
			(
				rf"get_value\([^,]+,\s*'{old_field}'",
				lambda m: m.group(0).replace(f"'{old_field}'", f"'{new_field}'"),
			),
			# Referencias en custom field definitions
			(rf'Custom Field["\'].*{old_field}["\']', lambda m: m.group(0).replace(old_field, new_field)),
			# Referencias en SQL
			(rf"`{old_field}`", f"`{new_field}`"),
			# Referencias en validation/condition strings
			(rf"\b{old_field}\s*[=<>!]+", lambda m: m.group(0).replace(old_field, new_field)),
		]

		for pattern, replacement in patterns:
			if callable(replacement):
				# Para casos complejos que requieren lambda
				matches = re.finditer(pattern, content, re.IGNORECASE)
				for match in reversed(list(matches)):  # Reverse to maintain positions
					start, end = match.span()
					old_text = content[start:end]
					new_text = replacement(match)
					if old_text != new_text:
						content = content[:start] + new_text + content[end:]
						changes_made.append(f"{old_text} → {new_text}")
			else:
				# Para reemplazos simples
				new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
				if new_content != content:
					changes_made.append(f"{pattern} → {replacement}")
					content = new_content

	# Escribir archivo actualizado si hubo cambios
	if content != original_content:
		try:
			with open(filepath, "w", encoding="utf-8") as f:
				f.write(content)
			return changes_made
		except Exception as e:
			print(f"❌ Error escribiendo {filepath}: {e!s}")
			return []

	return []


def update_custom_fields_definitions():
	"""Actualizar específicamente el archivo custom_fields.py"""

	custom_fields_file = "facturacion_mexico/facturacion_fiscal/custom_fields.py"

	if not os.path.exists(custom_fields_file):
		print(f"⚠️ No se encontró: {custom_fields_file}")
		return

	print(f"🔧 Actualizando definiciones de custom fields: {custom_fields_file}")

	# Mapeo específico para custom_fields.py
	field_updates = [
		# Sales Invoice updates
		('"informacion_fiscal_mx_section"', '"fm_informacion_fiscal_section"'),
		('"cfdi_use"', '"fm_cfdi_use"'),
		('"payment_method_sat"', '"fm_payment_method_sat"'),
		('"column_break_fiscal_mx"', '"fm_column_break_fiscal"'),
		('"fiscal_status"', '"fm_fiscal_status"'),
		('"uuid_fiscal"', '"fm_uuid_fiscal"'),
		('"factura_fiscal_mx"', '"fm_factura_fiscal_mx"'),
		# Customer updates
		('"rfc"', '"fm_rfc"'),
		('"column_break_fiscal_customer"', '"fm_column_break_fiscal_customer"'),
		('"regimen_fiscal"', '"fm_regimen_fiscal"'),
		('"uso_cfdi_default"', '"fm_uso_cfdi_default"'),
		# Item updates
		('"clasificacion_sat_section"', '"fm_clasificacion_sat_section"'),
		('"producto_servicio_sat"', '"fm_producto_servicio_sat"'),
		('"column_break_item_sat"', '"fm_column_break_item_sat"'),
		('"unidad_sat"', '"fm_unidad_sat"'),
		# Insert_after references que también necesitan actualización
		('insert_after": "cfdi_use"', 'insert_after": "fm_cfdi_use"'),
		('insert_after": "payment_method_sat"', 'insert_after": "fm_payment_method_sat"'),
		('insert_after": "rfc"', 'insert_after": "fm_rfc"'),
		('insert_after": "producto_servicio_sat"', 'insert_after": "fm_producto_servicio_sat"'),
		# Remove fields list updates
		("Sales Invoice-informacion_fiscal_mx_section", "Sales Invoice-fm_informacion_fiscal_section"),
		("Sales Invoice-cfdi_use", "Sales Invoice-fm_cfdi_use"),
		("Sales Invoice-payment_method_sat", "Sales Invoice-fm_payment_method_sat"),
		("Sales Invoice-column_break_fiscal_mx", "Sales Invoice-fm_column_break_fiscal"),
		("Sales Invoice-fiscal_status", "Sales Invoice-fm_fiscal_status"),
		("Sales Invoice-uuid_fiscal", "Sales Invoice-fm_uuid_fiscal"),
		("Sales Invoice-factura_fiscal_mx", "Sales Invoice-fm_factura_fiscal_mx"),
		("Customer-informacion_fiscal_mx_section", "Customer-fm_informacion_fiscal_section_customer"),
		("Customer-rfc", "Customer-fm_rfc"),
		("Customer-column_break_fiscal_customer", "Customer-fm_column_break_fiscal_customer"),
		("Customer-regimen_fiscal", "Customer-fm_regimen_fiscal"),
		("Customer-uso_cfdi_default", "Customer-fm_uso_cfdi_default"),
		("Item-clasificacion_sat_section", "Item-fm_clasificacion_sat_section"),
		("Item-producto_servicio_sat", "Item-fm_producto_servicio_sat"),
		("Item-column_break_item_sat", "Item-fm_column_break_item_sat"),
		("Item-unidad_sat", "Item-fm_unidad_sat"),
	]

	# Special handling for Customer section break that has different name
	field_updates.append(('"informacion_fiscal_mx_section"', '"fm_informacion_fiscal_section_customer"'))

	try:
		with open(custom_fields_file, encoding="utf-8") as f:
			content = f.read()

		changes_count = 0
		for old, new in field_updates:
			if old in content:
				content = content.replace(old, new)
				changes_count += 1
				print(f"   ✅ {old} → {new}")

		# Write updated file
		with open(custom_fields_file, "w", encoding="utf-8") as f:
			f.write(content)

		print(f"✅ custom_fields.py actualizado: {changes_count} cambios realizados")

	except Exception as e:
		print(f"❌ Error actualizando custom_fields.py: {e!s}")


def main():
	"""Actualizar todas las referencias en el proyecto"""

	print("🚀 Iniciando actualización de referencias a custom fields...")
	print("=" * 60)

	# Directorios a procesar
	directories = ["facturacion_mexico", "tests" if os.path.exists("tests") else None]
	directories = [d for d in directories if d and os.path.exists(d)]

	# Extensiones de archivo a procesar
	extensions = [".py", ".js", ".json"]

	total_files = 0
	updated_files = 0
	total_changes = 0

	# Actualizar custom_fields.py primero (más específico)
	update_custom_fields_definitions()

	print("\n🔍 Procesando archivos en directorios...")
	print("-" * 40)

	for directory in directories:
		print(f"\n📂 Procesando directorio: {directory}")

		for root, dirs, files in os.walk(directory):
			# Saltar directorios específicos
			dirs_to_skip = [".git", "__pycache__", ".egg-info", "patches", "node_modules"]
			dirs[:] = [d for d in dirs if not any(skip in d for skip in dirs_to_skip)]

			for file in files:
				if any(file.endswith(ext) for ext in extensions):
					filepath = os.path.join(root, file)
					total_files += 1

					# Saltar archivos específicos
					if any(skip in filepath for skip in ["migrate_custom_field", "backup_custom_field"]):
						continue

					changes = update_file(filepath)
					if changes:
						updated_files += 1
						total_changes += len(changes)
						relative_path = os.path.relpath(filepath)
						print(f"   ✅ {relative_path}")

						# Mostrar algunos cambios para verificación
						for change in changes[:2]:  # Mostrar primeros 2 cambios
							print(f"      - {change}")
						if len(changes) > 2:
							print(f"      ... y {len(changes) - 2} cambios más")

	print("\n" + "=" * 60)
	print("📊 RESUMEN DE ACTUALIZACIÓN:")
	print(f"📂 Archivos procesados: {total_files}")
	print(f"✅ Archivos actualizados: {updated_files}")
	print(f"🔄 Total de cambios: {total_changes}")

	if updated_files > 0:
		print("\n✅ ACTUALIZACIÓN COMPLETADA")
		print("🔄 Se recomienda ejecutar tests para verificar funcionamiento")
		print("🧹 Ejecutar: git diff para revisar cambios")
	else:
		print("\n⚠️ No se encontraron referencias para actualizar")
		print("INFO: Esto puede indicar que ya fueron actualizadas o no existen")


if __name__ == "__main__":
	main()
