// Factura Fiscal Mexico - JavaScript customizations
// Manejo de datos fiscales separados de Sales Invoice

frappe.ui.form.on("Factura Fiscal Mexico", {
	refresh: function (frm) {
		// Configurar interfaz del documento fiscal
		setup_fiscal_interface(frm);

		// Configurar radio buttons para payment method
		setup_payment_method_radio_buttons(frm);

		// PUNTOS 8-9: Controlar visibilidad según estado de timbrado
		control_field_visibility_by_status(frm);

		// Agregar botones de funcionalidad fiscal
		add_fiscal_buttons(frm);

		// Validar visualmente los datos de facturación
		setTimeout(() => {
			validate_billing_data_visual(frm);
		}, 500);
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

		// Validar visualmente los datos de facturación después del cambio
		setTimeout(() => {
			validate_billing_data_visual(frm);
		}, 1000);
	},

	validate: function (frm) {
		// Validaciones antes de guardar
		validate_fiscal_data(frm);
	},

	fm_fiscal_status: function (frm) {
		// PUNTOS 8-9: Actualizar visibilidad cuando cambia el estado fiscal
		control_field_visibility_by_status(frm);
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
		// Si no hay customer, limpiar campos de datos de facturación
		clear_billing_data_fields(frm);
		return;
	}

	frappe.show_alert({
		message: __("Actualizando datos fiscales del cliente..."),
		indicator: "blue",
	});

	// PASO 1: Obtener datos básicos del customer para uso CFDI y campos fiscales legacy
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
				"tax_id", // RFC principal del customer
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

				// Actualizar otros campos fiscales del customer si existen (legacy)
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

				// PASO 2: Activar función backend para poblar datos de facturación automáticamente
				// Esta función usa populate_billing_data() que maneja dirección principal, CP, email, etc.
				trigger_billing_data_population(frm);

				frappe.show_alert({
					message: __("Datos fiscales y de facturación actualizados"),
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

		// Validar datos fiscales localmente
		frm.add_custom_button(__("Validar Datos"), function () {
			validate_customer_fiscal_data(frm);
		}).addClass("btn-info");

		// Validar RFC con FacturAPI/SAT
		frm.add_custom_button(__("Validar RFC/CSF"), function () {
			validate_rfc_with_external_service(frm);
		}).addClass("btn-info");
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

// ========================================
// IMPLEMENTACIÓN RADIO BUTTONS - Punto 5
// ========================================

function setup_payment_method_radio_buttons(frm) {
	// Solo aplicar en formulario cargado y campo presente
	if (!frm.doc || !frm.fields_dict.fm_payment_method_sat) {
		return;
	}

	// Esperar a que el DOM esté completamente cargado
	setTimeout(() => {
		try {
			convert_payment_method_to_radio(frm, "fm_payment_method_sat");

			// Aplicar reglas iniciales basadas en el valor actual
			const current_method = frm.doc.fm_payment_method_sat || "PUE";
			handle_payment_form_field_visibility(frm, current_method);
		} catch (error) {
			console.log("Error setting up radio buttons:", error);
		}
	}, 500);
}

function convert_payment_method_to_radio(frm, field_name) {
	const field = frm.fields_dict[field_name];
	if (!field || !field.$wrapper) {
		console.log(`Campo ${field_name} no encontrado o sin wrapper DOM`);
		return;
	}

	// Verificar si ya se convirtió
	if (field.$wrapper.find(".payment-method-radio-container").length > 0) {
		sync_radio_buttons_with_field(frm, field_name);
		return;
	}

	// Ocultar el select original
	field.$wrapper.find("select").hide();
	field.$wrapper.find(".control-label").hide();

	// Configurar radio buttons
	setup_radio_buttons(frm, field);
}

function setup_radio_buttons(frm, field) {
	const current_value = frm.doc.fm_payment_method_sat || "PUE";

	const radio_html = `
		<div class="payment-method-radio-container" style="padding: 8px 0;">
			<label class="control-label" style="margin-bottom: 8px; display: block; font-weight: 600;">
				Método de Pago SAT <span class="text-danger">*</span>
			</label>
			<div class="radio-group" style="display: flex; gap: 20px; align-items: center;">
				<label class="radio-option" style="display: flex; align-items: center; cursor: pointer; margin: 0;">
					<input type="radio" name="fm_payment_method_sat_radio" value="PUE"
						   ${current_value === "PUE" ? "checked" : ""}
						   style="margin-right: 8px;">
					<span><strong>PUE</strong> - Pago en una exhibición</span>
				</label>
				<label class="radio-option" style="display: flex; align-items: center; cursor: pointer; margin: 0;">
					<input type="radio" name="fm_payment_method_sat_radio" value="PPD"
						   ${current_value === "PPD" ? "checked" : ""}
						   style="margin-right: 8px;">
					<span><strong>PPD</strong> - Pago en parcialidades o diferido</span>
				</label>
			</div>
		</div>
	`;

	// Insertar radio buttons
	field.$wrapper.append(radio_html);

	// Configurar event listeners
	field.$wrapper.find('input[name="fm_payment_method_sat_radio"]').on("change", function () {
		const selected_value = $(this).val();
		const previous_value = frm.doc.fm_payment_method_sat;

		// Actualizar el campo en Frappe
		frm.set_value("fm_payment_method_sat", selected_value);

		// Actualizar resaltado visual
		update_radio_button_highlighting(field, selected_value);

		// Punto 6: Mostrar avisos detallados al cambiar método
		show_payment_method_change_notification(frm, previous_value, selected_value);

		// Punto 7: Manejar campo "Forma de pago para Timbrado"
		handle_payment_form_field_visibility(frm, selected_value);

		// Trigger validations si existen
		frm.trigger("fm_payment_method_sat");
	});

	// Aplicar estilos de hover y resaltado inicial
	field.$wrapper.find(".radio-option").hover(
		function () {
			if (!$(this).find("input").is(":checked")) {
				$(this).css("background-color", "#f8f9fa");
			}
		},
		function () {
			if (!$(this).find("input").is(":checked")) {
				$(this).css("background-color", "transparent");
			}
		}
	);

	// Aplicar resaltado inicial
	update_radio_button_highlighting(field, current_value);
}

function sync_radio_buttons_with_field(frm, field_name) {
	const current_value = frm.doc[field_name] || "PUE";
	const field = frm.fields_dict[field_name];
	const radio_container = field.$wrapper.find(".payment-method-radio-container");

	if (radio_container.length > 0) {
		radio_container.find(`input[value="${current_value}"]`).prop("checked", true);
		update_radio_button_highlighting(field, current_value);
	}
}

function show_payment_method_change_notification(frm, previous_value, new_value) {
	// Punto 6: Avisos detallados al cambiar método de pago
	if (previous_value === new_value) {
		return; // No hay cambio
	}

	let message = "";
	let title = "";
	let indicator = "blue";

	if (new_value === "PPD") {
		title = "✅ Método cambiado a PPD";
		message = `
			<strong>Pago en Parcialidades o Diferido (PPD)</strong><br>
			• Forma de pago se asignó automáticamente a "99 - Por definir"<br>
			• Campo "Forma de pago para Timbrado" se ocultó (no aplica para PPD)<br>
			• Este método es para facturas con términos de pago diferido
		`;
		indicator = "orange";
	} else if (new_value === "PUE") {
		title = "✅ Método cambiado a PUE";
		message = `
			<strong>Pago en Una Exhibición (PUE)</strong><br>
			• Debe especificar una forma de pago específica<br>
			• Campo "Forma de pago para Timbrado" ahora es visible<br>
			• NO puede usar "99 - Por definir" para PUE
		`;
		indicator = "green";
	}

	if (message) {
		frappe.show_alert(
			{
				message: `<strong>${__(title)}</strong><br>${__(message)}`,
				indicator: indicator,
			},
			8
		); // 8 segundos de duración
	}
}

function handle_payment_form_field_visibility(frm, payment_method) {
	// Punto 7: Manejar visibilidad del campo "Forma de pago para Timbrado"

	if (!frm.fields_dict.fm_forma_pago_timbrado) {
		return; // Campo no existe
	}

	if (payment_method === "PPD") {
		// Para PPD: Ocultar campo y asignar "99 - Por definir"
		frm.set_df_property("fm_forma_pago_timbrado", "hidden", 1);

		// Remover filtros para PPD (todas las opciones disponibles)
		frm.set_query("fm_forma_pago_timbrado", function () {
			return {}; // Sin filtros
		});

		frm.set_value("fm_forma_pago_timbrado", "99 - Por definir");

		frappe.show_alert({
			message: __("Forma de pago asignada automáticamente: 99 - Por definir"),
			indicator: "orange",
		});
	} else if (payment_method === "PUE") {
		// Para PUE: Mostrar campo y filtrar opciones (sin "99 - Por definir")
		frm.set_df_property("fm_forma_pago_timbrado", "hidden", 0);

		// Filtrar Mode of Payment para excluir "99 - Por definir"
		frm.set_query("fm_forma_pago_timbrado", function () {
			return {
				filters: [["Mode of Payment", "name", "!=", "99 - Por definir"]],
			};
		});

		// Limpiar si tenía "99 - Por definir"
		if (frm.doc.fm_forma_pago_timbrado === "99 - Por definir") {
			frm.set_value("fm_forma_pago_timbrado", "");

			frappe.show_alert({
				message: __("Debe seleccionar una forma de pago específica para PUE"),
				indicator: "yellow",
			});
		}
	}
}

function show_payment_method_feedback(method) {
	// Función simplificada para casos donde no hay cambio específico
	let message = "";
	let color = "blue";

	if (method === "PUE") {
		message = "PUE: Requiere forma de pago específica (no '99 - Por definir')";
		color = "green";
	} else if (method === "PPD") {
		message = "PPD: Automáticamente usará '99 - Por definir' como forma de pago";
		color = "orange";
	}

	if (message) {
		frappe.show_alert({
			message: __(message),
			indicator: color,
		});
	}
}

function update_radio_button_highlighting(field, selected_value) {
	// Función para resaltar visualmente la opción seleccionada

	// Limpiar estilos previos
	field.$wrapper.find(".radio-option").css({
		"background-color": "transparent",
		border: "none",
		"border-radius": "0px",
		padding: "0px",
	});

	// Aplicar estilo según la opción seleccionada
	if (selected_value === "PUE") {
		// Verde suave para PUE
		field.$wrapper.find(".radio-option").has('input[value="PUE"]').css({
			"background-color": "#d4edda",
			border: "2px solid #28a745",
			"border-radius": "8px",
			padding: "8px 12px",
			"box-shadow": "0 2px 4px rgba(40, 167, 69, 0.2)",
		});
	} else if (selected_value === "PPD") {
		// Naranja suave para PPD
		field.$wrapper.find(".radio-option").has('input[value="PPD"]').css({
			"background-color": "#fff3cd",
			border: "2px solid #ffc107",
			"border-radius": "8px",
			padding: "8px 12px",
			"box-shadow": "0 2px 4px rgba(255, 193, 7, 0.2)",
		});
	}
}

// ========================================
// IMPLEMENTACIÓN PUNTOS 8-9: Visibilidad Dinámica por Estado
// ========================================

function control_field_visibility_by_status(frm) {
	// Control dinámico de visibilidad según fm_fiscal_status
	const fiscal_status = frm.doc.fm_fiscal_status || "Pendiente";

	// Campos que vienen de FacturAPI response (Punto 8)
	const facturapi_response_fields = [
		"uuid", // UUID fiscal del SAT (DocType field)
		"serie", // Serie de la factura (DocType field)
		"folio", // Folio de la factura (DocType field)
		"total_fiscal", // Total de la factura fiscal (DocType field)
		"facturapi_id", // ID retornado por FacturAPI.io (DocType field)
		"fm_uuid_fiscal", // UUID fiscal custom field (si existe)
		"fm_serie_folio", // Serie y Folio custom field (si existe)
	];

	// Campos de archivos fiscales
	const fiscal_files_fields = [
		"pdf_file", // Archivo PDF
		"xml_file", // Archivo XML
	];

	// Campos y sección de cancelación (Punto 9)
	const cancellation_fields = [
		"cancellation_reason", // Motivo de Cancelación
		"cancellation_date", // Fecha de Cancelación
	];

	// NUEVA FUNCIONALIDAD: Control de lugar_expedicion basado en multi-sucursal
	control_multisucursal_field_visibility(frm);

	// Lógica de visibilidad según estado
	if (fiscal_status === "Pendiente") {
		// ESTADO PENDIENTE: Ocultar todo lo que viene después del timbrado
		hide_fields(frm, facturapi_response_fields);
		hide_fields(frm, fiscal_files_fields);
		hide_fields(frm, cancellation_fields);
		hide_section(frm, "section_break_archivos"); // Sección Archivos Fiscales
		hide_section(frm, "section_break_cancelacion"); // Sección Cancelación
	} else if (fiscal_status === "Timbrada") {
		// ESTADO TIMBRADA: Mostrar datos de FacturAPI, ocultar cancelación
		show_fields(frm, facturapi_response_fields);
		show_fields(frm, fiscal_files_fields);
		hide_fields(frm, cancellation_fields);
		show_section(frm, "section_break_archivos"); // Mostrar Archivos Fiscales
		hide_section(frm, "section_break_cancelacion"); // Ocultar Cancelación
	} else if (fiscal_status === "Cancelada") {
		// ESTADO CANCELADA: Mostrar todo incluyendo información de cancelación
		show_fields(frm, facturapi_response_fields);
		show_fields(frm, fiscal_files_fields);
		show_fields(frm, cancellation_fields);
		show_section(frm, "section_break_archivos"); // Mostrar Archivos Fiscales
		show_section(frm, "section_break_cancelacion"); // Mostrar Cancelación
	} else if (fiscal_status === "Error") {
		// ESTADO ERROR: Mostrar campos básicos, ocultar respuesta y cancelación
		hide_fields(frm, facturapi_response_fields);
		hide_fields(frm, fiscal_files_fields);
		hide_fields(frm, cancellation_fields);
		hide_section(frm, "section_break_archivos");
		hide_section(frm, "section_break_cancelacion");
	} else if (fiscal_status === "Solicitud Cancelación") {
		// ESTADO SOLICITUD CANCELACIÓN: Como timbrada pero indicando proceso
		show_fields(frm, facturapi_response_fields);
		show_fields(frm, fiscal_files_fields);
		hide_fields(frm, cancellation_fields);
		show_section(frm, "section_break_archivos");
		hide_section(frm, "section_break_cancelacion"); // Aún no confirmada
	}
}

function hide_fields(frm, field_list) {
	// Ocultar lista de campos
	field_list.forEach((fieldname) => {
		if (frm.fields_dict[fieldname]) {
			frm.set_df_property(fieldname, "hidden", 1);
		}
	});
}

function show_fields(frm, field_list) {
	// Mostrar lista de campos
	field_list.forEach((fieldname) => {
		if (frm.fields_dict[fieldname]) {
			frm.set_df_property(fieldname, "hidden", 0);
		}
	});
}

function hide_section(frm, section_fieldname) {
	// Ocultar sección completa
	if (frm.fields_dict[section_fieldname]) {
		frm.set_df_property(section_fieldname, "hidden", 1);
	}
}

function show_section(frm, section_fieldname) {
	// Mostrar sección completa
	if (frm.fields_dict[section_fieldname]) {
		frm.set_df_property(section_fieldname, "hidden", 0);
	}
}

// ========================================
// FUNCIONALIDAD MULTI-SUCURSAL
// ========================================

function control_multisucursal_field_visibility(frm) {
	// Control de visibilidad de campos multi-sucursal basado en configuración

	// Verificar si multi-sucursal está habilitado a nivel de sitio
	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "System Settings",
			fieldname: ["multisucursal_enabled"],
		},
		callback: function (r) {
			const is_multisucursal_enabled = r.message && r.message.multisucursal_enabled;

			// Controlar visibilidad del campo lugar_expedicion
			if (is_multisucursal_enabled) {
				// Si multi-sucursal está habilitado, mostrar lugar_expedicion
				show_multisucursal_fields(frm);
			} else {
				// Si multi-sucursal NO está habilitado, ocultar lugar_expedicion
				hide_multisucursal_fields(frm);
			}
		},
		error: function () {
			// En caso de error, verificar por site_config.json
			check_site_config_multisucursal(frm);
		},
	});
}

function show_multisucursal_fields(frm) {
	// Mostrar campos relacionados con multi-sucursal
	const multisucursal_fields = [
		"fm_lugar_expedicion", // Campo lugar de expedición
		"fm_branch", // Campo de sucursal si existe
		"fm_serie_folio", // Serie y folio específico de sucursal
	];

	show_fields(frm, multisucursal_fields);

	// Mostrar sección multi-sucursal si existe
	show_section(frm, "section_break_multisucursal");
	show_section(frm, "fm_multibranch_section");

	// Agregar indicador visual de multi-sucursal activo
	if (!frm.doc.__multisucursal_indicator_shown) {
		frappe.show_alert(
			{
				message: __("Modo Multi-Sucursal activado - Lugar de expedición disponible"),
				indicator: "blue",
			},
			3
		);
		frm.doc.__multisucursal_indicator_shown = true;
	}
}

function hide_multisucursal_fields(frm) {
	// Ocultar campos relacionados con multi-sucursal
	const multisucursal_fields = [
		"fm_lugar_expedicion", // Campo lugar de expedición
		"fm_branch", // Campo de sucursal si existe
		"fm_serie_folio", // Serie y folio específico de sucursal
	];

	hide_fields(frm, multisucursal_fields);

	// Ocultar sección multi-sucursal si existe
	hide_section(frm, "section_break_multisucursal");
	hide_section(frm, "fm_multibranch_section");
}

function check_site_config_multisucursal(frm) {
	// Verificar configuración multi-sucursal en site_config.json
	frappe.call({
		method: "frappe.utils.get_site_config",
		args: {
			key: "multisucursal_enabled",
		},
		callback: function (r) {
			const is_multisucursal_enabled = r.message === 1 || r.message === true;

			if (is_multisucursal_enabled) {
				show_multisucursal_fields(frm);
			} else {
				hide_multisucursal_fields(frm);
			}
		},
		error: function () {
			// Si falla todo, usar comportamiento por defecto (ocultar)
			hide_multisucursal_fields(frm);
		},
	});
}

function validate_customer_fiscal_data(frm) {
	// Función para validar RFC y datos fiscales del cliente
	if (!frm.doc.customer) {
		frappe.msgprint({
			title: __("Cliente Requerido"),
			message: __("Debe seleccionar un cliente para validar datos fiscales"),
			indicator: "red",
		});
		return;
	}

	frappe.show_alert({
		message: __("Validando datos fiscales del cliente..."),
		indicator: "blue",
	});

	frappe.call({
		method: "facturacion_mexico.facturacion_fiscal.validations.validate_customer_fiscal_data",
		args: {
			customer: frm.doc.customer,
		},
		callback: function (r) {
			if (r.message && r.message.success) {
				const data = r.message.data;

				// Mostrar resultados de validación
				let validation_html = `
					<div style="font-family: monospace; line-height: 1.6;">
						<h4 style="color: #2ecc71; margin-bottom: 15px;">✅ Validación RFC/Datos Fiscales</h4>
						<p style="color: #f39c12; font-size: 12px; margin-bottom: 10px; font-style: italic;">
							📝 Nota: Validación local de formato únicamente, no verifica con SAT
						</p>
						<table style="width: 100%; border-collapse: collapse;">
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">RFC:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee; color: ${
									data.rfc_valid ? "#2ecc71" : "#e74c3c"
								};">
									${data.rfc || "No configurado"} ${data.rfc_valid ? "✅" : "❌"}
								</td>
							</tr>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Formato RFC:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee; color: ${
									data.rfc_format_valid ? "#2ecc71" : "#e74c3c"
								};">
									${data.rfc_format_valid ? "Válido ✅" : "Inválido ❌"}
								</td>
							</tr>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Dirección:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee; color: ${
									data.address_configured ? "#2ecc71" : "#e74c3c"
								};">
									${data.address_configured ? "Configurada ✅" : "Faltante ❌"}
								</td>
							</tr>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Email:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee; color: ${
									data.email_configured ? "#2ecc71" : "#f39c12"
								};">
									${data.email_configured ? "Configurado ✅" : "Recomendado ⚠️"}
								</td>
							</tr>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Uso CFDI Default:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee; color: ${
									data.cfdi_use_configured ? "#2ecc71" : "#f39c12"
								};">
									${data.cfdi_use_configured ? "Configurado ✅" : "Opcional ⚠️"}
								</td>
							</tr>
						</table>
						<div style="margin-top: 15px; padding: 10px; background-color: ${
							data.ready_for_invoicing ? "#d4edda" : "#f8d7da"
						}; border-radius: 5px;">
							<strong>Estado General:</strong> ${
								data.ready_for_invoicing
									? "Listo para facturación ✅"
									: "Requiere configuración ❌"
							}
						</div>
					</div>
				`;

				if (data.recommendations && data.recommendations.length > 0) {
					validation_html += `
						<div style="margin-top: 15px; padding: 10px; background-color: #fff3cd; border-radius: 5px;">
							<strong>Recomendaciones:</strong>
							<ul style="margin: 5px 0 0 20px;">
								${data.recommendations.map((rec) => `<li>${rec}</li>`).join("")}
							</ul>
						</div>
					`;
				}

				frappe.msgprint({
					title: __("Validación Datos Fiscales"),
					message: validation_html,
					indicator: data.ready_for_invoicing ? "green" : "orange",
					wide: true,
				});
			} else {
				frappe.msgprint({
					title: __("Error de Validación"),
					message: r.message
						? r.message.error
						: __("Error desconocido validando datos fiscales"),
					indicator: "red",
				});
			}
		},
		error: function (err) {
			frappe.msgprint({
				title: __("Error de Conexión"),
				message:
					__("No se pudo conectar al servicio de validación:") +
					" " +
					(err.message || "Error desconocido"),
				indicator: "red",
			});
		},
	});
}

function validate_rfc_with_external_service(frm) {
	// Validación RFC/CSD con servicios externos (FacturAPI/SAT)
	if (!frm.doc.customer) {
		frappe.msgprint({
			title: __("Cliente Requerido"),
			message: __("Debe seleccionar un cliente para validar RFC con servicios externos"),
			indicator: "red",
		});
		return;
	}

	frappe.show_alert({
		message: __("Validando RFC con FacturAPI/SAT..."),
		indicator: "blue",
	});

	frappe.call({
		method: "facturacion_mexico.facturacion_fiscal.validations.validate_rfc_external",
		args: {
			customer: frm.doc.customer,
		},
		callback: function (r) {
			// DEBUG: Solo log si hay debug_data disponible para troubleshooting
			if (r.message && r.message.data && r.message.data.debug_data) {
				console.log("🔍 [RFC_VALIDATION] debug_data:", r.message.data.debug_data);
			}

			if (r.message && r.message.success) {
				const data = r.message.data;

				// Mostrar resultados de validación externa
				let validation_html = `
					<div style="font-family: monospace; line-height: 1.6;">
						<h4 style="color: #2ecc71; margin-bottom: 15px;">🌐 Validación RFC con Servicios Externos</h4>
						<p style="color: #007bff; font-size: 12px; margin-bottom: 10px; font-style: italic;">
							🔍 Verificación en tiempo real con ${data.service_used || "FacturAPI/SAT"}
						</p>
						<table style="width: 100%; border-collapse: collapse;">
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">RFC:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee; color: ${
									data.rfc_exists ? "#2ecc71" : "#e74c3c"
								};">
									${data.rfc || "No configurado"} ${data.rfc_exists ? "✅ Existe" : "❌ No encontrado"}
								</td>
							</tr>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Estado SAT:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee; color: ${
									data.rfc_active ? "#2ecc71" : "#e74c3c"
								};">
									${data.rfc_active ? "Activo ✅" : "Inactivo/Cancelado ❌"}
								</td>
							</tr>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Razón Social:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee; color: ${
									data.name_matches ? "#2ecc71" : "#f39c12"
								};">
									${data.sat_name || "No disponible"} ${data.name_matches ? "✅" : "⚠️"}
								</td>
							</tr>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Régimen Fiscal:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee;">
									${data.tax_regime || "No disponible"}
								</td>
							</tr>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Código Postal:</td>
								<td style="padding: 8px; border-bottom: 1px solid #eee; color: ${
									data.postal_code_valid ? "#2ecc71" : "#f39c12"
								};">
									${data.postal_code || "No disponible"} ${data.postal_code_valid ? "✅" : "⚠️"}
								</td>
							</tr>
						</table>
						<div style="margin-top: 15px; padding: 10px; background-color: ${
							data.valid_for_invoicing ? "#d4edda" : "#f8d7da"
						}; border-radius: 5px;">
							<strong>Resultado:</strong> ${
								data.valid_for_invoicing
									? "RFC válido para facturación ✅"
									: "RFC no válido o inactivo ❌"
							}
						</div>
					</div>
				`;

				if (data.warnings && data.warnings.length > 0) {
					validation_html += `
						<div style="margin-top: 15px; padding: 10px; background-color: #fff3cd; border-radius: 5px;">
							<strong>Advertencias:</strong>
							<ul style="margin: 5px 0 0 20px;">
								${data.warnings.map((warning) => `<li>${warning}</li>`).join("")}
							</ul>
						</div>
					`;
				}

				// Mostrar datos de debugging si están disponibles (SIEMPRE, tanto en éxito como error)
				if (data.debug_data) {
					console.log("✅ Agregando sección debug_data al HTML");

					// Escapar datos para evitar errores de HTML
					const address_str = data.debug_data.address_enviada
						? JSON.stringify(data.debug_data.address_enviada).replace(/"/g, "&quot;")
						: "N/A";

					validation_html += `
						<div style="margin-top: 15px; padding: 10px; background-color: #e9ecef; border-radius: 5px; border-left: 4px solid #007bff;">
							<strong>📋 Datos Enviados a FacturAPI (Debug):</strong>
							<ul style="margin: 5px 0 0 20px; font-family: monospace; font-size: 12px; line-height: 1.4;">
								<li><strong>Nombre enviado:</strong> <code>${data.debug_data.customer_name || "N/A"}</code></li>
								<li><strong>RFC enviado:</strong> <code>${data.debug_data.rfc_enviado || "N/A"}</code></li>
								<li><strong>Régimen fiscal:</strong> <code>${
									data.debug_data.tax_system_enviado || "N/A"
								}</code></li>
								<li><strong>Email:</strong> <code>${data.debug_data.email_enviado || "N/A"}</code></li>
								<li><strong>Dirección:</strong> <span style="font-size: 10px;">${address_str}</span></li>
							</ul>
							<div style="margin-top: 10px; padding: 8px; background-color: #fff3cd; border-radius: 3px; font-size: 11px;">
								💡 <strong>Solución:</strong> El nombre del Customer debe coincidir exactamente con el registrado en SAT (mayúsculas, sin acentos, sin "S.A. de C.V.")
							</div>
						</div>
					`;
				} else {
					console.log("❌ debug_data no disponible para mostrar");
				}

				frappe.msgprint({
					title: __("Validación RFC Externa"),
					message: validation_html,
					indicator: data.valid_for_invoicing ? "green" : "red",
					wide: true,
				});
			} else {
				// Mostrar error con información de debugging si está disponible
				let error_message = r.message
					? r.message.error
					: __("Error validando RFC con servicios externos");

				// Si hay datos de debugging, mostrarlos
				if (r.message && r.message.data && r.message.data.debug_data) {
					const debug_data = r.message.data.debug_data;
					error_message += `
						<br><br><strong>📋 Datos enviados a FacturAPI:</strong>
						<ul style="text-align: left; margin: 10px 0;">
							<li><strong>Nombre enviado:</strong> ${debug_data.customer_name || "N/A"}</li>
							<li><strong>RFC enviado:</strong> ${debug_data.rfc_enviado || "N/A"}</li>
							<li><strong>Régimen fiscal:</strong> ${debug_data.tax_system_enviado || "N/A"}</li>
							<li><strong>Email:</strong> ${debug_data.email_enviado || "N/A"}</li>
							<li><strong>Dirección:</strong> ${
								debug_data.address_enviada
									? JSON.stringify(debug_data.address_enviada)
									: "N/A"
							}</li>
						</ul>
					`;
				}

				frappe.msgprint({
					title: __("Error de Validación Externa"),
					message: error_message,
					indicator: "red",
					wide: true,
				});
			}
		},
		error: function (err) {
			frappe.msgprint({
				title: __("Error de Conexión"),
				message:
					__("No se pudo conectar al servicio de validación RFC:") +
					" " +
					(err.message || "Error desconocido"),
				indicator: "red",
			});
		},
	});
}

// ========================================
// VALIDACIÓN VISUAL DATOS DE FACTURACIÓN
// ========================================

function validate_billing_data_visual(frm) {
	// Validación visual de campos de datos de facturación con resaltado rojo para campos faltantes
	console.log("🔧 [DEBUG] validate_billing_data_visual ejecutándose...");

	if (!frm.doc) {
		console.log("❌ [DEBUG] frm.doc no existe");
		return;
	}

	console.log("✅ [DEBUG] frm.doc existe, customer:", frm.doc.customer);

	// Campos de datos de facturación a validar
	const billing_fields = [
		{
			fieldname: "fm_cp_cliente",
			label: "CP Cliente",
			required: true,
			check_value: frm.doc.fm_cp_cliente,
		},
		{
			fieldname: "fm_email_facturacion",
			label: "Email Facturación",
			required: true,
			check_value: frm.doc.fm_email_facturacion,
		},
		{
			fieldname: "fm_rfc_cliente",
			label: "RFC Cliente",
			required: true,
			check_value: frm.doc.fm_rfc_cliente,
		},
		{
			fieldname: "fm_direccion_principal_display",
			label: "Dirección Principal",
			required: true,
			check_value:
				frm.doc.fm_direccion_principal_display &&
				!frm.doc.fm_direccion_principal_display.includes("⚠️ FALTA DIRECCIÓN"),
		},
	];

	console.log("📋 [DEBUG] billing_fields configurados:", billing_fields.length);

	// Aplicar validación visual a cada campo
	billing_fields.forEach((field) => {
		console.log(`🔍 [DEBUG] Validando campo ${field.fieldname}:`, field.check_value);
		apply_visual_validation(frm, field);
	});

	// Mostrar resumen de validación si hay campos faltantes
	const missing_fields = billing_fields.filter((field) => !field.check_value);
	console.log("⚠️ [DEBUG] Campos faltantes:", missing_fields.length);

	if (missing_fields.length > 0 && frm.doc.customer) {
		console.log("🚨 [DEBUG] Mostrando resumen de campos faltantes");
		show_billing_data_summary(frm, missing_fields);
	}
}

function apply_visual_validation(frm, field_config) {
	// Aplicar estilo visual a campo según validación
	console.log(`🎨 [DEBUG] Aplicando validación visual a ${field_config.fieldname}`);

	const field_wrapper = frm.fields_dict[field_config.fieldname];
	if (!field_wrapper || !field_wrapper.$wrapper) {
		console.log(`❌ [DEBUG] Campo ${field_config.fieldname} no encontrado en DOM`);
		return;
	}

	console.log(`✅ [DEBUG] Campo ${field_config.fieldname} encontrado en DOM`);

	// Remover estilos previos
	field_wrapper.$wrapper.find(".control-input").removeClass("billing-error billing-success");
	field_wrapper.$wrapper.find(".billing-validation-icon").remove();

	if (field_config.required && !field_config.check_value) {
		console.log(`🔴 [DEBUG] Campo ${field_config.fieldname} FALTANTE - aplicando estilo rojo`);
		// Campo faltante - resaltar en rojo
		const control_input = field_wrapper.$wrapper.find(".control-input");
		console.log(`🎯 [DEBUG] control-input encontrado:`, control_input.length);
		control_input.addClass("billing-error");

		// Agregar icono de error
		field_wrapper.$wrapper.find(".control-input").append(`
			<span class="billing-validation-icon" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); color: #e74c3c; font-weight: bold;">
				❌
			</span>
		`);

		// Agregar tooltip explicativo
		field_wrapper.$wrapper
			.find(".control-input")
			.attr("title", `${field_config.label} es requerido para facturación fiscal`);
	} else if (field_config.check_value) {
		// Campo válido - resaltar en verde
		field_wrapper.$wrapper.find(".control-input").addClass("billing-success");

		// Agregar icono de éxito
		field_wrapper.$wrapper.find(".control-input").append(`
			<span class="billing-validation-icon" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); color: #2ecc71; font-weight: bold;">
				✅
			</span>
		`);

		// Agregar tooltip de confirmación
		field_wrapper.$wrapper
			.find(".control-input")
			.attr("title", `${field_config.label} configurado correctamente`);
	}
}

function show_billing_data_summary(frm, missing_fields) {
	// Mostrar resumen de campos faltantes en datos de facturación
	if (!frm.doc.customer || missing_fields.length === 0) return;

	// Solo mostrar cada 30 segundos para evitar spam
	const now = Date.now();
	const last_shown = frm._last_billing_alert || 0;
	if (now - last_shown < 30000) return;
	frm._last_billing_alert = now;

	const missing_list = missing_fields.map((field) => field.label).join(", ");

	frappe.show_alert(
		{
			message: `⚠️ Datos de facturación incompletos: ${missing_list}. Configure estos datos en el Cliente.`,
			indicator: "orange",
		},
		8
	);
}

// Agregar estilos CSS para validación visual
if (!$("#billing-validation-styles").length) {
	$("head").append(`
		<style id="billing-validation-styles">
			.billing-error .form-control {
				border: 2px solid #e74c3c !important;
				background-color: #fdf2f2 !important;
				box-shadow: 0 0 5px rgba(231, 76, 60, 0.3) !important;
			}

			.billing-success .form-control {
				border: 2px solid #2ecc71 !important;
				background-color: #f2fdf2 !important;
				box-shadow: 0 0 5px rgba(46, 204, 113, 0.3) !important;
			}

			.billing-error .form-control:focus {
				border-color: #c0392b !important;
				box-shadow: 0 0 8px rgba(231, 76, 60, 0.5) !important;
			}

			.billing-success .form-control:focus {
				border-color: #27ae60 !important;
				box-shadow: 0 0 8px rgba(46, 204, 113, 0.5) !important;
			}

			.control-input {
				position: relative;
			}
		</style>
	`);
}

// ========================================
// FUNCIONES AUXILIARES DATOS DE FACTURACIÓN
// ========================================

function trigger_billing_data_population(frm) {
	// Activar función backend para poblar datos de facturación desde customer
	if (!frm.doc.customer) return;

	// Guardar documento para activar populate_billing_data() en before_save()
	frm.save()
		.then(() => {
			// Recargar para mostrar datos actualizados
			frm.reload_doc();

			// Activar validación visual después de recargar
			setTimeout(() => {
				validate_billing_data_visual(frm);
			}, 500);
		})
		.catch((err) => {
			console.log("Error activando población de datos de facturación:", err);

			// Si falla el save, al menos intentar validación visual con datos actuales
			validate_billing_data_visual(frm);
		});
}

function clear_billing_data_fields(frm) {
	// Limpiar campos de datos de facturación cuando no hay customer
	const billing_fields = [
		"fm_cp_cliente",
		"fm_email_facturacion",
		"fm_rfc_cliente",
		"fm_direccion_principal_link",
		"fm_direccion_principal_display",
	];

	billing_fields.forEach((fieldname) => {
		frm.set_value(fieldname, "");
	});

	// Limpiar validación visual
	setTimeout(() => {
		validate_billing_data_visual(frm);
	}, 100);
}
