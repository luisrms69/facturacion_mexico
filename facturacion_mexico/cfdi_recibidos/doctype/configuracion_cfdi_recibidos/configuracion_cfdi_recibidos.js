frappe.ui.form.on("Configuracion CFDI Recibidos", {
	onload(frm) {
		_set_cuenta_filter(frm);
		if (frm.is_new() && !frm.doc.reglas_impuesto?.length) {
			frappe.call({
				method: "facturacion_mexico.cfdi_recibidos.services.wizard_cfdi_recibidos.get_opciones_impuesto_iniciales",
				callback(r) {
					if (r.exc || !r.message?.length) return;
					r.message.forEach((opcion) => {
						const row = frappe.model.add_child(
							frm.doc,
							"Regla Impuesto CFDI Recibido",
							"reglas_impuesto"
						);
						Object.assign(row, {
							impuesto_sat: opcion.impuesto_sat,
							tipo_factor: opcion.tipo_factor,
							tasa_cuota: opcion.tasa_cuota,
							descripcion: opcion.descripcion,
							es_retencion: opcion.es_retencion,
							activo: 0,
						});
					});
					frm.refresh_field("reglas_impuesto");
				},
			});
		}
	},
	refresh(frm) {
		_set_cuenta_filter(frm);
		if (!frm.is_new()) {
			frm.add_custom_button(__("Generar Template de Impuestos"), () => {
				_generar_template(frm);
			});
			frm.add_custom_button(__("Ver Templates de Impuestos"), () => {
				frappe.set_route("List", "Purchase Taxes and Charges Template", {
					company: frm.doc.company,
				});
			});
		}
	},
	company(frm) {
		_set_cuenta_filter(frm);
	},
});

frappe.ui.form.on("Regla Impuesto CFDI Recibido", {
	cuenta_impuesto(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.cuenta_impuesto) {
			frappe.model.set_value(cdt, cdn, "activo", 1);
		}
	},
});

function _set_cuenta_filter(frm) {
	frm.set_query("cuenta_impuesto", "reglas_impuesto", function () {
		return {
			filters: {
				account_type: "Tax",
				company: frm.doc.company || "",
				is_group: 0,
			},
		};
	});
}

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
