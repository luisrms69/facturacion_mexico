// Factura Fiscal Mexico - JavaScript customizations
// Manejo de datos fiscales separados de Sales Invoice

frappe.ui.form.on("Factura Fiscal Mexico", {
	refresh: function (frm) {
		// Configurar interfaz del documento fiscal
		setup_fiscal_interface(frm);

		// Agregar botones de funcionalidad fiscal
		add_fiscal_buttons(frm);
	},

	onload: function (frm) {
		// Inicializar datos por defecto al cargar
		setup_default_values(frm);
	},

	fm_sales_invoice: function (frm) {
		// Cuando se selecciona Sales Invoice, cargar datos del cliente
		if (frm.doc.fm_sales_invoice) {
			load_customer_data_from_sales_invoice(frm);
		}
	},

	validate: function (frm) {
		// Validaciones antes de guardar
		validate_fiscal_data(frm);
	},
});

function setup_fiscal_interface(frm) {
	// Configurar interfaz específica para datos fiscales
	if (frm.doc.fm_fiscal_status === "Timbrado") {
		frm.set_df_property("fm_uuid_fiscal", "read_only", 1);
		frm.set_df_property("fm_serie_folio", "read_only", 1);
	}
}

function setup_default_values(frm) {
	// Establecer valores por defecto para nuevos documentos
	if (frm.is_new()) {
		frm.set_value("fm_fiscal_status", "Pendiente"); // Usar valor válido del DocType

		// Establecer método de pago por defecto
		if (!frm.doc.fm_payment_method_sat) {
			frm.set_value("fm_payment_method_sat", "PUE");
		}
	}
}

function load_customer_data_from_sales_invoice(frm) {
	// Cargar datos del cliente desde el Sales Invoice seleccionado
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Sales Invoice",
			name: frm.doc.fm_sales_invoice,
			fields: ["customer", "customer_name"],
		},
		callback: function (r) {
			if (r.message && r.message.customer) {
				// Auto-asignar uso CFDI default del cliente
				auto_assign_cfdi_from_customer(frm, r.message.customer);
			}
		},
	});
}

function auto_assign_cfdi_from_customer(frm, customer) {
	// Auto-asignar uso CFDI default cuando se selecciona cliente
	// ESTA ES LA IMPLEMENTACIÓN CORRECTA - En el DocType fiscal, no en Sales Invoice

	if (!customer) {
		return;
	}

	frappe.db
		.get_value("Customer", customer, "fm_uso_cfdi_default")
		.then((r) => {
			if (r.message && r.message.fm_uso_cfdi_default) {
				// Asignar directamente en este documento fiscal
				frm.set_value("fm_cfdi_use", r.message.fm_uso_cfdi_default);

				frappe.show_alert({
					message: __("Uso CFDI asignado automáticamente desde Cliente"),
					indicator: "green",
				});
			}
		})
		.catch((err) => {
			console.log("Error obteniendo uso CFDI default:", err);
		});
}

function validate_fiscal_data(frm) {
	// Validaciones específicas de datos fiscales

	// Validar que PUE tenga forma de pago específica
	if (frm.doc.fm_payment_method_sat === "PUE") {
		if (!frm.doc.fm_forma_pago_timbrado || frm.doc.fm_forma_pago_timbrado.startsWith("99 -")) {
			frappe.throw(__("Para método PUE debe especificar una forma de pago específica"));
		}
	}

	// Validar uso CFDI requerido
	if (!frm.doc.fm_cfdi_use) {
		frappe.throw(__("Uso del CFDI es requerido"));
	}
}

function add_fiscal_buttons(frm) {
	// Agregar botones de funcionalidad fiscal específica

	// Botón de timbrado (solo si está en estado pendiente)
	if (frm.doc.fm_fiscal_status === "Pendiente" || !frm.doc.fm_fiscal_status) {
		frm.add_custom_button(__("Timbrar Factura"), function () {
			timbrar_factura(frm);
		});

		// Hacer prominente
		frm.page.set_primary_action(__("Timbrar Factura"), function () {
			timbrar_factura(frm);
		});
	}

	// Botón de cancelación (solo si está timbrada)
	if (frm.doc.fm_fiscal_status === "Timbrada") {
		frm.add_custom_button(__("Cancelar Timbrado"), function () {
			cancelar_timbrado(frm);
		});
	}

	// Botón para probar conexión PAC
	frm.add_custom_button(__("Probar Conexión PAC"), function () {
		test_pac_connection(frm);
	});

	// Botón para ver Sales Invoice relacionado
	if (frm.doc.sales_invoice) {
		frm.add_custom_button(__("Ver Sales Invoice"), function () {
			frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
		});
	}
}

function timbrar_factura(frm) {
	// Función de timbrado principal
	frappe.confirm(__("¿Confirma que desea timbrar esta factura?"), function () {
		// Llamar API de timbrado
		frappe.call({
			method: "facturacion_mexico.facturacion_fiscal.timbrado_api.timbrar_factura",
			args: {
				sales_invoice: frm.doc.sales_invoice,
			},
			callback: function (r) {
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __("Factura timbrada exitosamente"),
						indicator: "green",
					});
					frm.reload_doc();
				} else {
					frappe.msgprint({
						title: __("Error en Timbrado"),
						message: r.message ? r.message.error : __("Error desconocido"),
						indicator: "red",
					});
				}
			},
		});
	});
}

function cancelar_timbrado(frm) {
	// Función de cancelación de timbrado
	frappe.confirm(__("¿Confirma que desea cancelar el timbrado de esta factura?"), function () {
		frappe.call({
			method: "facturacion_mexico.facturacion_fiscal.timbrado_api.cancelar_factura",
			args: {
				uuid: frm.doc.fm_uuid_fiscal,
			},
			callback: function (r) {
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __("Timbrado cancelado exitosamente"),
						indicator: "orange",
					});
					frm.reload_doc();
				} else {
					frappe.msgprint({
						title: __("Error en Cancelación"),
						message: r.message ? r.message.error : __("Error desconocido"),
						indicator: "red",
					});
				}
			},
		});
	});
}

function test_pac_connection(frm) {
	// Función para probar conexión con PAC
	frappe.call({
		method: "facturacion_mexico.facturacion_fiscal.timbrado_api.test_connection",
		callback: function (r) {
			if (r.message && r.message.success) {
				frappe.show_alert({
					message: __("Conexión con PAC exitosa"),
					indicator: "green",
				});
			} else {
				frappe.msgprint({
					title: __("Error de Conexión"),
					message: r.message ? r.message.error : __("No se pudo conectar con el PAC"),
					indicator: "red",
				});
			}
		},
	});
}
