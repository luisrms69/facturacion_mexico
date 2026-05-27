import frappe


class ItemResolver:
	"""
	Propone item_code e item_resolution para un concepto de CFDI Recibido.
	Solo lectura — no modifica documentos ni escribe en BD.
	"""

	def propose(
		self,
		sat_product_key: str,
		no_identificacion: str,
		item_group: str,
		company: str,
		supplier: str,
		supplier_rfc: str,
	) -> dict:
		"""
		Retorna {"item_code": str|None, "item_resolution": str|None}.
		Prioridad: Mapeado → Específico → Genérico → sin match.
		"""
		result = self._try_mapeado(company, supplier_rfc, sat_product_key)
		if result:
			return result

		result = self._try_especifico(supplier, no_identificacion)
		if result:
			return result

		result = self._try_generico(item_group)
		if result:
			return result

		return {"item_code": None, "item_resolution": None}

	def _try_mapeado(self, company: str, supplier_rfc: str, sat_product_key: str) -> dict | None:
		if not (company and supplier_rfc and sat_product_key):
			return None

		item_code = frappe.db.get_value(
			"CFDI Concepto Mapping",
			{
				"company": company,
				"supplier_rfc": supplier_rfc,
				"sat_product_key": sat_product_key,
				"target_type": "Item",
				"is_active": 1,
			},
			"target_item",
		)
		if item_code:
			return {"item_code": item_code, "item_resolution": "Mapeado"}
		return None

	def _try_especifico(self, supplier: str, no_identificacion: str) -> dict | None:
		if not (supplier and no_identificacion):
			return None

		item_code = frappe.db.get_value(
			"Item Supplier",
			{"supplier": supplier, "supplier_part_no": no_identificacion},
			"parent",
		)
		if item_code:
			return {"item_code": item_code, "item_resolution": "Específico"}
		return None

	def _try_generico(self, item_group: str) -> dict | None:
		if not item_group:
			return None

		candidates = frappe.db.get_all(
			"Item",
			filters={
				"item_group": item_group,
				"item_code": ["like", "GASTO-%"],
				"is_stock_item": 0,
				"is_sales_item": 0,
			},
			pluck="name",
		)
		if len(candidates) == 1:
			return {"item_code": candidates[0], "item_resolution": "Genérico"}
		return None
