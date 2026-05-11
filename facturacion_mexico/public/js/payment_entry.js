/**
 * Payment Entry — Complemento de Pago MX
 * Botones y guards controlados por fiscal_state centralizado.
 */

frappe.ui.form.on("Payment Entry", {
	refresh(frm) {
		_hide_technical_checkboxes(frm);
		_inject_complemento_summary(frm); // widget HTML — display rico, conservado

		if (frm.doc.docstatus !== 1) return;

		// Estado fiscal centralizado — una sola llamada controla botones y cancel guard
		frappe.call({
			method: "facturacion_mexico.fiscal_state.api.get_fiscal_ui_state",
			args: { doctype: "Payment Entry", name: frm.doc.name },
			callback(r) {
				if (!r.message) return;
				const { actions, messages, facts } = r.message;
				_apply_buttons(frm, actions);
				_apply_cancel_guard(frm, facts);
				_apply_messages(frm, messages);
			},
		});
	},
	fm_complemento_pago(frm) {
		_inject_complemento_summary(frm);
	},
});

// ── Aplicar botones desde fiscal_state ─────────────────────────────────────

function _apply_buttons(frm, actions) {
	if (actions.can_view_complement) {
		frm.add_custom_button(__("Ver Complemento de Pago"), function () {
			frappe.set_route("Form", "Complemento Pago MX", frm.doc.fm_complemento_pago);
		}).addClass("btn-info");
	}

	if (actions.can_create_complement) {
		frm.add_custom_button(__("Crear Complemento de Pago"), function () {
			frappe.confirm(__("¿Crear Complemento de Pago para este Payment Entry?"), function () {
				frappe.call({
					method: "facturacion_mexico.complementos_pago.api.crear_complemento_pago_desde_pe",
					args: { payment_entry_name: frm.doc.name },
					callback: function (r) {
						if (r.message && r.message.complemento_name) {
							frappe.show_alert(
								{
									message: __("Complemento {0} creado correctamente.", [
										r.message.complemento_name,
									]),
									indicator: "green",
								},
								5
							);
							frm.reload_doc();
						}
					},
				});
			});
		}).addClass("btn-primary");
	}
}

// ── Guard de cancelación desde fiscal_state ────────────────────────────────

function _apply_cancel_guard(frm, facts) {
	if (!facts.has_active_complement) return;
	_hide_cancel_button(frm);
	// prettier-ignore
	frm.dashboard.set_headline_alert(__("Este Payment Entry tiene un Complemento de Pago fiscal activo ({0}). Cancele primero el complemento antes de cancelar el pago.", [frm.doc.fm_complemento_pago]), "orange");
}

// ── Aplicar mensajes desde fiscal_state ────────────────────────────────────

function _apply_messages(frm, messages) {
	if (!messages || !messages.length) return;
	// Solo mostrar si no hay ya un headline del cancel guard
	if (frm.doc.fm_complemento_pago) return; // el widget ya muestra el estado
	frm.dashboard.clear_headline();
	const level_color = { success: "green", warning: "orange", error: "red", info: "blue" };
	const primary = messages[0];
	frm.dashboard.set_headline_alert(primary.text, level_color[primary.level] || "grey");
}

// ── Funciones sin cambio ───────────────────────────────────────────────────

function _hide_technical_checkboxes(frm) {
	frm.set_df_property("fm_require_complement", "hidden", 1);
	frm.set_df_property("fm_complement_generated", "hidden", 1);
}

function _hide_cancel_button(frm) {
	if (frm.page && frm.page.btn_cancel) frm.page.btn_cancel.addClass("hidden");
	frm.page.wrapper
		.find('button.btn-danger, .btn[data-label="Cancel"], button:contains("Cancel")')
		.addClass("hidden");
}

