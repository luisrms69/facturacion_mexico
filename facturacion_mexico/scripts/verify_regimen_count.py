import frappe


def run():
	"""Verificar cuántos regímenes fiscales tenemos total"""

	# Contar regímenes en la base
	total_regimenes = frappe.db.count("Regimen Fiscal SAT")
	print(f"📊 Total Regímenes Fiscales SAT en BD: {total_regimenes}")

	# Contar Tax Categories creadas
	total_tax_categories = frappe.db.count("Tax Category", {"title": ["like", "%-%"]})
	print(f"📊 Total Tax Categories SAT creadas: {total_tax_categories}")

	# Verificar si hay faltantes
	if total_regimenes > total_tax_categories:
		print(f"⚠️ FALTAN {total_regimenes - total_tax_categories} Tax Categories por crear")

		# Mostrar regímenes faltantes
		created_codes = []
		for tc in frappe.get_all("Tax Category", {"title": ["like", "%-%"]}, ["title"]):
			code = tc.title.split(" - ")[0]
			created_codes.append(code)

		missing_regimenes = frappe.get_all(
			"Regimen Fiscal SAT", {"code": ["not in", created_codes]}, ["code", "description"]
		)

		print("\n🔍 Regímenes faltantes:")
		for regimen in missing_regimenes:
			print(f"   - {regimen.code} - {regimen.description}")

		return {
			"total_regimenes": total_regimenes,
			"total_tax_categories": total_tax_categories,
			"missing": len(missing_regimenes),
		}
	else:
		print("✅ Todos los regímenes fiscales están cubiertos")
		return {
			"total_regimenes": total_regimenes,
			"total_tax_categories": total_tax_categories,
			"missing": 0,
		}
