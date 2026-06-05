"""
PurchaseInvoiceBuilder — Convierte CFDI Recibido a Purchase Invoice Draft.

Flujo: CFDI Recibido → idempotencia → validar item_codes → resolver cuentas → PI draft

Resolución de cuenta de gasto:
  Automático CoA SAT: family (dept) + subcuenta SAT (item_group) + formato CoA
    → busca en Account exactamente 1 cuenta activa e imputable con ese prefijo.
  Manual: lee concepto.expense_account (el usuario lo seleccionó previamente).

En ambos modos, el resultado se escribe en concepto.expense_account antes de crear la PI.
Si cualquier concepto no puede resolverse → ValidationError, no se crea PI.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt

from facturacion_mexico.cfdi_recibidos.services.tax_resolver import resolve_taxes

_DEFAULT_TOL_ABS = 1.00
_DEFAULT_TOL_PCT = 0.5


def _load_tolerances(company: str) -> "tuple[float, float]":
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
	if diff <= tol_abs:
		return True
	if tol_pct > 0 and total_xml > 0:
		return diff <= total_xml * (tol_pct / 100)
	return False


def build_purchase_invoice(cfdi_recibido_name: str) -> dict:
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
	    frappe.ValidationError: item_code faltante, cuenta no resuelta o incongruencia
	"""
	cfdi_doc = frappe.get_doc("CFDI Recibido", cfdi_recibido_name)

	recovery = _check_idempotency(cfdi_doc)
	if recovery is not None:
		return recovery

	_validate_all_conceptos_classified(cfdi_doc)

	# Resolver y escribir expense_account en cada concepto (en memoria)
	config = _load_resolution_config(cfdi_doc.company)
	_resolve_all_expense_accounts(cfdi_doc, config)

	pi = _build_pi_doc(cfdi_doc)
	pi.insert(ignore_permissions=True)

	_validate_grand_total(pi, cfdi_doc)

	cfdi_doc.purchase_invoice = pi.name
	cfdi_doc.status = "Convertido a PI"
	cfdi_doc.save(ignore_permissions=True)

	return {"status": "ok", "purchase_invoice": pi.name, "recovered": False}


def _load_resolution_config(company: str) -> dict:
	config_name = f"CFDI-REC-CFG-{company}"
	if not frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		return {}
	return (
		frappe.db.get_value(
			"Configuracion CFDI Recibidos",
			config_name,
			["modo_resolucion_contable", "formato_coa"],
			as_dict=True,
		)
		or {}
	)


def _resolve_all_expense_accounts(cfdi_doc, config: dict):
	"""
	Resuelve expense_account para cada concepto. Escribe en concepto.expense_account (en memoria).
	Si cualquier concepto falla → ValidationError. No se crea ninguna PI.
	"""
	mode = config.get("modo_resolucion_contable") or "Manual"
	formato = config.get("formato_coa") or ""

	family = None
	if mode == "Automatico CoA SAT":
		family = _get_familia_sat(cfdi_doc.company, cfdi_doc.department)
		if not family:
			frappe.throw(
				_(
					"Departamento '{0}' no tiene familia SAT configurada. "
					"Configure el mapeo en Configuracion CFDI Recibidos antes de convertir."
				).format(cfdi_doc.department or "—"),
				frappe.ValidationError,
			)
		if not formato:
			frappe.throw(
				_("Formato CoA no configurado en Configuracion CFDI Recibidos."),
				frappe.ValidationError,
			)

	for concepto in cfdi_doc.conceptos or []:
		concepto.expense_account = _resolve_one(concepto, cfdi_doc.company, mode, family, formato)


def _resolve_one(concepto, company: str, mode: str, family: str | None, formato: str) -> str:
	"""
	Resuelve la cuenta de gasto para un concepto. Retorna el nombre de la Account.
	Lanza ValidationError si no puede resolver.
	"""
	label = concepto.item_code or concepto.description or "?"

	if mode == "Manual":
		account = getattr(concepto, "expense_account", None) or ""
		if not account:
			frappe.throw(
				_(
					"Concepto '{0}': Cuenta de Gasto vacía. "
					"En modo Manual seleccione la cuenta en cada concepto antes de convertir."
				).format(label),
				frappe.ValidationError,
			)
		_validate_account(account, company, label)
		return account

	# Automatico CoA SAT
	subcuenta = _get_sufijo_sat(concepto.item_group)
	if not subcuenta:
		frappe.throw(
			_(
				"Concepto '{0}': el Grupo de Gasto '{1}' no tiene código SAT configurado "
				"(fm_codigo_sufijo_sat vacío). No se puede resolver automáticamente."
			).format(label, concepto.item_group or "—"),
			frappe.ValidationError,
		)

	prefix = _build_prefix(formato, family, subcuenta)

	accounts = frappe.get_all(
		"Account",
		filters={
			"company": company,
			"account_number": ["like", f"{prefix}%"],
			"is_group": 0,
			"disabled": 0,
		},
		pluck="name",
	)

	if len(accounts) == 1:
		return accounts[0]

	if len(accounts) == 0:
		frappe.throw(
			_(
				"No se pudo resolver una cuenta contable válida para el concepto '{0}'. "
				"No existe ninguna cuenta activa e imputable con account_number que empiece por '{1}'. "
				"Verifique el CoA o use modo Manual."
			).format(label, prefix),
			frappe.ValidationError,
		)

	frappe.throw(
		_(
			"Hay {0} cuentas con account_number que empieza por '{1}': {2}. "
			"Debe existir exactamente una cuenta imputable bajo ese prefijo. "
			"Corrija el CoA o use modo Manual."
		).format(len(accounts), prefix, ", ".join(accounts[:3])),
		frappe.ValidationError,
	)


