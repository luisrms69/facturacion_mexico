frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		inject_ffm_summary(frm);
		// Configurar botón una sola vez
		if (frm.fields_dict.fm_ffm_open_btn && frm.fields_dict.fm_ffm_open_btn.$input) {
			frm.fields_dict.fm_ffm_open_btn.$input.off("click").on("click", () => {
				const ffm = frm.doc.fm_factura_fiscal_mx;
				if (ffm) frappe.set_route("Form", "Factura Fiscal Mexico", ffm);
				else frappe.msgprint("No hay Factura Fiscal MX vinculada.");
			});
		}
	},
	fm_factura_fiscal_mx(frm) {
		inject_ffm_summary(frm);
	},
});

function inject_ffm_summary(frm) {
	const ffm = frm.doc.fm_factura_fiscal_mx;
	const wrapper = frm.fields_dict.fm_ffm_summary_html?.$wrapper;

	if (!wrapper) {
		// Fallback: si no existe el campo HTML, usar el botón como antes
		if (frm.fields_dict.fm_ffm_open_btn) {
			frm.fields_dict.fm_ffm_open_btn.$input.off("click").on("click", () => {
				const target = frm.doc.fm_factura_fiscal_mx;
				if (target) frappe.set_route("Form", "Factura Fiscal Mexico", target);
				else
					frappe.show_alert({
						message: __("No hay documento fiscal vinculado."),
						indicator: "orange",
					});
			});
		}
		return;
	}

	if (!ffm) {
		wrapper.html(
			`<div class="text-muted" style="padding: 8px; font-style: italic;">Sin Factura Fiscal vinculada.</div>`
		);
		return;
	}

	// Mostrar loading
	wrapper.html(`<div class="text-muted" style="padding: 8px;">
		<i class="fa fa-spinner fa-spin"></i> Cargando información fiscal...
	</div>`);

	frappe
		.call({
			method: "facturacion_mexico.api.ffm_summary.get_ffm_summary",
			args: { ffm_name: ffm },
		})
		.then((r) => {
			const d = r.message || {};
			// Renderizamos en HTML sin tocar el doc → no aparece "Not Saved"
			const estado_color = get_estado_color(d.estado);

			wrapper.html(`
				<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 13px;">
					<div><strong>Estado CFDI:</strong>
						<span class="indicator ${estado_color}" style="margin-left: 4px;">${frappe.utils.escape_html(
				d.estado || "-"
			)}</span>
					</div>
					<div><strong>Serie y Folio:</strong>
						<span style="font-family: monospace;">${frappe.utils.escape_html(d.folio || "-")}</span>
					</div>
					<div style="grid-column: span 2;"><strong>UUID:</strong>
						<span style="font-family: monospace; font-size: 11px; word-break: break-all;">${frappe.utils.escape_html(
							d.uuid || "-"
						)}</span>
					</div>
					<div><strong>Fecha Timbrado:</strong>
						${d.fecha ? frappe.datetime.str_to_user(d.fecha) : "-"}
					</div>
					<div><strong>Estado PAC:</strong>
						${
							d.pac_msg
								? `<span class="text-muted">${frappe.utils.escape_html(
										d.pac_msg.substring(0, 50)
								  )}${d.pac_msg.length > 50 ? "..." : ""}</span>`
								: "OK"
						}
					</div>
				</div>
			`);
		})
		.catch(() => {
			wrapper.html(`<div class="text-danger" style="padding: 8px;">
				<i class="fa fa-exclamation-triangle"></i> No fue posible cargar el resumen fiscal.
			</div>`);
		});
}

function get_estado_color(estado) {
	switch (estado) {
		case "TIMBRADO":
			return "green";
		case "CANCELADO":
			return "red";
		case "PENDIENTE_CANCELACION":
			return "orange";
		case "ERROR":
			return "red";
		case "PROCESANDO":
			return "blue";
		case "BORRADOR":
			return "grey";
		default:
			return "grey";
	}
}

function show_pac_status_dialog(resp) {
	const is_error = !resp || resp.ok === false;
	const title = is_error ? __("Timbrado rechazado por PAC") : __("Timbrado exitoso");
	const msg = frappe.utils.escape_html(
		(resp && (resp.error_message || resp.message)) ||
			(is_error ? __("Error desconocido del PAC") : __("Factura timbrada correctamente"))
	);

	// Normaliza el "estado de sincronización"
	const sync_state = is_error ? "ERROR" : "OK";

	const logLink =
		resp && resp.response_log
			? `<br><br><a class="btn btn-sm btn-default" href="#Form/FacturAPI Response Log/${
					resp.response_log
			  }">
			 ${__("Ver registro de respuesta")}
		   </a>`
			: "";

	const body = `
		<div class="alert alert-${is_error ? "danger" : "success"}" role="alert" style="margin-top:8px">
			<strong>${title}</strong><br>${msg}${logLink}
			<div style="margin-top:6px"><small>${__(
				"Estado de Sincronización"
			)}: <b>${sync_state}</b></small></div>
		</div>`;

	frappe.msgprint({
		title,
		indicator: is_error ? "red" : "green",
		message: body,
		wide: true,
	});
}
