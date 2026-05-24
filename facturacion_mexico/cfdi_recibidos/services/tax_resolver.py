"""
TaxResolver — Resuelve impuestos del XML CFDI a filas de Purchase Invoice.

Flujo: XML impuesto → Configuracion CFDI Recibidos → regla → cuenta → fila PI

SAT códigos de impuesto:
  001 = ISR
  002 = IVA
  003 = IEPS
"""

import json

import frappe
from frappe import _
from frappe.utils import flt

_SAT_ISR = "001"
_SAT_IVA = "002"
_SAT_IEPS = "003"

_TASA_TOLERANCE = 0.0001


def resolve_taxes(impuestos_json: "dict | str", company: str) -> list:
	"""
	Resuelve impuestos del XML CFDI a filas listas para Purchase Invoice.taxes.

	Args:
	    impuestos_json: dict (o JSON string) con claves 'traslados' y 'retenciones'
	                    según formato del parser: tasa_cuota, importe
	    company: Nombre de la empresa (para cargar Configuracion CFDI Recibidos)

	Returns:
	    Lista de dicts con charge_type, dont_recompute_tax, account_head, tax_amount, description

	Raises:
	    frappe.ValidationError: Si falta configuración requerida
	"""
	if isinstance(impuestos_json, str):
		impuestos_json = json.loads(impuestos_json)

	config = _load_config(company)
	rows = []

	for t in (impuestos_json or {}).get("traslados", []):
		row = _resolve_traslado(t, config)
		if row is not None:
			rows.append(row)

	for r in (impuestos_json or {}).get("retenciones", []):
		rows.append(_resolve_retencion(r, config))

	return rows


def _load_config(company: str):
	config_name = f"CFDI-REC-CFG-{company}"
	if not frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		frappe.throw(
			_(
				"No existe Configuracion CFDI Recibidos para la empresa {0}. "
				"Cree la configuración y ejecute el wizard de impuestos."
			).format(company),
			frappe.ValidationError,
		)
	config = frappe.get_doc("Configuracion CFDI Recibidos", config_name)
	if not config.wizard_completado:
		frappe.throw(
			_(
				"Configuracion CFDI Recibidos de {0} no tiene template generado. "
				"Ejecute el wizard 'Generar Template de Impuestos'."
			).format(company),
			frappe.ValidationError,
		)
	return config


def _find_traslado_rule(config, impuesto: str, tasa_cuota):
	"""
	Busca la regla activa para un traslado.

	Para IVA (002): coincidencia exacta de tasa_cuota (tolerancia ±0.0001).
	Para IEPS (003): cualquier tasa → primera regla activa IEPS no retención.
	"""
	tasa = flt(tasa_cuota)
	for regla in config.reglas_impuesto:
		if not regla.activo or regla.es_retencion:
			continue
		if regla.impuesto_sat != impuesto:
			continue
		if impuesto == _SAT_IVA:
			if abs(flt(regla.tasa_cuota) - tasa) > _TASA_TOLERANCE:
				continue
		return regla
	return None


def _find_retencion_rule(config, impuesto: str):
	"""Busca la regla activa de retención por código SAT de impuesto."""
	for regla in config.reglas_impuesto:
		if not regla.activo or not regla.es_retencion:
			continue
		if regla.impuesto_sat == impuesto:
			return regla
	return None


def _build_row(account: str, importe: float, descripcion: str) -> dict:
	return {
		"charge_type": "Actual",
		"dont_recompute_tax": 1,
		"account_head": account,
		"tax_amount": flt(importe),
		"description": descripcion,
	}


def _resolve_traslado(t: dict, config) -> "dict | None":
	impuesto = t.get("impuesto", "")
	tipo_factor = t.get("tipo_factor", "")

	if impuesto == _SAT_IVA and tipo_factor == "Exento":
		return None

	if impuesto not in (_SAT_IVA, _SAT_IEPS):
		frappe.throw(
			_("Impuesto trasladado no reconocido: {0}").format(impuesto),
			frappe.ValidationError,
		)

	tasa_cuota = t.get("tasa_cuota", "0")
	regla = _find_traslado_rule(config, impuesto, tasa_cuota)
	if regla is None:
		frappe.throw(
			_(
				"No existe regla activa en Configuracion CFDI Recibidos de {0} para: "
				"impuesto={1}, tasa={2}. Agregue la regla y regenere el template."
			).format(config.company, impuesto, tasa_cuota),
			frappe.ValidationError,
		)
	return _build_row(regla.cuenta_impuesto, t.get("importe", 0), regla.descripcion)


def _resolve_retencion(r: dict, config) -> dict:
	impuesto = r.get("impuesto", "")
	if impuesto not in (_SAT_ISR, _SAT_IVA):
		frappe.throw(
			_("Retención con código de impuesto desconocido: {0}").format(impuesto),
			frappe.ValidationError,
		)

	regla = _find_retencion_rule(config, impuesto)
	if regla is None:
		frappe.throw(
			_(
				"No existe regla activa de retención en Configuracion CFDI Recibidos de {0} "
				"para impuesto={1}. Agregue la regla y regenere el template."
			).format(config.company, impuesto),
			frappe.ValidationError,
		)
	return _build_row(regla.cuenta_impuesto, -flt(r.get("importe", 0)), regla.descripcion)