function _inject_complemento_summary(frm) {
	const comp = frm.doc.fm_complemento_pago;
	const wrapper = frm.fields_dict.fm_comp_summary_html?.$wrapper;
	if (!wrapper) return;

	if (!comp) {
		if (frm.doc.docstatus !== 1) return;
		const si_names = (frm.doc.references || [])
			.filter(
				(ref) => ref.reference_doctype === "Sales Invoice" && flt(ref.allocated_amount) > 0
			)
			.map((ref) => ref.reference_name);

		if (!si_names.length) {
			wrapper.html(
				`<div class="text-muted" style="padding:8px; font-style:italic;">Sin facturas vinculadas.</div>`
			);
			return;
		}

		frappe.db
			.get_list("Sales Invoice", {
				filters: [
					["name", "in", si_names],
					["fm_es_ppd", "=", 1],
				],
				fields: ["name"],
				limit: 1,
			})
			.then((rows) => {
				if (!rows.length) {
					wrapper.html(
						`<div style="padding:8px; color:#6c757d;">` +
							`<span class="indicator grey" style="margin-right:6px;"></span>` +
							`<strong>Pago PUE</strong> — No requiere Complemento de Pago.</div>`
					);
				} else {
					wrapper.html(
						`<div style="padding:8px; color:#e67e22;">` +
							`<span class="indicator orange" style="margin-right:6px;"></span>` +
							`<strong>Complemento de Pago pendiente</strong> — Use el botón "Crear Complemento de Pago".</div>`
					);
				}
			});
		return;
	}

	wrapper.html(
		`<div class="text-muted" style="padding: 8px;"><i class="fa fa-spinner fa-spin"></i> Cargando...</div>`
	);

	frappe
		.call({
			method: "facturacion_mexico.api.complemento_summary.get_complemento_summary",
			args: { complemento_name: comp },
		})
		.then((r) => {
			const d = r.message || {};
			const color = _complemento_status_color(d.status);
			const uuid = d.uuid_sat || "-";
			const fecha = d.fecha_timbrado ? frappe.datetime.str_to_user(d.fecha_timbrado) : "-";
			const serie = d.serie || "-";
			const folio = d.folio || "-";
			const badge = _complemento_status_badge(d.status);

			wrapper.html(`
				<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 13px;">
					<div><strong>Estado SAT:</strong>
						<span class="indicator ${color}" style="margin-left: 4px;">${frappe.utils.escape_html(
				d.status || "-"
			)}</span>
						${badge}
					</div>
					<div><strong>Fecha Timbrado:</strong> ${fecha}</div>
					<div><strong>Serie:</strong> <span style="font-family: monospace;">${frappe.utils.escape_html(
						serie
					)}</span></div>
					<div><strong>Folio:</strong> <span style="font-family: monospace;">${frappe.utils.escape_html(
						folio
					)}</span></div>
					<div style="grid-column: span 2;"><strong>Folio Fiscal (UUID):</strong>
						<span style="font-family: monospace; font-size: 11px; word-break: break-all;">${frappe.utils.escape_html(
							uuid
						)}</span>
					</div>
				</div>
			`);
		})
		.catch(() => {
			wrapper.html(
				`<div class="text-danger" style="padding: 8px;"><i class="fa fa-exclamation-triangle"></i> No fue posible cargar el resumen del complemento.</div>`
			);
		});
}

function _complemento_status_badge(status) {
	switch (status) {
		case "Timbrado":
			return '<span style="margin-left:6px; color:#28a745;">&#10003; Timbrado</span>';
		case "Pendiente Cancelación":
			return '<span style="margin-left:6px; color:#e67e22;">&#9650; Cancelación pendiente</span>';
		case "Cancelado":
			return '<span style="margin-left:6px; color:#c0392b;">&#10007; Cancelado ante SAT</span>';
		default:
			return "";
	}
}

function _complemento_status_color(status) {
	switch (status) {
		case "Timbrado":
			return "green";
		case "Cancelado":
			return "red";
		case "Pendiente Cancelación":
			return "orange";
		case "Error":
			return "red";
		case "Pendiente":
			return "grey";
		default:
			return "grey";
	}
}
