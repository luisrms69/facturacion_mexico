// Factura Fiscal Mexico - JavaScript customizations
// Manejo de datos fiscales separados de Sales Invoice

// console.log("✅ Cargando JS para Factura Fiscal Mexico desde directorio DocType");

(function () {
	// Guard contra doble inyección
	if (window.__FFM_UI_BIND__) return;
	window.__FFM_UI_BIND__ = true;

	let FISCAL_STATES = null;

	function load_fiscal_states(cb) {
		if (FISCAL_STATES) {
			cb && cb(FISCAL_STATES);
			return;
		}
		frappe.call({
			method: "facturacion_mexico.facturacion_fiscal.api.get_fiscal_states",
			callback: function (r) {
				FISCAL_STATES = r.message || null;
				cb && cb(FISCAL_STATES);
			},
		});
	}

	function norm(v) {
		return (v || "").toString().trim().toUpperCase();
	}
	function isValidTaxSystem(ts) {
		return ts && !ts.startsWith("⚠️") && !ts.startsWith("❌");
	}

	function controlCancelSection(frm, show) {
		const f = frm.get_field("section_break_cancelacion");
		if (f && f.$wrapper) f.$wrapper.toggle(!!show);
	}

	function addTimbrarButton(frm, status) {
		// Usar estados centralizados para determinar label
		load_fiscal_states(function (states) {
			const label =
				states && status === states.states.ERROR
					? __("Reintentar Timbrado")
					: __("Timbrar con FacturAPI");
			frm.add_custom_button(label, function () {
				timbrar_factura(frm);
			}).addClass("btn-primary");
		});
	}

	function handleButtonsWithFallback(frm, status) {
		// Fallback usando estados básicos (solo cuando no hay API disponible)
		const canTimbrar =
			frm.doc.docstatus === 1 &&
			(status === "BORRADOR" || status === "ERROR") &&
			isValidTaxSystem(frm.doc.fm_tax_system);

		const showCancel = status === "TIMBRADO" || status === "CANCELADO";

		controlCancelSection(frm, showCancel);
		if (frm.clear_custom_buttons) frm.clear_custom_buttons();
		if (canTimbrar) addTimbrarButton(frm, status);

		// Reponer navegación también en fallback
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("Ver Sales Invoice"), function () {
				frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
			});
		}
	}

	function applyFFMUi(frm) {
		const status = norm(frm.doc.fm_fiscal_status);

		load_fiscal_states(function (states) {
			if (!states) {
				console.warn("[FFM] No fiscal states config, usando fallback");
				handleButtonsWithFallback(frm, status);
				return;
			}

			// Usa fuente central: states.timbrable_states / cancelable_states / final_states
			const canTimbrar =
				frm.doc.docstatus === 1 &&
				states.timbrable_states.includes(status) &&
				isValidTaxSystem(frm.doc.fm_tax_system);

			const showCancel =
				states.cancelable_states.includes(status) || states.final_states.includes(status);

			controlCancelSection(frm, showCancel);
			if (frm.clear_custom_buttons) frm.clear_custom_buttons();
			if (canTimbrar) addTimbrarButton(frm, status);

			// --- BOTÓN DE CANCELACIÓN (repuesto) ---
			const syncStatus = (frm.doc.fm_sync_status || "").trim().toLowerCase();

			// Puede cancelar si:
			// 1) el doc está enviado (docstatus=1)
			// 2) el estado fiscal actual está en la lista de cancelables (desde API centralizada)
			// 3) NO está en pendiente de cancelación (evita duplicar solicitudes)
			const canCancelar =
				frm.doc.docstatus === 1 &&
				states.cancelable_states.includes(status) &&
				syncStatus !== "pending";

			// Muestra/oculta sección de cancelación y agrega botón
			const cancelSection = frm.get_field("section_break_cancelacion");
			if (canCancelar) {
				if (cancelSection && cancelSection.$wrapper) cancelSection.$wrapper.show();

				frm.add_custom_button(__("Cancelar en FacturAPI"), function () {
					cancelar_timbrado(frm);
				}).addClass("btn-danger");
			} else {
				if (cancelSection && cancelSection.$wrapper) cancelSection.$wrapper.hide();
			}

			// Reponer botón de navegación SIEMPRE que exista Sales Invoice
			if (frm.doc.sales_invoice) {
				frm.add_custom_button(__("Ver Sales Invoice"), function () {
					frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
				});
			}

			// --- Dev only: botón de prueba de conexión PAC ---
			// Evitar duplicados entre refresh con un flag simple
			if (frappe.boot.developer_mode && !frm._ffm_dev_test_btn_added) {
				frm.add_custom_button(__("Test Conexión PAC"), function () {
					try {
						// Esta función ya existe en el archivo (según tu código)
						test_pac_connection(frm);
					} catch (e) {
						console && console.error("[FFM] test_pac_connection no disponible:", e);
						const d1 = frappe.msgprint({
							title: __("Prueba de Conexión"),
							message: __(
								"La función de prueba no está disponible en este contexto."
							),
							indicator: "orange",
							primary_action: {
								label: __("Cerrar"),
								action: () => d1.hide(),
							},
						});
					}
				}).addClass("btn-secondary");
				frm._ffm_dev_test_btn_added = true;
			}
		});
	}

	function freeze_fiscal_fields_after_submit(frm) {
		/**
		 * Bloquear campos fiscales críticos después de Submit
		 * Evita que el form quede en "Update / Not saved" por toques accidentales
		 */
		const is_submitted = frm.doc.docstatus === 1;

		// Campos fiscales que NO deben tocarse post-submit
		const fiscal_fields = [
			"fm_tax_system", // Régimen fiscal
			"fm_payment_method", // PUE/PPD (CRÍTICO)
			"fm_forma_pago_timbrado", // Forma de pago específica
			"fm_cfdi_use", // Uso CFDI
			"fm_rfc_cliente", // RFC del cliente
			"fm_cp_cliente", // CP del cliente
			"fm_email_facturacion", // Email facturación
			"customer", // Customer (crítico)
			"sales_invoice", // Sales Invoice (crítico)
			"company", // Company (crítico)
		];

		fiscal_fields.forEach((field) => {
			if (frm.get_field(field)) {
				frm.set_df_property(field, "read_only", is_submitted ? 1 : 0);
			}
		});

		// Log para debugging
		if (is_submitted) {
			console.log("[FFM] Campos fiscales bloqueados post-submit");
		}
	}

	// === START: FREEZE PAYMENT SELECTS POST-SUBMIT (UI ONLY) ===
	function freeze_payment_fields_after_submit(frm) {
		if (frm.doc.docstatus !== 1) return;

		const FIELDS = ["fm_payment_method", "fm_payment_form"]; // ajusta a tus fieldnames

		FIELDS.forEach((f) => {
			const df = frm.get_field(f);
			if (!df) return;

			// 1) meta read-only
			frm.set_df_property(f, "read_only", 1);

			// 2) hard disable del input para evitar el dropdown
			try {
				if (df.$input) df.$input.prop("disabled", true);
				if (df.$wrapper) df.$wrapper.addClass("disabled");
			} catch (e) {
				// Ignorar errores al deshabilitar controles
			}
		});
	}
	// === END: FREEZE PAYMENT SELECTS POST-SUBMIT (UI ONLY) ===

	frappe.ui.form.on("Factura Fiscal Mexico", {
		refresh: function (frm) {
			// PROTECCIÓN: Bloquear campos fiscales post-submit
			freeze_fiscal_fields_after_submit(frm);
			freeze_payment_fields_after_submit(frm);

			// Aplicar nueva lógica de botones con estados centralizados
			applyFFMUi(frm);

			setup_fiscal_interface(frm);
			setup_payment_method_radio_buttons(frm);
			control_field_visibility_by_status(frm);

			// Verificar y mostrar estado de datos de facturación
			setTimeout(() => {
				check_and_show_billing_data_status(frm);
				check_customer_fiscal_warning(frm);
			}, 1500);
		},

		// NUEVO: después de save/reload
		after_save: function (frm) {
			setTimeout(() => setup_payment_method_radio_buttons(frm), 100);
		},

		onload: function (frm) {
			// Inicializar datos por defecto al cargar
			setup_default_values(frm);

			// FASE 3: Configurar filtros para Sales Invoice disponibles
			setup_sales_invoice_filters(frm);

			// Forzar carga de Use CFDI si customer está presente pero Use CFDI vacío
			if (frm.doc.customer && !frm.doc.fm_cfdi_use) {
				auto_assign_cfdi_from_customer(frm, frm.doc.customer);
			}

			// FASE 4: Auto-verificar forma de pago en documentos existentes
			// Caso: Usuario agregó Payment Entry después de crear Factura Fiscal
			if (frm.doc.sales_invoice && !frm.is_new() && frm.doc.docstatus === 0) {
				setTimeout(() => {
					check_and_update_payment_method_on_load(frm);
				}, 1000);
			}
		},

		sales_invoice: function (frm) {
			// FASE 3: Validar disponibilidad de Sales Invoice seleccionada
			validate_sales_invoice_availability(frm);

			// Cuando se selecciona Sales Invoice, cargar datos del cliente
			if (frm.doc.sales_invoice) {
				load_customer_data_from_sales_invoice(frm);

				// FASE 4: Auto-cargar forma de pago desde Payment Entry
				auto_load_payment_method_from_sales_invoice(frm);
			}

			// Verificar cliente fiscal después de cargar Sales Invoice
			setTimeout(() => {
				check_customer_fiscal_warning(frm);
			}, 500);
		},

		customer: function (frm) {
			// Cuando cambia el customer, actualizar datos fiscales
			if (frm.doc.customer) {
				update_fiscal_data_from_customer(frm);
			}

			// Verificar si cliente fiscal es diferente al del Sales Invoice
			check_customer_fiscal_warning(frm);

			// Verificar datos de facturación después del cambio
			setTimeout(() => {
				check_and_show_billing_data_status(frm);
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

		fm_payment_method_sat: function (frm) {
			// FASE 4: Cuando cambia método de pago, auto-cargar forma de pago
			if (frm.doc.sales_invoice && frm.doc.fm_payment_method_sat) {
				auto_load_payment_method_from_sales_invoice(frm);
			}
		},
	});

	function setup_fiscal_interface(frm) {
		// Configurar interfaz específica para datos fiscales
		if (frm.doc.fm_fiscal_status === "Timbrado") {
			frm.set_df_property("uuid", "read_only", 1);
			frm.set_df_property("fm_serie_folio", "read_only", 1);
		}
	}

	function setup_default_values(frm) {
		// Establecer valores por defecto para nuevos documentos
		if (frm.is_new()) {
			frm.set_value("fm_fiscal_status", "BORRADOR"); // Migrado arquitectura resiliente

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
			console.log("❌ auto_assign_cfdi_from_customer: No customer provided");
			return;
		}

		console.log(
			`🔍 auto_assign_cfdi_from_customer: Cargando Use CFDI para customer: ${customer}`
		);

		frappe.db
			.get_value("Customer", customer, "fm_uso_cfdi_default")
			.then((r) => {
				console.log("📥 Response from Customer.fm_uso_cfdi_default:", r);

				if (r.message && r.message.fm_uso_cfdi_default) {
					// Solo asignar SI el customer tiene configurado uso CFDI
					console.log(`✅ Asignando Use CFDI: ${r.message.fm_uso_cfdi_default}`);
					frm.set_value("fm_cfdi_use", r.message.fm_uso_cfdi_default);

					frappe.show_alert(
						{
							message: __("Uso CFDI cargado desde configuración del Cliente"),
							indicator: "green",
						},
						4
					);
				} else {
					// Customer no tiene uso CFDI configurado - dejar vacío
					console.log(
						"⚠️ Customer no tiene fm_uso_cfdi_default configurado - campo vacío"
					);
					frm.set_value("fm_cfdi_use", "");
				}
			})
			.catch((err) => {
				console.log("❌ Error obteniendo uso CFDI default:", err);
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
					"tax_category",
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
					if (r.message.tax_category) {
						frm.set_value("fm_regimen_fiscal_customer", r.message.tax_category);
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
		// Solo validar si el documento no es nuevo o si está intentando guardar
		if (frm.doc.__islocal && !frm.is_dirty()) {
			// Documento nuevo sin cambios - no validar aún
			return;
		}

		// Validaciones específicas de datos fiscales

		// Validar que PUE tenga forma de pago específica (solo si ya seleccionó PUE)
		if (frm.doc.fm_payment_method_sat === "PUE") {
			if (
				!frm.doc.fm_forma_pago_timbrado ||
				frm.doc.fm_forma_pago_timbrado.startsWith("99 -")
			) {
				frappe.throw(__("Para método PUE debe especificar una forma de pago específica"));
			}
		}

		// Validar uso CFDI requerido (solo si el documento no es completamente nuevo)
		if (!frm.doc.__islocal && !frm.doc.fm_cfdi_use) {
			frappe.throw(__("Uso del CFDI es requerido"));
		}
	}

	function validate_billing_data_visual(frm) {
		// TODO: INVESTIGAR - Esta función fue renombrada a _OLD por alguna razón desconocida
		// Renombrado temporalmente para fix ESLint - REVISAR historial git para entender cambio
		// Validación visual de campos de datos de facturación con sistema de colores basado en validación RFC
		if (!frm.doc) {
			return;
		}

		// Si no hay customer, aplicar color rojo (sin datos)
		if (!frm.doc.customer) {
			apply_billing_section_color(frm, "red", "Sin Cliente configurado");
			return;
		}

		// Verificar si el Customer tiene RFC validado
		check_customer_rfc_validation_status(frm, (rfc_validation_status) => {
			// Campos de datos de facturación a validar
			const billing_fields = [
				{
					fieldname: "fm_cp_cliente",
					label: "CP Cliente",
					check_value: frm.doc.fm_cp_cliente,
				},
				{
					fieldname: "fm_email_facturacion",
					label: "Email Facturación",
					check_value: frm.doc.fm_email_facturacion,
				},
				{
					fieldname: "fm_rfc_cliente",
					label: "RFC Cliente",
					check_value: frm.doc.fm_rfc_cliente,
				},
				{
					fieldname: "fm_direccion_principal_display",
					label: "Dirección Principal",
					check_value:
						frm.doc.fm_direccion_principal_display &&
						!frm.doc.fm_direccion_principal_display.includes("⚠️ FALTA DIRECCIÓN"),
				},
			];

			// Verificar si todos los campos tienen datos
			const missing_fields = billing_fields.filter((field) => !field.check_value);
			const has_all_data = missing_fields.length === 0;

			// Determinar color y mensaje según validación RFC y completitud de datos
			let color, message;

			if (!has_all_data) {
				// Rojo: Faltan datos de facturación
				color = "red";
				message = `Faltan datos: ${missing_fields.map((f) => f.label).join(", ")}`;
			} else if (rfc_validation_status.validated) {
				// Verde: RFC validado y datos completos
				color = "green";
				message = `RFC validado el ${rfc_validation_status.validation_date}`;
			} else {
				// Amarillo: Datos completos pero RFC no validado
				color = "yellow";
				message = "RFC pendiente de validación en Customer";
			}

			apply_billing_section_color(frm, color, message);
		});
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
						// Mensaje de error con información detallada del PAC
						const error_msg = r.message
							? r.message.error_message ||
							  r.message.error ||
							  r.message.message ||
							  r.message
							: __("Error desconocido del PAC");

						console.log("[FFM] mostrando msgprint de error de timbrado:", error_msg);

						const d2 = frappe.msgprint({
							title: __("Error de Timbrado"),
							message: error_msg,
							indicator: "red",
							primary_action: {
								label: __("Cerrar"),
								action: () => d2.hide(),
							},
						});
						// Auto-refresh para mostrar estado actualizado (failed)
						frm.reload_doc();
					}
				},
			});
		});
	}

	function cancelar_timbrado(frm) {
		// Función de cancelación de timbrado con selección de motivo desde enum SAT
		frappe.call({
			method: "facturacion_mexico.facturacion_fiscal.timbrado_api.get_sat_cancellation_motives",
			callback: function (motives_response) {
				if (!motives_response.message) {
					frappe.msgprint(__("Error cargando motivos de cancelación SAT"));
					return;
				}

				const motives_config = motives_response.message;

				frappe.prompt(
					[
						{
							fieldname: "motive",
							label: __("Motivo de Cancelación SAT"),
							fieldtype: "Select",
							reqd: 1,
							options: motives_config.select_options,
							description: __(
								"Seleccione el motivo de cancelación según catálogo SAT"
							),
						},
						{
							fieldname: "substitution_uuid",
							label: __("UUID de Sustitución"),
							fieldtype: "Data",
							depends_on: "eval:doc.motive=='01'",
							mandatory_depends_on: "eval:doc.motive=='01'",
							description: __(
								"Requerido solo para motivo 01 - Comprobantes con errores con relación"
							),
						},
					],
					function (values) {
						frappe.call({
							method: "facturacion_mexico.facturacion_fiscal.timbrado_api.cancelar_factura",
							args: {
								sales_invoice: frm.doc.sales_invoice,
								uuid: frm.doc.fm_uuid,
								motivo: values.motive,
								substitution_uuid: values.substitution_uuid,
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
										message: r.message
											? r.message.error
											: __("Error desconocido"),
										indicator: "red",
									});
								}
							},
						});
					},
					__("Cancelación Fiscal SAT"),
					__("Enviar")
				);
			},
		});
	}

	function test_pac_connection(frm) {
		// Función para probar conexión con PAC
		frappe.call({
			method: "facturacion_mexico.facturacion_fiscal.timbrado_api.test_connection",
			callback: function (r) {
				if (r.message && r.message.success) {
					const d3 = frappe.msgprint({
						title: __("Conexión Exitosa"),
						message: __(
							"La conexión con FacturAPI se estableció correctamente. El sistema está listo para timbrar facturas."
						),
						indicator: "green",
						primary_action: {
							label: __("Cerrar"),
							action: () => d3.hide(),
						},
					});
				} else {
					frappe.msgprint({
						title: __("Error de Conexión"),
						message: r.message
							? r.message.message
							: __("No se pudo conectar con el PAC"),
						indicator: "red",
					});
				}
			},
		});
	}

	// ========================================
	// FASE 3: FILTROS SALES INVOICE DISPONIBLES
	// ========================================

	function setup_sales_invoice_filters(frm) {
		/**
		 * Configurar filtros dinámicos para mostrar solo Sales Invoice disponibles
		 *
		 * CRITERIOS:
		 * - docstatus = 1 (submitted)
		 * - fm_factura_fiscal_mx vacío o NULL
		 * - Sin Factura Fiscal Mexico timbrada asociada
		 */
		frm.set_query("sales_invoice", function () {
			console.log("🔍 DEBUG: Aplicando filtros Sales Invoice - Solo submitted sin timbrar");

			return {
				filters: [
					// 1. CRÍTICO: Solo Sales Invoice submitted (docstatus = 1)
					// Evita facturas draft (0) y canceladas (2)
					["docstatus", "=", 1],

					// 2. CRÍTICO: Sin Factura Fiscal Mexico ya asignada
					// Evita doble facturación fiscal
					["fm_factura_fiscal_mx", "in", ["", null]],

					// 3. Tener RFC del cliente (requerido para facturación fiscal)
					// Sin RFC no se puede timbrar
					["tax_id", "!=", ""],
				],
			};
		});

		console.log(
			"✅ Filtros Sales Invoice configurados - Solo facturas disponibles para timbrado"
		);
	}

	function validate_sales_invoice_availability(frm) {
		/**
		 * Validar que Sales Invoice seleccionada sigue estando disponible
		 * Se ejecuta cuando usuario selecciona una Sales Invoice
		 */
		if (!frm.doc.sales_invoice) return;

		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Sales Invoice",
				filters: { name: frm.doc.sales_invoice },
				fieldname: ["fm_factura_fiscal_mx", "docstatus", "tax_id"],
			},
			callback: function (r) {
				if (r.message) {
					const sales_invoice_data = r.message;

					// Verificar si ya está asignada a otra Factura Fiscal
					if (
						sales_invoice_data.fm_factura_fiscal_mx &&
						sales_invoice_data.fm_factura_fiscal_mx !== frm.doc.name
					) {
						// Verificar si esa Factura Fiscal está timbrada
						frappe.call({
							method: "frappe.client.get_value",
							args: {
								doctype: "Factura Fiscal Mexico",
								filters: { name: sales_invoice_data.fm_factura_fiscal_mx },
								fieldname: "fm_fiscal_status",
							},
							callback: function (fiscal_r) {
								// Usar estados centralizados para verificar si está timbrada
								load_fiscal_states(function (states) {
									if (
										fiscal_r.message &&
										states &&
										states.cancelable_states.includes(
											fiscal_r.message.fm_fiscal_status
										)
									) {
										frappe.msgprint({
											title: __("Sales Invoice No Disponible"),
											message: __(
												"La Sales Invoice {0} ya ha sido timbrada en el documento {1}. Por favor seleccione otra factura."
											).format(
												frm.doc.sales_invoice,
												sales_invoice_data.fm_factura_fiscal_mx
											),
											indicator: "red",
										});

										// Limpiar selección
										frm.set_value("sales_invoice", "");
									}
								});
							},
						});
					}

					// Verificar otros criterios
					if (sales_invoice_data.docstatus !== 1) {
						frappe.msgprint({
							title: __("Sales Invoice No Válida"),
							message: __(
								"La Sales Invoice debe estar enviada (submitted) para crear factura fiscal."
							),
							indicator: "orange",
						});
						frm.set_value("sales_invoice", "");
					}

					if (!sales_invoice_data.tax_id) {
						frappe.msgprint({
							title: __("RFC Faltante"),
							message: __(
								"La Sales Invoice debe tener RFC del cliente para facturación fiscal."
							),
							indicator: "orange",
						});
						frm.set_value("sales_invoice", "");
					}
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
		field.$wrapper.find(".control-input").hide(); // Oculta el input/valor
		field.$wrapper.find(".control-value").hide(); // Oculta display del valor

		// Configurar radio buttons
		setup_radio_buttons(frm, field);
	}

	function setup_radio_buttons(frm, field) {
		const current_value = frm.doc.fm_payment_method_sat || "PUE";
		const is_submitted = frm.doc.docstatus === 1;
		const disabled_attr = is_submitted ? "disabled" : "";
		const disabled_class = is_submitted ? "radio-disabled" : "";
		const cursor_style = is_submitted
			? "cursor: not-allowed; opacity: 0.6;"
			: "cursor: pointer;";

		const radio_html = `
		<div class="payment-method-radio-container" style="padding: 8px 0;">
			<label class="control-label" style="margin-bottom: 8px; display: block; font-weight: 600;">
				Método de Pago SAT <span class="text-danger">*</span>
			</label>
			<div class="radio-group" style="display: flex; gap: 20px; align-items: center;">
				<label class="radio-option ${disabled_class}" style="display: flex; align-items: center; ${cursor_style} margin: 0;">
					<input type="radio" name="fm_payment_method_sat_radio" value="PUE"
						   ${current_value === "PUE" ? "checked" : ""}
						   ${disabled_attr}
						   style="margin-right: 8px;">
					<span><strong>PUE</strong> - Pago en una exhibición</span>
				</label>
				<label class="radio-option ${disabled_class}" style="display: flex; align-items: center; ${cursor_style} margin: 0;">
					<input type="radio" name="fm_payment_method_sat_radio" value="PPD"
						   ${current_value === "PPD" ? "checked" : ""}
						   ${disabled_attr}
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
			// Guard para documentos enviados
			if (frm.doc.docstatus === 1) {
				frappe.msgprint(__("No se puede cambiar PUE/PPD en documentos enviados"));
				// Revertir selección
				$(this).prop("checked", false);
				field.$wrapper
					.find(`input[value="${frm.doc.fm_payment_method_sat || "PUE"}"]`)
					.prop("checked", true);
				return false;
			}

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

		// CSS adicional para documentos enviados
		if (is_submitted) {
			field.$wrapper.find(".radio-option").addClass("text-muted");
			field.$wrapper.find("input[type=radio]").prop("disabled", true);
		}
	}

	function sync_radio_buttons_with_field(frm, field_name) {
		const current_value = frm.doc[field_name] || "PUE";
		const field = frm.fields_dict[field_name];
		const is_submitted = frm.doc.docstatus === 1;
		const radio_container = field.$wrapper.find(".payment-method-radio-container");

		if (radio_container.length > 0) {
			radio_container.find(`input[value="${current_value}"]`).prop("checked", true);

			// Re-aplicar disabled si es necesario
			if (is_submitted) {
				field.$wrapper
					.find('input[name="fm_payment_method_sat_radio"]')
					.prop("disabled", true);
				field.$wrapper.find(".radio-option").css({
					opacity: "0.6",
					cursor: "not-allowed",
				});
			}

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
		const fiscal_status = frm.doc.fm_fiscal_status || "BORRADOR"; // Migrado arquitectura resiliente

		// Campos que vienen de FacturAPI response (Punto 8)
		const facturapi_response_fields = [
			"uuid", // UUID fiscal del SAT (DocType field)
			"serie", // Serie de la factura (DocType field)
			"folio", // Folio de la factura (DocType field)
			"total_fiscal", // Total de la factura fiscal (DocType field)
			"facturapi_id", // ID retornado por FacturAPI.io (DocType field)
			// fm_uuid_fiscal eliminado - usar solo uuid
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

		// Usar estados centralizados para lógica de visibilidad
		load_fiscal_states(function (states) {
			if (!states) {
				// Fallback básico si no hay estados disponibles
				if (fiscal_status === "BORRADOR") {
					hide_fields(frm, facturapi_response_fields);
					hide_fields(frm, fiscal_files_fields);
					hide_fields(frm, cancellation_fields);
					hide_section(frm, "section_break_archivos");
					hide_section(frm, "section_break_cancelacion");
				}
				return;
			}

			// PROTECCIÓN: Ocultar botón Cancel del DocType cuando esté en estado cancelable
			if (states.cancelable_states.includes(fiscal_status)) {
				// Ocultar botón Cancel de Frappe para proteger facturas timbradas en el SAT
				frm.page.clear_secondary_action();
			}

			// Lógica de visibilidad según estado usando configuración centralizada
			if (states.timbrable_states.includes(fiscal_status)) {
				// ESTADOS TIMBRABLE: Ocultar todo lo que viene después del timbrado
				hide_fields(frm, facturapi_response_fields);
				hide_fields(frm, fiscal_files_fields);
				hide_fields(frm, cancellation_fields);
				hide_section(frm, "section_break_archivos");
				hide_section(frm, "section_break_cancelacion");
			} else if (states.cancelable_states.includes(fiscal_status)) {
				// ESTADOS CANCELABLE: Mostrar datos de FacturAPI, ocultar cancelación
				show_fields(frm, facturapi_response_fields);
				show_fields(frm, fiscal_files_fields);
				hide_fields(frm, cancellation_fields);
				show_section(frm, "section_break_archivos");
				hide_section(frm, "section_break_cancelacion");
			} else if (states.final_states.includes(fiscal_status)) {
				// ESTADOS FINALES: Mostrar todo incluyendo información de cancelación
				show_fields(frm, facturapi_response_fields);
				show_fields(frm, fiscal_files_fields);
				show_fields(frm, cancellation_fields);
				show_section(frm, "section_break_archivos");
				show_section(frm, "section_break_cancelacion");
			} else if (states.recoverable_error_states.includes(fiscal_status)) {
				// ESTADOS DE ERROR RECUPERABLE: Mostrar campos básicos, ocultar respuesta y cancelación
				hide_fields(frm, facturapi_response_fields);
				hide_fields(frm, fiscal_files_fields);
				hide_fields(frm, cancellation_fields);
				hide_section(frm, "section_break_archivos");
				hide_section(frm, "section_break_cancelacion");
			} else if (fiscal_status === states.states.PENDIENTE_CANCELACION) {
				// ESTADO SOLICITUD CANCELACIÓN: Como timbrada pero indicando proceso
				show_fields(frm, facturapi_response_fields);
				show_fields(frm, fiscal_files_fields);
				hide_fields(frm, cancellation_fields);
				show_section(frm, "section_break_archivos");
				hide_section(frm, "section_break_cancelacion"); // Aún no confirmada
			}
		});
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

	// ========================================
	// VALIDACIÓN VISUAL DATOS DE FACTURACIÓN
	// ========================================

	function check_and_show_billing_data_status(frm) {
		// Verificar estado de datos de facturación y aplicar colores de validación SAT
		if (!frm.doc) {
			return;
		}

		// Si no hay customer, aplicar estado rojo
		if (!frm.doc.customer) {
			apply_billing_section_color(frm, "red", "🔴 SELECCIONA UN CLIENTE");
			return;
		}

		// Verificar estado de validación SAT del Customer
		check_customer_rfc_validation_status(frm, (rfc_validation_status) => {
			// Verificar si los campos OBLIGATORIOS están poblados (sin email)
			const billing_fields = [
				{ field: "fm_cp_cliente", label: "CP" },
				{ field: "fm_rfc_cliente", label: "RFC" },
				{ field: "fm_direccion_principal_display", label: "Dirección" },
			];

			const empty_fields = billing_fields.filter(
				(f) =>
					!frm.doc[f.field] ||
					frm.doc[f.field].includes("⚠️ FALTA") ||
					frm.doc[f.field].includes("❌ ERROR")
			);

			// Determinar color y mensaje según validación SAT (RFC validado tiene prioridad)
			let color, message;

			if (rfc_validation_status.validated) {
				// VERDE: RFC validado exitosamente (prioridad sobre campos faltantes)
				color = "green";
				message = `✅ DATOS FISCALES VALIDADOS${
					rfc_validation_status.validation_date
						? ` (${rfc_validation_status.validation_date})`
						: ""
				}`;
			} else if (empty_fields.length > 0) {
				// ROJO: Faltan datos básicos y RFC no validado
				color = "red";
				const missing_list = empty_fields.map((f) => f.label).join(", ");
				message = `🔴 FALTA: ${missing_list}`;
			} else {
				// AMARILLO: Datos completos pero RFC no validado
				color = "yellow";
				message = "🟡 LISTO PARA VALIDAR RFC/CSF";
			}

			// Aplicar color a la sección
			apply_billing_section_color(frm, color, message);
		});
	}

	function show_billing_data_message(frm, type, message) {
		// Mostrar mensaje en la sección de datos de facturación
		const section_wrapper = frm.fields_dict.section_break_datos_facturacion;
		if (!section_wrapper || !section_wrapper.$wrapper) {
			return;
		}

		// Remover mensaje anterior
		section_wrapper.$wrapper.find(".billing-data-message").remove();

		// Configurar colores según tipo
		const config = {
			error: { bg: "#fff5f5", border: "#feb2b2", color: "#c53030", icon: "⚠️" },
			warning: { bg: "#fffbeb", border: "#fde68a", color: "#d97706", icon: "⚠️" },
			success: { bg: "#f0fff4", border: "#9ae6b4", color: "#2f855a", icon: "✅" },
		};

		const style = config[type] || config.warning;

		// Crear y agregar mensaje
		const message_html = $(`
		<div class="billing-data-message" style="
			background-color: ${style.bg};
			border: 1px solid ${style.border};
			color: ${style.color};
			padding: 8px 12px;
			margin: 8px 0;
			border-radius: 6px;
			font-size: 13px;
			display: flex;
			align-items: center;
			gap: 8px;
		">
			<span>${style.icon}</span>
			<span>${message}</span>
		</div>
	`);

		// Insertar después del título de la sección
		const section_head = section_wrapper.$wrapper.find(".section-head");
		if (section_head.length > 0) {
			section_head.after(message_html);
		}
	}

	/* TODO: FUNCIÓN DUPLICADA - SEGUNDA INSTANCIA COMENTADA
	 * Esta función está duplicada (línea 237 activa, línea 1300 comentada)
	 * INVESTIGAR: Por qué hay duplicación y determinar cuál eliminar
	 * Comentada temporalmente para evitar errores ESLint de función duplicada
	 */
	/*
function validate_billing_data_visual(frm) {
	// TODO: INVESTIGAR - Esta función fue renombrada a _OLD por alguna razón desconocida
	// Renombrado temporalmente para fix ESLint - REVISAR historial git para entender cambio
	// Validación visual de campos de datos de facturación con sistema de colores basado en validación RFC
	if (!frm.doc) {
		return;
	}

	// Si no hay customer, aplicar color rojo (sin datos)
	if (!frm.doc.customer) {
		apply_billing_section_color(frm, "red", "Sin Cliente configurado");
		return;
	}

	// Verificar si el Customer tiene RFC validado
	check_customer_rfc_validation_status(frm, (rfc_validation_status) => {
		// Campos de datos de facturación a validar
		const billing_fields = [
			{
				fieldname: "fm_cp_cliente",
				label: "CP Cliente",
				check_value: frm.doc.fm_cp_cliente,
			},
			{
				fieldname: "fm_email_facturacion",
				label: "Email Facturación",
				check_value: frm.doc.fm_email_facturacion,
			},
			{
				fieldname: "fm_rfc_cliente",
				label: "RFC Cliente",
				check_value: frm.doc.fm_rfc_cliente,
			},
			{
				fieldname: "fm_direccion_principal_display",
				label: "Dirección Principal",
				check_value:
					frm.doc.fm_direccion_principal_display &&
					!frm.doc.fm_direccion_principal_display.includes("⚠️ FALTA DIRECCIÓN"),
			},
		];

		// Verificar si todos los campos tienen datos
		const missing_fields = billing_fields.filter((field) => !field.check_value);
		const has_all_data = missing_fields.length === 0;

		// Determinar color y mensaje según validación RFC y completitud de datos
		let color, message;

		if (!has_all_data) {
			// Rojo: Faltan datos de facturación
			color = "red";
			message = `Faltan datos: ${missing_fields.map("f) => f.label).join(", ")}`;
		} else if (rfc_validation_status.validated) {
			// Verde: RFC validado y datos completos
			color = "green";
			message = `RFC validado el ${rfc_validation_status.validation_date}`;
		} else {
			// Amarillo: Datos completos pero RFC no validado
			color = "yellow";
			message = "RFC pendiente de validación en Customer";
		}

		apply_billing_section_color(frm, color, message);
	});
}
*/

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
			console.log(
				`🔴 [DEBUG] Campo ${field_config.fieldname} FALTANTE - aplicando estilo rojo`
			);
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

	// Agregar estilos CSS para validación visual y colores de sección
	if (!$("#billing-validation-styles").length) {
		$("head").append(`
		<style id="billing-validation-styles">
			/* Estilos para campos individuales (legacy) */
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

			/* Estilos para secciones de datos de facturación */
			.billing-section-red {
				background-color: #fff5f5 !important;
				border: 2px solid #feb2b2 !important;
				border-radius: 8px !important;
				padding: 12px !important;
				margin: 8px 0 !important;
			}

			.billing-section-yellow {
				background-color: #fffbeb !important;
				border: 2px solid #fde68a !important;
				border-radius: 8px !important;
				padding: 12px !important;
				margin: 8px 0 !important;
			}

			.billing-section-green {
				background-color: #f0fff4 !important;
				border: 2px solid #9ae6b4 !important;
				border-radius: 8px !important;
				padding: 12px !important;
				margin: 8px 0 !important;
			}

			/* Efectos de hover para secciones */
			.billing-section-red:hover {
				box-shadow: 0 4px 12px rgba(254, 178, 178, 0.4) !important;
			}

			.billing-section-yellow:hover {
				box-shadow: 0 4px 12px rgba(253, 230, 138, 0.4) !important;
			}

			.billing-section-green:hover {
				box-shadow: 0 4px 12px rgba(154, 230, 180, 0.4) !important;
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

	function check_customer_rfc_validation_status(frm, callback) {
		// Verificar estado de validación RFC del Customer
		if (!frm.doc.customer) {
			callback({ validated: false, validation_date: null });
			return;
		}

		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Customer",
				fieldname: ["fm_rfc_validated", "fm_rfc_validation_date"],
				filters: { name: frm.doc.customer },
			},
			callback: function (r) {
				if (r.message) {
					const is_validated = r.message.fm_rfc_validated == 1;
					const validation_date = r.message.fm_rfc_validation_date || null;

					callback({
						validated: is_validated,
						validation_date: validation_date
							? frappe.datetime.str_to_user(validation_date)
							: null,
					});
				} else {
					callback({ validated: false, validation_date: null });
				}
			},
			error: function () {
				callback({ validated: false, validation_date: null });
			},
		});
	}

	function apply_billing_section_color(frm, color, message) {
		// Aplicar color de fondo a toda la sección "Datos de Facturación"

		// MÉTODO 1: Intentar con frm.fields_dict
		const section_wrapper = frm.fields_dict.section_break_datos_facturacion;

		// MÉTODO 2: Buscar directamente en el DOM usando jQuery
		const section_element = $('div[data-fieldname="section_break_datos_facturacion"]');

		// MÉTODO 3: Buscar por el texto "Datos de Facturación"
		const section_by_text = $('.section-head:contains("Datos de Facturación")').parent();

		let target_element;

		if (section_wrapper && section_wrapper.$wrapper) {
			target_element = section_wrapper.$wrapper;
		} else if (section_element.length > 0) {
			target_element = section_element;
		} else if (section_by_text.length > 0) {
			target_element = section_by_text;
		} else {
			return;
		}

		// Remover clases de color previas
		target_element.removeClass(
			"billing-section-red billing-section-yellow billing-section-green"
		);

		// Definir colores según estado
		const color_config = {
			red: {
				class: "billing-section-red",
				bg_color: "#fff5f5",
				border_color: "#feb2b2",
				text_color: "#c53030",
				icon: "🔴",
			},
			yellow: {
				class: "billing-section-yellow",
				bg_color: "#fffbeb",
				border_color: "#fde68a",
				text_color: "#d97706",
				icon: "🟡",
			},
			green: {
				class: "billing-section-green",
				bg_color: "#f0fff4",
				border_color: "#9ae6b4",
				text_color: "#2f855a",
				icon: "🟢",
			},
		};

		const config = color_config[color];
		if (!config) {
			return;
		}

		// No aplicar clase CSS de fondo - solo mantener indicador de texto

		// Buscar o crear indicador de estado
		let status_indicator = target_element.find(".billing-status-indicator");

		if (status_indicator.length === 0) {
			// Crear indicador si no existe
			const section_label = target_element.find(".section-head");

			if (section_label.length > 0) {
				status_indicator = $(`
				<div class="billing-status-indicator" style="
					margin-top: 8px;
					padding: 8px 12px;
					border-radius: 6px;
					font-size: 13px;
					font-weight: 500;
					display: flex;
					align-items: center;
					gap: 8px;
				"></div>
			`);
				section_label.after(status_indicator);
			}
		}

		// Actualizar contenido y estilo del indicador (solo texto, sin fondo)
		if (status_indicator.length > 0) {
			status_indicator.html(`${config.icon} ${message}`);
			status_indicator.css({
				"background-color": "transparent",
				border: "none",
				color: config.text_color,
			});
		}
	}

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

	// ========================================
	// VERIFICACIÓN CLIENTE FISCAL DIFERENTE
	// ========================================

	function check_customer_fiscal_warning(frm) {
		// Verificar si el cliente fiscal es diferente al del Sales Invoice
		if (!frm.doc.sales_invoice || !frm.doc.customer) {
			hide_customer_fiscal_warning(frm);
			return;
		}

		// Obtener cliente del Sales Invoice
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Sales Invoice",
				fieldname: ["customer", "customer_name"],
				filters: { name: frm.doc.sales_invoice },
			},
			callback: function (r) {
				if (r.message) {
					const sales_invoice_customer = r.message.customer;
					const sales_invoice_customer_name = r.message.customer_name;

					// Comparar clientes
					if (frm.doc.customer !== sales_invoice_customer) {
						// Clientes diferentes - mostrar aviso
						show_customer_fiscal_warning(
							frm,
							sales_invoice_customer,
							sales_invoice_customer_name
						);
					} else {
						// Mismo cliente - ocultar aviso
						hide_customer_fiscal_warning(frm);
					}
				} else {
					hide_customer_fiscal_warning(frm);
				}
			},
			error: function () {
				hide_customer_fiscal_warning(frm);
			},
		});
	}

	function show_customer_fiscal_warning(frm, original_customer, original_customer_name) {
		// Mostrar aviso de cliente fiscal diferente
		const warning_field = frm.fields_dict.customer_fiscal_warning;
		if (!warning_field || !warning_field.$wrapper) {
			return;
		}

		// Obtener nombre del cliente fiscal actual
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Customer",
				fieldname: "customer_name",
				filters: { name: frm.doc.customer },
			},
			callback: function (r) {
				const fiscal_customer_name = r.message
					? r.message.customer_name
					: frm.doc.customer;

				const warning_html = `
				<div style="
					background-color: #fff3cd;
					border: 1px solid #ffeaa7;
					border-radius: 6px;
					padding: 12px;
					margin: 8px 0;
					font-size: 13px;
					display: flex;
					align-items: center;
					gap: 10px;
				">
					<span style="color: #d97706; font-size: 18px;">⚠️</span>
					<div>
						<strong style="color: #d97706;">Cliente Fiscal Diferente:</strong><br>
						<span style="color: #666;">
							<strong>Sales Invoice:</strong> ${original_customer_name} (${original_customer})<br>
							<strong>Factura Fiscal:</strong> ${fiscal_customer_name} (${frm.doc.customer})
						</span>
						<div style="margin-top: 6px; font-size: 11px; color: #856404;">
							💡 Uso común: Facturación a "Público en General" o cambio de receptor fiscal
						</div>
					</div>
				</div>
			`;

				warning_field.$wrapper.html(warning_html);
				warning_field.$wrapper.show();
			},
		});
	}

	function hide_customer_fiscal_warning(frm) {
		// Ocultar aviso de cliente fiscal
		const warning_field = frm.fields_dict.customer_fiscal_warning;
		if (warning_field && warning_field.$wrapper) {
			warning_field.$wrapper.hide();
		}
	}

	// ========================================
	// FASE 4: AUTO-CARGA PUE MEJORADA
	// ========================================

	function check_and_update_payment_method_on_load(frm) {
		/**
		 * FASE 4: Verificar consistencia de forma de pago en documentos existentes
		 *
		 * Nueva lógica (mejor UX):
		 * - Sin Payment Entry → Aviso "No hay pago registrado"
		 * - Con Payment Entry igual → Sin aviso (consistente)
		 * - Con Payment Entry diferente → Aviso "Forma de pago inconsistente"
		 */
		if (!frm.doc.sales_invoice || !frm.doc.fm_payment_method_sat) {
			return;
		}

		console.log(
			`🔍 FASE 4: Verificando consistencia Payment Entry para documento existente ${frm.doc.name}`
		);

		// Solo verificar para PUE (PPD siempre usa "99 - Por definir")
		if (frm.doc.fm_payment_method_sat === "PUE") {
			// Buscar Payment Entry relacionada
			frappe.call({
				method: "facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico.get_payment_entry_for_javascript",
				args: {
					invoice_name: frm.doc.sales_invoice,
				},
				callback: function (r) {
					try {
						console.log("🔍 FASE 4: Respuesta recibida:", r);

						const current_forma_pago = frm.doc.fm_forma_pago_timbrado;

						if (
							r.message &&
							r.message.success &&
							r.message.data &&
							r.message.data.length > 0
						) {
							const payment_entry = r.message.data[0];
							const payment_method = payment_entry.mode_of_payment;

							console.log(
								`🔍 FASE 4: Payment Entry encontrado - ${payment_entry.name}, Método: ${payment_method}`
							);

							if (current_forma_pago) {
								// Hay forma de pago en Factura Fiscal - verificar consistencia
								if (current_forma_pago === payment_method) {
									// ✅ Consistente - no mostrar aviso
									console.log(
										`✅ FASE 4: Forma de pago consistente: ${current_forma_pago}`
									);
								} else {
									// ⚠️ Inconsistente - mostrar mensaje persistente
									console.log(
										`⚠️ FASE 4: Inconsistencia detectada - Factura: ${current_forma_pago}, Payment: ${payment_method}`
									);

									const d4 = frappe.msgprint({
										title: __("⚠️ Forma de Pago Inconsistente"),
										message: __(
											"Se detectó una inconsistencia en la forma de pago:<br><br><b>Factura Fiscal Mexico:</b> {0}<br><b>Payment Entry:</b> {1}<br><br>Por favor, verifique y corrija la forma de pago antes de timbrar.",
											[
												"<span style='color: #d73502;'>" +
													current_forma_pago +
													"</span>",
												"<span style='color: #0066cc;'>" +
													payment_method +
													"</span>",
											]
										),
										indicator: "orange",
										primary_action: {
											label: __("Cerrar"),
											action: () => d4.hide(),
										},
									});
								}
							} else {
								// Sin forma de pago pero hay Payment Entry - auto-cargar
								console.log(
									`✅ FASE 4: Auto-cargando ${payment_method} desde ${payment_entry.name}`
								);

								frm.set_value("fm_forma_pago_timbrado", payment_method);
								frappe.show_alert(
									{
										message:
											"✅ Forma de pago cargada desde Payment Entry: " +
											payment_method,
										indicator: "green",
									},
									5
								);
							}
						} else {
							// Sin Payment Entry
							console.log("ℹ️ FASE 4: No hay Payment Entry registrado");

							if (current_forma_pago) {
								// Hay forma de pago pero no Payment Entry
								const d5 = frappe.msgprint({
									title: __("ℹ️ Sin Pago Registrado"),
									message: __(
										"No hay Payment Entry registrado para esta factura.<br><br><b>Forma de pago actual:</b> {0}<br><br>Considere crear un Payment Entry o verificar la forma de pago.",
										[
											"<span style='color: #0066cc;'>" +
												current_forma_pago +
												"</span>",
										]
									),
									indicator: "blue",
									primary_action: {
										label: __("Cerrar"),
										action: () => d5.hide(),
									},
								});
							} else {
								// Sin forma de pago y sin Payment Entry
								const d6 = frappe.msgprint({
									title: __("ℹ️ Sin Pago Registrado"),
									message: __(
										"No hay Payment Entry registrado para esta factura.<br><br>Seleccione la forma de pago manualmente antes de timbrar."
									),
									indicator: "blue",
									primary_action: {
										label: __("Cerrar"),
										action: () => d6.hide(),
									},
								});
							}
						}
					} catch (error) {
						console.error("❌ FASE 4: Error en callback de consistencia:", error);
						frappe.show_alert(
							{
								message: "❌ Error verificando consistencia de forma de pago",
								indicator: "red",
							},
							3
						);
					}
				},
				error: function (err) {
					console.error("❌ FASE 4: Error verificando consistencia Payment Entry:", err);
				},
			});
		}
	}

	function auto_load_payment_method_from_sales_invoice(frm) {
		/**
		 * FASE 4: Auto-cargar forma de pago desde Payment Entry
		 *
		 * Lógica según especificación:
		 * - PUE: Buscar Payment Entry relacionada y auto-cargar mode_of_payment
		 * - PPD: Siempre usar "99 - Por definir"
		 * - Solo auto-cargar si campo está vacío (no sobrescribir selección manual)
		 */
		if (!frm.doc.sales_invoice || !frm.doc.fm_payment_method_sat) {
			console.log("🔍 FASE 4: Sin Sales Invoice o método de pago - saltando auto-carga");
			return;
		}

		// Para PPD: Siempre asignar "99 - Por definir"
		if (frm.doc.fm_payment_method_sat === "PPD") {
			if (
				!frm.doc.fm_forma_pago_timbrado ||
				frm.doc.fm_forma_pago_timbrado !== "99 - Por definir"
			) {
				frm.set_value("fm_forma_pago_timbrado", "99 - Por definir");
				console.log("✅ FASE 4: Auto-asignado PPD - 99 - Por definir");
			}
			return;
		}

		// Para PUE: Buscar Payment Entry relacionada
		if (frm.doc.fm_payment_method_sat === "PUE") {
			// Solo auto-cargar si el campo está vacío (no sobrescribir selección manual)
			if (frm.doc.fm_forma_pago_timbrado) {
				console.log("🔍 FASE 4: PUE ya tiene forma de pago - no sobrescribir");
				return;
			}

			console.log(
				`🔍 FASE 4: Buscando Payment Entry para Sales Invoice ${frm.doc.sales_invoice}`
			);

			// Usar método Python con SQL correcto (no sintaxis child table problemática)
			frappe.call({
				method: "facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico.get_payment_entry_for_javascript",
				args: {
					invoice_name: frm.doc.sales_invoice,
				},
				callback: function (r) {
					if (r.message && r.message.success && r.message.data.length > 0) {
						const payment_entry = r.message.data[0];
						if (payment_entry.mode_of_payment) {
							// Auto-cargar forma de pago desde Payment Entry
							frm.set_value("fm_forma_pago_timbrado", payment_entry.mode_of_payment);

							frappe.show_alert(
								{
									message: __(
										"Forma de pago cargada automáticamente desde Payment Entry {0}"
									).format(payment_entry.name),
									indicator: "green",
								},
								4
							);

							console.log(
								`✅ FASE 4: Auto-cargado PUE - ${payment_entry.mode_of_payment} desde ${payment_entry.name}`
							);
						}
					} else {
						// PUE sin Payment Entry - dejar vacío para selección manual
						console.log(
							"ℹ️ FASE 4: PUE sin Payment Entry - usuario debe seleccionar manualmente"
						);

						frappe.show_alert(
							{
								message: __(
									"No se encontró Payment Entry. Seleccione forma de pago manualmente."
								),
								indicator: "yellow",
							},
							3
						);
					}
				},
				error: function (err) {
					console.error("❌ FASE 4: Error buscando Payment Entry:", err);
				},
			});
		}
	}
})(); // Cierre del IIFE
