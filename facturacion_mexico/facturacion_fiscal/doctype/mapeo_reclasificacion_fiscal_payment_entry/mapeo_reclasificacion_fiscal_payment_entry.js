frappe.ui.form.on("Mapeo Reclasificacion Fiscal Payment Entry", {
	refresh(frm) {
		_set_account_filters(frm);
	},
	company(frm) {
		frm.set_value("cuenta_origen", null);
		frm.set_value("cuenta_destino", null);
		_set_account_filters(frm);
	},
});

function _set_account_filters(frm) {
	const base = { account_type: "Tax", is_group: 0, disabled: 0 };
	const filters = frm.doc.company ? { ...base, company: frm.doc.company } : base;
	frm.set_query("cuenta_origen", () => ({ filters }));
	frm.set_query("cuenta_destino", () => ({ filters }));
}
