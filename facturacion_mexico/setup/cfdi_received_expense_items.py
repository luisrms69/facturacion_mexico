"""
Setup de Items genéricos de gasto para CFDI Recibidos.

ensure_cfdi_received_expense_items()
    Crea los 84 Items genéricos de gasto (uno por Item Group hoja bajo "Gastos").
    Idempotente: no modifica Items existentes.
    fm_producto_servicio_sat: se asigna solo si el código existe en SAT Producto Servicio.

    Ítem GASTO-OPR-003 (Energía eléctrica) usa UOM provisional MON - Mes.
    KWH - Kilowatt hora pendiente validación contra c_ClaveUnidad SAT (DC-09).
    Actualizar uom y fixture uom.json cuando se valide.

    Retorna: {creados, existentes, sin_clave_prod_serv}
"""

import frappe

# fmt: off
_ITEMS = [
    # ── Nómina y prestaciones (31) ─────────────────────────────────────────
    {"item_code": "GASTO-NOM-001", "item_name": "Sueldos y salarios",                         "item_group": "Sueldos y salarios",                         "uom": "MON - Mes",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-002", "item_name": "Compensaciones",                             "item_group": "Compensaciones",                             "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-003", "item_name": "Tiempos extras",                             "item_group": "Tiempos extras",                             "uom": "HUR - Hora",      "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-004", "item_name": "Premios de asistencia",                      "item_group": "Premios de asistencia",                      "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-005", "item_name": "Premios de puntualidad",                     "item_group": "Premios de puntualidad",                     "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-006", "item_name": "Vacaciones",                                 "item_group": "Vacaciones",                                 "uom": "DAY - Día",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-007", "item_name": "Prima vacacional",                           "item_group": "Prima vacacional",                           "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-008", "item_name": "Prima dominical",                            "item_group": "Prima dominical",                            "uom": "DAY - Día",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-009", "item_name": "Días festivos",                              "item_group": "Días festivos",                              "uom": "DAY - Día",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-010", "item_name": "Gratificaciones",                            "item_group": "Gratificaciones",                            "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-011", "item_name": "Primas de antigüedad",                       "item_group": "Primas de antigüedad",                       "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-012", "item_name": "Aguinaldo",                                  "item_group": "Aguinaldo",                                  "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-013", "item_name": "Indemnizaciones",                            "item_group": "Indemnizaciones",                            "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-014", "item_name": "Destajo",                                    "item_group": "Destajo",                                    "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-015", "item_name": "Despensa",                                   "item_group": "Despensa",                                   "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-016", "item_name": "Transporte",                                 "item_group": "Transporte",                                 "uom": "MON - Mes",       "clave_prod_serv": "78101600"},
    {"item_code": "GASTO-NOM-017", "item_name": "Servicio médico",                            "item_group": "Servicio médico",                            "uom": "MON - Mes",       "clave_prod_serv": "85100000"},
    {"item_code": "GASTO-NOM-018", "item_name": "Ayuda en gastos funerarios",                 "item_group": "Ayuda en gastos funerarios",                 "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-019", "item_name": "Fondo de ahorro",                            "item_group": "Fondo de ahorro",                            "uom": "MON - Mes",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-020", "item_name": "Cuotas sindicales",                          "item_group": "Cuotas sindicales",                          "uom": "MON - Mes",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-021", "item_name": "PTU",                                        "item_group": "PTU",                                        "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-022", "item_name": "Estímulo al personal",                       "item_group": "Estímulo al personal",                       "uom": "H87 - Pieza",     "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-023", "item_name": "Previsión social",                           "item_group": "Previsión social",                           "uom": "MON - Mes",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-024", "item_name": "Aportaciones para el plan de jubilación",    "item_group": "Aportaciones para el plan de jubilación",    "uom": "MON - Mes",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-025", "item_name": "Otras prestaciones al personal",             "item_group": "Otras prestaciones al personal",             "uom": "MON - Mes",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-026", "item_name": "Cuotas al IMSS",                             "item_group": "Cuotas al IMSS",                             "uom": "MON - Mes",       "clave_prod_serv": "84121500"},
    {"item_code": "GASTO-NOM-027", "item_name": "Aportaciones al Infonavit",                  "item_group": "Aportaciones al Infonavit",                  "uom": "MON - Mes",       "clave_prod_serv": "84121500"},
    {"item_code": "GASTO-NOM-028", "item_name": "Aportaciones al SAR",                        "item_group": "Aportaciones al SAR",                        "uom": "MON - Mes",       "clave_prod_serv": "84121500"},
    {"item_code": "GASTO-NOM-029", "item_name": "Impuesto estatal sobre nóminas",             "item_group": "Impuesto estatal sobre nóminas",             "uom": "MON - Mes",       "clave_prod_serv": "93121800"},
    {"item_code": "GASTO-NOM-030", "item_name": "Otras aportaciones",                         "item_group": "Otras aportaciones",                         "uom": "MON - Mes",       "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-NOM-031", "item_name": "Asimilados a salarios",                      "item_group": "Asimilados a salarios",                      "uom": "MON - Mes",       "clave_prod_serv": "80141600"},
    # ── Servicios administrativos y profesionales (14) ────────────────────
    {"item_code": "GASTO-SRV-001", "item_name": "Servicios administrativos",                                                  "item_group": "Servicios administrativos",                                                  "uom": "MON - Mes",       "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-002", "item_name": "Servicios administrativos partes relacionadas",                              "item_group": "Servicios administrativos partes relacionadas",                              "uom": "MON - Mes",       "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-003", "item_name": "Honorarios a personas físicas residentes nacionales",                        "item_group": "Honorarios a personas físicas residentes nacionales",                        "uom": "HUR - Hora",      "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-004", "item_name": "Honorarios a personas físicas residentes nacionales partes relacionadas",    "item_group": "Honorarios a personas físicas residentes nacionales partes relacionadas",    "uom": "HUR - Hora",      "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-005", "item_name": "Honorarios a personas físicas residentes del extranjero",                    "item_group": "Honorarios a personas físicas residentes del extranjero",                    "uom": "HUR - Hora",      "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-006", "item_name": "Honorarios a personas físicas residentes del extranjero partes relacionadas","item_group": "Honorarios a personas físicas residentes del extranjero partes relacionadas","uom": "HUR - Hora",      "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-007", "item_name": "Honorarios a personas morales residentes nacionales",                        "item_group": "Honorarios a personas morales residentes nacionales",                        "uom": "E48 - Servicio",  "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-008", "item_name": "Honorarios a personas morales residentes nacionales partes relacionadas",    "item_group": "Honorarios a personas morales residentes nacionales partes relacionadas",    "uom": "E48 - Servicio",  "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-009", "item_name": "Honorarios a personas morales residentes del extranjero",                    "item_group": "Honorarios a personas morales residentes del extranjero",                    "uom": "E48 - Servicio",  "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-010", "item_name": "Honorarios a personas morales residentes del extranjero partes relacionadas","item_group": "Honorarios a personas morales residentes del extranjero partes relacionadas","uom": "E48 - Servicio",  "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-011", "item_name": "Honorarios aduanales personas físicas",                                      "item_group": "Honorarios aduanales personas físicas",                                      "uom": "E48 - Servicio",  "clave_prod_serv": "78181500"},
    {"item_code": "GASTO-SRV-012", "item_name": "Honorarios aduanales personas morales",                                      "item_group": "Honorarios aduanales personas morales",                                      "uom": "E48 - Servicio",  "clave_prod_serv": "78181500"},
    {"item_code": "GASTO-SRV-013", "item_name": "Honorarios al consejo de administración",                                    "item_group": "Honorarios al consejo de administración",                                    "uom": "MON - Mes",       "clave_prod_serv": "80111500"},
    {"item_code": "GASTO-SRV-014", "item_name": "Asistencia técnica",                                                         "item_group": "Asistencia técnica",                                                         "uom": "HUR - Hora",      "clave_prod_serv": "80111501"},
    # ── Arrendamientos (3) ────────────────────────────────────────────────
    {"item_code": "GASTO-ARR-001", "item_name": "Arrendamiento a personas físicas residentes nacionales", "item_group": "Arrendamiento a personas físicas residentes nacionales", "uom": "MON - Mes", "clave_prod_serv": "80131501"},
    {"item_code": "GASTO-ARR-002", "item_name": "Arrendamiento a personas morales residentes nacionales", "item_group": "Arrendamiento a personas morales residentes nacionales", "uom": "MON - Mes", "clave_prod_serv": "80131501"},
    {"item_code": "GASTO-ARR-003", "item_name": "Arrendamiento a residentes del extranjero",              "item_group": "Arrendamiento a residentes del extranjero",              "uom": "MON - Mes", "clave_prod_serv": "80131501"},
    # ── Servicios básicos y operación (10) ────────────────────────────────
    {"item_code": "GASTO-OPR-001", "item_name": "Teléfono, internet",           "item_group": "Teléfono, internet",           "uom": "MON - Mes",        "clave_prod_serv": "83111500"},
    {"item_code": "GASTO-OPR-002", "item_name": "Agua",                         "item_group": "Agua",                         "uom": "MTQ - Metro cúbico","clave_prod_serv": "83111700"},
    # UOM provisional MON - Mes. KWH pendiente validación c_ClaveUnidad SAT (DC-09, bloqueante antes de PI).
    {"item_code": "GASTO-OPR-003", "item_name": "Energía eléctrica",            "item_group": "Energía eléctrica",            "uom": "MON - Mes",        "clave_prod_serv": "81101500"},
    {"item_code": "GASTO-OPR-004", "item_name": "Vigilancia y seguridad",       "item_group": "Vigilancia y seguridad",       "uom": "MON - Mes",        "clave_prod_serv": "92101500"},
    {"item_code": "GASTO-OPR-005", "item_name": "Limpieza",                     "item_group": "Limpieza",                     "uom": "MON - Mes",        "clave_prod_serv": "76111501"},
    {"item_code": "GASTO-OPR-006", "item_name": "Mantenimiento y conservación", "item_group": "Mantenimiento y conservación", "uom": "MON - Mes",        "clave_prod_serv": "72101500"},
    {"item_code": "GASTO-OPR-007", "item_name": "Papelería y artículos de oficina","item_group": "Papelería y artículos de oficina","uom": "H87 - Pieza", "clave_prod_serv": "44121700"},
    {"item_code": "GASTO-OPR-008", "item_name": "Cuotas y suscripciones",       "item_group": "Cuotas y suscripciones",       "uom": "MON - Mes",        "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-OPR-009", "item_name": "Capacitación al personal",     "item_group": "Capacitación al personal",     "uom": "ACT - Actividad",  "clave_prod_serv": "86101500"},
    {"item_code": "GASTO-OPR-010", "item_name": "Uniformes",                    "item_group": "Uniformes",                    "uom": "H87 - Pieza",      "clave_prod_serv": "53101600"},
    # ── Movilidad, viáticos y combustibles (2) ────────────────────────────
    {"item_code": "GASTO-MOV-001", "item_name": "Combustibles y lubricantes", "item_group": "Combustibles y lubricantes", "uom": "LTR - Litro",  "clave_prod_serv": "15101500"},
    {"item_code": "GASTO-MOV-002", "item_name": "Viáticos y gastos de viaje", "item_group": "Viáticos y gastos de viaje", "uom": "DAY - Día",    "clave_prod_serv": "90111501"},
    # ── Comercialización y ventas (3) ─────────────────────────────────────
    {"item_code": "GASTO-VNT-001", "item_name": "Propaganda y publicidad",        "item_group": "Propaganda y publicidad",        "uom": "MON - Mes", "clave_prod_serv": "82101500"},
    {"item_code": "GASTO-VNT-002", "item_name": "Comisiones sobre ventas",        "item_group": "Comisiones sobre ventas",        "uom": "MON - Mes", "clave_prod_serv": "80141600"},
    {"item_code": "GASTO-VNT-003", "item_name": "Comisiones por tarjetas de crédito","item_group": "Comisiones por tarjetas de crédito","uom": "MON - Mes", "clave_prod_serv": "84111500"},
    # ── Seguros, impuestos y cumplimiento (4) ─────────────────────────────
    {"item_code": "GASTO-SEG-001", "item_name": "Seguros y fianzas",            "item_group": "Seguros y fianzas",            "uom": "ANN - Año",   "clave_prod_serv": "84121500"},
    {"item_code": "GASTO-SEG-002", "item_name": "Otros impuestos y derechos",   "item_group": "Otros impuestos y derechos",   "uom": "H87 - Pieza", "clave_prod_serv": "93121800"},
    {"item_code": "GASTO-SEG-003", "item_name": "Recargos fiscales",            "item_group": "Recargos fiscales",            "uom": "H87 - Pieza", "clave_prod_serv": "93121800"},
    {"item_code": "GASTO-SEG-004", "item_name": "Prediales",                    "item_group": "Prediales",                    "uom": "ANN - Año",   "clave_prod_serv": "93121800"},
    # ── Donativos y no deducibles (2) ─────────────────────────────────────
    {"item_code": "GASTO-DON-001", "item_name": "Donativos y ayudas",                        "item_group": "Donativos y ayudas",                        "uom": "H87 - Pieza", "clave_prod_serv": "93141500"},
    {"item_code": "GASTO-DON-002", "item_name": "Gastos no deducibles (sin requisitos fiscales)","item_group": "Gastos no deducibles (sin requisitos fiscales)","uom": "H87 - Pieza", "clave_prod_serv": "80141600"},
    # ── Regalías y propiedad intelectual (8) ──────────────────────────────
    {"item_code": "GASTO-REG-001", "item_name": "Regalías sujetas a otros porcentajes", "item_group": "Regalías sujetas a otros porcentajes", "uom": "MON - Mes", "clave_prod_serv": "80141800"},
    {"item_code": "GASTO-REG-002", "item_name": "Regalías sujetas al 5%",               "item_group": "Regalías sujetas al 5%",               "uom": "MON - Mes", "clave_prod_serv": "80141800"},
    {"item_code": "GASTO-REG-003", "item_name": "Regalías sujetas al 10%",              "item_group": "Regalías sujetas al 10%",              "uom": "MON - Mes", "clave_prod_serv": "80141800"},
    {"item_code": "GASTO-REG-004", "item_name": "Regalías sujetas al 15%",              "item_group": "Regalías sujetas al 15%",              "uom": "MON - Mes", "clave_prod_serv": "80141800"},
    {"item_code": "GASTO-REG-005", "item_name": "Regalías sujetas al 25%",              "item_group": "Regalías sujetas al 25%",              "uom": "MON - Mes", "clave_prod_serv": "80141800"},
    {"item_code": "GASTO-REG-006", "item_name": "Regalías sujetas al 30%",              "item_group": "Regalías sujetas al 30%",              "uom": "MON - Mes", "clave_prod_serv": "80141800"},
    {"item_code": "GASTO-REG-007", "item_name": "Regalías sin retención",               "item_group": "Regalías sin retención",               "uom": "MON - Mes", "clave_prod_serv": "80141800"},
    {"item_code": "GASTO-REG-008", "item_name": "Patentes y marcas",                    "item_group": "Patentes y marcas",                    "uom": "ANN - Año", "clave_prod_serv": "80141800"},
    # ── Logística, fletes e importación (4) ───────────────────────────────
    {"item_code": "GASTO-LOG-001", "item_name": "Fletes y acarreos",                                           "item_group": "Fletes y acarreos",                                           "uom": "E48 - Servicio", "clave_prod_serv": "78101800"},
    {"item_code": "GASTO-LOG-002", "item_name": "Gastos de importación",                                       "item_group": "Gastos de importación",                                       "uom": "E48 - Servicio", "clave_prod_serv": "78181500"},
    {"item_code": "GASTO-LOG-003", "item_name": "Fletes del extranjero",                                       "item_group": "Fletes del extranjero",                                       "uom": "E48 - Servicio", "clave_prod_serv": "78101800"},
    {"item_code": "GASTO-LOG-004", "item_name": "Recolección de bienes del sector agropecuario y/o ganadero", "item_group": "Recolección de bienes del sector agropecuario y/o ganadero", "uom": "E48 - Servicio", "clave_prod_serv": "78102200"},
    # ── Construcción, urbanización y otros (3) ────────────────────────────
    {"item_code": "GASTO-OBR-001", "item_name": "Gastos generales de urbanización", "item_group": "Gastos generales de urbanización", "uom": "E48 - Servicio", "clave_prod_serv": "72131500"},
    {"item_code": "GASTO-OBR-002", "item_name": "Gastos generales de construcción", "item_group": "Gastos generales de construcción", "uom": "E48 - Servicio", "clave_prod_serv": "72131500"},
    {"item_code": "GASTO-OBR-003", "item_name": "Otros gastos generales",           "item_group": "Otros gastos generales",           "uom": "E48 - Servicio", "clave_prod_serv": "80141600"},
]
# fmt: on

assert len(_ITEMS) == 84, f"_ITEMS debe tener 84 entradas, tiene {len(_ITEMS)}"


def ensure_cfdi_received_expense_items() -> dict:
	"""Crea los 84 Items genéricos de gasto si no existen. Idempotente."""
	creados = 0
	existentes = 0
	sin_clave_prod_serv = 0

	for item_def in _ITEMS:
		item_code = item_def["item_code"]

		if frappe.db.exists("Item", item_code):
			existentes += 1
			continue

		if not frappe.db.exists("Item Group", item_def["item_group"]):
			frappe.log_error(
				f"Item Group '{item_def['item_group']}' no encontrado para {item_code}. "
				"Ejecutar ensure_cfdi_received_expense_item_groups() primero.",
				"[FMX][Setup] Item Group faltante para Item genérico de gasto",
			)
			continue

		if not frappe.db.exists("UOM", item_def["uom"]):
			frappe.log_error(
				f"UOM '{item_def['uom']}' no encontrada para {item_code}. "
				"Verificar fixture uom.json y ejecutar bench migrate.",
				"[FMX][Setup] UOM faltante para Item genérico de gasto",
			)
			continue

		item = frappe.new_doc("Item")
		item.item_code = item_code
		item.item_name = item_def["item_name"]
		item.item_group = item_def["item_group"]
		item.stock_uom = item_def["uom"]
		item.is_stock_item = 0
		item.is_purchase_item = 1
		item.is_sales_item = 0

		clave = item_def.get("clave_prod_serv")
		if clave and frappe.db.exists("SAT Producto Servicio", clave):
			item.fm_producto_servicio_sat = clave
		else:
			sin_clave_prod_serv += 1

		item.insert(ignore_permissions=True)
		creados += 1

	frappe.db.commit()  # nosemgrep: frappe-manual-commit
	return {"creados": creados, "existentes": existentes, "sin_clave_prod_serv": sin_clave_prod_serv}
