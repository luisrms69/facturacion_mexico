"""
TaxResolver — Resuelve impuestos del XML CFDI a filas de Purchase Invoice.

Flujo: XML impuesto → rol fiscal → CFM mapeo_cuentas → cuenta → template → fila PI

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

# IVA traslado: tasa normalizada → rol fiscal. Exento → None (sin línea).
_IVA_TASA_ROL = {
	"0.160000": "IVA Acreditable (Nacional)",
	"0.080000": "IVA Acreditable (Frontera)",
	"0.000000": "IVA Acreditable (0% exportación)",
}

# Campo en CFDI Concepto Mapping por código SAT de retención
_RETENCION_CAMPO = {
	_SAT_IVA: "retencion_iva_rol_fiscal",
	_SAT_ISR: "retencion_isr_rol_fiscal",
}

_RETENCION_NOMBRE = {
	_SAT_IVA: "IVA",
	_SAT_ISR: "ISR",
}


def resolve_taxes(impuestos_json: "dict | str", company: str, concepto_mappings: list) -> list:
	"""
	Resuelve impuestos del XML CFDI a filas listas para Purchase Invoice.taxes.

	Args:
	    impuestos_json: dict (o JSON string) con claves 'traslados' y 'retenciones'
	                    según formato del parser: tasa_cuota, importe
	    company: Nombre de la empresa (para cargar CFM)
	    concepto_mappings: Lista de CFDI Concepto Mapping docs o dicts
	                       (para lookup del rol de retenciones)

	Returns:
	    Lista de dicts con charge_type, dont_recompute_tax, account_head, tax_amount, description

	Raises:
	    frappe.ValidationError: Si falta configuración requerida
	"""
	if isinstance(impuestos_json, str):
		impuestos_json = json.loads(impuestos_json)

	cfm = _load_cfm(company)
	template_accounts = _load_template_accounts(cfm)
	rows = []

	for t in (impuestos_json or {}).get("traslados", []):
		row = _resolve_traslado(t, cfm, template_accounts)
		if row is not None:
			rows.append(row)

	for r in (impuestos_json or {}).get("retenciones", []):
		rows.append(_resolve_retencion(r, cfm, template_accounts, concepto_mappings))

	return rows


def _load_cfm(company: str):
	cfm_name = f"CFM-{company}"
	if not frappe.db.exists("Configuracion Fiscal Mexico", cfm_name):
		frappe.throw(
			_("No existe Configuracion Fiscal Mexico para la empresa {0}").format(company),
			frappe.ValidationError,
		)
	cfm = frappe.get_doc("Configuracion Fiscal Mexico", cfm_name)
	if not cfm.cfdi_recibidos_tax_template:
		frappe.throw(
			_(
				"Configuracion Fiscal Mexico de {0} no tiene Template Impuestos CFDI Recibidos configurado"
			).format(company),
			frappe.ValidationError,
		)
	return cfm


def _load_template_accounts(cfm) -> set:
	rows = frappe.get_all(
		"Purchase Taxes and Charges",
		filters={
			"parent": cfm.cfdi_recibidos_tax_template,
			"parenttype": "Purchase Taxes and Charges Template",
		},
		fields=["account_head"],
	)
	return {r.account_head for r in rows if r.account_head}


def _get_account_for_rol(cfm, rol_fiscal: str) -> str:
	for row in cfm.mapeo_cuentas:
		if row.rol_fiscal == rol_fiscal:
			return row.cuenta_impuesto
	frappe.throw(
		_("Rol fiscal '{0}' no tiene cuenta configurada en Configuracion Fiscal Mexico de {1}").format(
			rol_fiscal, cfm.company
		),
		frappe.ValidationError,
	)


def _validate_in_template(account: str, rol: str, template_name: str, template_accounts: set):
	if account not in template_accounts:
		frappe.throw(
			_("Cuenta '{0}' (rol: {1}) no está en el template '{2}'").format(account, rol, template_name),
			frappe.ValidationError,
		)


def _build_row(account: str, importe: float, rol: str) -> dict:
	return {
		"charge_type": "Actual",
		"dont_recompute_tax": 1,
		"account_head": account,
		"tax_amount": flt(importe),
		"description": rol,
	}


def _resolve_traslado(t: dict, cfm, template_accounts: set) -> "dict | None":
	impuesto = t.get("impuesto", "")
	tipo_factor = t.get("tipo_factor", "")

	if impuesto == _SAT_IVA:
		if tipo_factor == "Exento":
			return None

		try:
			tasa_norm = f"{flt(t.get('tasa_cuota', '0')):.6f}"
		except (TypeError, ValueError):
			tasa_norm = "0.000000"

		rol = _IVA_TASA_ROL.get(tasa_norm)
		if rol is None:
			frappe.throw(
				_("IVA no reconocido: tipo_factor={0}, tasa={1}").format(tipo_factor, tasa_norm),
				frappe.ValidationError,
			)
		account = _get_account_for_rol(cfm, rol)
		_validate_in_template(account, rol, cfm.cfdi_recibidos_tax_template, template_accounts)
		return _build_row(account, t.get("importe", 0), rol)

	if impuesto == _SAT_IEPS:
		rol = "IEPS Acreditable"
		account = _get_account_for_rol(cfm, rol)
		_validate_in_template(account, rol, cfm.cfdi_recibidos_tax_template, template_accounts)
		return _build_row(account, t.get("importe", 0), rol)

	frappe.throw(
		_("Impuesto trasladado no reconocido: {0}").format(impuesto),
		frappe.ValidationError,
	)


def _resolve_retencion(r: dict, cfm, template_accounts: set, concepto_mappings: list) -> dict:
	impuesto = r.get("impuesto", "")

	if impuesto not in _RETENCION_CAMPO:
		frappe.throw(
			_("Retención con código de impuesto desconocido: {0}").format(impuesto),
			frappe.ValidationError,
		)

	campo = _RETENCION_CAMPO[impuesto]
	nombre = _RETENCION_NOMBRE[impuesto]
	rol = _get_retencion_rol(concepto_mappings, campo, nombre)
	account = _get_account_for_rol(cfm, rol)
	_validate_in_template(account, rol, cfm.cfdi_recibidos_tax_template, template_accounts)
	return _build_row(account, -flt(r.get("importe", 0)), rol)


def _get_retencion_rol(concepto_mappings: list, campo: str, nombre_impuesto: str) -> str:
	for mapping in concepto_mappings or []:
		if isinstance(mapping, dict):
			rol = mapping.get(campo)
		else:
			rol = getattr(mapping, campo, None)
		if rol:
			return rol

	frappe.throw(
		_("Retención {0} en el XML pero ningún CFDI Concepto Mapping tiene '{1}' configurado").format(
			nombre_impuesto, campo
		),
		frappe.ValidationError,
	)
