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

		// Debug button para probar visibilidad
		frm.add_custom_button(__("🔧 Debug Visibilidad"), function () {
			console.log("=== DEBUG MANUAL ===");
			control_field_visibility_by_status(frm);
		}).addClass("btn-warning");
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

	// Debug logging
	console.log(`[DEBUG] Estado fiscal actual: ${fiscal_status}`);
	console.log(`[DEBUG] Campos disponibles:`, Object.keys(frm.fields_dict));

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

	// Log para debugging
	console.log(`[Field Visibility] Estado: ${fiscal_status} - Visibilidad aplicada`);
}

function hide_fields(frm, field_list) {
	// Ocultar lista de campos
	field_list.forEach((fieldname) => {
		if (frm.fields_dict[fieldname]) {
			frm.set_df_property(fieldname, "hidden", 1);
			console.log(`[DEBUG] ✅ Ocultando campo: ${fieldname}`);
		} else {
			console.log(`[DEBUG] ❌ Campo no encontrado: ${fieldname}`);
		}
	});
}

function show_fields(frm, field_list) {
	// Mostrar lista de campos
	field_list.forEach((fieldname) => {
		if (frm.fields_dict[fieldname]) {
			frm.set_df_property(fieldname, "hidden", 0);
			console.log(`[DEBUG] ✅ Mostrando campo: ${fieldname}`);
		} else {
			console.log(`[DEBUG] ❌ Campo no encontrado: ${fieldname}`);
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
	console.log(`[DEBUG] Controlando visibilidad multi-sucursal`);

	// Verificar si multi-sucursal está habilitado a nivel de sitio
	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "System Settings",
			fieldname: ["multisucursal_enabled"],
		},
		callback: function (r) {
			const is_multisucursal_enabled = r.message && r.message.multisucursal_enabled;
			console.log(`[DEBUG] Multi-sucursal habilitado: ${is_multisucursal_enabled}`);

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
			console.log(`[DEBUG] Fallback: Verificando site_config.json`);
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

	console.log(`[DEBUG] Mostrando campos multi-sucursal`);
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

	console.log(`[DEBUG] Ocultando campos multi-sucursal`);
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
			console.log(`[DEBUG] Site config multi-sucursal: ${is_multisucursal_enabled}`);

			if (is_multisucursal_enabled) {
				show_multisucursal_fields(frm);
			} else {
				hide_multisucursal_fields(frm);
			}
		},
		error: function () {
			// Si falla todo, usar comportamiento por defecto (ocultar)
			console.log(
				`[DEBUG] Error verificando configuración - ocultando campos multi-sucursal por defecto`
			);
			hide_multisucursal_fields(frm);
		},
	});
}
