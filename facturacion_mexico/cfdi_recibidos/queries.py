import frappe


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
