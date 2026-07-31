// Acciones de negocio sobre una Nota de Crédito (Sales Invoice Return) en borrador:
//   - "Aplicar como Descuento / Bonificación": asigna la cuenta de descuentos por empresa como
//     income_account de las líneas (el operador NO selecciona cuentas ni códigos SAT).
//   - "Revertir a Devolución de mercancía": restaura income_account/description desde el origen.
// Qué botón se muestra depende del estado CONTABLE real (income_account == cuenta de descuentos),
// no de la descripción (editable). Se consulta al servidor en refresh.
frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		// Solo en documentos guardados, en borrador, que sean nota de crédito con factura de origen.
		if (frm.is_new()) return;
		if (!(frm.doc.is_return && frm.doc.docstatus === 0 && frm.doc.return_against)) return;

		frappe.call({
			method: "facturacion_mexico.facturacion_fiscal.api.nota_credito.estado_nota_descuento",
			args: { sales_invoice: frm.doc.name },
			callback: function (r) {
				if (r.exc || !r.message) return;
				// Evitar botones duplicados tras reload_doc: quitar ambos antes de agregar el actual.
				frm.remove_custom_button(
					__("Aplicar como Descuento / Bonificación"),
					__("Acciones")
				);
				frm.remove_custom_button(__("Revertir a Devolución de mercancía"), __("Acciones"));
				if (r.message.es_descuento) {
					agregar_boton_revertir(frm);
				} else {
					agregar_boton_descuento(frm);
				}
			},
		});
	},
});

function agregar_boton_descuento(frm) {
	frm.add_custom_button(
		__("Aplicar como Descuento / Bonificación"),
		function () {
			frappe.call({
				method: "facturacion_mexico.facturacion_fiscal.api.nota_credito.aplicar_como_descuento",
				args: { sales_invoice: frm.doc.name },
				freeze: true,
				freeze_message: __("Preparando nota de crédito como descuento…"),
				callback: function (r) {
					if (r.exc) return;
					frappe.show_alert({
						message: __("Nota de crédito preparada como Descuento / Bonificación."),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		},
		__("Acciones")
	);
}

function agregar_boton_revertir(frm) {
	frm.add_custom_button(
		__("Revertir a Devolución de mercancía"),
		function () {
			frappe.call({
				method: "facturacion_mexico.facturacion_fiscal.api.nota_credito.revertir_a_devolucion",
				args: { sales_invoice: frm.doc.name },
				freeze: true,
				freeze_message: __("Revirtiendo a devolución de mercancía…"),
				callback: function (r) {
					if (r.exc) return;
					frappe.show_alert({
						message: __("Nota de crédito revertida a Devolución de mercancía."),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		},
		__("Acciones")
	);
}
