import frappe

SAT_UOMS: frozenset[str] = frozenset(
	{
		"H87 - Pieza",
		"KGM - Kilogramo",
		"GRM - Gramo",
		"LTR - Litro",
		"MLT - Mililitro",
		"MTR - Metro",
		"CMT - Centímetro",
		"MMT - Milímetro",
		"MTK - Metro cuadrado",
		"MTQ - Metro cúbico",
		"HUR - Hora",
		"MIN - Minuto",
		"SEC - Segundo",
		"DAY - Día",
		"E48 - Servicio",
		"ACT - Actividad",
		"E51 - Trabajo",
		"MON - Mes",
		"ANN - Año",
		"NA - No Aplica",
		"KWH - Kilowatt hora",
	}
)


def is_sat_uom(uom: str) -> bool:
	return uom in SAT_UOMS


def validate_sat_uom(uom: str, context: str = "") -> None:
	if not is_sat_uom(uom):
		msg = f"La UOM '{uom}' no pertenece al catálogo SAT (c_ClaveUnidad)."
		if context:
			msg = f"{context}: {msg}"
		frappe.throw(msg, frappe.ValidationError)


def get_sat_uom_list() -> list[str]:
	return sorted(SAT_UOMS)
