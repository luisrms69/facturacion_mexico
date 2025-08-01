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

		// Actualizar botones fiscales cuando cambie el método de pago
		if (frm.doc.docstatus === 1) {
			update_fiscal_buttons(frm);
		}
	},

	fm_cfdi_use: function (frm) {
		// Actualizar botones fiscales cuando cambie el uso CFDI
		if (frm.doc.docstatus === 1) {
			update_fiscal_buttons(frm);
		}
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
		// Verificar si la factura está lista para timbrar
		const validation_result = validate_payment_method_requirements(frm);
		const ready_to_stamp = validate_fiscal_data_for_button(frm);

		if (ready_to_stamp) {
			// Botón habilitado - todo está listo
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
		} else {
			// Botón deshabilitado - mostrar qué falta
			frm.add_custom_button(
				__("⚠️ Completar Datos Fiscales"),
				function () {
					show_missing_fiscal_data_dialog(frm);
				},
				__("Facturación Fiscal")
			);
		}
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
	// Validaciones básicas
	const required_fields = [
		{ field: "customer", label: "Cliente" },
		{ field: "fm_cfdi_use", label: "Uso del CFDI" },
		{ field: "fm_payment_method_sat", label: "Método de Pago SAT" },
	];

	for (let req of required_fields) {
		if (!frm.doc[req.field]) {
			frappe.msgprint(__("El campo {0} es requerido para el timbrado fiscal", [req.label]));
			return false;
		}
	}

	// Validaciones específicas PUE vs PPD
	const validation_result = validate_payment_method_requirements(frm);
	if (!validation_result.valid) {
		frappe.msgprint({
			title: __("Error Validación Pago"),
			message: validation_result.message,
			indicator: "red",
		});
		return false;
	}

	// Mostrar advertencias si las hay
	if (validation_result.warnings && validation_result.warnings.length > 0) {
		frappe.show_alert({
			message: validation_result.warnings.join("<br>"),
			indicator: "orange",
		});
	}

	return true;
}

function validate_payment_method_requirements(frm) {
	const payment_method = frm.doc.fm_payment_method_sat;
	const warnings = [];

	// Contar Payment Entries relacionados
	const payment_count = get_related_payment_entries_count(frm);

	if (payment_method === "PUE") {
		// PUE: Pago en Una Exhibición

		// Validar múltiples pagos (violación legislación SAT)
		if (payment_count > 1) {
			warnings.push(
				__(
					"⚠️ ADVERTENCIA FISCAL: PUE con múltiples pagos viola la normativa SAT. " +
						"Considere cambiar a PPD (Pago en Parcialidades Diferido)"
				)
			);
		}

		// PUE requiere forma de pago específica en Sales Invoice
		const forma_pago_invoice = get_forma_pago_from_sales_invoice(frm);

		if (!forma_pago_invoice) {
			return {
				valid: false,
				message: __(
					"PUE requiere definir 'Forma de Pago para Timbrado' en la factura. " +
						"Seleccione una forma de pago específica (01-Efectivo, 02-Cheque, 03-Transferencia, etc.)"
				),
			};
		}

		// Validar que forma de pago no sea "99 Por definir"
		if (forma_pago_invoice === "99") {
			return {
				valid: false,
				message: __(
					"PUE no puede usar forma de pago '99 - Por definir'. " +
						"Debe especificar forma de pago exacta (01, 02, 03, etc.)"
				),
			};
		}

		// Validar consistencia con Payment Entry si existe
		const forma_pago_payment = get_forma_pago_from_payment_entry(frm);
		if (forma_pago_payment && forma_pago_payment !== forma_pago_invoice) {
			warnings.push(
				__(
					"⚠️ DISCREPANCIA: Factura usa '{0}' pero Payment Entry usa '{1}'. " +
						"Para timbrado se usará el valor de la factura.",
					[forma_pago_invoice, forma_pago_payment]
				)
			);
		}
	} else if (payment_method === "PPD") {
		// PPD: Pago en Parcialidades o Diferido

		// PPD siempre debe usar "99 - Por definir" para timbrado
		const forma_pago_invoice = get_forma_pago_from_sales_invoice(frm);

		if (forma_pago_invoice && forma_pago_invoice !== "99") {
			// Auto-corregir a "99" si es necesario
			const mode_99 = get_mode_of_payment_with_code("99");
			if (mode_99) {
				frm.set_value("fm_forma_pago_timbrado", mode_99);
				frappe.show_alert({
					message: __("PPD corregido automáticamente a '99 - Por definir'"),
					indicator: "blue",
				});
			}
		} else if (!forma_pago_invoice) {
			// Auto-asignar "99" si está vacío
			const mode_99 = get_mode_of_payment_with_code("99");
			if (mode_99) {
				frm.set_value("fm_forma_pago_timbrado", mode_99);
				frappe.show_alert({
					message: __("PPD asignado automáticamente: '99 - Por definir'"),
					indicator: "blue",
				});
			}
		}

		// Verificar consistencia con Payment Entry
		const forma_pago_payment = get_forma_pago_from_payment_entry(frm);
		if (forma_pago_payment && forma_pago_payment !== "99") {
			warnings.push(
				__(
					"⚠️ ADVERTENCIA: Payment Entry usa '{0}' pero PPD requiere '99 - Por definir'. " +
						"Para timbrado se usará '99 - Por definir'.",
					[forma_pago_payment]
				)
			);
		}
	}

	return {
		valid: true,
		warnings: warnings,
	};
}

