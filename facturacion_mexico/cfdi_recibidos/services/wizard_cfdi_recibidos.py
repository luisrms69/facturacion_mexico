"""
Wizard de configuración de impuestos para CFDI Recibidos.

Genera o actualiza el Purchase Taxes and Charges Template a partir de las
reglas definidas en Configuracion CFDI Recibidos.

Reglas de seguridad:
- No elimina templates que estén referenciados en PIs submitted.
- Si el template está en uso, genera una nueva versión versionada.
- No usa frappe.db.commit() — el caller controla la transacción.
- IVA Exento no requiere regla; se ignora automáticamente en TaxResolver.
- IEPS Cuota emite advertencia si no hay datos en IEPS Cuota SAT.
"""

import re

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from facturacion_mexico.utils.roles_fiscales import (
	ROL_IEPS_ACR,
	ROL_IVA_ACR_CERO,
	ROL_IVA_ACR_FRO,
	ROL_IVA_ACR_NAC,
)

# Códigos canónicos SAT — ver fixtures/sat_impuesto.json
_SAT_ISR = "001"
_SAT_IVA = "002"
_SAT_IEPS = "003"
_TASA = "Tasa"
_CUOTA = "Cuota"

# Placeholder sin significado fiscal fijo; IEPS/retenciones se resuelven contra la regla/configuración real, no contra esta tasa.
_TASA_PLACEHOLDER = 0.0


@frappe.whitelist()
def get_opciones_impuesto_iniciales() -> list:
	"""
	Retorna opciones de impuesto iniciales para el wizard de Configuracion CFDI Recibidos.

	Las tasas IVA provienen del catálogo Tasa IVA SAT (DocType), no de configuración Python.
	Los nombres conceptuales son estables: no dependen de la tasa como identidad.
	"""
	tasas = {
		r.clave: flt(r.tasa_cuota)
		for r in frappe.get_all(
			"Tasa IVA SAT",
			filters={"activo": 1},
			fields=["clave", "tasa_cuota"],
		)
	}
	_claves_requeridas = ("IVA_NACIONAL", "IVA_FRONTERA", "IVA_TASA_CERO")
	faltantes = [c for c in _claves_requeridas if c not in tasas]
	if faltantes:
		frappe.throw(
			_(
				"Faltan registros activos en Tasa IVA SAT: {0}. "
				"Ejecute bench migrate para cargar el catálogo."
			).format(", ".join(faltantes)),
			frappe.ValidationError,
		)
	return [
		{
			"clave": "IVA_NACIONAL",
			"impuesto_sat": _SAT_IVA,
			"tipo_factor": _TASA,
			"tasa_cuota": tasas["IVA_NACIONAL"],
			"descripcion": ROL_IVA_ACR_NAC,
			"es_retencion": 0,
		},
		{
			"clave": "IVA_FRONTERA",
			"impuesto_sat": _SAT_IVA,
			"tipo_factor": _TASA,
			"tasa_cuota": tasas["IVA_FRONTERA"],
			"descripcion": ROL_IVA_ACR_FRO,
			"es_retencion": 0,
		},
		{
			"clave": "IVA_TASA_CERO",
			"impuesto_sat": _SAT_IVA,
			"tipo_factor": _TASA,
			"tasa_cuota": tasas["IVA_TASA_CERO"],
			"descripcion": ROL_IVA_ACR_CERO,
			"es_retencion": 0,
		},
		{
			"clave": "IEPS_TASA",
			"impuesto_sat": _SAT_IEPS,
			"tipo_factor": _TASA,
			"tasa_cuota": _TASA_PLACEHOLDER,
			"descripcion": f"{ROL_IEPS_ACR} (Tasa)",
			"es_retencion": 0,
		},
		{
			"clave": "IEPS_CUOTA",
			"impuesto_sat": _SAT_IEPS,
			"tipo_factor": _CUOTA,
			"tasa_cuota": _TASA_PLACEHOLDER,
			"descripcion": f"{ROL_IEPS_ACR} (Cuota)",
			"es_retencion": 0,
		},
		{
			"clave": "ISR_RETENIDO",
			"impuesto_sat": _SAT_ISR,
			"tipo_factor": _TASA,
			"tasa_cuota": _TASA_PLACEHOLDER,
			"descripcion": "ISR Retenido",
			"es_retencion": 1,
		},
		{
			"clave": "IVA_RETENIDO",
			"impuesto_sat": _SAT_IVA,
			"tipo_factor": _TASA,
			"tasa_cuota": _TASA_PLACEHOLDER,
			"descripcion": "IVA Retenido",
			"es_retencion": 1,
		},
	]


