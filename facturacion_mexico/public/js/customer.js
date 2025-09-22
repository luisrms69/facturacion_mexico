/**
 * Customer form customizations for Mexican Tax Validation
 * Adds "Validar RFC/CSF" button and validation logic
 */

frappe.ui.form.on("Customer", {
	refresh(frm) {
		// Agregar botón "Validar RFC/CSF" si es necesario
		add_rfc_validation_button(frm);

		// 1) Pintar UN solo aviso arriba
		render_sat_rfc_status(frm);

		// 2) Ocultar sección "Validación SAT" y sus campos (pero conservar datos para FFM)
		hide_sat_validation_section(frm);
	},

	tax_id: function (frm) {
		// Cuando cambia el RFC, limpiar validación anterior
		if (frm.doc.tax_id && frm.doc.fm_rfc_validated) {
			frappe.msgprint({
				title: __("RFC Modificado"),
				message: __("El RFC ha sido modificado. Se requiere nueva validación."),
				indicator: "orange",
			});

			// Limpiar campos de validación
			frm.set_value("fm_rfc_validated", 0);
			frm.set_value("fm_rfc_validation_date", "");
		}
	},
});

function add_rfc_validation_button(frm) {
	// Mostrar botón si hay RFC y dirección completa (independiente del estado de validación)
	if (frm.doc.tax_id && !frm.is_new()) {
		// Verificar que tiene dirección principal antes de mostrar botón
		if (frm.doc.customer_primary_address) {
			// Verificar completitud de dirección de forma asíncrona
			check_address_completeness(frm, function (is_complete) {
				if (is_complete) {
					// Texto del botón según estado actual
					const button_text = frm.doc.fm_rfc_validated
						? __("Revalidar RFC/CSF")
						: __("Validar RFC/CSF");

					frm.add_custom_button(
						button_text,
						function () {
							validate_customer_rfc_with_facturapi(frm);
						},
						__("Acciones")
					);
				}
			});
		}
	}
}

// --- Aviso único (Punto 1: RFC) ---
function render_sat_rfc_status(frm) {
	const id = "sat-rfc-status-banner";
	const existing = document.getElementById(id);
	if (existing) existing.remove();

	const tax_id = (frm.doc.tax_id || "").trim().toUpperCase();
	const validated = !!frm.doc.fm_rfc_validated; // Check (1/0)
	const validation_date = frm.doc.fm_rfc_validation_date; // Date (YYYY-MM-DD)

	let bsColor, message;
	if (!tax_id) {
		bsColor = "danger";
		message = "⚠️ RFC requerido.";
	} else if (validated) {
		const fecha = validation_date
			? frappe.datetime.str_to_user(validation_date)
			: frappe.datetime.str_to_user(frappe.datetime.get_today());
		bsColor = "success";
		message = `✅ RFC validado exitosamente el ${fecha}`;
	} else {
		bsColor = "warning";
		message = "📋 RFC listo para validar con SAT";
	}

	const html = `
		<div id="${id}" class="alert alert-${_bs_color(bsColor)}" role="alert" style="margin-top:8px">
			${frappe.utils.escape_html(message)}
		</div>
	`;

	const target =
		frm.fields_dict.tax_id && frm.fields_dict.tax_id.$wrapper
			? frm.fields_dict.tax_id.$wrapper
			: frm.$wrapper;

	$(html).insertAfter(target);
}

function _bs_color(color) {
	return (
		{ success: "success", warning: "warning", danger: "danger", secondary: "secondary" }[
			color
		] || "secondary"
	);
}

// --- Ocultar la sección y limpiar descripciones antiguas ---
function hide_sat_validation_section(frm) {
	// 1) Ocultar campos de datos (se siguen guardando en BD; FFM los lee)
	["fm_rfc_validated", "fm_rfc_validation_date"].forEach((fn) => {
		if (frm.get_field(fn)) {
			frm.set_df_property(fn, "hidden", 1);
			// Evita descripciones previas contradictorias:
			frm.get_field(fn).set_description("");
		}
	});

	// 2) Ocultar Section Break "Validación SAT" (si el fieldname no se conoce, localizar por label)
	(frm.fields || []).forEach((f) => {
		if (f.df.fieldtype === "Section Break" && f.df.label === "Validación SAT") {
			frm.toggle_display(f.df.fieldname, false);
		}
	});
}

