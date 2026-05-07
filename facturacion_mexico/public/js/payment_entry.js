/**
 * Payment Entry — Complemento de Pago MX
 *
 * Muestra botón "Crear Complemento de Pago" cuando el PE cumple las condiciones
 * para generar un complemento PPD: submitido, tipo Receive, con SIs PPD timbradas
 * referenciadas y sin complemento previo.
 */

frappe.ui.form.on("Payment Entry", {
	refresh(frm) {
		_setup_complemento_btn(frm);
		_setup_complemento_cancel_warning(frm);
		_inject_complemento_summary(frm);
	},
	fm_complemento_pago(frm) {
		_inject_complemento_summary(frm);
	},
});

function _setup_complemento_cancel_warning(frm) {
	if (frm.doc.docstatus !== 1) return;
	if (!frm.doc.fm_complemento_pago) return;

	frappe.db.get_value("Complemento Pago MX", frm.doc.fm_complemento_pago, "status").then((r) => {
		const st = r.message && r.message.status;
		if (st && st !== "Cancelado") {
			_hide_cancel_button(frm);
			frm.dashboard.set_headline_alert(
				__(
					"Este Payment Entry tiene un Complemento de Pago fiscal activo ({0}) en estado '{1}'. " +
						"Cancele primero el complemento antes de cancelar el pago.",
					[frm.doc.fm_complemento_pago, st]
				),
				"orange"
			);
		}
	});
}

function _inject_complemento_summary(frm) {
	const comp = frm.doc.fm_complemento_pago;
	const wrapper = frm.fields_dict.fm_comp_summary_html?.$wrapper;
	if (!wrapper) return;

	if (!comp) {
		wrapper.html(
			`<div class="text-muted" style="padding: 8px; font-style: italic;">Sin Complemento de Pago vinculado.</div>`
		);
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

function _hide_cancel_button(frm) {
	if (frm.page && frm.page.btn_cancel) frm.page.btn_cancel.addClass("hidden");
	frm.page.wrapper
		.find('button.btn-danger, .btn[data-label="Cancel"], button:contains("Cancel")')
		.addClass("hidden");
}

function _setup_complemento_btn(frm) {
	// Solo PE submitido
	if (frm.doc.docstatus !== 1) return;

	// Solo cobros (Receive)
	if (frm.doc.payment_type !== "Receive") return;

	// Ya tiene complemento — mostrar enlace de navegación en lugar de botón
	if (frm.doc.fm_complemento_pago) {
		frm.add_custom_button(__("Ver Complemento de Pago"), function () {
			frappe.set_route("Form", "Complemento Pago MX", frm.doc.fm_complemento_pago);
		}).addClass("btn-info");
		return;
	}

	// Verificar si hay al menos una SI PPD timbrada referenciada
	const tiene_ppd = (frm.doc.references || []).some(
		(ref) => ref.reference_doctype === "Sales Invoice" && flt(ref.allocated_amount) > 0
	);

	if (!tiene_ppd) return;

	// Mostrar botón
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
