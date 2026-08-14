"""Ambiente fiscal del sitio — fuente de verdad para el PAC (issue #215).

La variable explícita `fm_environment` en `site_config.json` decide el ambiente fiscal
del sitio y, por tanto, la credencial de FacturAPI que se usa:

  - "production" → credencial `api_key`
  - "sandbox"   → credencial `test_api_key`

`sandbox_mode` (BD) deja de decidir la credencial. Vive en `site_config.json` (filesystem),
que `bench restore` NO copia desde la BD de producción: una copia restaurada conserva su
propia configuración de ambiente.

Comportamiento fail-closed: si `fm_environment` falta o es inválida, se bloquea cualquier
operación MUTANTE al PAC (POST/PUT/PATCH/DELETE) antes de contactarlo. Los GET siguen
permitidos.
"""

import frappe
from frappe import _

VALID_ENVIRONMENTS = ("production", "sandbox")
MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def get_fm_environment() -> str:
	"""Ambiente fiscal declarado en el `site_config.json` DEL SITIO, normalizado.

	Estrictamente **por-sitio** (issue #215): se comprueba la **presencia** de la clave
	`fm_environment` en el `site_config.json` del propio sitio, no en la configuración mergeada
	(`frappe.conf` / `frappe.get_site_config()` combinan common + site). Así, un `fm_environment`
	presente únicamente en `common_site_config.json` NO habilita el ambiente de ningún sitio, y un
	sitio que la define explícitamente siempre cuenta (aunque el valor coincida con el de common).

	Se usa `frappe.get_file_json` sobre `frappe.get_site_path("site_config.json")` (API de Frappe; el
	acceso a archivo vive dentro del framework, no en la app). Ante cualquier error de lectura se
	devuelve cadena vacía → la guarda bloquea (fail-closed).
	"""
	try:
		site_config = frappe.get_file_json(frappe.get_site_path("site_config.json"))
	except Exception:
		return ""
	return (site_config.get("fm_environment") or "").strip().lower()


def credential_field_for(environment: str) -> str | None:
	"""Campo de credencial de Company Settings según ambiente; None si es inválido."""
	if environment == "production":
		return "api_key"
	if environment == "sandbox":
		return "test_api_key"
	return None


def assert_pac_operation_allowed(method: str, environment: str, effective_key: str) -> None:
	"""Guarda central fail-closed para operaciones mutantes al PAC (issue #215).

	No bloquea GET. Cuando bloquea, lanza `frappe.throw` (que Frappe registra en Error Log
	en contextos de background) SIN contactar a FacturAPI.
	"""
	if (method or "").upper() not in MUTATING_METHODS:
		return  # GET y demás de solo lectura: permitidos

	# Regla 3: ambiente ausente o inválido → fail-closed.
	if environment not in VALID_ENVIRONMENTS:
		frappe.throw(
			_(
				"Operación fiscal bloqueada: falta o es inválida la variable 'fm_environment' en site_config.json (valores válidos: 'production' o 'sandbox'). No se contactó a FacturAPI."
			),
			title=_("Ambiente fiscal no configurado"),
		)

	# Regla 4: credencial productiva (sk_live_) en un ambiente NO productivo.
	if effective_key.startswith("sk_live_") and environment != "production":
		frappe.throw(
			_(
				"Operación fiscal bloqueada: la credencial efectiva es de producción (sk_live_) pero el ambiente del sitio no es 'production'. No se contactó a FacturAPI."
			),
			title=_("Credencial de producción en ambiente no productivo"),
		)

	# Reglas 1 y 2: la credencial del ambiente debe existir (sin fallback al otro campo).
	if not effective_key:
		if environment == "production":
			frappe.throw(
				_(
					"Operación fiscal bloqueada: el ambiente es 'production' pero falta 'api_key' en Facturacion Mexico Company Settings. No se contactó a FacturAPI."
				),
				title=_("Falta api_key de producción"),
			)
		frappe.throw(
			_(
				"Operación fiscal bloqueada: el ambiente es 'sandbox' pero falta 'test_api_key' en Facturacion Mexico Company Settings. No se contactó a FacturAPI."
			),
			title=_("Falta test_api_key de sandbox"),
		)
