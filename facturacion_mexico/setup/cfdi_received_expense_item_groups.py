"""
Setup de Item Groups de gasto para facturacion_mexico.

ensure_cfdi_received_expense_item_groups()
    Crea el árbol de Item Groups de gasto (paraguas + 13 categorías + 105 subcategorías)
    basado en el Código Agrupador SAT. Idempotente.
    Retorna: {creados, existentes, conflictos}

    Conflicto = grupo con ese nombre existe pero bajo un padre diferente al esperado.
    En ese caso se omite y se registra en conflictos[].
"""

import frappe

_UMBRELLA = "Gastos"

# Mapa Item Group → código SAT de subcuenta (2 dígitos, base 10).
# Derivado del Código Agrupador SAT 2024 — familia 603 como referencia;
# los mismos subcódigos aplican a 601, 602 y 604 para las mismas categorías.
# Items sin entrada aquí no tienen resolución automática disponible.
_SAT_SUBCUENTA = {
	"Sueldos y salarios": "01",
	"Compensaciones": "02",
	"Tiempos extras": "03",
	"Premios de asistencia": "04",
	"Premios de puntualidad": "05",
	"Vacaciones": "06",
	"Prima vacacional": "07",
	"Prima dominical": "08",
	"Días festivos": "09",
	"Gratificaciones": "10",
	"Primas de antigüedad": "11",
	"Aguinaldo": "12",
	"Indemnizaciones": "13",
	"Destajo": "14",
	"Despensa": "15",
	"Transporte": "16",
	"Servicio médico": "17",
	"Ayuda en gastos funerarios": "18",
	"Fondo de ahorro": "19",
	"Cuotas sindicales": "20",
	"PTU": "21",
	"Estímulo al personal": "22",
	"Previsión social": "23",
	"Aportaciones para el plan de jubilación": "24",
	"Otras prestaciones al personal": "25",
	"Cuotas al IMSS": "26",
	"Aportaciones al Infonavit": "27",
	"Aportaciones al SAR": "28",
	"Impuesto estatal sobre nóminas": "29",
	"Otras aportaciones": "30",
	"Asimilados a salarios": "31",
	"Servicios administrativos": "32",
	"Servicios administrativos partes relacionadas": "33",
	"Honorarios a personas físicas residentes nacionales": "34",
	"Honorarios a personas físicas residentes nacionales partes relacionadas": "35",
	"Honorarios a personas físicas residentes del extranjero": "36",
	"Honorarios a personas físicas residentes del extranjero partes relacionadas": "37",
	"Honorarios a personas morales residentes nacionales": "38",
	"Honorarios a personas morales residentes nacionales partes relacionadas": "39",
	"Honorarios a personas morales residentes del extranjero": "40",
	"Honorarios a personas morales residentes del extranjero partes relacionadas": "41",
	"Honorarios aduanales personas físicas": "42",
	"Honorarios aduanales personas morales": "43",
	"Honorarios al consejo de administración": "44",
	"Arrendamiento a personas físicas residentes nacionales": "45",
	"Arrendamiento a personas morales residentes nacionales": "46",
	"Arrendamiento a residentes del extranjero": "47",
	"Combustibles y lubricantes": "48",
	"Viáticos y gastos de viaje": "49",
	"Teléfono, internet": "50",
	"Agua": "51",
	"Energía eléctrica": "52",
	"Vigilancia y seguridad": "53",
	"Limpieza": "54",
	"Papelería y artículos de oficina": "55",
	"Mantenimiento y conservación": "56",
	"Seguros y fianzas": "57",
	"Otros impuestos y derechos": "58",
	"Recargos fiscales": "59",
	"Cuotas y suscripciones": "60",
	"Propaganda y publicidad": "61",
	"Capacitación al personal": "62",
	"Donativos y ayudas": "63",
	"Asistencia técnica": "64",
	"Regalías sujetas a otros porcentajes": "65",
	"Regalías sujetas al 5%": "66",
	"Regalías sujetas al 10%": "67",
	"Regalías sujetas al 15%": "68",
	"Regalías sujetas al 25%": "69",
	"Regalías sujetas al 30%": "70",
	"Regalías sin retención": "71",
	"Fletes y acarreos": "72",
	"Gastos de importación": "73",
	"Patentes y marcas": "74",
	"Uniformes": "75",
	"Prediales": "76",
	"Fletes del extranjero": "79",
	"Gastos no deducibles (sin requisitos fiscales)": "81",
	"Otros gastos generales": "82",
	# Los siguientes no tienen código en la familia 601-604 del SAT.
	# En modo Automático CoA SAT fallarán (comportamiento correcto — usar modo Manual).
	# "Gastos generales de urbanización"  → CoA: 603-77 "Gastos de adm. de urbanización" (nombre diferente)
	# "Gastos generales de construcción"  → CoA: 603-78 "Gastos de adm. de construcción" (nombre diferente)
	# "Comisiones sobre ventas"           → no confirmado en familia 601-604
	# "Comisiones por tarjetas de crédito"→ no confirmado en familia 601-604
	# "Recolección de bienes del sector agropecuario y/o ganadero" → no en 601-604
	# Gastos financieros (pérdida cambiaria, intereses, comisiones bancarias) → familia 702
	# Productos financieros (utilidad cambiaria, intereses a favor)           → familia 702/701
}

