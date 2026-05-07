// si_post_fiscal_actions.js - Acciones post-cancelación fiscal para Sales Invoice
(function () {
	const E = window.FM_ENUMS || {};
	const S = E.FiscalStates || {};
	const norm =
		E.norm ||
		((x) =>
			("" + (x || ""))
				.toUpperCase()
				.replace("CANCELACION_PENDIENTE", "CANCELACIÓN_PENDIENTE"));

	function hide_native_cancel_conditionally(frm) {
		const linked = !!(frm.doc && frm.doc.fm_factura_fiscal_mx);

		// Si no hay FFM vinculada, permitir Cancel nativo siempre
		if (!linked) return;

		const fiscal_status = norm(frm.doc.fm_fiscal_status || "");

		// NUEVO: Si FFM está CANCELADA fiscalmente, permitir Cancel nativo (workflow 02/03/04)
		if (fiscal_status === "CANCELADO") {
			// No ocultar botón - permitir cancelación nativa con interceptor
			return;
		}

		// MANTENER: Ocultar Cancel nativo si FFM está activa (TIMBRADO/PENDIENTE)
		const $w = $(frm.page.wrapper);

		// Botón secundario "Cancel" (en la barra)
		frm.page.btn_secondary &&
			frm.page.btn_secondary
				.find(".btn,button")
				.filter((_, el) => /(^|\s)Cancel(\s|$)/i.test($(el).text().trim()))
				.hide();

		// Variantes por data-label
		$w.find('.btn[data-label="Cancel"]').hide();
		$w.find('button:contains("Cancel")').hide();

		// Menú de la elipsis: "Cancel" y "Cancel All Documents"
		$w.find(".menu-btn-group .menu-items a.grey-link")
			.filter((_, a) => /^(Cancel|Cancel All Documents)$/i.test($(a).text().trim()))
			.closest("li")
			.hide();

		// Clase CSS para refuerzo futuro
		$w.addClass("ffm-linked-no-native-cancel");
	}

	function add_post_fiscal_actions(frm) {
		if (frm.doc.docstatus !== 1) return;
		const st = norm(frm.doc.fm_fiscal_status || "");
		if (st !== S.CANCELADO && st !== "CANCELADO") return;

		// Limpiar botones existentes del grupo
		frm.remove_custom_button(__("🔄 Nueva factura fiscal"), __("Acciones Post-Fiscal"));
		frm.remove_custom_button(__("❌ Cancelar Sales Invoice"), __("Acciones Post-Fiscal"));

		// --- Botón: Nueva factura fiscal (misma Sales Invoice) ---
		frm.add_custom_button(
			__("🔄 Nueva factura fiscal"),
			() => {
				const ffm_prev = frm.doc.fm_factura_fiscal_mx || "N/A";
				const msg = [
					__(
						"Se desvinculará este Sales Invoice de la FFM cancelada para que puedas volver a timbrar desde Factura Fiscal. ¿Continuar?"
					),
					"<br><br>",
					`• ${__("Sales Invoice")}: ${frappe.utils.escape_html(frm.doc.name)}<br>`,
					`• ${__("FFM anterior")}: ${frappe.utils.escape_html(ffm_prev)}<br><br>`,
					__(
						"Después podrás modificar lo necesario y usar 'Generar Factura Fiscal' (flujo normal)."
					),
				].join("");

				frappe.confirm(msg, () => {
					frappe.dom.freeze(__("Preparando re-facturación..."));
					frappe
						.call({
							method: "facturacion_mexico.api.fiscal_operations.refacturar_misma_si",
							args: { si_name: frm.doc.name },
						})
						.then((r) => {
							const out = (r && r.message) || {};
							if (out.ok) {
								if (out.already_unlinked) {
									frappe.show_alert({
										message: __(
											out.message ||
												"Sales Invoice ya está listo para re-facturar"
										),
										indicator: "blue",
									});
								} else {
									frappe.show_alert({
										message: __(
											"Listo. Modifica lo necesario y usa 'Generar Factura Fiscal' (flujo normal)."
										),
										indicator: "green",
									});
								}
								frm.reload_doc();
							} else {
								frappe.msgprint({
									title: __("Re-facturación"),
									message: __(out.error || "Operación sin respuesta"),
									indicator: "red",
								});
							}
						})
						.catch((e) => {
							frappe.msgprint({
								title: __("Re-facturación"),
								message: __(e.message || "Error inesperado"),
								indicator: "red",
							});
						})
						.always(() => frappe.dom.unfreeze());
				});
			},
			__("Acciones Post-Fiscal")
		);

		// ELIMINADO: Botón "❌ Cancelar Sales Invoice" custom deprecado
		// El workflow 02/03/04 ahora usa cancelación nativa con interceptor backend.
		// El interceptor hook before_cancel_sales_invoice_orchestrator() maneja la cancelación automáticamente.
	}

	function add_fiscal_status_indicator(frm) {
		const status = norm(frm.doc.fm_fiscal_status || "");

		// Alert solo si NO hay FFM vinculada — si hay FFM, sales_invoice_block_cancel.js
		// maneja el headline con mensaje más específico (no duplicar)
		if (status === S.CANCELADO || status === "CANCELADO") {
			if (!frm.doc.fm_factura_fiscal_mx) {
				frm.dashboard &&
					frm.dashboard.set_headline_alert(
						__(
							"Fiscal Cancelado - Acciones Disponibles. La factura fiscal fue cancelada. Puede re-facturar o cancelar el Sales Invoice."
						),
						"orange"
					);
			}
		}
	}

	function add_substitute_button_mx(frm) {
		// [Milestone 3] Mostrar sólo si hay FFM timbrada vigente ligada al SI
		const status = (frm.doc.fm_fiscal_status || "").toUpperCase();
		if (frm.doc.docstatus === 1 && status === "TIMBRADO") {
			frm.add_custom_button(
				__("🔄 Sustituir CFDI (01)"),
				() => {
					frappe.confirm(
						__(
							"Se creará un Sales Invoice de reemplazo (borrador) para emitir el CFDI sustituto (TipoRelación 04). ¿Continuar?"
						),
						() => {
							frappe
								.call({
									method: "facturacion_mexico.facturacion_fiscal.timbrado_api.create_substitution_si",
									args: { si_name: frm.doc.name },
									freeze: true,
									freeze_message: __("Creando Sales Invoice de reemplazo..."),
								})
								.then((r) => {
									const out = (r && r.message) || {};
									if (!out || !out.new_si) return;
									frappe.show_alert({
										message: __("SI de reemplazo creado:") + " " + out.new_si,
										indicator: "green",
									});
									// Abrir el SI de reemplazo para que el usuario corrija datos antes de timbrar
									frappe.set_route("Form", "Sales Invoice", out.new_si);
								});
						}
					);
				},
				__("Acciones Fiscales")
			);
		}
	}

	frappe.ui.form.on("Sales Invoice", {
		refresh: function (frm) {
			// PRIMERO: Evaluar visibilidad botón Cancel nativo según estado fiscal
			hide_native_cancel_conditionally(frm);

			// Bloquear Amend en SI canceladas con historial fiscal (evita manipulación post-CFDI)
			if (frm.doc.docstatus === 2 && frm.doc.fm_fiscal_status === "CANCELADO") {
				if (frm.perm[0]) frm.perm[0].amend = 0;
				frm.page.clear_primary_action();
			}

			// DESPUÉS: Lógica existente de botones contextuales
			if (frm.doc.docstatus === 1) {
				add_post_fiscal_actions(frm);
				add_fiscal_status_indicator(frm);
				add_substitute_button_mx(frm); // [Milestone 3] Botón sustitución
			}
		},

		// NUEVO: Si cambia el link FFM en runtime
		fm_factura_fiscal_mx: function (frm) {
			hide_native_cancel_conditionally(frm);
		},

		fm_fiscal_status: function (frm) {
			// Actualizar acciones cuando cambie el estado fiscal
			if (frm.doc.docstatus === 1) {
				add_post_fiscal_actions(frm);
				add_fiscal_status_indicator(frm);
				add_substitute_button_mx(frm); // [Milestone 3] Botón sustitución

				// CONCURRENCY FIX: Mejorar UX post-sustitución exitosa
				if (
					frm.doc.fm_fiscal_status === "TIMBRADO" &&
					frm.doc.ffm_substitution_source_uuid
				) {
					// Si es un SI sustituto que se timbró exitosamente
					frappe.show_alert({
						message: __(
							"Sustitución CFDI completada exitosamente - Cascada automática ejecutada"
						),
						indicator: "green",
					});
				}
			}
		},
	});
})();
