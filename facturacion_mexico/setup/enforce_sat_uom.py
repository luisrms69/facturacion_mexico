import frappe

from facturacion_mexico.cfdi_recibidos.services.uom_policy import SAT_UOMS


def enforce_sat_uom_policy(is_install: bool = False) -> dict:
	sat_verificadas = 0
	sat_corregidas = 0
	deshabilitadas = 0
	ya_deshabilitadas = 0

	all_uoms = frappe.get_all("UOM", fields=["name", "enabled"])

	for uom in all_uoms:
		name = uom["name"]
		enabled = bool(uom["enabled"])

		if name.startswith("_Test"):
			continue

		if name in SAT_UOMS:
			if not enabled:
				frappe.db.set_value("UOM", name, "enabled", 1, update_modified=False)
				sat_corregidas += 1
			sat_verificadas += 1
		else:
			if enabled:
				frappe.db.set_value("UOM", name, "enabled", 0, update_modified=False)
				deshabilitadas += 1
			else:
				ya_deshabilitadas += 1

	frappe.db.commit()  # nosemgrep: frappe-manual-commit

	_handle_stock_settings(is_install)

	return {
		"sat_verificadas": sat_verificadas,
		"sat_corregidas": sat_corregidas,
		"deshabilitadas": deshabilitadas,
		"ya_deshabilitadas": ya_deshabilitadas,
	}


def _handle_stock_settings(is_install: bool) -> None:
	stock_uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or ""
	if stock_uom in SAT_UOMS:
		return

	if is_install:
		h87 = frappe.db.get_value("UOM", "H87 - Pieza", ["name", "enabled"], as_dict=True)
		if h87 and h87.enabled:
			frappe.db.set_single_value("Stock Settings", "stock_uom", "H87 - Pieza")
			frappe.db.commit()  # nosemgrep: frappe-manual-commit
	else:
		frappe.log_error(
			title="[FMX] stock_uom no es SAT",
			message=f"Stock Settings.stock_uom = '{stock_uom}'. Cambiar a UOM SAT (ej. 'H87 - Pieza').",
		)


def enforce_sat_uom_policy_on_install() -> dict:
	return enforce_sat_uom_policy(is_install=True)
