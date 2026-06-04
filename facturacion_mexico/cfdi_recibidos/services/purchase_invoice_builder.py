"""
PurchaseInvoiceBuilder — Convierte CFDI Recibido a Purchase Invoice Draft.

Flujo: CFDI Recibido → idempotencia → validar item_codes → items → taxes → PI draft

Precondición: todos los conceptos deben tener item_code confirmado en CFDI Recibido Concepto.
La clasificación (asignación de item_code) ocurre antes en el flujo de clasificación.
CFDI Concepto Mapping NO se consulta aquí — su rol es clasificar, no construir la PI.

Idempotencia:
  A: UUID existe, mismo CFDI, grand_total OK          → repara vínculo, recovered=True
  B: UUID existe, mismo CFDI, grand_total mismatch    → ValidationError
  C: UUID existe, CFDI diferente                      → ValidationError (bloqueo)
"""

import json

import frappe
from frappe import _
from frappe.utils import flt

from facturacion_mexico.cfdi_recibidos.services.tax_resolver import resolve_taxes

_DEFAULT_TOL_ABS = 1.00
_DEFAULT_TOL_PCT = 0.5


def _load_tolerances(company: str) -> "tuple[float, float]":
	"""Lee tolerancias de Configuracion CFDI Recibidos. Usa defaults si no están configuradas."""
	config_name = f"CFDI-REC-CFG-{company}"
	if not frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		return _DEFAULT_TOL_ABS, _DEFAULT_TOL_PCT
	values = frappe.db.get_value(
		"Configuracion CFDI Recibidos",
		config_name,
		["tolerancia_total_absoluta", "tolerancia_total_porcentual"],
		as_dict=True,
	)
	if not values:
		return _DEFAULT_TOL_ABS, _DEFAULT_TOL_PCT
	tol_abs = (
		flt(values.tolerancia_total_absoluta)
		if values.tolerancia_total_absoluta is not None
		else _DEFAULT_TOL_ABS
	)
	tol_pct = (
		flt(values.tolerancia_total_porcentual)
		if values.tolerancia_total_porcentual is not None
		else _DEFAULT_TOL_PCT
	)
	return tol_abs, tol_pct


def _within_tolerance(diff: float, total_xml: float, tol_abs: float, tol_pct: float) -> bool:
	"""True si diff es aceptable: cumple tolerancia absoluta O porcentual (si pct > 0)."""
	if diff <= tol_abs:
		return True
	if tol_pct > 0 and total_xml > 0:
		return diff <= total_xml * (tol_pct / 100)
	return False


def build_purchase_invoice(cfdi_recibido_name: str) -> dict:
	# El flag permite que los saves internos del builder pasen el lock de validate.
	frappe.flags.in_cfdi_builder = True
	try:
		return _build_purchase_invoice(cfdi_recibido_name)
	finally:
		frappe.flags.in_cfdi_builder = False


def _build_purchase_invoice(cfdi_recibido_name: str) -> dict:
	"""
	Crea Purchase Invoice Draft desde CFDI Recibido. Idempotente por UUID.

	Precondición: todos los conceptos deben tener item_code asignado.

	Returns:
	    {"status": "ok", "purchase_invoice": name, "recovered": bool}

	Raises:
	    frappe.ValidationError: item_code faltante, configuración faltante o incongruencia
	"""
	cfdi_doc = frappe.get_doc("CFDI Recibido", cfdi_recibido_name)

	recovery = _check_idempotency(cfdi_doc)
	if recovery is not None:
		return recovery

	_validate_all_conceptos_classified(cfdi_doc)

	pi = _build_pi_doc(cfdi_doc)
	pi.insert(ignore_permissions=True)

	_validate_grand_total(pi, cfdi_doc)

	cfdi_doc.purchase_invoice = pi.name
	cfdi_doc.status = "Convertido a PI"
	cfdi_doc.save(ignore_permissions=True)

	return {"status": "ok", "purchase_invoice": pi.name, "recovered": False}


def _validate_all_conceptos_classified(cfdi_doc):
	"""Bloquea si algún concepto no tiene item_code confirmado."""
	unclassified = [c for c in (cfdi_doc.conceptos or []) if not getattr(c, "item_code", None)]
	if unclassified:
		frappe.throw(
			_(
				"No se puede generar Purchase Invoice: {0} concepto(s) sin item_code. "
				"Clasifique todos los conceptos antes de generar la PI."
			).format(len(unclassified)),
			frappe.ValidationError,
		)


