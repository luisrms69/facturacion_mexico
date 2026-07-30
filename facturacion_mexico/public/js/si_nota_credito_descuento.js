// Acción de negocio: "Aplicar como Descuento / Bonificación" en una Nota de Crédito (Sales Invoice
// Return) en borrador. El operador NO selecciona cuentas ni códigos SAT: el sistema asigna
// automáticamente la cuenta de descuentos configurada por empresa como income_account de las líneas.
frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		// Solo en documentos guardados, en borrador, que sean nota de crédito con factura de origen.
		if (frm.is_new()) return;
		if (!(frm.doc.is_return && frm.doc.docstatus === 0 && frm.doc.return_against)) return;

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
							message: __(
								"Nota de crédito preparada como Descuento / Bonificación."
							),
							indicator: "green",
						});
						frm.reload_doc();
					},
				});
			},
			__("Acciones")
		);
	},
});
