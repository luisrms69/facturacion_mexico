// Sales Invoice customizations for Facturacion Mexico
frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Solo mostrar botones de timbrado si está submitted
		if (frm.doc.docstatus === 1) {
			add_fiscal_buttons(frm);
		}

		// Actualizar estado visual del timbrado
		update_fiscal_status_display(frm);

		// Convertir método de pago SAT a radio buttons
		convert_payment_method_to_radio(frm);
	},

	onload: function (frm) {
		// Configurar campos fiscales
		setup_fiscal_fields(frm);

		// Convertir método de pago SAT a radio buttons
		convert_payment_method_to_radio(frm);
	},

	customer: function (frm) {
		// Auto-asignar uso CFDI default cuando se selecciona cliente
		auto_assign_cfdi_use_default(frm);
	},

	fm_payment_method_sat: function (frm) {
		// Sincronizar radio buttons cuando el campo cambie programáticamente
		sync_radio_buttons_with_field(frm);
	},
});

function add_fiscal_buttons(frm) {
	// Verificar si el cliente tiene RFC para mostrar botones fiscales
	if (!has_customer_rfc(frm)) {
		return;
	}

	// Obtener estado actual del timbrado
	const fiscal_status = get_current_fiscal_status(frm);

	// Botón principal de timbrado
	if (fiscal_status !== "Exitoso") {
		frm.add_custom_button(
			__("Timbrar Factura"),
			function () {
				timbrar_factura(frm);
			},
			__("Facturación Fiscal")
		);

		// Hacer el botón más prominente
		frm.page.set_primary_action(__("Timbrar Factura"), function () {
			timbrar_factura(frm);
		});
	}

	// Botón de cancelación (solo si está timbrada)
	if (fiscal_status === "Exitoso") {
		frm.add_custom_button(
			__("Cancelar Timbrado"),
			function () {
				cancelar_timbrado(frm);
			},
			__("Facturación Fiscal")
		);
	}

	// Botón de prueba de conexión
	frm.add_custom_button(
		__("Probar Conexión PAC"),
		function () {
			test_pac_connection(frm);
		},
		__("Facturación Fiscal")
	);

	// Botón para recargar estado
	frm.add_custom_button(
		__("Actualizar Estado"),
		function () {
			frm.reload_doc();
		},
		__("Facturación Fiscal")
	);
}

function has_customer_rfc(frm) {
	if (!frm.doc.customer) return false;

	// Verificar si tenemos datos del cliente cargados
	return frappe.db.get_value("Customer", frm.doc.customer, ["tax_id"]).then((r) => {
		const customer = r.message;
		return !!customer.tax_id;
	});
}

function get_current_fiscal_status(frm) {
	// Verificar el último intento en la tabla fm_fiscal_attempts
	if (frm.doc.fm_fiscal_attempts && frm.doc.fm_fiscal_attempts.length > 0) {
		const last_attempt = frm.doc.fm_fiscal_attempts[frm.doc.fm_fiscal_attempts.length - 1];
		return last_attempt.status;
	}

	// Fallback al campo fm_fiscal_status
	return frm.doc.fm_fiscal_status || "Pendiente";
}

function timbrar_factura(frm) {
	// Validar datos antes del timbrado
	if (!validate_fiscal_data(frm)) {
		return;
	}

	// Mostrar diálogo de confirmación
	frappe.confirm(__("¿Está seguro de que desea timbrar esta factura?"), function () {
		// Mostrar indicador de progreso
		frappe.show_alert({
			message: __("Enviando factura para timbrado..."),
			indicator: "blue",
		});

		// Llamar a la API de timbrado
		frappe.call({
			method: "facturacion_mexico.facturacion_fiscal.timbrado_api.timbrar_factura",
			args: {
				sales_invoice_name: frm.doc.name,
			},
			callback: function (r) {
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __("Factura timbrada exitosamente"),
						indicator: "green",
					});
					frm.reload_doc();
				} else {
					const error_msg = r.message
						? r.message.user_error || r.message.message
						: "Error desconocido";
					show_fiscal_error_dialog(
						error_msg,
						r.message ? r.message.corrective_action : null
					);
				}
			},
			error: function (r) {
				frappe.show_alert({
					message: __("Error al timbrar factura"),
					indicator: "red",
				});
			},
		});
	});
}