function validate_customer_rfc_with_facturapi(frm) {
	// Validar RFC completo con FacturAPI

	// Verificaciones previas simplificadas (dirección ya verificada antes de mostrar botón)
	if (!frm.doc.tax_id) {
		frappe.msgprint({
			title: __("RFC Requerido"),
			message: __("Configure el RFC en el campo Tax ID antes de validar."),
			indicator: "red",
		});
		return;
	}

	if (frm.is_dirty()) {
		frappe.msgprint({
			title: __("Guardar Primero"),
			message: __("Guarde el Customer antes de validar el RFC."),
			indicator: "orange",
		});
		return;
	}

	// Variable para controlar si la validación fue cancelada
	let validation_cancelled = false;

	// Mostrar modal de progreso
	const progress_dialog = new frappe.ui.Dialog({
		title: __("Validando RFC"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "progress_html",
				options: `
					<div class="text-center">
						<div class="spinner-border text-primary" role="status">
							<span class="sr-only">Validando...</span>
						</div>
						<p class="mt-3">
							<strong>Validando RFC:</strong> ${frm.doc.tax_id}<br>
							<small class="text-muted">Validando RFC con FacturAPI...</small>
						</p>
					</div>
				`,
			},
		],
		primary_action_label: __("Cancelar"),
		primary_action: function () {
			validation_cancelled = true;
			progress_dialog.hide();
		},
	});

	// Manejar cierre del modal
	progress_dialog.$wrapper.on("hidden.bs.modal", function () {
		validation_cancelled = true;
	});

	progress_dialog.show();

	// Llamar API de validación
	frappe.call({
		method: "facturacion_mexico.validaciones.api.validate_customer_rfc_with_facturapi",
		args: {
			customer_name: frm.doc.name,
		},
		callback: function (response) {
			progress_dialog.hide();

			// Verificar si la validación fue cancelada antes de mostrar resultados
			if (validation_cancelled) {
				return;
			}

			if (response.message && response.message.success) {
				show_validation_results(frm, response.message.data);
			} else {
				// No mostrar mensaje automático, manejarlo en el modal
				show_validation_results(frm, {
					validation_successful: false,
					rfc_format_valid: true,
					address_configured: true,
					address_valid_for_facturapi: true,
					rfc_exists_in_sat: false,
					rfc_active_in_sat: false,
					validation_error:
						response.message?.error || "Error desconocido en validación RFC",
					warnings: [],
					recommendations: [
						"⚠️ No se pudo completar la validación con SAT. Verificar conexión o contactar soporte.",
					],
				});
			}
		},
		error: function (error) {
			progress_dialog.hide();

			// Verificar si la validación fue cancelada antes de mostrar error
			if (validation_cancelled) {
				return;
			}

			// Manejar error de conexión en modal también
			show_validation_results(frm, {
				validation_successful: false,
				rfc_format_valid: true,
				address_configured: true,
				address_valid_for_facturapi: false,
				rfc_exists_in_sat: false,
				rfc_active_in_sat: false,
				validation_error: "Error de conexión con el servicio de validación",
				warnings: ["No se pudo conectar con FacturAPI. Verificar conectividad."],
				recommendations: ["⚠️ Revisar conexión a internet o contactar soporte técnico."],
			});
			console.error("RFC Validation Error:", error);
		},
	});
}

