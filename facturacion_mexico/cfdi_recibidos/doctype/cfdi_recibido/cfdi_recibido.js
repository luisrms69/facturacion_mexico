// Form controller — CFDI Recibido
// List view settings: cfdi_recibido_list.js

frappe.ui.form.on("CFDI Recibido", {
	refresh(frm) {
		_set_item_code_query(frm);
		if (!frm.is_new() && frm.doc.status === "Falta clasificación") {
			_add_classify_button(frm);
		}
	},
});

frappe.ui.form.on("CFDI Recibido Concepto", {
	item_code(frm, cdt, cdn) {
		_derive_item_group(frm, cdt, cdn);
	},
});

function _set_item_code_query(frm) {
	// Solo ítems de compra, no de inventario, no de venta, grupo hoja bajo "Gastos"
	frm.set_query("item_code", "conceptos", function () {
		return {
			query: "facturacion_mexico.cfdi_recibidos.queries.get_expense_items",
		};
	});
}

function _add_classify_button(frm) {
	frm.add_custom_button(__("Clasificar automáticamente"), () => {
		frappe.call({
			method: "facturacion_mexico.cfdi_recibidos.api.classify_all_concepts",
			args: { cfdi_recibido: frm.doc.name },
			freeze: true,
			freeze_message: __("Clasificando conceptos..."),
			callback(r) {
				if (!r.message) return;
				const { actualizados, sin_match, nuevo_status } = r.message;
				frappe.msgprint({
					title: __("Clasificación automática"),
					message: `
						<p>${__("Conceptos clasificados")}: <strong>${actualizados}</strong></p>
						<p>${__("Sin coincidencia")}: <strong>${sin_match}</strong></p>
						<p>${__("Estado")}: <strong>${nuevo_status}</strong></p>
					`,
					indicator: sin_match > 0 ? "orange" : "green",
				});
				frm.reload_doc();
			},
		});
	});
}

function _derive_item_group(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row.item_code) {
		frappe.model.set_value(cdt, cdn, "item_group", "");
		frappe.model.set_value(cdt, cdn, "item_resolution", "");
		return;
	}
	frappe.db.get_value("Item", row.item_code, "item_group", (r) => {
		if (r && r.item_group) {
			frappe.model.set_value(cdt, cdn, "item_group", r.item_group);
		}
		frappe.model.set_value(cdt, cdn, "item_resolution", "Manual");
	});
}