_GROUPS = [
	{
		"name": "Nómina y prestaciones",
		"children": [
			"Sueldos y salarios",
			"Compensaciones",
			"Tiempos extras",
			"Premios de asistencia",
			"Premios de puntualidad",
			"Vacaciones",
			"Prima vacacional",
			"Prima dominical",
			"Días festivos",
			"Gratificaciones",
			"Primas de antigüedad",
			"Aguinaldo",
			"Indemnizaciones",
			"Destajo",
			"Despensa",
			"Transporte",
			"Servicio médico",
			"Ayuda en gastos funerarios",
			"Fondo de ahorro",
			"Cuotas sindicales",
			"PTU",
			"Estímulo al personal",
			"Previsión social",
			"Aportaciones para el plan de jubilación",
			"Otras prestaciones al personal",
			"Cuotas al IMSS",
			"Aportaciones al Infonavit",
			"Aportaciones al SAR",
			"Impuesto estatal sobre nóminas",
			"Otras aportaciones",
			"Asimilados a salarios",
		],
	},
	{
		"name": "Servicios administrativos y profesionales",
		"children": [
			"Servicios administrativos",
			"Servicios administrativos partes relacionadas",
			"Honorarios a personas físicas residentes nacionales",
			"Honorarios a personas físicas residentes nacionales partes relacionadas",
			"Honorarios a personas físicas residentes del extranjero",
			"Honorarios a personas físicas residentes del extranjero partes relacionadas",
			"Honorarios a personas morales residentes nacionales",
			"Honorarios a personas morales residentes nacionales partes relacionadas",
			"Honorarios a personas morales residentes del extranjero",
			"Honorarios a personas morales residentes del extranjero partes relacionadas",
			"Honorarios aduanales personas físicas",
			"Honorarios aduanales personas morales",
			"Honorarios al consejo de administración",
			"Asistencia técnica",
		],
	},
	{
		"name": "Arrendamientos",
		"children": [
			"Arrendamiento a personas físicas residentes nacionales",
			"Arrendamiento a personas morales residentes nacionales",
			"Arrendamiento a residentes del extranjero",
		],
	},
	{
		"name": "Servicios básicos y operación",
		"children": [
			"Teléfono, internet",
			"Agua",
			"Energía eléctrica",
			"Vigilancia y seguridad",
			"Limpieza",
			"Mantenimiento y conservación",
			"Papelería y artículos de oficina",
			"Cuotas y suscripciones",
			"Capacitación al personal",
			"Uniformes",
		],
	},
	{
		"name": "Movilidad, viáticos y combustibles",
		"children": [
			"Combustibles y lubricantes",
			"Viáticos y gastos de viaje",
		],
	},
	{
		"name": "Comercialización y ventas",
		"children": [
			"Propaganda y publicidad",
			"Comisiones sobre ventas",
			"Comisiones por tarjetas de crédito",
		],
	},
	{
		"name": "Seguros, impuestos y cumplimiento",
		"children": [
			"Seguros y fianzas",
			"Otros impuestos y derechos",
			"Recargos fiscales",
			"Prediales",
		],
	},
	{
		"name": "Donativos y no deducibles",
		"children": [
			"Donativos y ayudas",
			"Gastos no deducibles (sin requisitos fiscales)",
		],
	},
	{
		"name": "Regalías y propiedad intelectual",
		"children": [
			"Regalías sujetas a otros porcentajes",
			"Regalías sujetas al 5%",
			"Regalías sujetas al 10%",
			"Regalías sujetas al 15%",
			"Regalías sujetas al 25%",
			"Regalías sujetas al 30%",
			"Regalías sin retención",
			"Patentes y marcas",
		],
	},
	{
		"name": "Logística, fletes e importación",
		"children": [
			"Fletes y acarreos",
			"Gastos de importación",
			"Fletes del extranjero",
			"Recolección de bienes del sector agropecuario y/o ganadero",
		],
	},
	{
		"name": "Construcción, urbanización y otros",
		"children": [
			"Gastos generales de urbanización",
			"Gastos generales de construcción",
			"Otros gastos generales",
		],
	},
	{
		"name": "Gastos financieros",
		"children": [
			"Pérdida cambiaria",
			"Pérdida cambiaria nacional parte relacionada",
			"Pérdida cambiaria extranjero parte relacionada",
			"Intereses a cargo bancario nacional",
			"Intereses a cargo bancario extranjero",
			"Intereses a cargo de personas físicas nacional",
			"Intereses a cargo de personas físicas extranjero",
			"Intereses a cargo de personas morales nacional",
			"Intereses a cargo de personas morales extranjero",
			"Comisiones bancarias",
			"Otros gastos financieros",
		],
	},
	{
		"name": "Productos financieros",
		"parent": None,  # Se crea bajo la raíz (All Item Groups), no bajo Gastos
		"children": [
			"Utilidad cambiaria",
			"Utilidad cambiaria nacional parte relacionada",
			"Utilidad cambiaria extranjero parte relacionada",
			"Intereses a favor bancarios nacional",
			"Intereses a favor bancarios extranjero",
			"Intereses a favor de personas físicas nacional",
			"Intereses a favor de personas físicas extranjero",
			"Intereses a favor de personas morales nacional",
			"Intereses a favor de personas morales extranjero",
			"Otros productos financieros",
		],
	},
]


