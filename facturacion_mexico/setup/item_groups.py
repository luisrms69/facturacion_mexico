import frappe
from frappe.utils import cint

# -----------------------------------------------------------
# TABLA MAESTRA ÚNICA - FUENTE DE VERDAD
# -----------------------------------------------------------
# Esta tabla define TODO: Item Group, ITT pattern, Categoría fiscal
# De aquí derivan todas las demás estructuras (sin duplicación)

TABLA_MAESTRA_GRUPOS_FISCALES = [
	# (Item Group Name, ITT Pattern, Categoría Fiscal, Tipo)
	# Resto (IVA normal, 0%, exento)
	("Artículos con IVA al 0%", "ITT IVA 0% - {suffix}", "Resto", "IVA_ESPECIAL"),
	("Artículos Exentos", "ITT Exento - {suffix}", "Resto", "IVA_ESPECIAL"),
	# IEPS (4 categorías)
	("Artículos IEPS Alcohol", "ITT IEPS Alcohol - {suffix}", "Alcohol", "IEPS"),
	("Artículos IEPS Azúcar", "ITT IEPS Azúcar - {suffix}", "Azucar", "IEPS"),
	("Artículos IEPS Combustibles", "ITT IEPS Combustibles - {suffix}", "Combustibles", "IEPS"),
	("Artículos IEPS Tabaco", "ITT IEPS Tabaco - {suffix}", "Tabaco", "IEPS"),
	# Retenciones (4 tipos, misma categoría fiscal)
	(
		"Servicios Profesionales (Honorarios)",
		"ITT ISR + IVA Ret Honorarios - {suffix}",
		"Retenciones",
		"RETENCION",
	),
	("Arrendamiento", "ITT ISR + IVA Ret Arrendamiento - {suffix}", "Retenciones", "RETENCION"),
	("Autotransporte", "ITT ISR + IVA Ret Autotransporte - {suffix}", "Retenciones", "RETENCION"),
	("RESICO", "ITT ISR + IVA Ret RESICO - {suffix}", "Retenciones", "RETENCION"),
]

# -----------------------------------------------------------
# CONSTANTES DERIVADAS (generadas automáticamente)
# -----------------------------------------------------------
ROOT_IG = "All Item Groups"

# Diccionario Item Group → ITT pattern (para asignación)
ITEM_GROUP_ITT_MAP = {row[0]: row[1] for row in TABLA_MAESTRA_GRUPOS_FISCALES}

# Diccionario Item Group → Categoría fiscal (para clasificación)
ITEM_GROUP_CATEGORIA = {row[0]: row[2] for row in TABLA_MAESTRA_GRUPOS_FISCALES}

# Set de categorías IEPS (para clasificación rápida)
CATEGORIAS_IEPS = {row[2] for row in TABLA_MAESTRA_GRUPOS_FISCALES if row[3] == "IEPS"}

# Set de categorías Retención (para clasificación rápida)
CATEGORIAS_RETENCION = {row[2] for row in TABLA_MAESTRA_GRUPOS_FISCALES if row[3] == "RETENCION"}

# Lista de nombres Item Groups (para creación/validación)
ITEM_GROUPS_FISCALES = [row[0] for row in TABLA_MAESTRA_GRUPOS_FISCALES]


def _ensure_item_group(name: str) -> str:
	"""Crea (si no existe) un Item Group raíz con is_group=1. Devuelve el name."""
	existing = frappe.db.exists("Item Group", {"name": name})
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": name,
			"name": name,  # para forzar nombre exacto
			"is_group": 1,
			"parent_item_group": ROOT_IG,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def ensure_groups_after_install():
	"""Hook after_install: garantizar que EXISTAN todos los grupos raíz (sin asignar ITT)."""
	try:
		# Crear todos los grupos del mapa
		for group_name in ITEM_GROUP_ITT_MAP.keys():
			_ensure_item_group(group_name)

		frappe.logger().info(
			f"[FMX][ItemGroups] {len(ITEM_GROUP_ITT_MAP)} grupos raíz creados/verificados (after_install)."
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "[FMX][ItemGroups] Error ensure_groups_after_install")
		raise


