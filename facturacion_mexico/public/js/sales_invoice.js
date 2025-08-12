// Sales Invoice customizations for Facturacion Mexico - ARQUITECTURA MIGRADA
// Funcionalidad fiscal centralizada en Factura Fiscal Mexico

// Helper de normalización y diagnóstico
function norm(x) {
	return (x || "").toString().trim().toUpperCase();
}

function log_ffm_debug(frm, context = "UNKNOWN") {
	console.log(`[FFM DEBUG ${context}]`, {
		si_name: frm.doc.name,
		docstatus: frm.doc.docstatus,
		fm_fiscal_status: frm.doc.fm_fiscal_status,
		fm_uuid_fiscal: frm.doc.fm_uuid_fiscal,
		fm_ffm_uuid: frm.doc.fm_ffm_uuid,
		fm_factura_fiscal_mx: frm.doc.fm_factura_fiscal_mx,
		timestamp: new Date().toISOString(),
	});
}

// Cargar configuración de estados fiscales al inicio
let FISCAL_STATES = null;

// Función para obtener estados fiscales desde el servidor
function load_fiscal_states(callback) {
	if (FISCAL_STATES) {
		// Ya cargado, usar cache
		if (callback) callback(FISCAL_STATES);
		return;
	}

	frappe.call({
		method: "facturacion_mexico.facturacion_fiscal.api.get_fiscal_states",
		callback: function (r) {
			if (r.message) {
				FISCAL_STATES = r.message;
				if (callback) callback(FISCAL_STATES);
			}
		},
	});
}

// Cargar estados al inicio
load_fiscal_states();

frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Diagnóstico inmediato
		log_ffm_debug(frm, "REFRESH_START");

		// Limpiar botones previos
		frm.remove_custom_button(__("Timbrar Factura"));

		if (frm.doc.docstatus === 1) {
			has_customer_rfc(frm, function (has_rfc) {
				if (has_rfc) {
					if (should_show_timbrar_button(frm)) {
						add_timbrar_button(frm);
						log_ffm_debug(frm, "TIMBRAR_BUTTON_ADDED");
					} else if (is_already_timbrada(frm)) {
						add_view_fiscal_button(frm);
						log_ffm_debug(frm, "VIEW_FISCAL_BUTTON_ADDED");
					}
				}
			});
		}

		log_ffm_debug(frm, "REFRESH_END");
	},
});

function has_customer_rfc(frm, callback) {
	// Verificar si el cliente tiene RFC configurado - RFC está en Customer, no en Sales Invoice
	if (!frm.doc.customer) {
		callback(false);
		return;
	}

	// Obtener RFC del Customer vinculado
	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "Customer",
			filters: { name: frm.doc.customer },
			fieldname: "tax_id",
		},
		callback: function (r) {
			const has_rfc = !!(r.message && r.message.tax_id);
			callback(has_rfc);
		},
		error: function (err) {
			callback(false);
		},
	});
}

function is_already_timbrada(frm) {
	const status = norm(frm.doc.fm_fiscal_status);
	const uuid_fiscal = (frm.doc.fm_uuid_fiscal || "").trim();
	const ffm_uuid = (frm.doc.fm_ffm_uuid || "").trim();

	// REGLA ESTRICTA: Timbrada solo si status=TIMBRADO Y tiene UUID
	const is_timbrada = status === "TIMBRADO" && (uuid_fiscal || ffm_uuid);

	log_ffm_debug(frm, `is_already_timbrada=${is_timbrada}`);
	return is_timbrada;
}

function should_show_timbrar_button(frm) {
	const status = norm(frm.doc.fm_fiscal_status);
	const allowed_statuses = ["BORRADOR", "ERROR", ""]; // Incluir vacío como válido
	const should_show = frm.doc.docstatus === 1 && allowed_statuses.includes(status);

	log_ffm_debug(frm, `should_show_timbrar=${should_show}, status="${status}"`);
	return should_show;
}

