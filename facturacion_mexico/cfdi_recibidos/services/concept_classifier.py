"""
ConceptClassifier — clasifica conceptos de un CFDI Recibido via CFDI Concepto Mapping.

Matching MVP (3 niveles, sin regex ni priority):
  1. company + supplier_rfc + sat_product_key  (exacto)
  2. supplier_rfc + sat_product_key vacío       (fallback por proveedor)
  3. sat_product_key + supplier vacío           (fallback por clave SAT)

El resultado NO se almacena en CFDI Recibido Concepto.
El estado del padre se calcula via status_manager.compute_stage().
"""

import frappe


def classify_concepts(cfdi_recibido_name: str) -> dict:
	"""
	Aplica reglas de CFDI Concepto Mapping sobre todos los conceptos del CFDI.

	Retorna: {status, total, matched, unmatched, message}
	"""
	from facturacion_mexico.cfdi_recibidos.services.status_manager import compute_stage

	doc = frappe.get_doc("CFDI Recibido", cfdi_recibido_name)

	if not doc.conceptos:
		stage = compute_stage(doc)
		doc.db_set("status", stage)
		return _result("ok", 0, 0, 0, "Sin conceptos — marcado como Clasificado")

	supplier_rfc = doc.supplier_rfc or ""
	company = doc.company or ""

	matched = 0
	unmatched_keys = []

	for concepto in doc.conceptos:
		sat_key = concepto.sat_product_key or ""
		rule = _find_rule(company, supplier_rfc, sat_key)
		if rule and _rule_is_complete(rule):
			matched += 1
		else:
			unmatched_keys.append(sat_key or "(sin clave SAT)")

	total = len(doc.conceptos)
	unmatched = total - matched

	stage = compute_stage(doc)
	doc.db_set("status", stage)

	if unmatched == 0:
		return _result("ok", total, matched, 0, "Todos los conceptos clasificados")

	return _result(
		"falta_clasif",
		total,
		matched,
		unmatched,
		f"Sin clasificación completa para: {', '.join(set(unmatched_keys))}",
	)


def _rule_is_complete(rule: dict) -> bool:
	"""Verifica que la regla tenga un target válido según su tipo."""
	if rule.get("target_type") == "Item":
		return bool(rule.get("target_item"))
	if rule.get("target_type") == "ExpenseAccount":
		return bool(rule.get("target_account"))
	return False


def _find_rule(company: str, supplier_rfc: str, sat_product_key: str) -> dict | None:
	"""
	Busca la primera regla activa aplicable en 3 niveles de especificidad.
	Retorna el registro de CFDI Concepto Mapping o None.
	"""
	# Reglas globales (company="") aplican a cualquier empresa — siempre se incluyen en la búsqueda
	company_filter = ["in", [company, "", None]]

	filters_levels = [
		# Nivel 1: exacto — company + supplier_rfc + sat_product_key
		{
			"is_active": 1,
			"company": company_filter,
			"supplier_rfc": supplier_rfc,
			"sat_product_key": sat_product_key,
		},
		# Nivel 2: fallback por proveedor — supplier_rfc, cualquier clave SAT
		{
			"is_active": 1,
			"company": company_filter,
			"supplier_rfc": supplier_rfc,
			"sat_product_key": ["in", ["", None]],
		},
		# Nivel 3: fallback por clave SAT — cualquier proveedor
		{
			"is_active": 1,
			"company": company_filter,
			"supplier_rfc": ["in", ["", None]],
			"sat_product_key": sat_product_key,
		},
	]

	fields = ["name", "target_type", "target_item", "target_account", "target_cost_center"]

	for filters in filters_levels:
		result = frappe.db.get_value("CFDI Concepto Mapping", filters, fields, as_dict=True)
		if result:
			return result

	return None


def get_rule_for_concept(company: str, supplier_rfc: str, sat_product_key: str) -> dict | None:
	"""Expone la búsqueda de regla para uso externo (API, tests)."""
	return _find_rule(company, supplier_rfc, sat_product_key)


def _result(status: str, total: int, matched: int, unmatched: int, message: str) -> dict:
	return {
		"status": status,
		"total": total,
		"matched": matched,
		"unmatched": unmatched,
		"message": message,
	}
