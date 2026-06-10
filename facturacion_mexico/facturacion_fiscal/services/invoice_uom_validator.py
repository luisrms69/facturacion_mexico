import frappe
from frappe import _

from facturacion_mexico.cfdi_recibidos.services.uom_policy import try_normalize_uom_to_sat_code


def validate_invoice_items_uom(items: list) -> None:
	"""Verifica que todas las líneas del Sales Invoice tengan UOM con código SAT válido.

	Acepta formatos canónico ("H87 - Pieza"), legacy ("H87 Pieza") y código puro ("H87").
	Debe llamarse antes de contactar el PAC.

	Raises:
		frappe.ValidationError: si alguna línea tiene UOM sin código SAT válido.
	"""
	invalid = []
	for item in items:
		uom = getattr(item, "uom", "") or ""
		if try_normalize_uom_to_sat_code(uom) is None:
			idx = getattr(item, "idx", "?")
			item_code = getattr(item, "item_code", "?")
			item_name = getattr(item, "item_name", "") or ""
			label = f"'{item_code}' ({item_name})" if item_name else f"'{item_code}'"
			invalid.append(f"Línea {idx} — {label}: UOM '{uom}'")

	if invalid:
		frappe.throw(
			_(
				"Las siguientes líneas tienen UOM fuera del catálogo SAT (c_ClaveUnidad).\n"
				"Corrija la UOM en cada ítem antes de timbrar:\n\n{0}"
			).format("\n".join(f"  • {i}" for i in invalid)),
			frappe.ValidationError,
			title=_("UOM no válida para timbrado"),
		)
