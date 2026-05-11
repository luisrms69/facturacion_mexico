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

		// Con FFM vinculada (cualquier estado), ocultar Cancel nativo.
		// El usuario debe usar los botones de Acciones Fiscales:
		// - FFM TIMBRADO: cancelar primero en FacturAPI
		// - FFM CANCELADO: usar "❌ Cancelar documento" (limpia vínculos fiscales)
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

		// Estado fiscal centralizado — reemplaza chequeo de fm_fiscal_status + get_active_pe_for_si
		frappe.call({
			method: "facturacion_mexico.fiscal_state.api.get_fiscal_ui_state",
			args: { doctype: "Sales Invoice", name: frm.doc.name },
			callback: function (r) {
				if (!r.message) return;
				const { actions, facts } = r.message;
				// Opciones Fiscales solo cuando hay FFM cancelada y sin PE activo
				if (facts.has_cancelled_ffm && !facts.has_submitted_payment_entries) {
					_add_post_fiscal_action_buttons(frm);
				}
			},
		});
	}

	function _add_post_fiscal_action_buttons(frm) {
		const GROUP = __("Opciones Fiscales");
		const can_cancel = frappe.model.can_cancel("Sales Invoice");

		// --- Botón: Nueva factura fiscal (retimbra misma factura de venta sin cambios) ---
		frm.add_custom_button(
			__("🔄 Nueva factura fiscal"),
			() => {
				const ffm_prev = frm.doc.fm_factura_fiscal_mx || "N/A";
				const msg = [
					__(
						"Se desvinculará esta factura de venta de la FFM cancelada para retimbrar. ¿Continuar?"
					),
					"<br><br>",
					`• ${__("Factura de venta")}: ${frappe.utils.escape_html(frm.doc.name)}<br>`,
					`• ${__("FFM anterior")}: ${frappe.utils.escape_html(ffm_prev)}<br><br>`,
					__(
						"Nota: retimbra esta misma factura de venta sin modificaciones. Para cambiar datos, usa '❌ Cancelar documento' y crea una nueva."
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
												"Factura de venta ya está lista para re-facturar"
										),
										indicator: "blue",
									});
								} else {
									frappe.show_alert({
										message: __(
											"Listo. Usa 'Generar Factura Fiscal' para retimbrar."
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
			GROUP
		);

		// --- Botón: Cancelar documento (solo si tiene permiso) ---
		if (can_cancel) {
			frm.add_custom_button(
				__("❌ Cancelar documento"),
				function () {
					frappe.confirm(
						__(
							"Se cancelará esta factura de venta. Esta acción no se puede deshacer. ¿Continuar?"
						),
						function () {
							frappe.call({
								method: "facturacion_mexico.api.fiscal_operations.cancelar_si_post_fiscal",
								args: { si_name: frm.doc.name },
								freeze: true,
								freeze_message: __("Cancelando..."),
								callback: function (r) {
									if (r.message && r.message.ok) {
										frm.reload_doc();
									}
								},
							});
						}
					);
				},
				GROUP
			);
		}
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
		if (frm.doc.docstatus !== 1) return;

		// Estado fiscal centralizado — reemplaza chequeo local fm_fiscal_status=TIMBRADO
		frappe.call({
			method: "facturacion_mexico.fiscal_state.api.get_fiscal_ui_state",
			args: { doctype: "Sales Invoice", name: frm.doc.name },
			callback: function (r) {
				if (!r.message || !r.message.actions.can_substitute) return;
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
										freeze_message: __(
											"Creando Sales Invoice de reemplazo..."
										),
									})
									.then((r) => {
										const out = (r && r.message) || {};
										if (!out || !out.new_si) return;
										frappe.show_alert({
											message:
												__("SI de reemplazo creado:") + " " + out.new_si,
											indicator: "green",
										});
										frappe.set_route("Form", "Sales Invoice", out.new_si);
									});
							}
						);
					},
					__("Opciones Fiscales")
				);
			},
		});
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
