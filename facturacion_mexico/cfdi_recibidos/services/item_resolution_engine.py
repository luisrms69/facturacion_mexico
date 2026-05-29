"""
Motor de resolución de Items para conceptos CFDI Recibidos.

8 niveles de búsqueda, en orden de confianza:
  1. Regla exacta (empresa + RFC + clave SAT)
  2. Regla RFC + clave SAT (sin empresa)
  3. Regla RFC + palabras clave
  4. Regla clave SAT + palabras clave
  5. Item.item_code == no_identificacion del proveedor
  6. Búsqueda por palabras en descripción
  7-8. Opciones creación / genérico — nunca auto-asignadas

Niveles 1-5 con match_confidence="Alta" son candidatos para auto-asignación.
Niveles 6+ siempre requieren acción explícita del usuario.
"""

import frappe

from facturacion_mexico.cfdi_recibidos.services.concept_text_normalizer import (
	keywords_match,
	normalize,
)


def get_resolution_options(concepto_data: dict, cfdi_data: dict) -> dict:
	"""
	Analiza un concepto y retorna opciones de resolución de Item.

	concepto_data: sat_product_key, no_identificacion, description, item_group
	cfdi_data:     company, supplier, supplier_rfc

	Retorna:
	    primary      — mejor match (dict | None)
	    alternatives — otras opciones automáticas (list[dict])
	    generic      — fallback GASTO-* (dict | None)
	    can_create   — siempre True

	Cada opción incluye: item_code, item_name, item_group,
	                     item_resolution, match_reason, match_confidence
	"""
	company = cfdi_data.get("company", "")
	supplier_rfc = cfdi_data.get("supplier_rfc", "")
	sat_product_key = concepto_data.get("sat_product_key", "")
	no_identificacion = concepto_data.get("no_identificacion", "")
	description = concepto_data.get("description", "")
	item_group = concepto_data.get("item_group", "")

	seen: set[str] = set()
	primary = None
	alternatives = []

	for opt in _resolve_by_rules(
		company, supplier_rfc, sat_product_key, description, no_identificacion, seen
	):
		seen.add(opt["item_code"])
		if primary is None:
			primary = opt
		else:
			alternatives.append(opt)

	opt = _resolve_by_no_identificacion(no_identificacion, seen)
	if opt:
		seen.add(opt["item_code"])
		if primary is None:
			primary = opt
		else:
			alternatives.append(opt)

	for opt in _resolve_by_text(description, seen)[:3]:
		seen.add(opt["item_code"])
		if primary is None:
			primary = opt
		else:
			alternatives.append(opt)

	generic = _resolve_generic(item_group, seen)

	return {
		"primary": primary,
		"alternatives": alternatives,
		"generic": generic,
		"can_create": True,
	}


def _resolve_by_rules(company, supplier_rfc, sat_product_key, description, no_identificacion, seen):
	rules = frappe.get_all(
		"Regla Item CFDI Recibido",
		filters={"is_active": 1},
		fields=[
			"name",
			"company",
			"supplier_rfc",
			"sat_product_key",
			"keywords",
			"target_item",
			"match_reason",
			"priority",
		],
		order_by="priority asc",
	)

	results = []
	for rule in rules:
		target = rule.get("target_item") if isinstance(rule, dict) else rule.target_item
		if not target or target in seen:
			continue
		level = _match_level(rule, company, supplier_rfc, sat_product_key, description, no_identificacion)
		if level is None:
			continue
		item_data = frappe.db.get_value("Item", target, ["item_name", "item_group"], as_dict=True)
		if not item_data:
			continue
		match_reason = rule.get("match_reason") if isinstance(rule, dict) else rule.match_reason
		results.append(
			{
				"item_code": target,
				"item_name": item_data.item_name,
				"item_group": item_data.item_group or "",
				"item_resolution": "Mapeado",
				"match_reason": match_reason or _level_label(level),
				"match_confidence": "Alta" if level <= 2 else "Media",
			}
		)

	return results


