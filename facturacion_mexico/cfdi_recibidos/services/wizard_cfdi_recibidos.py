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

	config.purchase_taxes_template = template_name
	config.wizard_completado = 1
	config.ultima_generacion = now_datetime()
	config.save(ignore_permissions=True)

	return {
		"status": "ok",
		"template_name": template_name,
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
		if frappe.db.exists("Purchase Taxes and Charges Template", base_name):
			base_name = _versioned_name(base_name)
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


def _versioned_name(base_name: str) -> str:
	clean = re.sub(r" v\d+$", "", base_name)
	for v in range(2, 100):
		candidate = f"{clean} v{v}"
		if not frappe.db.exists("Purchase Taxes and Charges Template", candidate):
			return candidate
	return f"{clean} v{frappe.generate_hash()[:6]}"
