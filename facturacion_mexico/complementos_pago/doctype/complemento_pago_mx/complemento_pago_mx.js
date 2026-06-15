/**
 * Complemento Pago MX — UI
 * Botones y mensajes controlados por fiscal_state centralizado.
 */

frappe.ui.form.on("Complemento Pago MX", {
	refresh(frm) {
		_hide_standard_actions(frm);
		_setup_status_indicators(frm);
		_setup_pe_link(frm);

		// Estado fiscal centralizado — una sola llamada controla todos los botones y mensajes
		frappe.call({
			method: "facturacion_mexico.fiscal_state.api.get_fiscal_ui_state",
			args: { doctype: "Complemento Pago MX", name: frm.doc.name },
			callback(r) {
				const { actions = {}, messages = [] } = r.message || {};
				_apply_buttons(frm, actions);
				_apply_messages(frm, messages);
			},
		});
	},
});

// ── Aplicar botones desde fiscal_state ─────────────────────────────────────

function _apply_buttons(frm, actions) {
	if (actions.can_stamp) _setup_timbrar_btn(frm);
	if (actions.can_retry_cancel) _setup_revisar_estatus_btn(frm);
	if (actions.can_cancel) _setup_cancelar_btn(frm);
	if (actions.can_download_xml || actions.can_download_pdf) _setup_descargar_btn(frm);
	if (actions.can_send_email) _setup_email_btn(frm);
}

// ── Aplicar mensajes desde fiscal_state ────────────────────────────────────

function _apply_messages(frm, messages) {
	frm.dashboard.clear_headline();
	if (!messages || !messages.length) return;
	const level_color = { success: "green", warning: "orange", error: "red", info: "blue" };
	const primary = messages[0];
	frm.dashboard.set_headline_alert(primary.text, level_color[primary.level] || "grey");
}

// ── Indicador de color de estado (cosmético, sin lógica fiscal) ────────────

function _status_color(status) {
	switch (status) {
		case "Timbrado":
			return "green";
		case "Pendiente Cancelación":
			return "orange";
		case "Cancelado":
			return "red";
		case "Error":
			return "red";
		case "Pendiente":
			return "grey";
		default:
			return "grey";
	}
}

function _setup_status_indicators(frm) {
	const status = frm.doc.status;
	if (!status) return;
	const color = _status_color(status);
	const $val = frm.fields_dict.status?.$wrapper?.find(".control-value");
	if ($val && $val.length) {
		$val.html(
			`<span class="indicator ${color}" style="margin-right:4px; vertical-align:middle;"></span>` +
				`<strong>${frappe.utils.escape_html(status)}</strong>`
		);
	}
}

// ── Ocultar acciones estándar de Frappe (sin cambio) ───────────────────────

function _hide_standard_actions(frm) {
	if (frm.page && frm.page.btn_primary) frm.page.btn_primary.addClass("hidden");
	frm.page.wrapper.find('.btn[data-label="Submit"]').addClass("hidden");
	if (frm.page && frm.page.btn_cancel) frm.page.btn_cancel.addClass("hidden");
	frm.page.wrapper.find('.btn[data-label="Cancel"]').addClass("hidden");
	frm.page.wrapper
		.find('.btn[data-label="Amend"], .btn[data-label="Corregir"]')
		.addClass("hidden");
	frm.page.wrapper
		.find(
			'.menu-items .dropdown-item:contains("Amend"), .menu-items .dropdown-item:contains("Corregir")'
		)
		.addClass("disabled")
		.css("pointer-events", "none");
}

// ── Botones — callbacks sin cambio ─────────────────────────────────────────

function _setup_pe_link(frm) {
	if (frm.doc.payment_entry) {
		frm.add_custom_button(__("Ver Payment Entry"), function () {
			frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry);
		}).addClass("btn-info");
	}
}

