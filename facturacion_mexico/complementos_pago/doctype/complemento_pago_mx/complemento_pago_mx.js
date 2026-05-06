/**
 * Complemento Pago MX — UI
 * Botón de timbrado manual (Bloque 3E).
 */

frappe.ui.form.on("Complemento Pago MX", {
	refresh(frm) {
		_hide_standard_actions(frm);
		_setup_status_indicators(frm);
		_setup_timbrar_btn(frm);
		_setup_cancelar_btn(frm);
		_setup_pe_link(frm);
	},
});

function _status_color(status) {
	switch (status) {
		case "Timbrado":            return "green";
		case "Pendiente Cancelación": return "orange";
		case "Cancelado":           return "red";
		case "Error":               return "red";
		case "Pendiente":           return "grey";
		default:                    return "grey";
	}
}

function _setup_status_indicators(frm) {
	const status = frm.doc.status;
	if (!status) return;
	const color = _status_color(status);

	// Cuerpo: inyecta dot de color junto al valor del campo Estado
	// El encabezado lo maneja Frappe nativamente via states + status_field
	const $val = frm.fields_dict.status?.$wrapper?.find(".control-value");
	if ($val && $val.length) {
		$val.html(
			`<span class="indicator ${color}" style="margin-right:4px; vertical-align:middle;"></span>` +
			`<strong>${frappe.utils.escape_html(status)}</strong>`
		);
	}
}

function _setup_pe_link(frm) {
	if (frm.doc.payment_entry) {
		frm.add_custom_button(__("Ver Payment Entry"), function () {
			frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry);
		}).addClass("btn-info");
	}
}

function _setup_timbrar_btn(frm) {
	if (frm.doc.docstatus !== 0) return;
	if (!["Pendiente", "Error"].includes(frm.doc.status)) return;
	if (frm.doc.uuid_sat) return;

	frm.add_custom_button(__("Timbrar Complemento de Pago"), function () {
		frappe.confirm(
			__("¿Timbrar este Complemento de Pago con FacturAPI? Esta operación enviará el CFDI al SAT."),
			function () {
				frappe.call({
					method: "facturacion_mexico.complementos_pago.api.timbrar_complemento_pago",
					args: { complemento_name: frm.doc.name },
					callback: function (r) {
						if (r.message && r.message.uuid) {
							frappe.show_alert(
								{
									message: __("Complemento timbrado. UUID: {0}", [r.message.uuid]),
									indicator: "green",
								},
								8
							);
							frm.reload_doc();
						}
					},
				});
			}
		);
	}).addClass("btn-primary");
}

function _hide_standard_actions(frm) {
	// Submit estándar — el timbrado llama submit() internamente
	if (frm.page && frm.page.btn_primary) frm.page.btn_primary.addClass("hidden");
	frm.page.wrapper.find('.btn[data-label="Submit"]').addClass("hidden");
	// Cancel estándar de Frappe — la cancelación va por API cancelar_complemento_pago
	if (frm.page && frm.page.btn_cancel) frm.page.btn_cancel.addClass("hidden");
	frm.page.wrapper.find('.btn[data-label="Cancel"]').addClass("hidden");
}

function _setup_cancelar_btn(frm) {
	if (frm.doc.docstatus !== 1) return;
	if (frm.doc.status !== "Timbrado") return;

	frm.add_custom_button(__("Cancelar Complemento"), function () {
		frappe.prompt(
			[{
				label: __("Motivo de Cancelación SAT"),
				fieldname: "motivo",
				fieldtype: "Select",
				options: [
					"02 - Comprobante emitido con errores sin relación",
					"03 - No se llevó a cabo la operación",
					"04 - Operación nominativa relacionada en factura global",
				],
				default: "02 - Comprobante emitido con errores sin relación",
				reqd: 1,
			}],
			function (values) {
				const motivo = values.motivo.split(" - ")[0];
				frappe.confirm(
					__("¿Solicitar cancelación del Complemento de Pago ante el SAT? Motivo: {0}", [motivo]),
					function () {
						frappe.call({
							method: "facturacion_mexico.complementos_pago.api.cancelar_complemento_pago",
							args: { complemento_name: frm.doc.name, motivo: motivo },
							callback: function (r) {
								if (r.message) {
									const st = r.message.status;
									const color = st === "Cancelado" ? "green" : "orange";
									frappe.show_alert({ message: __("Estado: {0}", [st]), indicator: color }, 6);
									frm.reload_doc();
								}
							},
						});
					}
				);
			},
			__("Cancelar Complemento de Pago"),
			__("Solicitar")
		);
	}).addClass("btn-danger");

}
