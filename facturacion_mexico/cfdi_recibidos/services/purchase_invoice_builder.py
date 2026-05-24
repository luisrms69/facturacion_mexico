"""
PurchaseInvoiceBuilder — Convierte CFDI Recibido a Purchase Invoice Draft.

Flujo: CFDI Recibido → idempotencia → items (via mapeo) → taxes (via TaxResolver) → PI draft

Idempotencia:
  A: UUID existe, mismo CFDI, grand_total OK          → repara vínculo, recovered=True
  B: UUID existe, mismo CFDI, grand_total mismatch    → ValidationError
  C: UUID existe, CFDI diferente                      → ValidationError (bloqueo)
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, today

from facturacion_mexico.cfdi_recibidos.services.tax_resolver import resolve_taxes

_TOLERANCE = 0.02
_DEFAULT_UOM = "Nos"


def build_purchase_invoice(cfdi_recibido_name: str) -> dict:
	"""
	Crea Purchase Invoice Draft desde CFDI Recibido. Idempotente por UUID.

	Returns:
	    {"status": "ok", "purchase_invoice": name, "recovered": bool}

	Raises:
	    frappe.ValidationError: configuración faltante o incongruencia de datos
	"""
	cfdi_doc = frappe.get_doc("CFDI Recibido", cfdi_recibido_name)

	recovery = _check_idempotency(cfdi_doc)
	if recovery is not None:
		return recovery

	concepto_mappings = _get_concepto_mappings(cfdi_doc)
	pi = _build_pi_doc(cfdi_doc, concepto_mappings)
	pi.insert(ignore_permissions=True)

	_validate_grand_total(pi, cfdi_doc)

	cfdi_doc.purchase_invoice = pi.name
	cfdi_doc.status = "Convertido a PI"
	cfdi_doc.save(ignore_permissions=True)

	return {"status": "ok", "purchase_invoice": pi.name, "recovered": False}


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
	if diff <= _TOLERANCE:
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
			"difiere del XML ({3}) en {4} MXN, mayor a la tolerancia ({5})."
		).format(
			existing.name,
			cfdi_doc.uuid,
			flt(existing.grand_total, 2),
			flt(cfdi_doc.total, 2),
			round(diff, 4),
			_TOLERANCE,
		),
		frappe.ValidationError,
	)


def _build_pi_doc(cfdi_doc, concepto_mappings: list):
	pi = frappe.new_doc("Purchase Invoice")
	pi.supplier = cfdi_doc.supplier
	pi.company = cfdi_doc.company
	pi.posting_date = today()
	pi.bill_date = cfdi_doc.issue_date
	pi.bill_no = _fmt_bill_no(cfdi_doc)
	pi.currency = cfdi_doc.currency or "MXN"
	pi.conversion_rate = flt(cfdi_doc.exchange_rate) or 1.0
	pi.fm_cfdi_uuid = cfdi_doc.uuid
	pi.fm_cfdi_recibido = cfdi_doc.name
	pi.update_stock = 0
	pi.is_paid = 0

	for concepto in cfdi_doc.conceptos:
		mapping = _get_mapping_for_concepto(
			cfdi_doc.company, cfdi_doc.supplier_rfc or "", concepto.sat_product_key or ""
		)
		_append_item(pi, concepto, mapping)

	impuestos = cfdi_doc.impuestos_json
	if isinstance(impuestos, str):
		impuestos = json.loads(impuestos)

	tax_rows = resolve_taxes(impuestos or {}, cfdi_doc.company)
	for row in tax_rows:
		_append_tax(pi, row)

	return pi


def _get_concepto_mappings(cfdi_doc) -> list:
	"""Retorna lista deduplicada de mappings completos para todos los conceptos."""
	seen = set()
	mappings = []
	for concepto in cfdi_doc.conceptos:
		mapping = _get_mapping_for_concepto(
			cfdi_doc.company, cfdi_doc.supplier_rfc or "", concepto.sat_product_key or ""
		)
		if mapping and mapping.get("name") not in seen:
			seen.add(mapping["name"])
			mappings.append(mapping)
	return mappings


def _get_mapping_for_concepto(company: str, supplier_rfc: str, sat_product_key: str) -> "dict | None":
	company_filter = ["in", [company, "", None]]
	fields = [
		"name",
		"target_type",
		"target_item",
		"target_account",
		"target_cost_center",
	]
	for filters in [
		{
			"is_active": 1,
			"company": company_filter,
			"supplier_rfc": supplier_rfc,
			"sat_product_key": sat_product_key,
		},
		{
			"is_active": 1,
			"company": company_filter,
			"supplier_rfc": supplier_rfc,
			"sat_product_key": ["in", ["", None]],
		},
		{
			"is_active": 1,
			"company": company_filter,
			"supplier_rfc": ["in", ["", None]],
			"sat_product_key": sat_product_key,
		},
	]:
		result = frappe.db.get_value("CFDI Concepto Mapping", filters, fields, as_dict=True)
		if result:
			return result
	return None


def _append_item(pi, concepto, mapping: "dict | None"):
	if not mapping:
		frappe.throw(
			_("Concepto con clave SAT '{0}' no tiene regla de clasificación configurada").format(
				concepto.sat_product_key or "(sin clave)"
			),
			frappe.ValidationError,
		)

	row = {
		"description": concepto.description or concepto.sat_product_key or "",
		"qty": flt(concepto.quantity) or 1,
		"rate": flt(concepto.unit_price),
		"uom": _DEFAULT_UOM,
	}

	if mapping.get("target_type") == "Item":
		row["item_code"] = mapping["target_item"]
	else:
		row["item_name"] = concepto.description or concepto.sat_product_key or "Servicio"
		row["expense_account"] = mapping["target_account"]

	if mapping.get("target_cost_center"):
		row["cost_center"] = mapping["target_cost_center"]

	pi.append("items", row)


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
	if diff > _TOLERANCE:
		frappe.throw(
			_(
				"grand_total calculado ({0}) difiere del XML ({1}) en {2} MXN, "
				"mayor a la tolerancia ({3}). Verificar impuestos y conceptos."
			).format(
				flt(pi.grand_total, 2),
				flt(cfdi_doc.total, 2),
				round(diff, 4),
				_TOLERANCE,
			),
			frappe.ValidationError,
		)


def _fmt_bill_no(cfdi_doc) -> str:
	if cfdi_doc.serie and cfdi_doc.folio:
		return f"{cfdi_doc.serie}-{cfdi_doc.folio}"
	if cfdi_doc.folio:
		return cfdi_doc.folio
	return (cfdi_doc.uuid or "")[:13]
