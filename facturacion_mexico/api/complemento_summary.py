import frappe


@frappe.whitelist()
def get_complemento_summary(complemento_name: str) -> dict:
	"""Resumen del Complemento Pago MX para widget en Payment Entry."""
	if not complemento_name:
		return {}

	try:
		doc = frappe.db.get_value(
			"Complemento Pago MX",
			complemento_name,
			["complement_status", "uuid_sat", "fecha_timbrado", "serie_folio", "folio_fiscal"],
			as_dict=True,
		)
		if not doc:
			return {}

		serie = ""
		folio = ""
		if doc.serie_folio and "-" in doc.serie_folio:
			parts = doc.serie_folio.split("-", 1)
			serie = parts[0]
			folio = parts[1]
		elif doc.serie_folio:
			folio = doc.serie_folio

		return {
			"complement_status": doc.complement_status,
			"uuid_sat": doc.uuid_sat,
			"fecha_timbrado": doc.fecha_timbrado,
			"serie": serie,
			"folio": folio,
			"name": complemento_name,
		}
	except Exception as e:
		frappe.log_error(f"Error en complemento_summary {complemento_name}: {e}", "Complemento Summary")
		return {}
