"""
Clasificación de items por categoría fiscal para autoselección STCT.

Fuente de verdad única: TABLA_MAESTRA_GRUPOS_FISCALES en setup/item_groups.py
Todas las constantes se importan directamente desde allí (sin duplicación).
"""

import frappe

from facturacion_mexico.setup.item_groups import (
	CATEGORIAS_IEPS,
	ITEM_GROUP_CATEGORIA,
)


def clasificar_items_documento(doc: "Sales Invoice") -> dict:
	"""
	Clasifica items del documento en categorías fiscales.

	Fuente de verdad: ITEM_GROUP_CATEGORIA (derivada de ITEM_GROUP_ITT_MAP)

	Workflow:
	1. Lee item.item_group de cada item en factura
	2. Mapea Item Group → Categoría fiscal (directo desde tabla)
	3. Retorna clasificación agregada del documento

	Asume:
	- Item Groups estandarizados creados por setup (ensure_groups_after_install)
	- ITT asignados a Item Groups por setup (assign_itt_to_groups)
	- Usuario asignó items a Item Groups correctos

	Args:
		doc: Sales Invoice document

	Returns:
		dict: {
			"tiene_ieps": bool,
			"tiene_retenciones": bool,
			"categorias": ["Alcohol", "Resto"],
			"items_por_categoria": {
				"Alcohol": ["Item-001"],
				"Resto": ["Item-002"],
			}
		}

	Examples:
		>>> si = frappe.get_doc("Sales Invoice", "SI-001")
		>>> clasificacion = clasificar_items_documento(si)
		>>> print(clasificacion["tiene_ieps"])
		True
		>>> print(clasificacion["categorias"])
		["Alcohol", "Resto"]
	"""
	categorias = set()
	items_por_categoria = {}

	for item in doc.items:
		# Obtener Item Group del item (con cache)
		item_group = _get_item_group(item.item_code)

		# Mapear Item Group → Categoría (directo desde tabla maestra)
		categoria = ITEM_GROUP_CATEGORIA.get(item_group, "Resto")

		# Agregar a resultados
		categorias.add(categoria)
		if categoria not in items_por_categoria:
			items_por_categoria[categoria] = []
		items_por_categoria[categoria].append(item.item_code)

	return {
		"tiene_ieps": bool(categorias & CATEGORIAS_IEPS),
		"tiene_retenciones": "Retenciones" in categorias,
		"categorias": list(categorias),
		"items_por_categoria": items_por_categoria,
	}


def _get_item_group(item_code: str) -> str:
	"""
	Obtiene Item Group de un item con cache.

	Args:
		item_code: Código del item

	Returns:
		str: Nombre del Item Group (default: "All Item Groups")
	"""
	try:
		return frappe.get_cached_value("Item", item_code, "item_group") or "All Item Groups"
	except frappe.DoesNotExistError:
		frappe.logger().warning(f"Item {item_code} no existe, asumiendo grupo 'All Item Groups'")
		return "All Item Groups"
