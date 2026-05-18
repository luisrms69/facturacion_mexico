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


def _get_root_item_group() -> str | None:
	"""Detect the root Item Group without assuming the site language."""
	root = frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name")
	if not root:
		# ERPNext may store NULL instead of empty string
		root = frappe.db.sql(
			"SELECT name FROM `tabItem Group` WHERE (parent_item_group IS NULL OR parent_item_group = '') AND is_group = 1 LIMIT 1"
		)
		root = root[0][0] if root else None
	if not root:
		frappe.logger().warning(
			"[FMX][ItemGroups] No se encontró grupo raíz de Item Group — reintento pendiente"
		)
	return root


def _ensure_item_group(name: str) -> str | None:
	"""Create fiscal Item Group (is_group=1) if it does not exist. Returns name or None if root is missing."""
	existing = frappe.db.exists("Item Group", {"name": name})
	if existing:
		return existing

	root = _get_root_item_group()
	if not root:
		frappe.logger().warning(f"[FMX][ItemGroups] No se puede crear '{name}': grupo raíz no encontrado")
		return None

	doc = frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": name,
			"name": name,
			"is_group": 1,
			"parent_item_group": root,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def ensure_fiscal_item_groups():
	"""
	Ensure all 10 fiscal Item Groups exist (without assigning ITTs).
	Idempotent — safe to call in after_install, after_migrate, and before the wizard.
	If no root group exists (ERPNext not yet configured), logs a warning and exits without error.
	"""
	try:
		creados = []
		sin_raiz = False
		for group_name in ITEM_GROUP_ITT_MAP.keys():
			result = _ensure_item_group(group_name)
			if result is None:
				sin_raiz = True
				break
			if result == group_name:
				creados.append(group_name)

		if sin_raiz:
			frappe.logger().warning(
				"[FMX][ItemGroups] Grupos fiscales no creados: grupo raíz de Item Group no encontrado. "
				"Se reintentará al correr el wizard fiscal."
			)
		else:
			frappe.logger().info(
				f"[FMX][ItemGroups] {len(ITEM_GROUP_ITT_MAP)} grupos verificados, {len(creados)} creados."
			)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "[FMX][ItemGroups] Error ensure_fiscal_item_groups")
		raise


# Alias para compatibilidad con after_install existente
ensure_groups_after_install = ensure_fiscal_item_groups


def _find_company_suffixes(company_doc) -> list[str]:
	"""Return possible suffixes used by the wizard to name ITTs per company."""
	suffixes = []
	if getattr(company_doc, "abbr", None):
		suffixes.append(company_doc.abbr.strip())
	if getattr(company_doc, "company_name", None):
		suffixes.append(company_doc.company_name.strip())
	if getattr(company_doc, "name", None):
		suffixes.append(company_doc.name.strip())
	# deduplicate preserving order
	seen, ordered = set(), []
	for s in suffixes:
		if s and s not in seen:
			seen.add(s)
			ordered.append(s)
	return ordered


def _resolve_itt_name(base_pattern: str, company_doc) -> str | None:
	"""
	Resolve the ITT name covering 3 historical naming scenarios:
	  A) name == title == "ITT IVA 0% - _TC"          (correct — created post-fix)
	  B) name == "ITT IVA 0% - _TC - _TC",             (double name, simple title — old workaround)
	     title == "ITT IVA 0% - _TC"
	  C) name == title == "ITT IVA 0% - _TC - _TC"    (both doubled — pre-fix bug)
	"""
	for suf in _find_company_suffixes(company_doc):
		base_title = base_pattern.format(suffix=suf)
		canonical = base_title
		double = f"{base_title} - {suf}"

		candidates = [
			{"name": canonical},  # A: name correcto
			{"title": canonical, "company": company_doc.name},  # B: title correcto, name doble
			{"name": double},  # C: ambos dobles — busca por name
			{"title": double, "company": company_doc.name},  # C: fallback por title doble
		]

		for filters in candidates:
			result = frappe.db.get_value("Item Tax Template", filters, "name")
			if result:
				return result

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