def _check_idempotency(cfdi_doc) -> "dict | None":
	existing = frappe.db.get_value(
		"Purchase Invoice",
		{"fm_cfdi_uuid": cfdi_doc.uuid},
		["name", "fm_cfdi_recibido", "grand_total"],
		as_dict=True,
	)
	if not existing:
		return None

	# Caso C: mismo UUID, CFDI diferente → bloquear
	if existing.fm_cfdi_recibido and existing.fm_cfdi_recibido != cfdi_doc.name:
		frappe.throw(
			_(
				"UUID {0} ya está asociado a la Purchase Invoice {1} "
				"de un CFDI diferente ({2}). No se puede reutilizar."
			).format(cfdi_doc.uuid, existing.name, existing.fm_cfdi_recibido),
			frappe.ValidationError,
		)

	# Mismo CFDI → Caso A (reparación) o Caso B (mismatch)
	diff = abs(flt(existing.grand_total) - flt(cfdi_doc.total))
	tol_abs, tol_pct = _load_tolerances(cfdi_doc.company)
	if _within_tolerance(diff, flt(cfdi_doc.total), tol_abs, tol_pct):
		# Caso A: reparar vínculo si es necesario
		needs_save = cfdi_doc.purchase_invoice != existing.name or cfdi_doc.status != "Convertido a PI"
		if needs_save:
			cfdi_doc.purchase_invoice = existing.name
			cfdi_doc.status = "Convertido a PI"
			cfdi_doc.save(ignore_permissions=True)
		return {"status": "ok", "purchase_invoice": existing.name, "recovered": True}

	# Caso B: grand_total difiere más de la tolerancia → error
	frappe.throw(
		_(
			"Purchase Invoice {0} ya existe para UUID {1} pero su grand_total ({2}) "
			"difiere del XML ({3}) en {4} MXN, mayor a la tolerancia configurada."
		).format(
			existing.name,
			cfdi_doc.uuid,
			flt(existing.grand_total, 2),
			flt(cfdi_doc.total, 2),
			round(diff, 4),
		),
		frappe.ValidationError,
	)


def _build_pi_doc(cfdi_doc):
	pi = frappe.new_doc("Purchase Invoice")
	pi.supplier = cfdi_doc.supplier
	pi.company = cfdi_doc.company
	pi.posting_date = cfdi_doc.issue_date
	pi.due_date = cfdi_doc.issue_date
	pi.bill_date = cfdi_doc.issue_date
	pi.bill_no = _fmt_bill_no(cfdi_doc)
	pi.currency = cfdi_doc.currency or "MXN"
	pi.conversion_rate = flt(cfdi_doc.exchange_rate) or 1.0
	pi.fm_cfdi_uuid = cfdi_doc.uuid
	pi.fm_cfdi_recibido = cfdi_doc.name
	pi.update_stock = 0
	pi.is_paid = 0
	if cfdi_doc.cost_center:
		pi.cost_center = cfdi_doc.cost_center
	if cfdi_doc.project:
		pi.project = cfdi_doc.project

	for concepto in cfdi_doc.conceptos:
		_append_item(pi, concepto, cfdi_doc)

	impuestos = cfdi_doc.impuestos_json
	if isinstance(impuestos, str):
		impuestos = json.loads(impuestos)

	tax_rows = resolve_taxes(impuestos or {}, cfdi_doc.company)
	for row in tax_rows:
		_append_tax(pi, row)

	return pi


def _get_familia_sat(company: str, department: str) -> str | None:
	"""Retorna el código de 3 dígitos de familia SAT para el department (ej: '603')."""
	if not department:
		return None
	config_name = f"CFDI-REC-CFG-{company}"
	if not frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		return None
	rows = frappe.get_all(
		"Mapeo Departamento CFDI Recibido",
		filters={"parent": config_name, "department": department},
		fields=["familia_sat"],
		limit=1,
	)
	if not rows or not rows[0].familia_sat:
		return None
	return rows[0].familia_sat.split()[0]  # "603 Gastos de administración" → "603"


def _get_sufijo_sat(item_group: str) -> str | None:
	"""Retorna el sufijo SAT de 2 dígitos configurado en el Item Group (ej: '48')."""
	if not item_group:
		return None
	suffix = frappe.db.get_value("Item Group", item_group, "fm_codigo_sufijo_sat")
	return suffix.strip() if suffix else None


