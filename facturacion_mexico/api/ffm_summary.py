import frappe

# DocType correcto
FFM_DOCTYPE = "Factura Fiscal Mexico"

# Mapeo de campos basado en la estructura real del DocType
ALIASES = {
	"estado": ["fm_fiscal_status", "status", "cfdi_status"],
	"folio": ["fm_serie_folio", "folio", "serie", "folio_fiscal"],
	"uuid": ["fm_uuid", "uuid", "uuid_fiscal"],
	"fecha": ["fecha_timbrado", "cfdi_date", "fm_fecha_cfdi"],
	"pac_msg": ["fm_sync_error", "last_pac_message", "pac_response", "ultimo_mensaje_pac"],
}


def _pick(d, keys):
	"""Obtiene el primer valor no vacío de las keys especificadas"""
	for k in keys:
		if d.get(k):
			return d[k]
	return None


@frappe.whitelist()
def get_ffm_summary(ffm_name: str) -> dict:
	"""
	Obtiene resumen de información de Factura Fiscal Mexico.

	Args:
	    ffm_name: Nombre del documento Factura Fiscal Mexico

	Returns:
	    dict: Información resumida de la factura fiscal
	"""
	if not ffm_name:
		return {}

	try:
		doc = frappe.get_doc(FFM_DOCTYPE, ffm_name).as_dict()

		# "Serie y Folio": preferir el combinado ya persistido; si no, unir serie+folio;
		# como último recurso, mostrar lo que haya suelto (folio, serie o folio_fiscal).
		folio_display = (doc.get("fm_serie_folio") or "").strip()
		if not folio_display:
			serie = (doc.get("serie") or "").strip()
			folio = (doc.get("folio") or "").strip()
			if serie and folio:
				folio_display = f"{serie}-{folio}"
			else:
				folio_display = folio or serie or (doc.get("folio_fiscal") or "").strip() or None

		metodo_pago = doc.get("fm_payment_method_sat") or ""
		metodo_pago_label = {
			"PUE": "PUE — Pago en una sola exhibición",
			"PPD": "PPD — Pago en parcialidades o diferido",
		}.get(metodo_pago, metodo_pago or "-")

		return {
			"estado": _pick(doc, ALIASES["estado"]),
			"folio": folio_display,
			"uuid": _pick(doc, ALIASES["uuid"]),
			"fecha": _pick(doc, ALIASES["fecha"]),
			"pac_msg": _pick(doc, ALIASES["pac_msg"]),
			"metodo_pago": metodo_pago_label,
			"name": doc.get("name"),
			"doctype": doc.get("doctype"),
		}

	except frappe.DoesNotExistError:
		frappe.log_error(f"Factura Fiscal Mexico {ffm_name} no encontrada", "FFM Summary Error")
		return {}
	except Exception as e:
		frappe.log_error(f"Error obteniendo summary FFM {ffm_name}: {e}", "FFM Summary Error")
		return {}
