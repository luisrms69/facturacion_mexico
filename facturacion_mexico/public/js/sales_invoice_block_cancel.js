/* global _check_rfc_and_show_timbrar */
frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		// Solo interesa cuando está submitida
		if (frm.doc.docstatus !== 1) return;

		// Bloquear Create y mostrar aviso si FFM está cancelada fiscalmente
		_block_si_if_ffm_cancelada(frm);

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
				} else {
					frm.dashboard && frm.dashboard.clear_headline(); // limpia "Cancelación bloqueada"
					_check_rfc_and_show_timbrar(frm); // RFC check corre después del clear
				}
			})
			.catch(() => {
				// ante error, mejor no ocultar para no bloquear indebidamente; el server-hook sigue protegiendo
			});

		// Suscribir una sola vez por instancia de formulario al evento de cancelación PAC
		if (!frm._fm_cancel_realtime_bound) {
			frm._fm_cancel_realtime_bound = true;
			frappe.realtime.on("fiscal_status_changed", function (data) {
				if (frm.doc && data.sales_invoice === frm.doc.name) {
					frm.reload_doc();
				}
			});
		}
	},
});

function _block_si_if_ffm_cancelada(frm) {
	const fiscal_status = (frm.doc.fm_fiscal_status || "").toUpperCase();
	if (fiscal_status !== "CANCELADO") return;
	if (!frm.doc.fm_factura_fiscal_mx) return;

	// setTimeout para correr después de que otros scripts (si_post_fiscal_actions)
	// terminen de renderizar y sobrescriban el headline
	setTimeout(() => {
		// Remover solo "Payment" del grupo Create — ERPNext lo agrega con add_custom_button
		frm.remove_custom_button && frm.remove_custom_button(__("Payment"), __("Create"));
		// Fallback por si remove_custom_button no lo elimina completamente
		frm.page.wrapper
			.find(".inner-group-button .dropdown-item, .dropdown-menu .dropdown-item")
			.filter((_, el) => $(el).text().trim() === __("Payment"))
			.closest("li")
			.hide();

		// Restaurar botón Cancel — FFM cancelada = SI debe poder cancelarse
		if (frm.page && frm.page.btn_cancel) frm.page.btn_cancel.removeClass("hidden");
		frm.page.wrapper
			.find('button.btn-danger, .btn[data-label="Cancel"], button:contains("Cancel")')
			.removeClass("hidden");

		// Sobreescribir headline con mensaje rojo (último en ejecutar)
		frm.dashboard &&
			frm.dashboard.set_headline_alert(
				// prettier-ignore
				__("Factura cancelada ante el SAT ({0}). No se pueden registrar pagos. Opciones: '🔄 Nueva factura fiscal' retimbra esta misma factura sin modificaciones. Para cambiar datos de la factura: cancela y crea una nueva. Nota de Crédito disponible si aplica.", [frm.doc.fm_factura_fiscal_mx]),
				"red"
			);
	}, 300);
}

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