@frappe.whitelist()
def generar_template_impuestos(config_name: str) -> dict:
	"""
	Genera o actualiza el Purchase Taxes and Charges Template para CFDI Recibidos.

	Args:
	    config_name: Nombre del documento Configuracion CFDI Recibidos

	Returns:
	    dict con status, template_name, warnings[]
	"""
	if not config_name:
		frappe.throw(_("Se requiere el nombre de Configuracion CFDI Recibidos"), frappe.MandatoryError)

	config = frappe.get_doc("Configuracion CFDI Recibidos", config_name)
	frappe.has_permission("Configuracion CFDI Recibidos", "write", doc=config, throw=True)

	active_rules = [r for r in config.reglas_impuesto if r.activo]
	if not active_rules:
		frappe.throw(
			_("No hay reglas de impuesto activas. Agregue al menos una regla antes de generar el template."),
			frappe.ValidationError,
		)

	warnings = _collect_warnings(config, active_rules)

	template_name = _safe_generate_template(config, active_rules)

	# Generar también el template porcentual para PIs manuales y asignarlo como default
	manual_template_name = _ensure_manual_template(config)

	config.purchase_taxes_template = template_name
	config.wizard_completado = 1
	config.ultima_generacion = now_datetime()
	config.save(ignore_permissions=True)

	return {
		"status": "ok",
		"template_name": template_name,
		"manual_template_name": manual_template_name,
		"warnings": warnings,
		"message": _("Template '{0}' generado correctamente.").format(template_name),
	}


def _collect_warnings(config, active_rules: list) -> list:
	warnings = []

	has_ieps_cuota = any(r.impuesto_sat == "003" and r.tipo_factor == "Cuota" for r in active_rules)
	if has_ieps_cuota and not frappe.db.count("IEPS Cuota SAT"):
		warnings.append(
			_(
				"Hay reglas de IEPS Cuota pero no existe ningún registro en IEPS Cuota SAT. "
				"El template se generará, pero la conversión de CFDI fallará si el XML incluye IEPS Cuota."
			)
		)

	has_iva_zero = any(
		r.impuesto_sat == "002" and not r.es_retencion and abs(flt(r.tasa_cuota)) < 0.0001
		for r in active_rules
	)
	if has_iva_zero:
		warnings.append(
			_(
				"Se incluye IVA 0% (exportación). La fila de impuesto se generará con importe $0 "
				"cuando el XML lo declare — sin impacto contable, solo para trazabilidad."
			)
		)

	return warnings


def _safe_generate_template(config, active_rules: list) -> str:
	"""
	Genera o actualiza el template de forma segura.

	- Si no existe template previo → crea nuevo.
	- Si existe y no está en uso en PIs submitted → actualiza sus filas en lugar.
	- Si existe y está en uso en PIs submitted → crea versión nueva.
	"""
	existing = config.purchase_taxes_template

	if existing and frappe.db.exists("Purchase Taxes and Charges Template", existing):
		pi_count = frappe.db.count(
			"Purchase Invoice",
			{"taxes_and_charges": existing, "docstatus": 1},
		)
		if pi_count > 0:
			new_name = _versioned_name(existing)
			return _create_template(new_name, config.company, active_rules)
		else:
			return _update_template_in_place(existing, active_rules)
	else:
		base_name = f"{config.company} — CFDI Recibidos"
		# Frappe autonombra como "{title} - {abbr}", buscar por título + empresa
		existing_by_title = frappe.db.get_value(
			"Purchase Taxes and Charges Template",
			{"title": base_name, "company": config.company},
			"name",
		)
		if existing_by_title:
			pi_count = frappe.db.count(
				"Purchase Invoice",
				{"taxes_and_charges": existing_by_title, "docstatus": 1},
			)
			if pi_count > 0:
				return _create_template(_versioned_name(base_name), config.company, active_rules)
			return _update_template_in_place(existing_by_title, active_rules)
		return _create_template(base_name, config.company, active_rules)


