# facturacion_mexico/hooks_handlers/sales_invoice_automated_tax.py
# AUTOMATED TAX SYSTEM - Sales Invoice
# Sistema Automatizado de Impuestos

import json

import frappe

from facturacion_mexico.utils.clasificacion_items import clasificar_items_documento

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


def _determinar_variante_stct(doc) -> str:
	"""
	Determinar variante STCT según clasificación items del documento.

	Matriz decisión:
	- tiene_ieps=False, tiene_retenciones=False → "Básico"
	- tiene_ieps=True, tiene_retenciones=False → "IEPS"
	- tiene_ieps=False, tiene_retenciones=True → "Retenciones"
	- tiene_ieps=True, tiene_retenciones=True → "Total"

	Args:
		doc: Sales Invoice document

	Returns:
		str: Una de las 4 variantes: "Básico", "IEPS", "Retenciones", "Total"
	"""
	# Clasificar items del documento
	clasificacion = clasificar_items_documento(doc)

	# Matriz decisión
	if clasificacion["tiene_ieps"] and clasificacion["tiene_retenciones"]:
		return "Total"
	elif clasificacion["tiene_ieps"]:
		return "IEPS"
	elif clasificacion["tiene_retenciones"]:
		return "Retenciones"
	else:
		return "Básico"


def _find_stct_by_variant(company: str, zona: str, variant: str) -> str | None:
	"""
	Buscar STCT por zona y variante según convención E1.

	Patrón de búsqueda:
	- "IVA Nacional - Básico - {abbr}"
	- "IVA Nacional - IEPS - {abbr}"
	- "IVA Nacional - Retenciones - {abbr}"
	- "IVA Nacional - Total - {abbr}"
	- "IVA Frontera - Básico - {abbr}"
	- "IVA Frontera - IEPS - {abbr}"
	- "IVA Frontera - Retenciones - {abbr}"
	- "IVA Frontera - Total - {abbr}"

	Args:
		company: Company name
		zona: "Nacional" o "Frontera"
		variant: "Básico", "IEPS", "Retenciones", "Total"

	Returns:
		str | None: STCT name or None if not found
	"""
	if not company:
		return None

	# Obtener company abbr
	company_abbr = frappe.db.get_value("Company", company, "abbr")
	if not company_abbr:
		return None

	# Patrón exacto según convención E1
	# name = title - abbr (garantizado por ERPNext autoname en STCT)
	title_pattern = f"IVA {zona} - {variant} - {company_abbr}"

	# Buscar por name (siempre incluye abbr, independiente de cómo se guardó title)
	stct = frappe.db.get_value(
		"Sales Taxes and Charges Template",
		{"name": title_pattern, "disabled": 0},
		"name",
	)

	return stct


def _set_stct_by_branch(doc, branch: str | None):
	"""
	PASO 3: Seleccionar STCT automáticamente según Branch y clasificación items.

	Autoselección inteligente:
	1. Determinar zona fiscal (Nacional/Frontera) desde Branch.fm_is_border_zone
	2. Clasificar items del documento (tiene_ieps, tiene_retenciones)
	3. Matriz decisión: zona x (tiene_ieps, tiene_retenciones) → 8 STCT específicos

	Ejemplo:
	- Zona Nacional + items IEPS (sin retenciones) → "IVA Nacional - IEPS - {abbr}"
	- Zona Frontera + items básicos (sin IEPS/retenciones) → "IVA Frontera - Básico - {abbr}"
	- Zona Nacional + items IEPS + retenciones → "IVA Nacional - Total - {abbr}"

	NOTA E1: Fuerza carga de taxes desde STCT incluso si ya estaba asignado,
	         para garantizar que STCT + ITT se combinen correctamente (fix issue #STCT-enabled).
	"""
	if not branch or not getattr(doc, "company", None):
		return

	# Verificar si es zona fronteriza
	is_border = _get_border_zone_status(branch)
	if is_border is None:
		return

	# Determinar zona según Branch
	zona = "Frontera" if is_border else "Nacional"

	# Determinar variante según clasificación items
	variant = _determinar_variante_stct(doc)

	# Buscar STCT específico
	stct = _find_stct_by_variant(doc.company, zona, variant)
	used_fallback = False

	# FALLBACK: Si no existe variante específica, buscar Básico de la misma zona
	if not stct and variant != "Básico":
		stct = _find_stct_by_variant(doc.company, zona, "Básico")
		if stct:
			used_fallback = True

	if stct:
		# Flag para evitar múltiples cargas en mismo request
		if getattr(doc.flags, "__stct_applied", False):
			return

		# Asignar STCT encontrado (específico o fallback)
		if getattr(doc, "taxes_and_charges", None) != stct:
			doc.taxes_and_charges = stct

		# FORZAR carga de taxes desde STCT (incluso si ya estaba asignado)
		# Esto replica comportamiento "STCT disabled → enabled" que funciona correctamente
		from erpnext.controllers.accounts_controller import get_taxes_and_charges

		# Limpiar taxes actuales y cargar desde template
		doc.set("taxes", [])
		tax_rows = get_taxes_and_charges("Sales Taxes and Charges Template", stct)
		doc.extend("taxes", tax_rows)

		# Marcar que ya aplicamos STCT en este request
		doc.flags.__stct_applied = True

		# Mensaje según si usó fallback o no
		iva_label = "Frontera" if is_border else "Nacional"
		if used_fallback:
			frappe.msgprint(
				f"⚠️ Template <b>IVA {iva_label} - {variant}</b> no disponible.<br>"
				f"Se usó <b>IVA {iva_label} - Básico</b> como alternativa.<br>"
				f"<small>Configure mapeos faltantes en Mapeo Cuenta Fiscal Mexico para obtener template completo.</small>",
				alert=True,
				indicator="orange",
			)
		else:
			frappe.msgprint(
				f"Impuestos configurados automáticamente: <b>IVA {iva_label} - {variant}</b>",
				alert=True,
				indicator="green",
			)
	else:
		# STCT no encontrado (ni específico ni Básico) - bloquear con mensaje accionable
		company_abbr = frappe.db.get_value("Company", doc.company, "abbr")
		if variant == "Básico":
			# Si ya estaba buscando Básico y no existe
			title_expected = f"IVA {zona} - Básico - {company_abbr}"
			errormsg = f"No se encontró template STCT mínimo requerido: <b>{title_expected}</b>.<br>"
		else:
			# Si buscó variante específica y tampoco existe Básico
			title_expected = f"IVA {zona} - {variant} - {company_abbr}"
			title_fallback = f"IVA {zona} - Básico - {company_abbr}"
			errormsg = f"No se encontró STCT específico <b>{title_expected}</b> ni fallback <b>{title_fallback}</b>.<br>"
		errormsg += "Genere los 8 STCT específicos desde <b>Configuracion Fiscal Mexico</b> (botón 'Generate Templates')."
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