function get_related_payment_entries_count(frm) {
	// Contar Payment Entries que referencian esta Sales Invoice
	let count = 0;

	if (frm.doc.advances && frm.doc.advances.length > 0) {
		// Contar advance payments
		count += frm.doc.advances.length;
	}

	// Buscar Payment Entry References usando llamada síncrona para validación inmediata
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Payment Entry Reference",
			filters: {
				reference_doctype: "Sales Invoice",
				reference_name: frm.doc.name,
			},
		},
		async: false, // Síncrona para validación inmediata
		callback: function (r) {
			if (r.message) {
				count += r.message.length;
			}
		},
	});

	return count;
}

function get_forma_pago_from_payment_entry(frm) {
	// Obtener código SAT desde Mode of Payment del Payment Entry relacionado
	let forma_pago_sat = null;

	// Buscar en advances (Payment Entry References)
	if (frm.doc.advances && frm.doc.advances.length > 0) {
		const advance = frm.doc.advances[0];
		if (advance.reference_name) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Payment Entry",
					name: advance.reference_name,
					fieldname: "mode_of_payment",
				},
				async: false,
				callback: function (r) {
					if (r.message && r.message.mode_of_payment) {
						// Extraer código SAT del formato "01 - Efectivo"
						const mode_parts = r.message.mode_of_payment.split(" - ");
						if (mode_parts.length >= 2 && mode_parts[0].match(/^\d+$/)) {
							forma_pago_sat = mode_parts[0];
						}
					}
				},
			});
		}
	}

	return forma_pago_sat;
}

function get_forma_pago_from_sales_invoice(frm) {
	// Obtener código SAT desde fm_forma_pago_timbrado de Sales Invoice
	if (!frm.doc.fm_forma_pago_timbrado) {
		return null;
	}

	// Extraer código SAT del formato "01 - Efectivo"
	const mode_parts = frm.doc.fm_forma_pago_timbrado.split(" - ");
	if (mode_parts.length >= 2 && mode_parts[0].match(/^\d+$/)) {
		return mode_parts[0];
	}

	return null;
}

function get_mode_of_payment_with_code(code) {
	// Buscar Mode of Payment que tenga el código SAT especificado
	let result = null;

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Mode of Payment",
			filters: {
				name: ["like", `${code} - %`],
			},
			fields: ["name"],
			limit_page_length: 1,
		},
		async: false,
		callback: function (r) {
			if (r.message && r.message.length > 0) {
				result = r.message[0].name;
			}
		},
	});

	return result;
}

function validate_fiscal_data_for_button(frm) {
	// Validación rápida para habilitar/deshabilitar botón de timbrado
	const required_fields = ["customer", "fm_cfdi_use", "fm_payment_method_sat"];

	// Verificar campos básicos
	for (let field of required_fields) {
		if (!frm.doc[field]) {
			return false;
		}
	}

	// Validar PUE vs PPD
	if (frm.doc.fm_payment_method_sat === "PUE") {
		// PUE requiere forma de pago específica en Sales Invoice
		const forma_pago = get_forma_pago_from_sales_invoice(frm);
		if (!forma_pago || forma_pago === "99") {
			return false;
		}
	}

	return true;
}

function show_missing_fiscal_data_dialog(frm) {
	const missing_items = [];

	// Verificar campos básicos
	if (!frm.doc.customer) missing_items.push("• Cliente");
	if (!frm.doc.fm_cfdi_use) missing_items.push("• Uso del CFDI");
	if (!frm.doc.fm_payment_method_sat) missing_items.push("• Método de Pago SAT (PUE/PPD)");

	// Validaciones específicas PUE
	if (frm.doc.fm_payment_method_sat === "PUE") {
		const forma_pago = get_forma_pago_from_sales_invoice(frm);
		if (!forma_pago) {
			missing_items.push("• Forma de Pago para Timbrado");
		} else if (forma_pago === "99") {
			missing_items.push("• Forma de pago específica (no '99 - Por definir')");
		}
	}

	const dialog_content = `
		<div class="alert alert-warning">
			<strong>Datos Fiscales Incompletos</strong><br>
			Para habilitar el timbrado, complete los siguientes campos:
		</div>
		<div style="margin: 15px 0;">
			${missing_items.join("<br>")}
		</div>
		<div class="alert alert-info">
			<strong>Nota:</strong> El botón de timbrado se habilitará automáticamente
			cuando todos los datos estén completos.
		</div>
	`;

	const d = new frappe.ui.Dialog({
		title: __("Completar Datos Fiscales"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "missing_data",
				options: dialog_content,
			},
		],
		primary_action_label: __("Entendido"),
		primary_action: function () {
			d.hide();
		},
	});

	d.show();
}

function update_fiscal_buttons(frm) {
	// Limpiar botones existentes
	frm.clear_custom_buttons();

	// Volver a agregar botones con estado actualizado
	add_fiscal_buttons(frm);
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
