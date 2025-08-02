// Sales Invoice customizations for Facturacion Mexico - ARQUITECTURA MIGRADA
// Funcionalidad fiscal centralizada en Factura Fiscal Mexico

frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Solo mostrar botón de timbrado si está submitted y tiene RFC
		if (frm.doc.docstatus === 1 && has_customer_rfc(frm)) {
			add_timbrar_button(frm);
		}
	},
});

function has_customer_rfc(frm) {
	// Verificar si el cliente tiene RFC configurado
	return frm.doc.customer && frm.doc.tax_id;
}

function add_timbrar_button(frm) {
	// Botón único y prominente: Timbrar Factura que redirije a Factura Fiscal Mexico
	frm.page.set_primary_action(__("Timbrar Factura"), function () {
		redirect_to_fiscal_document(frm);
	});
}

function redirect_to_fiscal_document(frm) {
	// Verificar si ya existe documento fiscal
	if (frm.doc.fm_factura_fiscal_mx) {
		// Ya existe, ir directamente
		frappe.set_route("Form", "Factura Fiscal Mexico", frm.doc.fm_factura_fiscal_mx);
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
				fm_fiscal_status: "Pendiente", // Valor válido según el DocType
				fm_payment_method_sat: "PUE", // Valor por defecto para evitar validaciones
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
						// Ir al documento fiscal recién creado
						frappe.set_route("Form", "Factura Fiscal Mexico", r.message.name);
					},
				});
			}
		},
	});
}
