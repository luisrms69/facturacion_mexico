import frappe

from facturacion_mexico.cfdi_recibidos.services.uom_policy import is_sat_uom


def validate_expense_item(item_code: str) -> tuple[bool, str]:
	"""
	Verifica que item_code sea un ítem transaccional de gasto válido.

	Condiciones:
	- Item existe
	- is_purchase_item = 1
	- is_stock_item = 0
	- is_sales_item = 0
	- stock_uom pertenece al catálogo SAT (c_ClaveUnidad)
	- item_group existe y es hoja (is_group = 0)
	- item_group está dentro del árbol "Gastos" (si la raíz existe)

	Retorna (True, "") si válido, (False, motivo) si no.
	"""
	item = frappe.db.get_value(
		"Item",
		item_code,
		["is_purchase_item", "is_stock_item", "is_sales_item", "item_group", "stock_uom"],
		as_dict=True,
	)
	if not item:
		return False, f"El Item '{item_code}' no existe"
	if not item.is_purchase_item:
		return False, f"El Item '{item_code}' no es de compra (is_purchase_item=0)"
	if item.is_stock_item:
		return False, f"El Item '{item_code}' es de inventario (is_stock_item=1)"
	if item.is_sales_item:
		return False, f"El Item '{item_code}' es de venta (is_sales_item=1)"
	if not is_sat_uom(item.stock_uom or ""):
		return False, f"La UOM '{item.stock_uom}' del Item '{item_code}' no pertenece al catálogo SAT"

	ig = frappe.db.get_value("Item Group", item.item_group, ["is_group", "lft", "rgt"], as_dict=True)
	if not ig:
		return False, f"El grupo '{item.item_group}' no existe"
	if ig.is_group:
		return False, f"El grupo '{item.item_group}' es padre, no hoja (is_group=1)"

	gastos = frappe.db.get_value("Item Group", "Gastos", ["lft", "rgt"], as_dict=True)
	if gastos and not (ig.lft > gastos.lft and ig.rgt < gastos.rgt):
		return False, f"El grupo '{item.item_group}' no está bajo 'Gastos'"

	return True, ""
