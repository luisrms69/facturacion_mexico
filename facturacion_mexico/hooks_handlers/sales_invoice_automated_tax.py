# facturacion_mexico/hooks_handlers/sales_invoice_automated_tax.py
# AUTOMATED TAX SYSTEM - Sales Invoice
# Sistema Automatizado de Impuestos

import frappe

# ---- Utilidades internas -----------------------------------------------


def _get_customer_default_cc(customer: str) -> str | None:
	"""Cost Center por defecto del Customer (campo canónico)."""
	if not customer:
		return None
	return frappe.db.get_value("Customer", customer, "fm_customer_default_cost_center")


def _get_branch_from_cost_center(cost_center: str) -> str | None:
	"""Mapeo 1:1 Cost Center → Branch (campo canónico)."""
	if not cost_center:
		return None
	return frappe.db.get_value("Cost Center", cost_center, "fm_mapped_branch")


def _get_customer_default_price_list(customer: str) -> str | None:
	"""Price List por defecto del Customer (nativo ERPNext)."""
	if not customer:
		return None
	# En ERPNext v15 el campo suele llamarse 'default_price_list' (Selling).
	return frappe.db.get_value("Customer", customer, "default_price_list")


def _get_cc_default_price_list(cost_center: str) -> str | None:
	"""Price List por defecto del Cost Center (campo custom)."""
	if not cost_center:
		return None
	return frappe.db.get_value("Cost Center", cost_center, "fm_default_selling_price_list")


def _get_company_default_selling_price_list() -> str | None:
	"""Price List default desde Selling Settings."""
	return frappe.db.get_single_value("Selling Settings", "selling_price_list")


def _pick_price_list(customer: str | None, cost_center: str | None) -> tuple[str | None, str]:
	"""
	Regresa (price_list, source_label) con prioridad:
	1) Customer.default_price_list
	2) Cost Center.fm_default_selling_price_list
	3) Selling Settings.selling_price_list (Company default)
	"""
	# 1) Customer
	pl = _get_customer_default_price_list(customer)
	if pl:
		return pl, "Customer.default_price_list"

	# 2) Cost Center
	pl = _get_cc_default_price_list(cost_center)
	if pl:
		return pl, "Cost Center.fm_default_selling_price_list"

	# 3) Selling Settings
	pl = _get_company_default_selling_price_list()
	if pl:
		return pl, "Selling Settings.selling_price_list"

	return None, "Sin default (ninguna fuente)"


def _maybe_set_company_address_from_branch(doc, branch: str | None):
	"""
	(Opcional) Si tu Branch ya tiene un Link a Address fiscal del emisor,
	puedes setear doc.company_address aquí para ayudar a Tax Rules.
	Ajusta el nombre del campo si existe; si no, no hacemos nada.
	"""
	if not branch:
		return
	# Ejemplo si tuvieran 'fm_company_address' en Branch:
	# addr = frappe.db.get_value("Branch", branch, "fm_company_address")
	# if addr and getattr(doc, "company_address", None) != addr:
	#     doc.company_address = addr
	#     # Nota: No seteamos tax_category. Deja a Tax Rules/ERPNext hacer lo suyo.


# ---- Handlers Doc Events ------------------------------------------------


def before_validate(doc, method=None):
	"""
	1) Si el documento aún no tiene cost_center:
	   - tomar fm_customer_default_cost_center del Customer y setearlo.
	2) Con cost_center (propio o cambiado por el usuario):
	   - derivar Branch 1:1 (fm_mapped_branch) y setear fm_branch
	   - escoger Price List con prioridad (Customer -> CC -> Company)
	   - (Opcional) setear company_address desde Branch si existe
	* Sin tax_category. No programamos impuestos por producto.
	"""
	# 1) Asegurar cost_center desde Customer si está vacío
	if not getattr(doc, "cost_center", None) and getattr(doc, "customer", None):
		cc = _get_customer_default_cc(doc.customer)
		if cc:
			doc.cost_center = cc
			frappe.msgprint(
				f"Se asignó Centro de Costos por defecto del Cliente: <b>{cc}</b>.",
				alert=True,
				indicator="blue",
			)

	# 2) Con cost_center presente (nuevo o modificado), derivar Branch y Price List
	cc_now = getattr(doc, "cost_center", None)
	if cc_now:
		# 2.1) Branch 1:1 desde CC
		branch = _get_branch_from_cost_center(cc_now)
		if branch and hasattr(doc, "fm_branch"):
			doc.fm_branch = branch

		# 2.2) Price List por prioridad
		pl, source = _pick_price_list(doc.customer, cc_now)
		if pl and getattr(doc, "selling_price_list", None) != pl:
			doc.selling_price_list = pl
			frappe.msgprint(
				f"Price List seleccionado: <b>{pl}</b> (fuente: {source}).", alert=True, indicator="green"
			)

		# 2.3) (Opcional) Company Address desde Branch (si tu Branch lo maneja)
		_maybe_set_company_address_from_branch(doc, branch)


def validate(doc, method=None):
	"""
	Bloqueos finales antes de guardar:
	- cost_center es obligatorio (no se puede facturar sin CC)
	- todas las líneas deben tener fm_producto_servicio_sat via Item
	* Sin tax_category. No programamos impuestos por producto.
	"""
	# 1) cost_center obligatorio
	if not getattr(doc, "cost_center", None):
		frappe.throw("No se puede guardar la factura: <b>Centro de Costos</b> es obligatorio.")

	# 2) Validar SAT en cada línea via Item.fm_producto_servicio_sat
	for i, row in enumerate(getattr(doc, "items", []) or [], start=1):
		if not getattr(row, "item_code", None):
			frappe.throw(f"Línea {i} sin <b>Item Code</b>. No se puede guardar la factura.")

		# Verificar fm_producto_servicio_sat en Item
		sat_field = frappe.db.get_value("Item", row.item_code, "fm_producto_servicio_sat")
		if not sat_field:
			frappe.throw(
				f"Línea {i} (Item: {row.item_code}) sin <b>ClaveProdServ SAT</b> configurada en el Item. No se puede guardar la factura."
			)
