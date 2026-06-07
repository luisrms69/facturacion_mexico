/**
 * Widget E-Receipt para Sales Invoice.
 * Muestra estado, self_invoice_url y datos del CFDI generado
 * leyendo desde EReceipt MX — sin copiar UUID ni folio en la SI.
 */

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		inject_ereceipt_summary(frm);
	},
	fm_ereceipt_mx(frm) {
		inject_ereceipt_summary(frm);
	},
});

function inject_ereceipt_summary(frm) {
	const ereceipt_name = frm.doc.fm_ereceipt_mx;
	const wrapper = frm.fields_dict.fm_ereceipt_summary_html?.$wrapper;
	if (!wrapper) return;

	if (!ereceipt_name) {
		wrapper.html("");
		return;
	}

	wrapper.html(
		`<div class="text-muted" style="padding:6px;font-size:12px;">
			<i class="fa fa-spinner fa-spin"></i> Cargando E-Receipt...
		</div>`
	);

	frappe
		.call({
			method: "facturacion_mexico.api.ereceipt_summary.get_ereceipt_summary",
			args: { ereceipt_name },
		})
		.then((r) => {
			const d = r.message || {};
			if (!d.name) {
				wrapper.html("");
				return;
			}
			wrapper.html(render_ereceipt_summary(d, ereceipt_name));
		})
		.catch(() => {
			wrapper.html(
				`<div class="text-danger" style="padding:6px;font-size:12px;">
					<i class="fa fa-exclamation-triangle"></i> No se pudo cargar E-Receipt.
				</div>`
			);
		});
}

function render_ereceipt_summary(d, ereceipt_name) {
	const status = d.status || "";
	const { color, label } = get_status_display(status);

	let detail_html = "";

	if (status === "open") {
		const expiry = d.expires_at
			? frappe.datetime.str_to_user(d.expires_at)
			: __("Sin fecha");
		const url_btn = d.self_invoice_url
			? `<a href="${frappe.utils.escape_html(d.self_invoice_url)}" target="_blank"
				class="btn btn-xs btn-default" style="margin-left:8px;">
				<i class="fa fa-external-link"></i> ${__("Abrir portal")}
			</a>
			<button class="btn btn-xs btn-default" style="margin-left:4px;"
				onclick="navigator.clipboard.writeText('${frappe.utils.escape_html(d.self_invoice_url)}');
					frappe.show_alert('URL copiada');">
				<i class="fa fa-copy"></i> ${__("Copiar URL")}
			</button>`
			: `<span class="text-muted">${__("URL no disponible")}</span>`;
		detail_html = `
			<div style="margin-top:6px;">
				<strong>${__("Portal autofactura:")}</strong> ${url_btn}
			</div>
			<div style="margin-top:4px;">
				<strong>${__("Expira:")}</strong> ${expiry}
			</div>`;
	} else if (status === "invoiced_to_customer") {
		const uuid = d.invoice_uuid
			? `<span style="font-family:monospace;font-size:11px;">${frappe.utils.escape_html(d.invoice_uuid)}</span>`
			: "-";
		detail_html = `
			<div style="margin-top:4px;"><strong>${__("UUID:")}</strong> ${uuid}</div>
			<div style="margin-top:4px;"><strong>${__("Folio:")}</strong>
				${frappe.utils.escape_html(d.invoice_folio || "-")}
			</div>
			<div style="margin-top:4px;"><strong>${__("Facturado:")}</strong>
				${d.invoiced_at ? frappe.datetime.str_to_user(d.invoiced_at) : "-"}
			</div>`;
	} else if (status === "invoiced_globally") {
		const fg_link = d.factura_global_mx
			? `<a href="/app/factura-global-mx/${encodeURIComponent(d.factura_global_mx)}"
				target="_blank">${frappe.utils.escape_html(d.factura_global_mx)}</a>`
			: "-";
		const uuid = d.factura_global_uuid
			? `<span style="font-family:monospace;font-size:11px;">${frappe.utils.escape_html(d.factura_global_uuid)}</span>`
			: "-";
		detail_html = `
			<div style="margin-top:4px;">
				<strong>${__("Factura Global:")}</strong> ${fg_link}
			</div>
			<div style="margin-top:4px;"><strong>${__("UUID Global:")}</strong> ${uuid}</div>`;
	}

	const er_link = `<a href="/app/ereceipt-mx/${encodeURIComponent(ereceipt_name)}"
		target="_blank" style="font-size:11px;">${frappe.utils.escape_html(ereceipt_name)}</a>`;

	return `<div style="padding:8px;background:#f8f9fa;border-radius:4px;font-size:13px;">
		<div>
			<strong>${__("E-Receipt:")}</strong> ${er_link}
			&nbsp;<span class="indicator ${color}" style="margin-left:4px;">${frappe.utils.escape_html(label)}</span>
		</div>
		${detail_html}
	</div>`;
}

function get_status_display(status) {
	const MAP = {
		open: { color: "orange", label: "Abierto" },
		invoiced_to_customer: { color: "green", label: "Autofacturado" },
		invoiced_globally: { color: "green", label: "Factura Global" },
		cancelled: { color: "red", label: "Cancelado" },
		expired: { color: "grey", label: "Expirado" },
	};
	return MAP[status] || { color: "grey", label: status || "Desconocido" };
}
