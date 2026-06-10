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

# Códigos SAT puros derivados de SAT_UOMS (primer token antes del " - ").
# Usar para validar el código extraído, no el string completo de la UOM.
SAT_UOM_CODES: frozenset[str] = frozenset(uom.split(" - ")[0] for uom in SAT_UOMS)


def try_normalize_uom_to_sat_code(uom: str) -> str | None:
	"""Extrae el código SAT de una UOM sin lanzar excepción.

	Acepta múltiples formatos de entrada:
	  - Canónico:  "H87 - Pieza"  → "H87"
	  - Legacy:    "H87 Pieza"    → "H87"  (facturacion_mx usaba este formato;
	                                         ERPNext no permite cambiar la UOM de
	                                         Items con transacciones, por lo que la
	                                         compatibilidad se resuelve aquí)
	  - Código puro: "H87"        → "H87"

	Retorna el código SAT si es válido, o None si no se puede extraer código válido.
	No modifica datos en base de datos.
	"""
	if not uom:
		return None
	candidate = uom.split(" - ")[0].strip() if " - " in uom else uom.split(" ")[0].strip()
	return candidate if candidate in SAT_UOM_CODES else None


def normalize_uom_to_sat_code(uom: str) -> str:
	"""Extrae y valida el código SAT de una UOM. Lanza ValidationError si no es válida.

	Ver try_normalize_uom_to_sat_code para detalle de formatos aceptados.
	"""
	code = try_normalize_uom_to_sat_code(uom)
	if code is None:
		frappe.throw(
			f"UOM '{uom}' no contiene un código SAT válido (c_ClaveUnidad). "
			f"Use formato 'CODIGO - Descripción' (ej. 'H87 - Pieza') o código puro (ej. 'H87').",
			frappe.ValidationError,
		)
	return code


def is_sat_uom(uom: str) -> bool:
	"""Verifica si una UOM está en el catálogo canónico SAT_UOMS (match exacto).

	Para validar UOMs en formato legacy, usar try_normalize_uom_to_sat_code en su lugar.
	"""
	return uom in SAT_UOMS


def validate_sat_uom(uom: str, context: str = "") -> None:
	if not is_sat_uom(uom):
		msg = f"La UOM '{uom}' no pertenece al catálogo SAT (c_ClaveUnidad)."
		if context:
			msg = f"{context}: {msg}"
		frappe.throw(msg, frappe.ValidationError)


def get_sat_uom_list() -> list[str]:
	return sorted(SAT_UOMS)