def _build_prefix(formato_coa: str, family: str, subcuenta: str) -> str:
	"""Construye el prefijo para buscar account_number en CoA."""
	sub = subcuenta.zfill(2)
	if formato_coa == "###-##-###":
		return f"{family}-{sub}-"
	if formato_coa == "###.##.###":
		return f"{family}.{sub}."
	if formato_coa == "########":
		return f"{family}{sub}"
	frappe.throw(
		_("Formato CoA '{0}' no reconocido. Formatos válidos: ########, ###-##-###, ###.##.###").format(
			formato_coa
		),
		frappe.ValidationError,
	)


def _validate_account(account_name: str, company: str, label: str):
	"""Valida que la cuenta exista, sea de la empresa, activa y no grupo."""
	data = frappe.db.get_value("Account", account_name, ["company", "is_group", "disabled"], as_dict=True)
	if not data:
		frappe.throw(
			_("Concepto '{0}': la cuenta '{1}' no existe.").format(label, account_name),
			frappe.ValidationError,
		)
	if data.company != company:
		frappe.throw(
			_("Concepto '{0}': la cuenta '{1}' pertenece a '{2}', no a '{3}'.").format(
				label, account_name, data.company, company
			),
			frappe.ValidationError,
		)
	if data.is_group:
		frappe.throw(
			_("Concepto '{0}': la cuenta '{1}' es un grupo contable, no es imputable.").format(
				label, account_name
			),
			frappe.ValidationError,
		)
	if data.disabled:
		frappe.throw(
			_("Concepto '{0}': la cuenta '{1}' está deshabilitada.").format(label, account_name),
			frappe.ValidationError,
		)


def _get_familia_sat(company: str, department: str) -> str | None:
	"""Retorna el código de 3 dígitos de familia SAT para el department."""
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
	parts = rows[0].familia_sat.split()
	return parts[0] if parts else None


def _get_sufijo_sat(item_group: str) -> str | None:
	"""Retorna el código SAT de 2 dígitos del Item Group."""
	if not item_group:
		return None
	suffix = frappe.db.get_value("Item Group", item_group, "fm_codigo_sufijo_sat")
	return suffix.strip() if suffix else None


def _validate_all_conceptos_classified(cfdi_doc):
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

	if existing.fm_cfdi_recibido and existing.fm_cfdi_recibido != cfdi_doc.name:
		frappe.throw(
			_(
				"UUID {0} ya está asociado a la Purchase Invoice {1} "
				"de un CFDI diferente ({2}). No se puede reutilizar."
			).format(cfdi_doc.uuid, existing.name, existing.fm_cfdi_recibido),
			frappe.ValidationError,
		)

	diff = abs(flt(existing.grand_total) - flt(cfdi_doc.total))
	tol_abs, tol_pct = _load_tolerances(cfdi_doc.company)
	if _within_tolerance(diff, flt(cfdi_doc.total), tol_abs, tol_pct):
		needs_save = cfdi_doc.purchase_invoice != existing.name or cfdi_doc.status != "Convertido a PI"
		if needs_save:
			cfdi_doc.purchase_invoice = existing.name
			cfdi_doc.status = "Convertido a PI"
			cfdi_doc.save(ignore_permissions=True)
		return {"status": "ok", "purchase_invoice": existing.name, "recovered": True}

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


def _append_item(pi, concepto, cfdi_doc=None):
	item = {
		"item_code": concepto.item_code,
		"description": concepto.description or concepto.sat_product_key or "",
		"qty": flt(concepto.quantity) or 1,
		"rate": flt(concepto.unit_price),
		"expense_account": concepto.expense_account,
	}
	if cfdi_doc and cfdi_doc.cost_center:
		item["cost_center"] = cfdi_doc.cost_center
	if cfdi_doc and cfdi_doc.project:
		item["project"] = cfdi_doc.project
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