def _find_company_suffixes(company_doc) -> list[str]:
	"""Posibles sufijos usados por el wizard para nombrar ITT por compañía."""
	suffixes = []
	if getattr(company_doc, "abbr", None):
		suffixes.append(company_doc.abbr.strip())
	if getattr(company_doc, "company_name", None):
		suffixes.append(company_doc.company_name.strip())
	if getattr(company_doc, "name", None):
		suffixes.append(company_doc.name.strip())
	# quitar duplicados manteniendo orden
	seen, ordered = set(), []
	for s in suffixes:
		if s and s not in seen:
			seen.add(s)
			ordered.append(s)
	return ordered


def _resolve_itt_name(base_pattern: str, company_doc) -> str | None:
	"""Intenta resolver el nombre exacto del ITT para la compañía probando varios sufijos."""
	for suf in _find_company_suffixes(company_doc):
		candidate = base_pattern.format(suffix=suf)
		# Búsqueda por name exacto (único método válido)
		by_name = frappe.db.exists("Item Tax Template", candidate)
		if by_name:
			return by_name
	return None


def _assign_group_itt(group_name: str, itt_name: str) -> bool:
	"""Asigna el ITT a la tabla taxes del Item Group si no existe ya. Devuelve True si cambió."""
	# Verificar si ya existe este ITT en la tabla taxes del grupo
	existing = frappe.db.exists("Item Tax", {"parent": group_name, "item_tax_template": itt_name})
	if existing:
		return False

	# Obtener el documento del Item Group y agregar el ITT
	doc = frappe.get_doc("Item Group", group_name)
	doc.append(
		"taxes",
		{
			"item_tax_template": itt_name,
			"tax_category": "",  # Vacío para aplicar a todas las categorías
			"valid_from": "2025-10-01",  # Fecha de inicio solicitada
		},
	)
	doc.save(ignore_permissions=True)
	return True


def assign_itt_to_groups(company_name: str | None = None):
	"""
	Hook idempotente para asignar ITT a todos los grupos raíz.
	- Llamar desde after_migrate (sin company_name) para procesar todas las companies
	- Llamar desde wizard (con company_name) para procesar solo una company
	- Si los ITT aún no existen, loguea y sale sin error (se reintenta en próxima ejecución).

	Args:
		company_name: Nombre de company a procesar (None = todas)
	"""
	try:
		# Asegurar que todos los grupos existen
		for group_name in ITEM_GROUP_ITT_MAP.keys():
			_ensure_item_group(group_name)

		# Companies a procesar (filtrado opcional)
		if company_name:
			companies = frappe.get_all(
				"Company", filters={"name": company_name}, fields=["name", "company_name", "abbr"]
			)
		else:
			companies = frappe.get_all("Company", fields=["name", "company_name", "abbr"])

		changes = []
		missing_log = []

		for c in companies:
			company = frappe._dict(c)

			# Iterar sobre todos los grupos del mapa
			for group_name, itt_pattern in ITEM_GROUP_ITT_MAP.items():
				itt_name = _resolve_itt_name(itt_pattern, company)

				# Si no existe aún el ITT, log y continuar (reintento posterior)
				if not itt_name:
					missing_log.append(f"{group_name} ({itt_pattern.format(suffix=company.abbr)})")
					continue

				# Asignar solo si cambia
				if _assign_group_itt(group_name, itt_name):
					changes.append((company.name, group_name, itt_name))

		# Log de ITT faltantes
		if missing_log:
			frappe.logger().info(
				f"[FMX][ItemGroups] ITT faltantes: {', '.join(missing_log[:5])}"
				+ (f" (+{len(missing_log) - 5} más)" if len(missing_log) > 5 else "")
			)

		# Log de asignaciones realizadas
		if changes:
			for comp, grp, itt in changes:
				frappe.logger().info(f"[FMX][ItemGroups] Asignado ITT '{itt}' a '{grp}' (Company={comp}).")
			frappe.db.commit()
		else:
			frappe.logger().info("[FMX][ItemGroups] Sin cambios.")

	except Exception:
		frappe.log_error(frappe.get_traceback(), "[FMX][ItemGroups] Error assign_itt_to_groups")
		raise
