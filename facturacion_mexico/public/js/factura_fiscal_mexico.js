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

	sales_invoice: function (frm) {
		// Cuando se selecciona Sales Invoice, cargar datos del cliente
		if (frm.doc.sales_invoice) {
			load_customer_data_from_sales_invoice(frm);
		}
	},

	customer: function (frm) {
		// Cuando cambia el customer, actualizar datos fiscales
		if (frm.doc.customer) {
			update_fiscal_data_from_customer(frm);
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

	// Si hay Sales Invoice pero no customer, cargar customer desde Sales Invoice
	if (frm.doc.sales_invoice && !frm.doc.customer) {
		load_customer_data_from_sales_invoice(frm);
	}
}

function load_customer_data_from_sales_invoice(frm) {
	// Cargar datos del cliente desde el Sales Invoice seleccionado
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Sales Invoice",
			name: frm.doc.sales_invoice,
			fields: ["customer", "customer_name", "grand_total"],
		},
		callback: function (r) {
			if (r.message && r.message.customer) {
				// Asignar customer al campo customer del DocType
				frm.set_value("customer", r.message.customer);

				// Auto-asignar uso CFDI default del cliente SI lo tiene configurado
				auto_assign_cfdi_from_customer(frm, r.message.customer);

				// Cargar total fiscal desde Sales Invoice
				if (r.message.grand_total) {
					frm.set_value("total_fiscal", r.message.grand_total);
				}
			}
		},
	});
}

function auto_assign_cfdi_from_customer(frm, customer) {
	// Lógica: Si customer tiene uso CFDI default configurado, cargarlo
	// Si no tiene, dejar vacío (no seleccionar nada por defecto)

	if (!customer) {
		return;
	}

	frappe.db
		.get_value("Customer", customer, "fm_uso_cfdi_default")
		.then((r) => {
			if (r.message && r.message.fm_uso_cfdi_default) {
				// Solo asignar SI el customer tiene configurado uso CFDI
				frm.set_value("fm_cfdi_use", r.message.fm_uso_cfdi_default);

				frappe.show_alert({
					message: __("Uso CFDI cargado desde configuración del Cliente"),
					indicator: "green",
				});
			} else {
				// Customer no tiene uso CFDI configurado - dejar vacío
				frm.set_value("fm_cfdi_use", "");
				console.log("Customer no tiene fm_uso_cfdi_default configurado - campo vacío");
			}
		})
		.catch((err) => {
			console.log("Error obteniendo uso CFDI default:", err);
			// En caso de error, dejar vacío
			frm.set_value("fm_cfdi_use", "");
		});
}

function update_fiscal_data_from_customer(frm) {
	// Actualizar datos fiscales cuando cambia el customer
	if (!frm.doc.customer) {
		return;
	}

	frappe.show_alert({
		message: __("Actualizando datos fiscales del cliente..."),
		indicator: "blue",
	});

	// Obtener datos fiscales del customer
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Customer",
			name: frm.doc.customer,
			fields: [
				"fm_uso_cfdi_default",
				"fm_regimen_fiscal_customer",
				"fm_codigo_postal_customer",
				"fm_rfc_customer",
			],
		},
		callback: function (r) {
			if (r.message) {
				// Actualizar uso CFDI si está configurado
				if (r.message.fm_uso_cfdi_default) {
					frm.set_value("fm_cfdi_use", r.message.fm_uso_cfdi_default);
				} else {
					// Limpiar campo si no hay default
					frm.set_value("fm_cfdi_use", "");
				}

				// Actualizar otros campos fiscales del customer si existen
				if (r.message.fm_regimen_fiscal_customer) {
					frm.set_value(
						"fm_regimen_fiscal_customer",
						r.message.fm_regimen_fiscal_customer
					);
				}
				if (r.message.fm_codigo_postal_customer) {
					frm.set_value(
						"fm_codigo_postal_customer",
						r.message.fm_codigo_postal_customer
					);
				}
				if (r.message.fm_rfc_customer) {
					frm.set_value("fm_rfc_customer", r.message.fm_rfc_customer);
				}

				frappe.show_alert({
					message: __("Datos fiscales actualizados desde el Cliente"),
					indicator: "green",
				});
			}
		},
		error: function () {
			frappe.show_alert({
				message: __("Error al cargar datos fiscales del Cliente"),
				indicator: "red",
			});
		},
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
	// OPCIÓN C: Solo botones específicos para operaciones FacturAPI
	// Save/Submit son manejados automáticamente por Frappe

	// Control del botón Cancel de Frappe: Solo disponible cuando está definitivamente cancelada
	if (frm.doc.fm_fiscal_status !== "Cancelada") {
		frm.page.clear_actions();
		// Re-agregar botones básicos excepto Cancel
		if (frm.doc.docstatus === 0) {
			frm.page.set_primary_action(__("Save"), () => frm.save());
			frm.page.set_secondary_action(__("Submit"), () => frm.submit());
		}
	}

	if (frm.doc.docstatus === 1 && frm.doc.fm_fiscal_status === "Pendiente") {
		// Botón FacturAPI: Timbrar solo cuando documento está submitted
		frm.add_custom_button(__("Timbrar con FacturAPI"), function () {
			timbrar_factura(frm);
		}).addClass("btn-primary");
	}

	if (frm.doc.docstatus === 1 && frm.doc.fm_fiscal_status === "Timbrada") {
		// Botón FacturAPI: Cancelar solo facturas timbradas
		frm.add_custom_button(__("Cancelar en FacturAPI"), function () {
			cancelar_timbrado(frm);
		}).addClass("btn-danger");
	}

	// Test conexión PAC (solo desarrollo)
	if (frappe.boot.developer_mode) {
		frm.add_custom_button(__("Test Conexión PAC"), function () {
			test_pac_connection(frm);
		}).addClass("btn-secondary");
	}

	// Navegación a Sales Invoice relacionada
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
