frappe.ui.form.on("Facturacion Mexico Company Settings", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Probar Conexión"), () => {
				frappe.call({
					method: "facturacion_mexico.facturacion_fiscal.api_client.test_facturapi_connection",
					callback(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({ message: __("Conexión exitosa"), indicator: "green" });
						} else {
							frappe.show_alert({ message: __("Error de conexión"), indicator: "red" });
						}
					},
				});
			});
		}
	},
});