# Correcciones de padre para grupos que pueden haber sido creados bajo el padre incorrecto
# en versiones anteriores del setup. Se aplican antes de crear grupos nuevos.
# Formato: {"name": "Nombre del grupo", "correct_parent": "Padre correcto"}
_PARENT_FIXES = [
	{"name": "Productos financieros", "correct_parent": None},  # None = raíz
]


def ensure_cfdi_received_expense_item_groups() -> dict:
	"""Crea el árbol de Item Groups de gasto si no existen. Idempotente."""
	root = _get_root_item_group()

	# Aplicar correcciones de padre antes de crear grupos
	for fix in _PARENT_FIXES:
		correct_parent = fix["correct_parent"] if fix["correct_parent"] is not None else root
		existing_parent = frappe.db.get_value("Item Group", fix["name"], "parent_item_group")
		if existing_parent is not None and existing_parent != correct_parent:
			frappe.db.set_value("Item Group", fix["name"], "parent_item_group", correct_parent)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit
	creados = 0
	existentes = 0
	conflictos = []

	# Paraguas
	created, conflict = _ensure_group(_UMBRELLA, root, is_group=True)
	if conflict:
		conflictos.append(conflict)
		return {"creados": 0, "existentes": 0, "conflictos": conflictos}
	if created:
		creados += 1
	else:
		existentes += 1

	for group in _GROUPS:
		parent_name = group["name"]
		# Soporte para parent override: None = raíz, omitido = _UMBRELLA
		if "parent" in group:
			group_parent = group["parent"] if group["parent"] is not None else root
		else:
			group_parent = _UMBRELLA
		created, conflict = _ensure_group(parent_name, group_parent, is_group=True)
		if conflict:
			conflictos.append(conflict)
			continue
		if created:
			creados += 1
		else:
			existentes += 1

		for child_name in group["children"]:
			created, conflict = _ensure_group(child_name, parent_name, is_group=False)
			if conflict:
				conflictos.append(conflict)
				continue
			if created:
				creados += 1
			else:
				existentes += 1

	frappe.db.commit()  # nosemgrep: frappe-manual-commit
	return {"creados": creados, "existentes": existentes, "conflictos": conflictos}


def _ensure_group(name: str, parent: str, is_group: bool) -> "tuple[bool, dict | None]":
	"""
	Crea el Item Group si no existe y asigna fm_codigo_sufijo_sat desde _SAT_SUBCUENTA.
	Retorna (created: bool, conflict: dict | None).
	Conflicto = existe con padre diferente al esperado.
	"""
	existing_parent = frappe.db.get_value("Item Group", name, "parent_item_group")
	if existing_parent is not None:
		if existing_parent != parent:
			return False, {
				"name": name,
				"expected_parent": parent,
				"actual_parent": existing_parent,
			}
		# Actualizar fm_codigo_sufijo_sat si está vacío y tenemos el código
		sat_code = _SAT_SUBCUENTA.get(name)
		if sat_code:
			current = frappe.db.get_value("Item Group", name, "fm_codigo_sufijo_sat")
			if not current:
				frappe.db.set_value("Item Group", name, "fm_codigo_sufijo_sat", sat_code)
		return False, None

	doc = frappe.new_doc("Item Group")
	doc.item_group_name = name
	doc.parent_item_group = parent
	doc.is_group = 1 if is_group else 0
	sat_code = _SAT_SUBCUENTA.get(name)
	if sat_code:
		doc.fm_codigo_sufijo_sat = sat_code
	doc.insert(ignore_permissions=True)
	return True, None


def _get_root_item_group() -> str:
	root = frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name")
	if not root:
		result = frappe.db.sql(
			"SELECT name FROM `tabItem Group` WHERE (parent_item_group IS NULL OR parent_item_group = '') AND is_group = 1 LIMIT 1"
		)
		root = result[0][0] if result else None
	if not root:
		frappe.throw(frappe._("No se encontró el Item Group raíz. Instale ERPNext primero."))
	return root
