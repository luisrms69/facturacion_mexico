import frappe

from facturacion_mexico.cfdi_recibidos.services.uom_policy import is_sat_uom


def validate_invoice_items_uom(items) -> None:
	"""Verifica que todas las líneas del Sales Invoice tengan UOM del catálogo SAT.

	Debe llamarse antes de contactar el PAC para evitar que _extract_sat_code_from_uom
	mapee silenciosamente UOMs no-SAT a H87, generando CFDIs fiscalmente incorrectos.

	Raises:
		frappe.ValidationError: si alguna línea tiene UOM fuera de c_ClaveUnidad SAT.
	"""
	invalid = []
	for item in items:
		uom = getattr(item, "uom", "") or ""
		if not is_sat_uom(uom):
			idx = getattr(item, "idx", "?")
			item_code = getattr(item, "item_code", "?")
			item_name = getattr(item, "item_name", "") or ""
			label = f"'{item_code}' ({item_name})" if item_name else f"'{item_code}'"
			invalid.append(f"Línea {idx} — {label}: UOM '{uom}'")

	if invalid:
		frappe.throw(
			"Las siguientes líneas tienen UOM fuera del catálogo SAT (c_ClaveUnidad).\n"
			"Corrija la UOM en cada ítem antes de timbrar:\n\n" + "\n".join(f"  • {i}" for i in invalid),
			frappe.ValidationError,
			title="UOM no válida para timbrado",
		)
