// Sales Invoice customizations for Facturacion Mexico - NUEVA ARQUITECTURA
// Lee datos fiscales desde Factura Fiscal Mexico en lugar de Sales Invoice

frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Cargar datos fiscales desde Factura Fiscal Mexico
		load_fiscal_data(frm);

		// Solo mostrar botones de timbrado si está submitted
		if (frm.doc.docstatus === 1) {
			add_fiscal_buttons(frm);
		}

		// Actualizar estado visual del timbrado
		update_fiscal_status_display(frm);
	},

	onload: function (frm) {
		// Cargar datos fiscales al cargar el documento
		load_fiscal_data(frm);
	},

	customer: function (frm) {
		// Auto-asignar uso CFDI default cuando se selecciona cliente
		auto_assign_cfdi_use_default(frm);
	},
});

function load_fiscal_data(frm) {
	// Cargar datos fiscales desde Factura Fiscal Mexico
	if (!frm.doc.fm_factura_fiscal_mx) {
		// No hay referencia fiscal todavía
		frm._fiscal_data = {};
		return;
	}

	// Obtener datos de Factura Fiscal Mexico
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Factura Fiscal Mexico",
			name: frm.doc.fm_factura_fiscal_mx,
		},
		callback: function (r) {
			if (r.message) {
				frm._fiscal_data = r.message;

				// Actualizar UI con datos fiscales
				update_fiscal_ui(frm);
			}
		},
	});
}

function update_fiscal_ui(frm) {
	// Actualizar interfaz con datos fiscales
	if (!frm._fiscal_data) return;

	const fiscal = frm._fiscal_data;

	// Mostrar información fiscal en el dashboard
	if (fiscal.fm_cfdi_use) {
		frm.dashboard.add_indicator(__("Uso CFDI: {0}", [fiscal.fm_cfdi_use]), "blue");
	}

	if (fiscal.fm_payment_method_sat) {
		frm.dashboard.add_indicator(__("Método: {0}", [fiscal.fm_payment_method_sat]), "green");
	}

	if (fiscal.fm_fiscal_status) {
		const color = fiscal.fm_fiscal_status === "Timbrada" ? "green" : "orange";
		frm.dashboard.add_indicator(__("Estado: {0}", [fiscal.fm_fiscal_status]), color);
	}
}

function get_or_create_fiscal_doc(frm, callback) {
	// Obtener o crear documento Factura Fiscal Mexico
	if (frm.doc.fm_factura_fiscal_mx) {
		// Ya existe, obtenerlo
		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Factura Fiscal Mexico",
				name: frm.doc.fm_factura_fiscal_mx,
			},
			callback: callback,
		});
	} else {
		// Crear nuevo documento fiscal
		const fiscal_name = frm.doc.name + "-FISCAL";

		frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: {
					doctype: "Factura Fiscal Mexico",
					name: fiscal_name,
					sales_invoice: frm.doc.name,
					status: "draft",
				},
			},
			callback: function (r) {
				if (r.message) {
					// Actualizar referencia en Sales Invoice
					frm.set_value("fm_factura_fiscal_mx", r.message.name);
					frm.save();

					if (callback) callback(r);
				}
			},
		});
	}
}

function update_fiscal_field(frm, fieldname, value, callback) {
	// Comentario actualizado
	get_or_create_fiscal_doc(frm, function (r) {
		if (r.message) {
			const fiscal_name = r.message.name;

			frappe.call({
				method: "frappe.client.set_value",
				args: {
					doctype: "Factura Fiscal Mexico",
					name: fiscal_name,
					fieldname: fieldname,
					value: value,
				},
				callback: function (result) {
					if (result.message) {
						// Actualizar cache local
						if (!frm._fiscal_data) frm._fiscal_data = {};
						frm._fiscal_data[fieldname] = value;

						if (callback) callback(result);
					}
				},
			});
		}
	});
}

