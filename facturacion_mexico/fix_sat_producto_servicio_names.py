import frappe


def run():
	"""Corregir names de SAT Producto Servicio para usar código SAT como ID"""

	print("🔧 CORRIGIENDO SAT PRODUCTO SERVICIO NAMES")
	print("=" * 50)

	try:
		# 1. Obtener registros actuales
		registros = frappe.get_all("SAT Producto Servicio", fields=["name", "codigo", "descripcion"])

		print(f"📊 Registros encontrados: {len(registros)}")

		corrected = 0
		for registro in registros:
			old_name = registro.name
			new_name = registro.codigo  # Usar código SAT como name

			print(f"🔄 Corrigiendo: {old_name} → {new_name}")

			# Actualizar name del registro
			frappe.db.sql(
				"""
                UPDATE `tabSAT Producto Servicio`
                SET name = %s
                WHERE name = %s
            """,
				(new_name, old_name),
			)

			corrected += 1

		# 2. Commit cambios
		frappe.db.commit()

		# 3. Verificar resultado
		verificacion = frappe.get_all("SAT Producto Servicio", fields=["name", "descripcion"], limit=5)

		print(f"\n✅ Corrección completada: {corrected} registros")
		print("📋 Registros actualizados:")
		for reg in verificacion:
			print(f"   - {reg.name}: {reg.descripcion}")

		return {
			"success": True,
			"corrected": corrected,
			"message": f"Actualizados {corrected} registros SAT Producto Servicio",
		}

	except Exception as e:
		print(f"💥 Error: {str(e)}")
		return {"success": False, "error": str(e)}