function cancelar_timbrado(frm) {
	// Solicitar motivo de cancelación
	frappe.prompt(
		[
			{
				fieldname: "motivo",
				fieldtype: "Select",
				label: __("Motivo de Cancelación"),
				options: [
					"01 - Comprobante emitido con errores con relación",
					"02 - Comprobante emitido con errores sin relación",
					"03 - No se llevó a cabo la operación",
					"04 - Operación nominativa relacionada en la factura global",
				],
				default: "02",
				reqd: 1,
			},
		],
		function (values) {
			frappe.call({
				method: "facturacion_mexico.facturacion_fiscal.timbrado_api.cancelar_factura",
				args: {
					sales_invoice_name: frm.doc.name,
					motivo: values.motivo.substring(0, 2), // Extraer solo el código
				},
				callback: function (r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: __("Factura cancelada exitosamente"),
							indicator: "green",
						});
						frm.reload_doc();
					} else {
						frappe.msgprint(
							__(
								"Error al cancelar factura: " +
									(r.message ? r.message.message : "Error desconocido")
							)
						);
					}
				},
			});
		},
		__("Cancelar Timbrado Fiscal")
	);
}

function test_pac_connection(frm) {
	frappe.call({
		method: "facturacion_mexico.facturacion_fiscal.api_client.test_facturapi_connection",
		callback: function (r) {
			if (r.message && r.message.success) {
				frappe.show_alert({
					message: __("Conexión exitosa con el PAC"),
					indicator: "green",
				});
			} else {
				frappe.msgprint(
					__(
						"Error de conexión con el PAC: " +
							(r.message ? r.message.message : "Error desconocido")
					)
				);
			}
		},
	});
}

function validate_fiscal_data(frm) {
	const required_fields = [
		{ field: "customer", label: "Cliente" },
		{ field: "fm_cfdi_use", label: "Uso del CFDI" },
	];

	for (let req of required_fields) {
		if (!frm.doc[req.field]) {
			frappe.msgprint(__("El campo {0} es requerido para el timbrado fiscal", [req.label]));
			return false;
		}
	}

	return true;
}

function show_fiscal_error_dialog(error_message, corrective_action) {
	let dialog_content = `<div class="alert alert-danger">
        <strong>Error en Timbrado Fiscal:</strong><br>
        ${error_message}
    </div>`;

	if (corrective_action) {
		dialog_content += `<div class="alert alert-info">
            <strong>Acción Correctiva:</strong><br>
            ${corrective_action}
        </div>`;
	}

	const d = new frappe.ui.Dialog({
		title: __("Error de Timbrado"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "error_details",
				options: dialog_content,
			},
		],
		primary_action_label: __("Cerrar"),
		primary_action: function () {
			d.hide();
		},
	});

	d.show();
}

function setup_fiscal_fields(frm) {
	// Auto-configurar campos fiscales si están vacíos
	if (frm.doc.fm_payment_method_sat === undefined) {
		frm.set_value("fm_payment_method_sat", "PUE");
	}
}

function update_fiscal_status_display(frm) {
	// Actualizar indicadores visuales basados en el estado fiscal
	const fiscal_status = get_current_fiscal_status(frm);

	let indicator_color = "grey";
	let status_text = "Sin Estado";

	switch (fiscal_status) {
		case "Exitoso":
			indicator_color = "green";
			status_text = "Timbrada";
			break;
		case "Error":
		case "Rechazado":
			indicator_color = "red";
			status_text = "Error";
			break;
		case "Pendiente":
			indicator_color = "orange";
			status_text = "Pendiente";
			break;
	}

	// Actualizar el indicador en el dashboard si existe
	if (frm.dashboard && frm.dashboard.add_indicator) {
		frm.dashboard.add_indicator(__("Estado Fiscal: {0}", [status_text]), indicator_color);
	}
}

function auto_assign_cfdi_use_default(frm) {
	// Solo procesar si hay cliente seleccionado
	if (!frm.doc.customer) {
		return;
	}

	// Obtener uso CFDI default del cliente
	frappe.db
		.get_value("Customer", frm.doc.customer, "fm_uso_cfdi_default")
		.then((r) => {
			if (r.message && r.message.fm_uso_cfdi_default) {
				// Solo asignar si el campo está vacío
				if (!frm.doc.fm_cfdi_use) {
					frm.set_value("fm_cfdi_use", r.message.fm_uso_cfdi_default);

					// Mostrar mensaje informativo
					frappe.show_alert({
						message: __("Uso CFDI asignado automáticamente desde Cliente"),
						indicator: "green",
					});
				}
			} else {
				// Cliente no tiene default, limpiar campo si venía de otro cliente
				if (frm.doc.fm_cfdi_use && frm._previous_customer) {
					frm.set_value("fm_cfdi_use", "");
					frappe.show_alert({
						message: __("Cliente sin Uso CFDI default - campo limpiado"),
						indicator: "blue",
					});
				}
			}

			// Recordar el cliente actual para comparaciones futuras
			frm._previous_customer = frm.doc.customer;
		})
		.catch((err) => {
			// Error silencioso, no interrumpir el flujo
			console.log("Error obteniendo uso CFDI default:", err);
		});
}

