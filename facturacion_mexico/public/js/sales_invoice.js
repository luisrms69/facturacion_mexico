// Sales Invoice customizations for Facturacion Mexico
frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Solo mostrar botones de timbrado si está submitted
		if (frm.doc.docstatus === 1) {
			add_fiscal_buttons(frm);
		}

		// Actualizar estado visual del timbrado
		update_fiscal_status_display(frm);
	},

	onload: function (frm) {
		// Configurar campos fiscales
		setup_fiscal_fields(frm);
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
	// Verificar el último intento en la tabla fiscal_attempts
	if (frm.doc.fiscal_attempts && frm.doc.fiscal_attempts.length > 0) {
		const last_attempt = frm.doc.fiscal_attempts[frm.doc.fiscal_attempts.length - 1];
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
