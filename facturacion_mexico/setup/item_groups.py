import frappe
from frappe.utils import cint

# Nombres fijos de los grupos (raíz)
IG_ZERO = "Artículos con IVA al 0%"
IG_EXENTO = "Artículos Exentos"
ROOT_IG = "All Item Groups"

# Patrones de nombres de ITT generados por tu wizard E0.5
# Nota: Buscar por title (formato simple) no por name (formato con doble sufijo)
ITT_ZERO_TITLE = "ITT IVA 0% - {suffix}"
ITT_EXENTO_TITLE = "ITT Exento - {suffix}"


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
	"""Hook after_install: solo garantizar que EXISTAN los dos grupos raíz (sin asignar ITT)."""
	try:
		_ensure_item_group(IG_ZERO)
		_ensure_item_group(IG_EXENTO)
		frappe.logger().info("[FMX][ItemGroups] Grupos raíz creados/verificados (after_install).")
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
		# Preferir búsqueda por name exacto (post-normalización)
		by_name = frappe.db.exists("Item Tax Template", candidate)
		if by_name:
			return by_name
		# Fallback por title (para compatibilidad con templates viejos si existen)
		by_title = frappe.db.get_value("Item Tax Template", {"title": candidate}, "name")
		if by_title:
			return by_title
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


def assign_itt_to_groups():
	"""
	Hook idempotente para asignar ITT a los dos grupos raíz.
	- Llamar desde after_migrate y desde el cierre del wizard E0.5.
	- Si los ITT aún no existen, loguea y sale sin error (se reintenta en próxima ejecución).
	"""
	try:
		# Asegurar que los grupos existen
		_ensure_item_group(IG_ZERO)
		_ensure_item_group(IG_EXENTO)

		# Obtener todas las compañías activas
		companies = frappe.get_all("Company", fields=["name", "company_name", "abbr"])
		changes = []

		for c in companies:
			company = frappe._dict(c)

			itt_zero = _resolve_itt_name(ITT_ZERO_TITLE, company)
			itt_exento = _resolve_itt_name(ITT_EXENTO_TITLE, company)

			# Si no existen aún los ITT, log y continuar (reintento posterior)
			if not itt_zero or not itt_exento:
				frappe.logger().info(
					f"[FMX][ItemGroups] ITT faltantes para '{company.name}': "
					f"zero={'OK' if itt_zero else 'MISSING'}, exento={'OK' if itt_exento else 'MISSING'}"
				)
				continue

			# Asignar solo si cambia
			if _assign_group_itt(IG_ZERO, itt_zero):
				changes.append((company.name, IG_ZERO, itt_zero))
			if _assign_group_itt(IG_EXENTO, itt_exento):
				changes.append((company.name, IG_EXENTO, itt_exento))

		if changes:
			for comp, grp, itt in changes:
				frappe.logger().info(
					f"[FMX][ItemGroups] Asignado ITT '{itt}' a grupo '{grp}' (Company={comp})."
				)
			frappe.db.commit()
		else:
			frappe.logger().info("[FMX][ItemGroups] Sin cambios (ITT ya asignados o faltantes).")

	except Exception:
		frappe.log_error(frappe.get_traceback(), "[FMX][ItemGroups] Error assign_itt_to_groups")
		raise
