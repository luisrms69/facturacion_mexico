import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# Campo Link existente en Sales Invoice
FFM_LINK_FIELD = "fm_factura_fiscal_mx"


def _pick_anchor_for_ffm_section() -> str:
	"""Elige un field estable que ya exista para que nuestra sección quede
	DESPUÉS de los checkboxes de la derecha y no los absorba."""
	meta = frappe.get_meta("Sales Invoice")
	# Orden de preferencia: más a la derecha y abajo en 'Details'
	for candidate in [
		"is_debit_note",
		"is_rate_adjustment",
		"is_return",
		"is_pos",
		"posting_date",
		"due_date",
	]:
		if meta.has_field(candidate):
			return candidate
	# fallback muy conservador
	return "due_date"


def apply_customization():
	"""Crea/actualiza la sección 'Factura Fiscal México' en Sales Invoice."""
	anchor = _pick_anchor_for_ffm_section()

	fields = {
		"Sales Invoice": [
			{
				"fieldname": "fm_ffm_section",
				"fieldtype": "Section Break",
				"label": "Factura Fiscal México",
				"insert_after": anchor,  # <— usamos el ancla calculada
				"collapsible": 1,
				"depends_on": f"eval:doc.{FFM_LINK_FIELD}",
			},
			# HTML de solo display (no ensucia el doc)
			{
				"fieldname": "fm_ffm_summary_html",
				"fieldtype": "HTML",
				"label": "Resumen CFDI",
				"insert_after": "fm_ffm_section",
			},
			# Campos persistentes (con allow_on_submit=1 para evitar errores after submit)
			{
				"fieldname": "fm_ffm_estado",
				"fieldtype": "Data",
				"label": "Estado CFDI",
				"read_only": 1,
				"allow_on_submit": 1,
				"insert_after": "fm_ffm_summary_html",
			},
			{
				"fieldname": "fm_ffm_numero",
				"fieldtype": "Data",
				"label": "Serie y Folio",
				"read_only": 1,
				"allow_on_submit": 1,
				"insert_after": "fm_ffm_estado",
			},
			{
				"fieldname": "fm_ffm_uuid",
				"fieldtype": "Data",
				"label": "UUID Fiscal",
				"read_only": 1,
				"allow_on_submit": 1,
				"insert_after": "fm_ffm_numero",
			},
			{
				"fieldname": "fm_ffm_fecha",
				"fieldtype": "Datetime",
				"label": "Fecha de Timbrado",
				"read_only": 1,
				"allow_on_submit": 1,
				"insert_after": "fm_ffm_uuid",
			},
			{
				"fieldname": "fm_ffm_pac_msg",
				"fieldtype": "Small Text",
				"label": "Último mensaje PAC",
				"read_only": 1,
				"allow_on_submit": 1,
				"insert_after": "fm_ffm_fecha",
			},
			{
				"fieldname": "fm_ffm_col_break",
				"fieldtype": "Column Break",
				"insert_after": "fm_ffm_pac_msg",
			},
			{
				"fieldname": "fm_ffm_open_btn",
				"fieldtype": "Button",
				"label": "Abrir Factura Fiscal MX",
				"insert_after": "fm_ffm_col_break",
			},
		]
	}
	create_custom_fields(fields, update=True)


def run_once_now():
	apply_customization()
	frappe.db.commit()
