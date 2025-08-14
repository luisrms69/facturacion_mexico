frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		// Solo interesa cuando está submitida
		if (frm.doc.docstatus !== 1) return;
		// Consulta si se puede cancelar
		frappe
			.call({
				method: "facturacion_mexico.validaciones.sales_invoice_cancel_guard.can_cancel_sales_invoice",
				args: { si_name: frm.doc.name },
			})
			.then((r) => {
				const res = r.message || {};
				if (!res.allowed) {
					hide_cancel_button(frm);
					// indicador opcional
					frm.dashboard &&
						frm.dashboard.set_headline_alert(
							__("Cancelación bloqueada: {0}", [
								res.reason || "Razón no especificada",
							]),
							"orange"
						);
				}
			})
			.catch(() => {
				// ante error, mejor no ocultar para no bloquear indebidamente; el server-hook sigue protegiendo
			});
	},
});

function hide_cancel_button(frm) {
	// Frappe cambia selectores entre versiones; cubrimos varias variantes.
	if (frm.page && frm.page.btn_cancel) {
		frm.page.btn_cancel.addClass("hidden");
	}
	// Menú secundario / botón rojo
	frm.page.wrapper
		.find('button.btn-danger, .btn[data-label="Cancel"], button:contains("Cancel")')
		.addClass("hidden");
	// También el item del menú ... si existiera
	frm.page.wrapper
		.find('.menu-items .dropdown-item:contains("Cancel")')
		.addClass("disabled")
		.css("pointer-events", "none");
}
