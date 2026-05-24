frappe.ui.form.on("Configuracion CFDI Recibidos", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Generar Template de Impuestos"), () => {
				_generar_template(frm);
			});
		}
	},
});

function _generar_template(frm) {
	frappe.confirm(
		__(
			"¿Generar o actualizar el Purchase Taxes and Charges Template con las reglas actuales?"
		),
		() => {
			frappe.call({
				method: "facturacion_mexico.cfdi_recibidos.services.wizard_cfdi_recibidos.generar_template_impuestos",
				args: { config_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Generando template de impuestos..."),
				callback(r) {
					if (r.exc) return;
					const result = r.message;
					frm.reload_doc();
					if (result.warnings && result.warnings.length) {
						const warning_list = result.warnings.map((w) => `<li>${w}</li>`).join("");
						frappe.msgprint({
							title: __("Template generado con advertencias"),
							message: `<p>${result.message}</p><ul>${warning_list}</ul>`,
							indicator: "orange",
						});
					} else {
						frappe.show_alert({
							message: result.message,
							indicator: "green",
						});
					}
				},
			});
		}
	);
}
