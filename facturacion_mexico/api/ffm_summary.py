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

		# Construir folio combinado si existe serie y folio por separado
		folio_display = _pick(doc, ALIASES["folio"])
		if not folio_display and doc.get("serie") and doc.get("folio"):
			folio_display = f"{doc.get('serie')}-{doc.get('folio')}"

		return {
			"estado": _pick(doc, ALIASES["estado"]),
			"folio": folio_display,
			"uuid": _pick(doc, ALIASES["uuid"]),
			"fecha": _pick(doc, ALIASES["fecha"]),
			"pac_msg": _pick(doc, ALIASES["pac_msg"]),
			"name": doc.get("name"),
			"doctype": doc.get("doctype"),
		}

	except frappe.DoesNotExistError:
		frappe.log_error(f"Factura Fiscal Mexico {ffm_name} no encontrada", "FFM Summary Error")
		return {}
	except Exception as e:
		frappe.log_error(f"Error obteniendo summary FFM {ffm_name}: {e}", "FFM Summary Error")
		return {}