def _match_level(rule, company, supplier_rfc, sat_product_key, description, no_identificacion=""):
	"""
	Evalúa en qué nivel aplica una regla sobre los datos del concepto.
	Retorna 1-4 si aplica, None si no.

	Keywords se evalúan contra descripción O no_identificacion (para reglas auto-aprendidas).
	"""
	_get = (lambda k: rule.get(k)) if isinstance(rule, dict) else (lambda k: getattr(rule, k, None))
	r_co = _get("company") or ""
	r_rfc = _get("supplier_rfc") or ""
	r_sat = _get("sat_product_key") or ""
	r_kw = _get("keywords") or ""

	def _kw_match(kw):
		return keywords_match(description, kw) or (
			bool(no_identificacion) and keywords_match(no_identificacion, kw)
		)

	# Nivel 1: empresa + RFC + clave SAT (keywords opcionales)
	if r_co and r_rfc and r_sat:
		if r_co == company and r_rfc == supplier_rfc and r_sat == sat_product_key:
			if not r_kw or _kw_match(r_kw):
				return 1

	# Nivel 2: RFC + clave SAT sin empresa (keywords opcionales)
	if not r_co and r_rfc and r_sat:
		if r_rfc == supplier_rfc and r_sat == sat_product_key:
			if not r_kw or _kw_match(r_kw):
				return 2

	# Nivel 3: RFC + keywords (sin clave SAT) — incluye reglas auto-aprendidas por no_identificacion
	if r_rfc and r_kw and not r_sat:
		if r_rfc == supplier_rfc and _kw_match(r_kw):
			return 3

	# Nivel 4: clave SAT + keywords (sin RFC)
	if r_sat and r_kw and not r_rfc:
		if r_sat == sat_product_key and _kw_match(r_kw):
			return 4

	return None


def _level_label(level: int) -> str:
	return {
		1: "Regla exacta (empresa + RFC + clave SAT)",
		2: "Regla RFC + clave SAT",
		3: "Regla RFC + palabras clave",
		4: "Regla clave SAT + palabras clave",
	}.get(level, f"Regla nivel {level}")


def _resolve_by_no_identificacion(no_identificacion: str, seen: set) -> "dict | None":
	if not no_identificacion or no_identificacion in seen:
		return None
	item = frappe.db.get_value(
		"Item",
		no_identificacion,
		["item_name", "item_group", "is_purchase_item", "is_stock_item"],
		as_dict=True,
	)
	if not item or not item.is_purchase_item or item.is_stock_item:
		return None
	return {
		"item_code": no_identificacion,
		"item_name": item.item_name,
		"item_group": item.item_group or "",
		"item_resolution": "Código proveedor",
		"match_reason": f"Código de proveedor: {no_identificacion}",
		"match_confidence": "Alta",
	}


def _resolve_by_text(description: str, seen: set) -> list[dict]:
	if not description:
		return []

	from facturacion_mexico.cfdi_recibidos.services.uom_policy import SAT_UOMS

	expense_groups = _get_expense_item_groups()
	filters: dict = {
		"is_purchase_item": 1,
		"is_stock_item": 0,
		"is_sales_item": 0,
		"stock_uom": ["in", list(SAT_UOMS)],
		"item_code": ["not like", "GASTO-%"],
	}
	if expense_groups:
		filters["item_group"] = ["in", expense_groups]

	candidates = frappe.get_all(
		"Item",
		filters=filters,
		fields=["name", "item_name", "item_group"],
		limit=100,
	)

	norm_desc = normalize(description)
	scored = []
	for c in candidates:
		if c.name in seen:
			continue
		score = _word_overlap(norm_desc, normalize(c.item_name or ""))
		if score > 0:
			scored.append((score, c))

	scored.sort(key=lambda x: x[0], reverse=True)

	return [
		{
			"item_code": c.name,
			"item_name": c.item_name,
			"item_group": c.item_group or "",
			"item_resolution": "Sugerido",
			"match_reason": f"Coincidencia por descripcion ({score} palabras comunes)",
			"match_confidence": "Baja",
		}
		for score, c in scored[:5]
	]


def _resolve_generic(item_group: str, seen: set) -> "dict | None":
	if not item_group:
		return None
	rows = frappe.get_all(
		"Item",
		filters={
			"item_group": item_group,
			"item_code": ["like", "GASTO-%"],
			"is_stock_item": 0,
			"is_sales_item": 0,
		},
		fields=["name", "item_name", "item_group"],
		limit=1,
	)
	if not rows:
		return None
	c = rows[0]
	if c.name in seen:
		return None
	return {
		"item_code": c.name,
		"item_name": c.item_name,
		"item_group": c.item_group or "",
		"item_resolution": "Genérico",
		"match_reason": f"Item generico de gasto para {item_group}",
		"match_confidence": "Baja",
	}


def _word_overlap(norm_a: str, norm_b: str) -> int:
	return len(set(norm_a.split()) & set(norm_b.split()))


def _get_expense_item_groups() -> list[str]:
	root = frappe.db.get_value("Item Group", "Gastos", ["lft", "rgt"], as_dict=True)
	if not root:
		return []
	return frappe.get_all(
		"Item Group",
		filters={"lft": [">=", root.lft], "rgt": ["<=", root.rgt]},
		pluck="name",
	)