function add_timbrar_button(frm) {
	// Botón único y prominente: Timbrar Factura que redirije a Factura Fiscal Mexico
	frm.page.set_primary_action(__("Timbrar Factura"), function () {
		redirect_to_fiscal_document(frm);
	});
}

function add_view_fiscal_button(frm) {
	// Botón para ver documento fiscal ya timbrado
	frm.add_custom_button(__("Ver Factura Fiscal"), function () {
		frappe.set_route("Form", "Factura Fiscal Mexico", frm.doc.fm_factura_fiscal_mx);
	}).addClass("btn-info");

	// Agregar indicador visual de que ya está timbrada
	frm.dashboard.add_indicator(__("Ya Timbrada"), "green");
}

function redirect_to_fiscal_document(frm) {
	// VALIDACIÓN DOBLE PREVENCIÓN: Verificar si ya existe documento fiscal
	if (frm.doc.fm_factura_fiscal_mx) {
		// Verificar estado del documento fiscal existente
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Factura Fiscal Mexico",
				name: frm.doc.fm_factura_fiscal_mx,
				fieldname: "fm_fiscal_status",
			},
			callback: function (r) {
				// Usar estados desde configuración
				load_fiscal_states(function (states) {
					if (r.message && r.message.fm_fiscal_status === states.states.TIMBRADO) {
						frappe.msgprint({
							title: __("Ya Timbrada"),
							message: __(
								"Esta Sales Invoice ya está timbrada. No se puede volver a timbrar."
							),
							indicator: "orange",
						});
						return;
					}
				});
				// Si no está timbrada, ir al documento para continuar proceso
				frappe.set_route("Form", "Factura Fiscal Mexico", frm.doc.fm_factura_fiscal_mx);
			},
		});
		return;
	}

	// No existe, crear uno nuevo
	// Calcular IVA y otros impuestos desde la tabla taxes
	let iva_total = 0;
	let otros_impuestos = 0;

	if (frm.doc.taxes && frm.doc.taxes.length > 0) {
		frm.doc.taxes.forEach(function (tax) {
			// Identificar IVA por el account_head
			if (tax.account_head && tax.account_head.toUpperCase().includes("IVA")) {
				iva_total += tax.tax_amount || 0;
			} else {
				otros_impuestos += tax.tax_amount || 0;
			}
		});
	}

	frappe.call({
		method: "frappe.client.insert",
		args: {
			doc: {
				doctype: "Factura Fiscal Mexico",
				sales_invoice: frm.doc.name,
				company: frm.doc.company,
				customer: frm.doc.customer, // AÑADIR: Customer requerido
				fm_fiscal_status: FISCAL_STATES ? FISCAL_STATES.states.BORRADOR : "BORRADOR", // Estado desde configuración
				fm_payment_method_sat: "PUE", // Valor por defecto
				// Agregar montos del Sales Invoice para validación posterior
				si_total_antes_iva: frm.doc.net_total || 0,
				si_total_neto: frm.doc.grand_total || 0,
				si_iva: iva_total,
				si_otros_impuestos: otros_impuestos,
			},
		},
		callback: function (r) {
			if (r.message) {
				// Actualizar referencia en Sales Invoice
				frappe.call({
					method: "frappe.client.set_value",
					args: {
						doctype: "Sales Invoice",
						name: frm.doc.name,
						fieldname: "fm_factura_fiscal_mx",
						value: r.message.name,
					},
					callback: function () {
						// Mostrar mensaje de éxito
						frappe.show_alert(
							{
								message: __("Documento fiscal creado exitosamente"),
								indicator: "green",
							},
							3
						);

						// Forzar navegación completa con reload para corregir título
						setTimeout(() => {
							window.location.href = `/app/factura-fiscal-mexico/${r.message.name}`;
						}, 1000);
					},
				});
			} else {
				frappe.msgprint({
					title: __("Error"),
					message: __("No se pudo crear el documento fiscal"),
					indicator: "red",
				});
			}
		},
		error: function (r) {
			frappe.msgprint({
				title: __("Error al Crear Documento"),
				message: r.message || __("Error desconocido al crear Factura Fiscal Mexico"),
				indicator: "red",
			});
		},
	});
}
