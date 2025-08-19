// si_post_fiscal_actions.js - Acciones post-cancelación fiscal para Sales Invoice
(function () {
	const S = (window.FM_ENUMS || {}).FiscalStates || {};

	function norm(s) {
		return ("" + (s || ""))
			.toUpperCase()
			.replace("CANCELACION_PENDIENTE", "CANCELACIÓN_PENDIENTE");
	}

	function hide_native_cancel_always_if_ffm_linked(frm) {
		const linked = !!(frm.doc && frm.doc.fm_factura_fiscal_mx);

		// Solo proceder si hay FFM vinculada
		if (!linked) return;

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
		const status = norm(frm.doc.fm_fiscal_status || "");

		// Solo mostrar opciones si FFM cancelada fiscalmente
		if (status === S.CANCELADO || status === "CANCELADO") {
			// Verificar estado actual para mostrar botones apropiados
			frappe.call({
				method: "facturacion_mexico.api.cancel_operations.get_cancellation_status",
				args: { si_name: frm.doc.name },
				callback: function (r) {
					if (r.message && !r.message.error) {
						const state = r.message;

						// Limpiar botones existentes del grupo
						frm.remove_custom_button(
							__("Generar nueva factura fiscal"),
							__("Acciones Fiscales")
						);
						frm.remove_custom_button(
							__("Cancelar Sales Invoice"),
							__("Acciones Fiscales")
						);

						// Solo mostrar si SI está submitted
						if (state.si_docstatus === 1) {
							// Opción A: Re-facturación
							if (state.can_refacturar) {
								frm.add_custom_button(
									__("🔄 Generar nueva factura fiscal"),
									() => {
										// Mostrar confirmación con información
										frappe.confirm(
											__(
												"¿Crear nueva factura fiscal para este Sales Invoice?<br><br>" +
													"<b>Situación actual:</b><br>" +
													"• Sales Invoice: {0} (activo)<br>" +
													"• FFM anterior: {1} (cancelada)<br><br>" +
													"<b>Resultado:</b><br>" +
													"• Se creará nueva FFM vinculada al mismo SI<br>" +
													"• La FFM cancelada se conserva para auditoría"
											).format(frm.doc.name, state.ffm_info?.name || "N/A"),
											() => {
												// Aquí iría la llamada al método de re-facturación
												// Por ahora mostrar mensaje de implementación pendiente
												frappe.msgprint({
													title: __("Función en desarrollo"),
													message: __(
														"La re-facturación automática estará disponible en la próxima actualización.<br><br>" +
															"<b>Alternativa actual:</b><br>" +
															"1. Crear nueva Factura Fiscal Mexico manualmente<br>" +
															"2. Vincular al mismo Sales Invoice<br>" +
															"3. Proceder con timbrado normal"
													),
													indicator: "orange",
												});
											},
											__("Re-facturación"),
											__("Crear nueva FFM"),
											__("Cancelar")
										);
									},
									__("Acciones Fiscales")
								).attr(
									"title",
									__(
										"Crear nueva factura fiscal para este Sales Invoice. " +
											"La FFM cancelada se conserva para auditoría."
									)
								);
							}

							// Opción B: Cancelar Sales Invoice
							if (state.can_cancel_si) {
								frm.add_custom_button(
									__("❌ Cancelar Sales Invoice"),
									() => {
										// Mostrar confirmación detallada con secuencia
										frappe.confirm(
											__(
												"¿Confirma cancelar definitivamente este Sales Invoice?<br><br>" +
													"<b>Secuencia automática:</b><br>" +
													"1️⃣ Cancelar FFM {0} (si aún activa)<br>" +
													"2️⃣ Cancelar Sales Invoice {1}<br><br>" +
													"<b>⚠️ Importante:</b><br>" +
													"• Esta acción NO es reversible<br>" +
													"• El documento queda permanentemente cancelado<br>" +
													"• Los datos se conservan para auditoría"
											).format(state.ffm_info?.name || "N/A", frm.doc.name),
											() => {
												// Mostrar loading
												frappe.show_alert({
													message: __("Procesando cancelación..."),
													indicator: "blue",
												});

												// Ejecutar cancelación orquestada
												frappe.call({
													method: "facturacion_mexico.api.cancel_operations.cancel_sales_invoice_after_ffm",
													args: { si_name: frm.doc.name },
													callback: function (r) {
														if (r.message && r.message.success) {
															frappe.show_alert({
																message: __(
																	"Sales Invoice cancelado exitosamente"
																),
																indicator: "green",
															});

															// Mostrar detalles del resultado
															frappe.msgprint({
																title: __(
																	"Cancelación completada"
																),
																message: __("✅ {0}").format(
																	r.message.message
																),
																indicator: "green",
															});

															// Recargar documento
															frm.reload_doc();
														}
													},
													error: function (r) {
														// Error ya manejado por el API, solo recargar
														frm.reload_doc();
													},
												});
											},
											__("Confirmar cancelación"),
											__("Sí, cancelar definitivamente"),
											__("No, mantener activo")
										);
									},
									__("Acciones Fiscales")
								)
									.addClass("btn-danger")
									.attr(
										"title",
										__(
											"Cancelar definitivamente este Sales Invoice. " +
												"La FFM se cancelará automáticamente primero."
										)
									);
							}
						}
					}
				},
			});
		} else {
			// Limpiar botones si no aplican
			frm.remove_custom_button(__("Generar nueva factura fiscal"), __("Acciones Fiscales"));
			frm.remove_custom_button(__("Cancelar Sales Invoice"), __("Acciones Fiscales"));
		}
	}

	function add_fiscal_status_indicator(frm) {
		const status = norm(frm.doc.fm_fiscal_status || "");

		// Alert específico para estado post-cancelación fiscal (al mismo nivel que otros mensajes)
		if (status === S.CANCELADO || status === "CANCELADO") {
			frm.dashboard &&
				frm.dashboard.set_headline_alert(
					__(
						"Fiscal Cancelado - Acciones Disponibles. La factura fiscal fue cancelada. Puede re-facturar o cancelar el Sales Invoice."
					),
					"orange"
				);
		}
	}

	frappe.ui.form.on("Sales Invoice", {
		refresh: function (frm) {
			// PRIMERO: Ocultar botón Cancel nativo si hay FFM (propuesta experto)
			hide_native_cancel_always_if_ffm_linked(frm);

			// DESPUÉS: Lógica existente de botones contextuales
			if (frm.doc.docstatus === 1) {
				add_post_fiscal_actions(frm);
				add_fiscal_status_indicator(frm);
			}
		},

		// NUEVO: Si cambia el link FFM en runtime
		fm_factura_fiscal_mx: function (frm) {
			hide_native_cancel_always_if_ffm_linked(frm);
		},

		fm_fiscal_status: function (frm) {
			// Actualizar acciones cuando cambie el estado fiscal
			if (frm.doc.docstatus === 1) {
				add_post_fiscal_actions(frm);
				add_fiscal_status_indicator(frm);
			}
		},
	});
})();