def _resolve_expense_account(company: str, family: str, suffix: str, config) -> str | None:
	"""
	Resuelve expense_account según modo_resolucion_cuenta_gasto de la config.
	Retorna el name de la Account, o None con advertencia en frappe.msgprint si no se encuentra.
	Nunca asigna silenciosamente — si no hay cuenta, retorna None y registra advertencia.
	"""
	sat_code = f"{family}.{suffix.zfill(2)}"
	mode = config.get("modo_resolucion_cuenta_gasto") or "manual_asistido"

	if mode == "manual_asistido":
		return None

	if mode in {"patron", "matriz_equivalencias"}:
		if mode == "patron":
			fmt = config.get("formato_cuenta_gasto") or "{f}{s}000"
			suffix_padded = suffix.zfill(2)
			account_number = fmt.replace("{f}", family).replace("{s}", suffix_padded)
			account = frappe.db.get_value(
				"Account",
				{"company": company, "account_number": account_number, "is_group": 0, "disabled": 0},
				"name",
			)
			if account:
				return account

			use_fallback = config.get("usar_fallback_matriz")
			if not use_fallback:
				frappe.msgprint(
					f"No se encontró cuenta para SAT {sat_code} con patrón '{account_number}'. "
					f"Asigne la cuenta manualmente o configure la Matriz de Equivalencias SAT.",
					indicator="orange",
					alert=True,
				)
				return None

		# Buscar en matriz (modo matriz_equivalencias, o patron con fallback)
		config_name = f"CFDI-REC-CFG-{company}"
		rows = frappe.get_all(
			"Mapeo Equivalencias SAT",
			filters={"parent": config_name, "codigo_agrupador_sat": sat_code, "validado_por_contador": 1},
			fields=["account"],
			order_by="idx asc",
			limit=2,
		)
		if len(rows) > 1:
			frappe.throw(
				_(
					"Hay múltiples equivalencias SAT validadas para {0}. "
					"Deje solo una fila con 'Validado por contador' activo."
				).format(sat_code),
				frappe.ValidationError,
			)
		if rows and rows[0].account:
			return rows[0].account

		frappe.msgprint(
			f"No se encontró cuenta para SAT {sat_code} en la Matriz de Equivalencias SAT. "
			f"Asigne la cuenta manualmente o agregue la equivalencia.",
			indicator="orange",
			alert=True,
		)
		return None

	return None


def _append_item(pi, concepto, cfdi_doc=None):
	item = {
		"item_code": concepto.item_code,
		"description": concepto.description or concepto.sat_product_key or "",
		"qty": flt(concepto.quantity) or 1,
		"rate": flt(concepto.unit_price),
	}
	if cfdi_doc and cfdi_doc.cost_center:
		item["cost_center"] = cfdi_doc.cost_center
	if cfdi_doc and cfdi_doc.project:
		item["project"] = cfdi_doc.project

	if cfdi_doc and cfdi_doc.company and concepto.item_group:
		family = _get_familia_sat(cfdi_doc.company, cfdi_doc.department)
		suffix = _get_sufijo_sat(concepto.item_group)
		if family and suffix:
			config_name = f"CFDI-REC-CFG-{cfdi_doc.company}"
			config = (
				frappe.db.get_value(
					"Configuracion CFDI Recibidos",
					config_name,
					["modo_resolucion_cuenta_gasto", "formato_cuenta_gasto", "usar_fallback_matriz"],
					as_dict=True,
				)
				or {}
			)
			expense_account = _resolve_expense_account(cfdi_doc.company, family, suffix, config)
			if expense_account:
				item["expense_account"] = expense_account

	pi.append("items", item)


def _append_tax(pi, row: dict):
	tax_amount = flt(row["tax_amount"])
	if tax_amount < 0:
		add_deduct = "Deduct"
		tax_amount = -tax_amount
	else:
		add_deduct = "Add"

	pi.append(
		"taxes",
		{
			"charge_type": row["charge_type"],
			"dont_recompute_tax": row["dont_recompute_tax"],
			"account_head": row["account_head"],
			"tax_amount": tax_amount,
			"add_deduct_tax": add_deduct,
			"description": row["description"],
		},
	)


def _validate_grand_total(pi, cfdi_doc):
	diff = abs(flt(pi.grand_total) - flt(cfdi_doc.total))
	tol_abs, tol_pct = _load_tolerances(cfdi_doc.company)
	if not _within_tolerance(diff, flt(cfdi_doc.total), tol_abs, tol_pct):
		frappe.throw(
			_(
				"grand_total calculado ({0}) difiere del XML ({1}) en {2} MXN, "
				"mayor a la tolerancia configurada. Verificar impuestos y conceptos."
			).format(
				flt(pi.grand_total, 2),
				flt(cfdi_doc.total, 2),
				round(diff, 4),
			),
			frappe.ValidationError,
		)


def _fmt_bill_no(cfdi_doc) -> str:
	if cfdi_doc.serie and cfdi_doc.folio:
		return f"{cfdi_doc.serie}-{cfdi_doc.folio}"
	if cfdi_doc.folio:
		return cfdi_doc.folio
	return (cfdi_doc.uuid or "")[:13]