function convert_payment_method_to_radio(frm) {
	// Solo procesar si el campo existe y el form no está en modo de solo lectura
	const field = frm.get_field("fm_payment_method_sat");
	if (!field || !field.$wrapper) {
		return;
	}

	// No convertir si el documento está submitted (solo lectura)
	if (frm.doc.docstatus === 1) {
		return;
	}

	// Esperar un momento para que el DOM esté completamente cargado
	setTimeout(() => {
		setup_radio_buttons(frm, field);
	}, 100);
}

function setup_radio_buttons(frm, field) {
	// Obtener valor actual
	const current_value = frm.doc.fm_payment_method_sat || "PUE";

	// Crear HTML de radio buttons con estilos mejorados
	const radio_html = `
		<div class="payment-method-radio-container" style="padding: 8px 0;">
			<div class="radio-group" style="display: flex; gap: 20px; align-items: center;">
				<label class="radio-option" style="display: flex; align-items: center; cursor: pointer; font-weight: normal; margin-bottom: 0;">
					<input type="radio" name="fm_payment_method_sat_radio" value="PUE"
						   ${current_value === "PUE" ? "checked" : ""}
						   style="margin-right: 8px; transform: scale(1.2);">
					<span style="font-size: 14px;">
						<strong>PUE</strong> - Pago en una exhibición
					</span>
				</label>
				<label class="radio-option" style="display: flex; align-items: center; cursor: pointer; font-weight: normal; margin-bottom: 0;">
					<input type="radio" name="fm_payment_method_sat_radio" value="PPD"
						   ${current_value === "PPD" ? "checked" : ""}
						   style="margin-right: 8px; transform: scale(1.2);">
					<span style="font-size: 14px;">
						<strong>PPD</strong> - Pago en parcialidades o diferido
					</span>
				</label>
			</div>
		</div>
	`;

	// Reemplazar el contenido del select con los radio buttons
	const $control_input = field.$wrapper.find(".control-input");
	if ($control_input.length) {
		// Ocultar el select original y añadir los radio buttons
		$control_input.find("select").hide();

		// Remover radio buttons previos si existen
		$control_input.find(".payment-method-radio-container").remove();

		// Añadir los radio buttons
		$control_input.append(radio_html);

		// Manejar cambios en los radio buttons
		$control_input.find('input[type="radio"]').on("change", function () {
			const selected_value = $(this).val();

			// Actualizar el campo en el documento
			frm.set_value("fm_payment_method_sat", selected_value);

			// Mostrar feedback visual
			frappe.show_alert({
				message: __("Método de pago actualizado: {0}", [
					selected_value === "PUE"
						? "PUE - Pago en una exhibición"
						: "PPD - Pago en parcialidades",
				]),
				indicator: "blue",
			});
		});

		// Añadir estilos CSS personalizados si no existen
		add_radio_button_styles();
	}
}

function add_radio_button_styles() {
	// Añadir estilos CSS una sola vez
	if (!document.getElementById("payment-method-radio-styles")) {
		const style = document.createElement("style");
		style.id = "payment-method-radio-styles";
		style.textContent = `
			.payment-method-radio-container .radio-option:hover {
				background-color: #f8f9fa;
				border-radius: 4px;
				padding: 4px 8px;
				transition: background-color 0.2s ease;
			}

			.payment-method-radio-container input[type="radio"]:checked + span {
				color: #007bff;
				font-weight: 600;
			}

			.payment-method-radio-container input[type="radio"] {
				accent-color: #007bff;
			}

			.payment-method-radio-container .radio-group {
				border: 1px solid #e9ecef;
				border-radius: 6px;
				padding: 12px 16px;
				background-color: #ffffff;
			}
		`;
		document.head.appendChild(style);
	}
}

function sync_radio_buttons_with_field(frm) {
	// Sincronizar radio buttons cuando el campo cambie programáticamente
	const field = frm.get_field("fm_payment_method_sat");
	if (!field || !field.$wrapper) {
		return;
	}

	const current_value = frm.doc.fm_payment_method_sat || "PUE";
	const $radio_buttons = field.$wrapper.find('input[name="fm_payment_method_sat_radio"]');

	if ($radio_buttons.length) {
		// Actualizar el estado de los radio buttons
		$radio_buttons.each(function () {
			$(this).prop("checked", $(this).val() === current_value);
		});

		// Actualizar estilos visuales
		field.$wrapper.find(".radio-option span").removeClass("active");
		field.$wrapper.find(`input[value="${current_value}"] + span`).addClass("active");
	}
}
