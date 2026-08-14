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

import json

import frappe
from frappe import _

VALID_ENVIRONMENTS = ("production", "sandbox")
MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def _read_site_only_config() -> dict:
	"""Leer SOLO el `site_config.json` del sitio actual (sin merge con common_site_config.json).

	`frappe.conf` / `frappe.get_site_config()` combinan `common_site_config.json` + `site_config.json`,
	por lo que un `fm_environment` puesto en common se heredaría a sitios que lo omiten. Para que el
	ambiente sea estrictamente **por-sitio** (issue #215), se lee el archivo del sitio directamente y
	NO se consulta la configuración mergeada.
	"""
	try:
		with open(frappe.get_site_path("site_config.json")) as fh:
			return json.load(fh)
	except (OSError, ValueError):
		return {}


def get_fm_environment() -> str:
	"""Ambiente fiscal declarado en el `site_config.json` DEL SITIO (no heredado de common), normalizado.

	Estrictamente por-sitio: un valor presente únicamente en `common_site_config.json` se ignora.
	"""
	return (_read_site_only_config().get("fm_environment") or "").strip().lower()


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
