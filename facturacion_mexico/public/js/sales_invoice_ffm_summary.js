frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		setTimeout(() => update_ffm_summary(frm), 0);
	},
	fm_factura_fiscal_mx(frm) {
		update_ffm_summary(frm);
	},
	fm_ffm_open_btn(frm) {
		const target = frm.doc.fm_factura_fiscal_mx;
		if (target) frappe.set_route("Form", "Factura Fiscal Mexico", target);
		else
			frappe.show_alert({
				message: __("No hay documento fiscal vinculado."),
				indicator: "orange",
			});
	},
});

function update_ffm_summary(frm) {
	const link = frm.doc.fm_factura_fiscal_mx;
	if (!link) {
		clear_ffm_summary(frm);
		return;
	}

	frappe
		.call({
			method: "facturacion_mexico.api.ffm_summary.get_ffm_summary",
			args: { ffm_name: link },
		})
		.then((r) => {
			const m = (r && r.message) || {};
			frm.set_value("fm_ffm_estado", m.estado || "");
			frm.set_value("fm_ffm_numero", m.folio || "");
			frm.set_value("fm_ffm_uuid", m.uuid || "");
			frm.set_value("fm_ffm_fecha", m.fecha || "");
			frm.set_value("fm_ffm_pac_msg", m.pac_msg || "");
		})
		.catch(() => clear_ffm_summary(frm));
}

function clear_ffm_summary(frm) {
	["fm_ffm_estado", "fm_ffm_numero", "fm_ffm_uuid", "fm_ffm_fecha", "fm_ffm_pac_msg"].forEach(
		(f) => {
			if (frm.get_field(f)) frm.set_value(f, null);
		}
	);
}