def _update_template_in_place(template_name: str, active_rules: list) -> str:
	tmpl = frappe.get_doc("Purchase Taxes and Charges Template", template_name)
	tmpl.taxes = []
	for row_data in _build_template_rows(active_rules):
		tmpl.append("taxes", row_data)
	tmpl.save(ignore_permissions=True)
	return tmpl.name


def _create_template(template_name: str, company: str, active_rules: list) -> str:
	tmpl = frappe.new_doc("Purchase Taxes and Charges Template")
	tmpl.title = template_name
	tmpl.company = company
	for row_data in _build_template_rows(active_rules):
		tmpl.append("taxes", row_data)
	tmpl.insert(ignore_permissions=True)
	return tmpl.name


def _build_template_rows(active_rules: list) -> list:
	rows = []
	for regla in active_rules:
		rows.append(
			{
				"charge_type": "Actual",
				"account_head": regla.cuenta_impuesto,
				"description": regla.descripcion,
				"add_deduct_tax": "Deduct" if regla.es_retencion else "Add",
				"tax_amount": 0,
			}
		)
	return rows


def _ensure_manual_template(config) -> str:
	"""
	Genera un PTCT porcentual (On Net Total) por cada regla de IVA traslado activa.
	Son los templates para Purchase Invoices manuales (sin XML).
	El de mayor tasa se marca como is_default=1.
	Es idempotente — re-ejecutar el wizard no duplica templates.
	Retorna el nombre del template marcado como default.
	"""
	# Reglas de traslado activas con tipo_factor=Tasa (IVA o IEPS Tasa) — generan template porcentual
	# Excluir: retenciones, Cuota (monto fijo/litro — no aplica como % sobre base)
	iva_rules = [
		r
		for r in config.reglas_impuesto
		if r.activo and not r.es_retencion and r.tipo_factor == "Tasa" and r.cuenta_impuesto
	]
	if not iva_rules:
		return ""

	# Ordenar: primero IVA (002), luego IEPS (003); dentro de cada grupo, descendente por tasa
	iva_rules.sort(key=lambda r: (r.impuesto_sat, -flt(r.tasa_cuota)))

	default_template_name = ""

	for idx, rule in enumerate(iva_rules):
		tasa = flt(rule.tasa_cuota)
		tasa_pct = round(tasa * 100, 4)
		impuesto_label = "IVA" if rule.impuesto_sat == "002" else "IEPS"
		title = f"{config.company} — {rule.impuesto_sat} {impuesto_label} Compras {tasa_pct}%"

		existing = frappe.db.get_value(
			"Purchase Taxes and Charges Template",
			{"title": title, "company": config.company},
			"name",
		)

		row_data = {
			"charge_type": "On Net Total",
			"account_head": rule.cuenta_impuesto,
			"description": rule.descripcion or f"{impuesto_label} {tasa_pct}%",
			"add_deduct_tax": "Add",
			"rate": tasa_pct,
		}

		is_default = 1 if idx == 0 else 0  # solo el primero (mayor tasa) es default

		if existing:
			tmpl = frappe.get_doc("Purchase Taxes and Charges Template", existing)
			tmpl.taxes = []
			tmpl.append("taxes", row_data)
			tmpl.is_default = is_default
			tmpl.save(ignore_permissions=True)
			template_name = tmpl.name
		else:
			tmpl = frappe.new_doc("Purchase Taxes and Charges Template")
			tmpl.title = title
			tmpl.company = config.company
			tmpl.is_default = is_default
			tmpl.append("taxes", row_data)
			tmpl.insert(ignore_permissions=True)
			template_name = tmpl.name

		if idx == 0:
			default_template_name = template_name

	return default_template_name


def _versioned_name(base_name: str) -> str:
	clean = re.sub(r" v\d+$", "", base_name)
	for v in range(2, 100):
		candidate = f"{clean} v{v}"
		if not frappe.db.exists("Purchase Taxes and Charges Template", candidate):
			return candidate
	return f"{clean} v{frappe.generate_hash()[:6]}"
