// Sales Invoice customizations for Facturacion Mexico - ARQUITECTURA MIGRADA
// Funcionalidad fiscal centralizada en Factura Fiscal Mexico

frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Solo mostrar botón de timbrado si está submitted, tiene RFC y NO está timbrada
		if (frm.doc.docstatus === 1) {
			has_customer_rfc(frm, function (has_rfc) {
				if (has_rfc && !is_already_timbrada(frm)) {
					add_timbrar_button(frm);
				} else if (is_already_timbrada(frm)) {
					add_view_fiscal_button(frm);
				}
			});
		}
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
	// PREVENCIÓN DOBLE FACTURACIÓN: Verificar si ya está vinculada a una Factura Fiscal Mexico
	return frm.doc.fm_factura_fiscal_mx && frm.doc.fm_factura_fiscal_mx.trim() !== "";
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
				if (r.message && r.message.fm_fiscal_status === "Timbrada") {
					frappe.msgprint({
						title: __("Ya Timbrada"),
						message: __(
							"Esta Sales Invoice ya está timbrada. No se puede volver a timbrar."
						),
						indicator: "orange",
					});
					return;
				}
				// Si no está timbrada, ir al documento para continuar proceso
				frappe.set_route("Form", "Factura Fiscal Mexico", frm.doc.fm_factura_fiscal_mx);
			},
		});
		return;
	}

	// No existe, crear uno nuevo
	frappe.call({
		method: "frappe.client.insert",
		args: {
			doc: {
				doctype: "Factura Fiscal Mexico",
				sales_invoice: frm.doc.name,
				company: frm.doc.company,
				customer: frm.doc.customer, // AÑADIR: Customer requerido
				fm_fiscal_status: "Pendiente", // Valor correcto en español
				fm_payment_method_sat: "PUE", // Valor por defecto
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
