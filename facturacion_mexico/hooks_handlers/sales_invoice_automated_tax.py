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


def _get_border_zone_status(branch: str | None) -> bool | None:
	"""Verificar si la sucursal está en zona fronteriza."""
	if not branch:
		return None
	return frappe.db.get_value("Branch", branch, "fm_is_border_zone")


def _find_stct_by_pattern(company: str, is_border: bool) -> str | None:
	"""
	Buscar STCT por patrón de título según convención E0.5.
	Busca por título conteniendo:
	- IVA 8% - Zona Fronteriza - {abbr} (para zona fronteriza)
	- IVA 16% - México - {abbr} (para zona no fronteriza)
	"""
	if not company:
		return None

	# Obtener company abbr
	company_abbr = frappe.db.get_value("Company", company, "abbr")
	if not company_abbr:
		return None

	if is_border:
		# Buscar STCT 8% para zona fronteriza
		patterns = [
			f"IVA 8% - Zona Fronteriza - {company_abbr}",
			f"IVA 8%{company_abbr}",  # Fallback más flexible
		]
	else:
		# Buscar STCT 16% para zona no fronteriza
		patterns = [
			f"IVA 16% - México - {company_abbr}",
			f"IVA 16%{company_abbr}",  # Fallback más flexible
		]

	# Buscar por cada patrón
	for pattern in patterns:
		stct = frappe.db.get_value(
			"Sales Taxes and Charges Template",
			{"title": ["like", f"%{pattern}%"], "company": company, "disabled": 0},
			"name",
		)
		if stct:
			return stct

	return None


def _set_stct_by_branch(doc, branch: str | None):
	"""
	PASO 3: Seleccionar STCT automáticamente según si Branch es zona fronteriza.
	- fm_is_border_zone = 1 → STCT 8%
	- fm_is_border_zone = 0 → STCT 16%
	"""
	if not branch or not getattr(doc, "company", None):
		return

	# Verificar si es zona fronteriza
	is_border = _get_border_zone_status(branch)
	if is_border is None:
		return

	# Buscar STCT apropiado
	stct = _find_stct_by_pattern(doc.company, bool(is_border))

	if stct:
		# Asignar STCT encontrado
		if getattr(doc, "taxes_and_charges", None) != stct:
			doc.taxes_and_charges = stct
			zone_type = "Zona Fronteriza (8%)" if is_border else "México (16%)"
			frappe.msgprint(
				f"Impuestos configurados automáticamente: <b>{zone_type}</b>", alert=True, indicator="green"
			)
	else:
		# STCT no encontrado - bloquear con mensaje accionable
		zone_type = "8% (Zona Fronteriza)" if is_border else "16% (México)"
		company_abbr = frappe.db.get_value("Company", doc.company, "abbr")
		errormsg = f"No se encontró STCT de IVA {zone_type} para {doc.company}. "
		errormsg += f"Genere el template 'IVA {'8% - Zona Fronteriza' if is_border else '16% - México'} - {company_abbr}' desde el wizard fiscal."
		frappe.throw(errormsg)


def _get_item_master_itt(item_code: str, **kwargs) -> str | None:
	"""
	Obtener ITT sugerido desde el Item usando función ERPNext nativa.
	Usa get_item_tax_template() que maneja Tax Category, rangos, etc.
	"""
	if not item_code:
		return None

	try:
		from erpnext.stock.get_item_details import get_item_tax_template

		args = {
			"item_code": item_code,
			"company": kwargs.get("company"),
			"tax_category": kwargs.get("tax_category"),
			"base_net_rate": kwargs.get("base_net_rate", 0),
		}

		return get_item_tax_template(args)
	except Exception:
		# Fallback silencioso si no funciona
		return None


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
				"Centro de Costos asignado automáticamente.",
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
			frappe.msgprint("Lista de precios asignada automáticamente.", alert=True, indicator="green")

		# 2.3) (Opcional) Company Address desde Branch (si tu Branch lo maneja)
		_maybe_set_company_address_from_branch(doc, branch)

		# 2.4) PASO 3: Seleccionar STCT automáticamente según Branch (fronteriza/no fronteriza)
		_set_stct_by_branch(doc, branch)

	# 3) Para cada línea: asegurar ITT desde Item (si existe en el maestro) para excepciones 0%/Exento
	for row in getattr(doc, "items", []):
		if not getattr(row, "item_tax_template", None):
			itt = _get_item_master_itt(
				row.item_code,
				company=doc.company,
				tax_category=getattr(doc, "tax_category", None),
				base_net_rate=getattr(row, "rate", 0),
			)
			if itt:
				row.item_tax_template = itt


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
