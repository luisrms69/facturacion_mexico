import frappe


class ItemResolver:
	"""
	Propone item_code e item_resolution para un concepto de CFDI Recibido.
	Solo lectura — no modifica documentos ni escribe en BD.

	propose() cubre solo niveles automáticos confiables:
	  Nivel 1: Mapeado — CFDI Concepto Mapping con target_type=Item
	  Nivel 2: Específico — Item Supplier por NoIdentificacion

	Para niveles asistidos (requieren decisión del usuario):
	  search_candidates()      — candidatos por descripción/clave SAT
	  suggest_generic_fallback() — último fallback GASTO-* (solo con aceptación explícita)
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
		Prioridad: Mapeado → Específico → sin match (None).
		No asigna Items genéricos GASTO-* automáticamente.
		"""
		result = self._try_mapeado(company, supplier_rfc, sat_product_key)
		if result:
			return result

		result = self._try_especifico(supplier, no_identificacion)
		if result:
			return result

		return {"item_code": None, "item_resolution": None}

	def search_candidates(self, description: str, sat_product_key: str, company: str) -> list[dict]:
		"""
		Retorna Items válidos como candidatos para clasificación asistida por el usuario.

		Filtros: is_purchase_item=1, is_stock_item=0, is_sales_item=0, UOM SAT, bajo Gastos.
		Retorna hasta 20 candidatos ordenados por coincidencia de descripción.
		"""
		from facturacion_mexico.cfdi_recibidos.services.uom_policy import SAT_UOMS

		expense_groups = _get_expense_item_groups()

		filters = {
			"is_purchase_item": 1,
			"is_stock_item": 0,
			"is_sales_item": 0,
			"stock_uom": ["in", list(SAT_UOMS)],
		}
		if expense_groups:
			filters["item_group"] = ["in", expense_groups]

		candidates = frappe.db.get_all(
			"Item",
			filters=filters,
			fields=["name", "item_name", "item_group", "stock_uom"],
			limit=50,
		)

		return _rank_candidates(candidates, description)

	def suggest_generic_fallback(self, item_group: str) -> "dict | None":
		"""
		Retorna un Item GASTO-* para el item_group dado.
		Solo para aceptación explícita del usuario — nunca llamado desde propose().
		"""
		return self._try_generico(item_group)

	def _try_mapeado(self, company: str, supplier_rfc: str, sat_product_key: str) -> "dict | None":
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

	def _try_especifico(self, supplier: str, no_identificacion: str) -> "dict | None":
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

	def _try_generico(self, item_group: str) -> "dict | None":
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


def _get_expense_item_groups() -> list[str]:
	"""Retorna todos los Item Groups bajo el nodo raíz 'Gastos'."""
	root = frappe.db.get_value("Item Group", "Gastos", ["lft", "rgt"], as_dict=True)
	if not root:
		return []
	return frappe.db.get_all(
		"Item Group",
		filters={"lft": [">=", root["lft"]], "rgt": ["<=", root["rgt"]]},
		pluck="name",
	)


def _rank_candidates(candidates: list, description: str) -> list[dict]:
	"""Ordena candidatos por coincidencia de palabras con la descripción del concepto."""
	desc_words = set((description or "").lower().split())

	def score(item):
		name_words = set((item.get("item_name") or "").lower().split())
		return len(desc_words & name_words)

	return sorted(candidates, key=score, reverse=True)[:20]
