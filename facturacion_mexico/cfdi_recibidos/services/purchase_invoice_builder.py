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

_TOLERANCE = 0.02


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

	for concepto in cfdi_doc.conceptos:
		_append_item(pi, concepto)

	impuestos = cfdi_doc.impuestos_json
	if isinstance(impuestos, str):
		impuestos = json.loads(impuestos)

	tax_rows = resolve_taxes(impuestos or {}, cfdi_doc.company)
	for row in tax_rows:
		_append_tax(pi, row)

	return pi


def _append_item(pi, concepto):
	pi.append(
		"items",
		{
			"item_code": concepto.item_code,
			"description": concepto.description or concepto.sat_product_key or "",
			"qty": flt(concepto.quantity) or 1,
			"rate": flt(concepto.unit_price),
		},
	)


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