function show_validation_results(frm, validation_data) {
	// Mostrar resultados detallados de la validación

	const is_successful = validation_data.validation_successful;
	const warnings = validation_data.warnings || [];
	const recommendations = validation_data.recommendations || [];

	// Determinar estado real de validación (RFC válido = existe + activo + nombre coincide + dirección coincide)
	const rfc_fully_valid =
		validation_data.rfc_exists_in_sat &&
		validation_data.rfc_active_in_sat &&
		validation_data.name_matches &&
		validation_data.address_matches !== false; // Si no está definido o es true, OK

	// Construir HTML de resultados
	let results_html = `
		<div class="validation-results">
			<div class="alert ${rfc_fully_valid ? "alert-success" : "alert-warning"}" role="alert">
				<h6><strong>${
					rfc_fully_valid ? "✅ RFC Completamente Válido" : "⚠️ RFC Requiere Corrección"
				}</strong></h6>
			</div>
	`;

	// Detalles de validación
	results_html += '<div class="row">';

	// Columna izquierda - Estado de validaciones
	results_html += `
		<div class="col-md-6">
			<h6>Estado de Validaciones:</h6>
			<ul class="list-unstyled">
				<li>${validation_data.rfc_format_valid ? "✅" : "❌"} Formato RFC válido</li>
				<li>${validation_data.address_configured ? "✅" : "❌"} Dirección configurada</li>
				<li>${
					validation_data.address_valid_for_facturapi ? "✅" : "❌"
				} Dirección completa para FacturAPI</li>
				<li>${validation_data.postal_code_format_valid ? "✅" : "❌"} Código postal formato válido</li>
				<li>${validation_data.rfc_exists_in_sat ? "✅" : "❌"} RFC existe en SAT</li>
				<li>${validation_data.rfc_active_in_sat ? "✅" : "❌"} RFC activo en SAT</li>
			</ul>
		</div>
	`;

	// Columna derecha - Información SAT
	results_html += `
		<div class="col-md-6">
			<h6>Información SAT:</h6>
			<ul class="list-unstyled">
				<li><strong>RFC:</strong> ${validation_data.rfc}</li>
				<li><strong>Nombre SAT:</strong> ${validation_data.sat_name || "No disponible"}</li>
				<li><strong>Coincide nombre:</strong> ${validation_data.name_matches ? "✅ Sí" : "❌ No"}</li>
				<li><strong>Customer actualizado:</strong> ${
					validation_data.customer_updated ? "✅ Sí" : "❌ No"
				}</li>
			</ul>
		</div>
	`;

	results_html += "</div>";

	// Warnings y errores específicos de FacturAPI
	if (warnings.length > 0) {
		results_html += '<div class="mt-3"><h6>⚠️ Advertencias:</h6><ul>';
		warnings.forEach((warning) => {
			results_html += `<li class="text-warning">${warning}</li>`;
		});
		results_html += "</ul></div>";
	}

	// Mostrar error específico de validación si existe
	if (validation_data.validation_error) {
		// Escapar caracteres especiales para evitar errores de template
		const safe_error = validation_data.validation_error
			.replace(/'/g, "&#39;")
			.replace(/"/g, "&quot;");

		results_html += `<div class="mt-3">
			<h6>📋 Detalle de Validación SAT:</h6>
			<div class="alert alert-info" role="alert">
				<small>${safe_error}</small>
			</div>
		</div>`;
	}

	// Recomendaciones
	if (recommendations.length > 0) {
		results_html += '<div class="mt-3"><h6>💡 Recomendaciones:</h6><ul>';
		recommendations.forEach((rec) => {
			// Escapar caracteres especiales en recomendaciones
			const safe_rec = rec.replace(/'/g, "&#39;").replace(/"/g, "&quot;");
			results_html += `<li class="small">${safe_rec}</li>`;
		});
		results_html += "</ul></div>";
	}

	results_html += "</div>";

	// Mostrar modal con resultados
	const results_dialog = new frappe.ui.Dialog({
		title: __("Resultados de Validación RFC"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "results_html",
				options: results_html,
			},
		],
		primary_action_label: __("Cerrar"),
		primary_action: function () {
			results_dialog.hide();

			// Refresh form para mostrar campos actualizados y botones
			frm.reload_doc().then(() => {
				// Después del reload, actualizar estado visual
				setTimeout(() => {
					render_sat_rfc_status(frm);
					add_rfc_validation_button(frm);
				}, 500);
			});
		},
	});

	results_dialog.show();
}

function check_address_completeness(frm, callback) {
	// Verificar si la dirección está completa para FacturAPI
	if (!frm.doc.customer_primary_address) {
		callback(false, ["Dirección principal"]);
		return;
	}

	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Address",
			name: frm.doc.customer_primary_address,
		},
		callback: function (r) {
			if (!r.message) {
				callback(false, ["Dirección principal"]);
				return;
			}

			const address = r.message;
			const missing_fields = [];

			// Verificar campos críticos para FacturAPI
			if (!address.address_line1) missing_fields.push("Calle");
			if (!address.pincode) missing_fields.push("Código Postal");
			if (!address.city) missing_fields.push("Ciudad");
			if (!address.state) missing_fields.push("Estado");
			if (!address.country) missing_fields.push("País");

			callback(missing_fields.length === 0, missing_fields);
		},
	});
}