function add_fiscal_buttons(frm) {
	// Verificar si el cliente tiene RFC para mostrar botones fiscales
	if (!has_customer_rfc(frm)) {
		return;
	}

	// Obtener estado actual del timbrado desde datos fiscales
	const fiscal_status = get_current_fiscal_status(frm);

	// Botón principal de timbrado
	if (fiscal_status !== "Timbrada") {
		// Verificar si la factura está lista para timbrar
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
	if (fiscal_status === "Timbrada") {
		frm.add_custom_button(
			__("Cancelar Timbrado"),
			function () {
				cancelar_timbrado(frm);
			},
			__("Facturación Fiscal")
		);
	}

	// Botón para abrir Factura Fiscal Mexico
	if (frm.doc.fm_factura_fiscal_mx) {
		frm.add_custom_button(
			__("Ver Datos Fiscales"),
			function () {
				frappe.set_route("Form", "Factura Fiscal Mexico", frm.doc.fm_factura_fiscal_mx);
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
}

function get_current_fiscal_status(frm) {
	// Comentario actualizado
	if (frm._fiscal_data && frm._fiscal_data.fm_fiscal_status) {
		return frm._fiscal_data.fm_fiscal_status;
	}

	// Fallback al campo fm_fiscal_status de Sales Invoice (temporal)
	return frm.doc.fm_fiscal_status || "Pendiente";
}

function validate_fiscal_data_for_button(frm) {
	// Comentario actualizado
	const required_fields = ["customer"];

	// Verificar campos básicos en Sales Invoice
	for (let field of required_fields) {
		if (!frm.doc[field]) {
			return false;
		}
	}

	// Verificar datos fiscales
	if (!frm._fiscal_data) return false;

	const fiscal = frm._fiscal_data;

	// Validar campos fiscales requeridos
	if (!fiscal.fm_cfdi_use) return false;
	if (!fiscal.fm_payment_method_sat) return false;

	// Validar PUE vs PPD
	if (fiscal.fm_payment_method_sat === "PUE") {
		// PUE requiere forma de pago específica
		const forma_pago = get_forma_pago_from_fiscal_data(fiscal);
		if (!forma_pago || forma_pago === "99") {
			return false;
		}
	}

	return true;
}

function get_forma_pago_from_fiscal_data(fiscal_data) {
	// Comentario actualizado
	if (!fiscal_data.fm_forma_pago_timbrado) {
		return null;
	}

	// Extraer código SAT del formato "01 - Efectivo"
	const mode_parts = fiscal_data.fm_forma_pago_timbrado.split(" - ");
	if (mode_parts.length >= 2 && mode_parts[0].match(/^\d+$/)) {
		return mode_parts[0];
	}

	return null;
}

function show_missing_fiscal_data_dialog(frm) {
	// Comentario actualizado
	const missing_items = [];

	// Verificar campos básicos
	if (!frm.doc.customer) missing_items.push("• Cliente");

	// Verificar datos fiscales
	const fiscal = frm._fiscal_data || {};

	if (!fiscal.fm_cfdi_use) missing_items.push("• Uso del CFDI");
	if (!fiscal.fm_payment_method_sat) missing_items.push("• Método de Pago SAT (PUE/PPD)");

	// Validaciones específicas PUE
	if (fiscal.fm_payment_method_sat === "PUE") {
		const forma_pago = get_forma_pago_from_fiscal_data(fiscal);
		if (!forma_pago) {
			missing_items.push("• Forma de Pago para Timbrado");
		} else if (forma_pago === "99") {
			missing_items.push("• Forma de pago específica (no '99 - Por definir')");
		}
	}

	// Agregar botón para configurar datos fiscales
	missing_items.push("");
	missing_items.push("📝 Configure estos datos en la pestaña 'Datos Fiscales'");

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
		primary_action_label: __("Ir a Datos Fiscales"),
		primary_action: function () {
			if (frm.doc.fm_factura_fiscal_mx) {
				frappe.set_route("Form", "Factura Fiscal Mexico", frm.doc.fm_factura_fiscal_mx);
			} else {
				// Crear documento fiscal
				get_or_create_fiscal_doc(frm, function (r) {
					if (r.message) {
						frappe.set_route("Form", "Factura Fiscal Mexico", r.message.name);
					}
				});
			}
			d.hide();
		},
	});

	d.show();
}

// Mantener funciones existentes que no dependen de datos fiscales
function has_customer_rfc(frm) {
	if (!frm.doc.customer) return false;

	// Verificar si tenemos datos del cliente cargados
	return frappe.db.get_value("Customer", frm.doc.customer, ["tax_id"]).then((r) => {
		const customer = r.message;
		return !!customer.tax_id;
	});
}

function timbrar_factura(frm) {
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

function update_fiscal_status_display(frm) {
	// Actualizar indicadores visuales basados en el estado fiscal
	const fiscal_status = get_current_fiscal_status(frm);

	let indicator_color = "grey";
	let status_text = "Sin Estado";

	switch (fiscal_status) {
		case "Timbrada":
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
				// Actualizar en Factura Fiscal Mexico
				update_fiscal_field(
					frm,
					"fm_cfdi_use",
					r.message.fm_uso_cfdi_default,
					function () {
						frappe.show_alert({
							message: __("Uso CFDI asignado automáticamente desde Cliente"),
							indicator: "green",
						});

						// Recargar datos fiscales
						load_fiscal_data(frm);
					}
				);
			}
		})
		.catch((err) => {
			// Error silencioso, no interrumpir el flujo
			console.log("Error obteniendo uso CFDI default:", err);
		});
}
