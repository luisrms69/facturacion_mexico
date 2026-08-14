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
	"""Ambiente fiscal declarado en site_config.json, normalizado (minúsculas)."""
	return (frappe.conf.get("fm_environment") or "").strip().lower()


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
