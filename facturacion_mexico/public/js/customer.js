/**
 * Customer form customizations for Mexican Tax Validation
 * Adds "Validar RFC/CSF" button and validation logic
 */

frappe.ui.form.on("Customer", {
	refresh: function (frm) {
		// Agregar botón "Validar RFC/CSF" si es necesario
		add_rfc_validation_button(frm);

		// Mostrar estado de validación RFC
		show_rfc_validation_status(frm);
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

function show_rfc_validation_status(frm) {
	// Mostrar indicador visual inteligente del estado de validación
	const tax_id_field = frm.get_field("tax_id");
	const rfc_validated_field = frm.get_field("fm_rfc_validated");

	if (!frm.doc.tax_id) {
		// Sin RFC
		if (tax_id_field) {
			tax_id_field.$wrapper.find(".control-label").css("color", "#d73925");
			tax_id_field.set_description("⚠️ RFC requerido para facturación fiscal mexicana");
		}
	} else if (frm.doc.fm_rfc_validated) {
		// RFC validado - mostrar información útil y posibilidad de revalidar
		if (rfc_validated_field) {
			rfc_validated_field.$wrapper.find(".control-label").css("color", "#28a745");
			rfc_validated_field.set_description(
				`✅ RFC validado exitosamente el ${
					frm.doc.fm_rfc_validation_date || "fecha no disponible"
				}. Puede revalidar si hay cambios.`
			);
		}
	} else {
		// RFC sin validar - verificar qué falta específicamente
		if (rfc_validated_field) {
			rfc_validated_field.$wrapper.find(".control-label").css("color", "#fd7e14");

			// Verificar qué falta para ser más específicos
			if (!frm.doc.customer_primary_address) {
				rfc_validated_field.set_description(
					"⚠️ Se requiere dirección principal completa para validar RFC"
				);
			} else {
				// Verificar completitud de dirección
				check_address_completeness(frm, function (is_complete, missing_fields) {
					if (!is_complete && missing_fields.length > 0) {
						rfc_validated_field.set_description(
							`⚠️ Complete la dirección principal: ${missing_fields.join(", ")}`
						);
					} else {
						rfc_validated_field.set_description("📋 RFC listo para validar con SAT");
					}
				});
			}
		}
	}
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
					show_rfc_validation_status(frm);
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
