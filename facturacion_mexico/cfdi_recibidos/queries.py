import frappe

from facturacion_mexico.cfdi_recibidos.services.uom_policy import get_sat_uom_list


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_expense_item_groups(doctype, txt, searchfield, start, page_len, filters):
	"""
	Retorna Item Groups que son hojas (is_group=0) bajo el grupo "Gastos".
	Usa el árbol anidado (lft/rgt) para incluir todos los descendientes, no solo hijos directos.
	Si el grupo "Gastos" no existe, retorna todas las hojas.
	"""
	gastos = frappe.db.get_value("Item Group", "Gastos", ["lft", "rgt"], as_dict=True)

	if gastos:
		return frappe.db.sql(
			"""
			SELECT name
			FROM `tabItem Group`
			WHERE is_group = 0
			  AND lft > %(lft)s
			  AND rgt < %(rgt)s
			  AND name LIKE %(txt)s
			ORDER BY name
			LIMIT %(start)s, %(page_len)s
			""",
			{
				"lft": gastos.lft,
				"rgt": gastos.rgt,
				"txt": f"%{txt}%",
				"start": start,
				"page_len": page_len,
			},
		)

	# Fallback: si no existe el grupo "Gastos", al menos filtra hojas
	return frappe.db.sql(
		"""
		SELECT name
		FROM `tabItem Group`
		WHERE is_group = 0
		  AND name LIKE %(txt)s
		ORDER BY name
		LIMIT %(start)s, %(page_len)s
		""",
		{"txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_expense_items(doctype, txt, searchfield, start, page_len, filters):
	"""
	Retorna Items válidos para asignar en conceptos CFDI:
	is_purchase_item=1, is_stock_item=0, is_sales_item=0,
	stock_uom SAT (c_ClaveUnidad), grupo hoja bajo "Gastos".
	"""
	sat_uoms = tuple(get_sat_uom_list())
	sat_placeholders = ", ".join(["%s"] * len(sat_uoms))

	gastos = frappe.db.get_value("Item Group", "Gastos", ["lft", "rgt"], as_dict=True)

	if gastos:
		return frappe.db.sql(
			f"""
			SELECT i.name, i.item_name, ig.name AS item_group_name
			FROM `tabItem` i
			JOIN `tabItem Group` ig ON ig.name = i.item_group
			WHERE i.is_purchase_item = 1
			  AND i.is_stock_item = 0
			  AND i.is_sales_item = 0
			  AND ig.is_group = 0
			  AND ig.lft > %s
			  AND ig.rgt < %s
			  AND i.stock_uom IN ({sat_placeholders})
			  AND (i.name LIKE %s OR i.item_name LIKE %s)
			ORDER BY i.name
			LIMIT %s, %s
			""",
			(gastos.lft, gastos.rgt, *sat_uoms, f"%{txt}%", f"%{txt}%", start, page_len),
		)

	# Fallback: sin árbol "Gastos", al menos filtra por flags y UOM SAT
	return frappe.db.sql(
		f"""
		SELECT i.name, i.item_name
		FROM `tabItem` i
		WHERE i.is_purchase_item = 1
		  AND i.is_stock_item = 0
		  AND i.is_sales_item = 0
		  AND i.stock_uom IN ({sat_placeholders})
		  AND (i.name LIKE %s OR i.item_name LIKE %s)
		ORDER BY i.name
		LIMIT %s, %s
		""",
		(*sat_uoms, f"%{txt}%", f"%{txt}%", start, page_len),
	)