function _setup_timbrar_btn(frm) {
	frm.add_custom_button(__("Timbrar Complemento de Pago"), function () {
		frappe.confirm(
			__(
				"¿Timbrar este Complemento de Pago con FacturAPI? Esta operación enviará el CFDI al SAT."
			),
			function () {
				frappe.call({
					method: "facturacion_mexico.complementos_pago.api.timbrar_complemento_pago",
					args: { complemento_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Enviando a FacturAPI..."),
					callback: function (r) {
						if (r.message && r.message.uuid) {
							frappe.show_alert(
								{
									message: __("Complemento timbrado. UUID: {0}", [
										r.message.uuid,
									]),
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

function _setup_revisar_estatus_btn(frm) {
	frm.add_custom_button(__("Revisar Estatus Cancelación"), function () {
		frappe.call({
			method: "facturacion_mexico.complementos_pago.api.revisar_estatus_cancelacion_complemento",
			args: { complemento_name: frm.doc.name },
			callback: function (r) {
				if (r.message) {
					const st = r.message.status;
					const color =
						st === "Cancelado" ? "red" : st === "Timbrado" ? "green" : "orange";
					frappe.show_alert(
						{ message: __("Estado actualizado: {0}", [st]), indicator: color },
						6
					);
					frm.reload_doc();
				}
			},
		});
	}).addClass("btn-warning");
}

function _setup_cancelar_btn(frm) {
	// Rol controlado por DocPerm de Frappe (configurable por cliente)
	if (!frappe.model.can_cancel("Complemento Pago MX")) return;

	frm.add_custom_button(__("Cancelar Complemento"), function () {
		frappe.prompt(
			[
				{
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
				},
			],
			function (values) {
				const motivo = values.motivo.split(" - ")[0];
				frappe.confirm(
					__("¿Solicitar cancelación del Complemento de Pago ante el SAT? Motivo: {0}", [
						motivo,
					]),
					function () {
						frappe.call({
							method: "facturacion_mexico.complementos_pago.api.cancelar_complemento_pago",
							args: { complemento_name: frm.doc.name, motivo: motivo },
							callback: function (r) {
								if (r.message) {
									const st = r.message.status;
									const color = st === "Cancelado" ? "green" : "orange";
									frappe.show_alert(
										{ message: __("Estado: {0}", [st]), indicator: color },
										6
									);
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

function _setup_email_btn(frm) {
	frm.add_custom_button(
		__("Enviar por email"),
		async () => {
			try {
				const r = await frappe.call({
					method: "facturacion_mexico.complementos_pago.api.action_send_email_complemento",
					args: { complemento_name: frm.doc.name, to: null },
				});
				const res = r && r.message;
				if (res && res.sent) {
					frappe.msgprint({
						message: __("Complemento enviado a: {0}", [res.to]),
						indicator: "green",
					});
				} else if (res && res.reason === "no-recipient") {
					frappe.msgprint({
						message: __(
							"No se envió: no hay destinatario en el Payment Entry ni en el cliente."
						),
						indicator: "orange",
					});
				} else {
					frappe.msgprint({
						message: __("No se pudo enviar: {0}", [(res && res.error) || ""]),
						indicator: "red",
					});
				}
			} catch (e) {
				frappe.msgprint({ message: __(String(e)), indicator: "red" });
			}
		},
		__("Comprobantes")
	);
}

function _setup_descargar_btn(frm) {
	frm.add_custom_button(__("Descargar PDF+XML"), function () {
		frappe.call({
			method: "facturacion_mexico.complementos_pago.api.descargar_archivos_complemento",
			args: { complemento_name: frm.doc.name },
			callback: function (r) {
				if (r.message && r.message.success) {
					frappe.show_alert(
						{ message: __("PDF y XML adjuntados correctamente."), indicator: "green" },
						5
					);
					frm.reload_doc();
				} else {
					frappe.show_alert(
						{
							message: __("Error al descargar archivos. Revisar Error Log."),
							indicator: "red",
						},
						6
					);
				}
			},
		});
	});
}
