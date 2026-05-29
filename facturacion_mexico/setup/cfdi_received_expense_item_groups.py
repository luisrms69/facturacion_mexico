"""
Setup de Item Groups de gasto para facturacion_mexico.

ensure_cfdi_received_expense_item_groups()
    Crea el árbol de Item Groups de gasto (paraguas + 11 categorías + 84 subcategorías)
    basado en el Código Agrupador SAT. Idempotente.
    Retorna: {creados, existentes, conflictos}

    Conflicto = grupo con ese nombre existe pero bajo un padre diferente al esperado.
    En ese caso se omite y se registra en conflictos[].
"""

import frappe

_UMBRELLA = "Gastos"

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
]


def ensure_cfdi_received_expense_item_groups() -> dict:
	"""Crea el árbol de Item Groups de gasto si no existen. Idempotente."""
	root = _get_root_item_group()
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
		created, conflict = _ensure_group(parent_name, _UMBRELLA, is_group=True)
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
	Crea el Item Group si no existe.
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
		return False, None

	doc = frappe.new_doc("Item Group")
	doc.item_group_name = name
	doc.parent_item_group = parent
	doc.is_group = 1 if is_group else 0
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