# ---- E4: IEPS Cuota Helpers ---------------------------------------------


def _obtener_cuotas_vigentes(company: str, clave_sat: str, fecha) -> list[dict]:
	"""
	Obtener cuotas IEPS vigentes desde tabla IEPS Cuota SAT.

	Args:
		company: Company name
		clave_sat: ClaveProdServ SAT del producto (ej: "50202301")
		fecha: Fecha de vigencia (posting_date del documento)

	Returns:
		list[dict]: Lista de cuotas vigentes con campos:
			- cuenta_ieps: Cuenta contable IEPS
			- cuota: Cuota en $/UOM
			- uom: UOM canónica SAT (LTR, H87, etc)
	"""
	if not company or not clave_sat or not fecha:
		return []

	return frappe.db.sql(
		"""
		SELECT
			cuenta_ieps,
			cuota,
			uom
		FROM `tabIEPS Cuota SAT`
		WHERE company = %(company)s
		  AND clave_prod_serv = %(clave_sat)s
		  AND vigencia_desde <= %(fecha)s
		  AND (vigencia_hasta IS NULL OR vigencia_hasta >= %(fecha)s)
		  AND docstatus < 2
		ORDER BY vigencia_desde DESC
		""",
		{"company": company, "clave_sat": clave_sat, "fecha": fecha},
		as_dict=True,
	)


def _convertir_cuota_a_uom_item(cuota: float, uom_base: str, item_code: str, item_uom: str) -> float:
	"""
	Convertir cuota de UOM canónica SAT a UOM del item en SI.

	Ejemplo:
		Cuota SAT: $1.27/litro (LTR)
		Item UOM: Pieza (H87)
		Conversión: 1 pieza = 0.6 litros
		Cuota convertida: $1.27 x 0.6 = $0.762/pieza

	Args:
		cuota: Cuota en UOM base (ej: 1.27)
		uom_base: UOM canónica SAT (ej: "LTR")
		item_code: Código del item
		item_uom: UOM del item en SI (ej: "H87")

	Returns:
		float: Cuota convertida a UOM del item

	Raises:
		frappe.ValidationError: Si no existe conversión UOM configurada
	"""
	# Si UOMs son iguales, no hay conversión
	if uom_base == item_uom:
		return cuota

	# Obtener factor conversión usando función ERPNext nativa
	try:
		from erpnext.stock.get_item_details import get_conversion_factor

		conversion_data = get_conversion_factor(item_code, uom_base)
		factor = conversion_data.get("conversion_factor", 0)

		if factor <= 0:
			frappe.throw(
				f"Item <b>{item_code}</b>: Falta configurar conversión UOM "
				f"de <b>{item_uom}</b> → <b>{uom_base}</b> (UOM SAT).<br>"
				f"Configure conversión en Item Master → UOMs."
			)

		# Convertir cuota: cuota_base x factor
		# Ejemplo: $1.27/litro x 0.6 litros/pieza = $0.762/pieza
		return cuota * factor

	except Exception as e:
		frappe.throw(
			f"Error conversión UOM para Item <b>{item_code}</b>: {e!s}<br>"
			f"UOM Item: <b>{item_uom}</b>, UOM SAT: <b>{uom_base}</b>"
		)


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
		pl, _source = _pick_price_list(doc.customer, cc_now)
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
				f"Línea {i} (Item: {row.item_code}): sin <b>Clave SAT de Producto o Servicio</b> configurada. Asígnela en el artículo para poder facturar."
			)
