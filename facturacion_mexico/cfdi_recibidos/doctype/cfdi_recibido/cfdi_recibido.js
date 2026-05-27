// Form controller — CFDI Recibido
// List view settings: cfdi_recibido_list.js

frappe.ui.form.on("CFDI Recibido", {
	refresh(frm) {
		_set_item_group_query(frm);
	},
});

function _set_item_group_query(frm) {
	// item_group en conceptos: solo hojas (is_group=0) bajo el grupo "Gastos"
	frm.set_query("item_group", "conceptos", function () {
		return {
			query: "facturacion_mexico.cfdi_recibidos.queries.get_expense_item_groups",
		};
	});
}
