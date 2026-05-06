/**
 * Payment Entry — Complemento de Pago MX
 *
 * Muestra botón "Crear Complemento de Pago" cuando el PE cumple las condiciones
 * para generar un complemento PPD: submitido, tipo Receive, con SIs PPD timbradas
 * referenciadas y sin complemento previo.
 */

frappe.ui.form.on("Payment Entry", {
	refresh(frm) {
		_setup_complemento_btn(frm);
		_setup_complemento_cancel_warning(frm);
	},
});

function _setup_complemento_cancel_warning(frm) {
	if (frm.doc.docstatus !== 1) return;
	if (!frm.doc.fm_complemento_pago) return;

	// Mostrar advertencia visual si el complemento no está cancelado
	frappe.db
		.get_value("Complemento Pago MX", frm.doc.fm_complemento_pago, "complement_status")
		.then((r) => {
			const st = r.message && r.message.complement_status;
			if (st && st !== "Cancelado") {
				frm.dashboard.set_headline_alert(
					__(
						"Este Payment Entry tiene un Complemento de Pago fiscal activo ({0}) en estado '{1}'. " +
							"Cancele primero el complemento antes de cancelar el pago.",
						[frm.doc.fm_complemento_pago, st]
					),
					"orange"
				);
			}
		});
}

function _setup_complemento_btn(frm) {
	// Solo PE submitido
	if (frm.doc.docstatus !== 1) return;

	// Solo cobros (Receive)
	if (frm.doc.payment_type !== "Receive") return;

	// Ya tiene complemento — mostrar enlace de navegación en lugar de botón
	if (frm.doc.fm_complemento_pago) {
		frm.add_custom_button(__("Ver Complemento de Pago"), function () {
			frappe.set_route("Form", "Complemento Pago MX", frm.doc.fm_complemento_pago);
		}).addClass("btn-info");
		return;
	}

	// Verificar si hay al menos una SI PPD timbrada referenciada
	const tiene_ppd = (frm.doc.references || []).some(
		(ref) => ref.reference_doctype === "Sales Invoice" && flt(ref.allocated_amount) > 0
	);

	if (!tiene_ppd) return;

	// Mostrar botón
	frm.add_custom_button(__("Crear Complemento de Pago"), function () {
		frappe.confirm(__("¿Crear Complemento de Pago para este Payment Entry?"), function () {
			frappe.call({
				method: "facturacion_mexico.complementos_pago.api.crear_complemento_pago_desde_pe",
				args: { payment_entry_name: frm.doc.name },
				callback: function (r) {
					if (r.message && r.message.complemento_name) {
						frappe.show_alert(
							{
								message: __("Complemento {0} creado correctamente.", [
									r.message.complemento_name,
								]),
								indicator: "green",
							},
							5
						);
						frm.reload_doc();
					}
				},
			});
		});
	}).addClass("btn-primary");
}
