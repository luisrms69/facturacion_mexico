frappe.ui.form.on("Addenda Configuration", {
	addenda_type(frm) {
		if (frm.doc.addenda_type) {
			_load_field_definitions(frm);
		}
	},

	refresh(frm) {
		// Si ya hay addenda_type pero los labels están vacíos, cargar labels silenciosamente
		if (frm.doc.addenda_type && frm.doc.field_values && frm.doc.field_values.length > 0) {
			const has_empty_labels = frm.doc.field_values.some((r) => !r.field_label);
			if (has_empty_labels) {
				_fill_missing_labels(frm);
			}
		}
	},
});

function _fill_missing_labels(frm) {
	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Addenda Type", name: frm.doc.addenda_type },
		callback(r) {
			if (!r.message) return;
			const defs = r.message.field_definitions || [];
			const def_map = {};
			defs.forEach((d) => {
				def_map[d.name] = d.field_label || d.field_name;
			});
			frm.doc.field_values.forEach((row) => {
				if (!row.field_label && row.field_definition) {
					frappe.model.set_value(
						row.doctype,
						row.name,
						"field_label",
						def_map[row.field_definition] || row.field_definition
					);
				}
			});
			frm.refresh_field("field_values");
		},
	});
}

function _load_field_definitions(frm) {
	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Addenda Type", name: frm.doc.addenda_type },
		callback(r) {
			if (!r.message) return;
			const defs = r.message.field_definitions || [];
			if (!defs.length) return;

			const has_values =
				frm.doc.field_values &&
				frm.doc.field_values.some(
					(row) => row.field_value && row.field_value.trim() !== ""
				);

			if (has_values) {
				frappe.confirm(
					__("¿Recargar campos? Se perderán los valores ya capturados."),
					() => _populate_fields(frm, defs)
				);
			} else {
				_populate_fields(frm, defs);
			}
		},
	});
}

function _populate_fields(frm, defs) {
	frm.clear_table("field_values");
	defs.forEach((fd) => {
		const row = frm.add_child("field_values");
		row.field_definition = fd.name;
		row.field_label = fd.field_label || fd.field_name;
		row.field_value = fd.default_value || "";
		row.is_required = fd.is_mandatory || 0;
	});
	frm.refresh_field("field_values");
	frappe.show_alert({
		message: __('{0} campos cargados desde "{1}"', [defs.length, frm.doc.addenda_type]),
		indicator: "green",
	});
}
