/**
 * E-Receipt Handler para Sales Invoice
 * Maneja avisos visuales y configuración automática
 */

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		handle_ereceipt_warnings(frm);
		setup_ereceipt_defaults(frm);
	},

	fm_ereceipt_mode(frm) {
		handle_ereceipt_mode_change(frm);
	},

	fm_ereceipt_expiry_type(frm) {
		handle_expiry_type_change(frm);
	},

	onload(frm) {
		setup_ereceipt_defaults_from_settings(frm);
	},
});

function handle_ereceipt_mode_change(frm) {
	const is_ereceipt = frm.doc.fm_ereceipt_mode === "E-Receipt";

	// Mostrar/ocultar warning
	toggle_ereceipt_warning(is_ereceipt);

	// Cambiar color del form si es E-Receipt
	if (is_ereceipt) {
		add_ereceipt_styling(frm);
		// Configurar valores por defecto
		set_ereceipt_defaults(frm);
	} else {
		remove_ereceipt_styling(frm);
		// Limpiar campos E-Receipt
		clear_ereceipt_fields(frm);
	}

	frm.refresh_fields();
}

function toggle_ereceipt_warning(show) {
	const warning = document.getElementById("ereceipt-warning");
	if (warning) {
		warning.style.display = show ? "block" : "none";
	}
}

function add_ereceipt_styling(frm) {
	// Agregar clase CSS para highlighting
	if (frm.wrapper) {
		frm.wrapper.classList.add("ereceipt-mode");
	}

	// Agregar estilo personalizado
	if (!document.getElementById("ereceipt-style")) {
		const style = document.createElement("style");
		style.id = "ereceipt-style";
		style.textContent = `
            .ereceipt-mode .form-layout {
                border-left: 4px solid #ff9800;
                background-color: #fff3e0;
            }
            .ereceipt-mode .page-title {
                color: #f57c00;
            }
            .ereceipt-mode .page-title::before {
                content: "🧾 ";
            }
            .ereceipt-mode .form-section {
                background-color: #fff8e1;
            }
        `;
		document.head.appendChild(style);
	}

	// Mostrar mensaje en el indicador
	frm.page.set_indicator(__("MODO E-RECEIPT - NO SE TIMBRARÁ"), "orange");

	// Mostrar alerta prominente
	frm.dashboard.add_comment(
		__(
			"⚠️ MODO E-RECEIPT ACTIVO: Esta factura NO se timbrará automáticamente. Se enviará como recibo electrónico para autofacturación del cliente."
		),
		"orange",
		true
	);
}

function remove_ereceipt_styling(frm) {
	if (frm.wrapper) {
		frm.wrapper.classList.remove("ereceipt-mode");
	}
	frm.page.clear_indicator();
}

function set_ereceipt_defaults(frm) {
	// Obtener defaults de settings
	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "Facturacion Mexico Settings",
			name: "Facturacion Mexico Settings",
			fieldname: ["ereceipt_expiry_type_default", "ereceipt_expiry_days_default"],
		},
		callback: function (r) {
			if (r.message) {
				const settings = r.message;

				if (!frm.doc.fm_ereceipt_expiry_type) {
					frm.set_value(
						"fm_ereceipt_expiry_type",
						settings.ereceipt_expiry_type_default || "Fixed Days"
					);
				}

				if (!frm.doc.fm_ereceipt_expiry_days) {
					frm.set_value(
						"fm_ereceipt_expiry_days",
						settings.ereceipt_expiry_days_default || 3
					);
				}
			}
		},
	});
}

function clear_ereceipt_fields(frm) {
	// Limpiar campos relacionados con E-Receipt
	frm.set_value("fm_ereceipt_expiry_type", "");
	frm.set_value("fm_ereceipt_expiry_days", "");
	frm.set_value("fm_ereceipt_expiry_date", "");
}

function handle_expiry_type_change(frm) {
	const expiry_type = frm.doc.fm_ereceipt_expiry_type;

	if (expiry_type === "End of Month") {
		// Calcular último día del mes
		const today = new Date();
		const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
		frm.set_value("fm_ereceipt_expiry_date", frappe.datetime.obj_to_str(lastDay));
	} else if (expiry_type === "Fixed Days") {
		// Calcular basado en días
		const days = frm.doc.fm_ereceipt_expiry_days || 3;
		const expiry_date = frappe.datetime.add_days(frappe.datetime.get_today(), days);
		frm.set_value("fm_ereceipt_expiry_date", expiry_date);
	}
}

function setup_ereceipt_defaults_from_settings(frm) {
	// Solo para nuevos documentos
	if (frm.is_new()) {
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Facturacion Mexico Settings",
				name: "Facturacion Mexico Settings",
				fieldname: "ereceipt_mode_default",
			},
			callback: function (r) {
				if (r.message && r.message.ereceipt_mode_default) {
					// Configurar modo por defecto
					frm.set_value("fm_ereceipt_mode", r.message.ereceipt_mode_default);
				}
			},
		});
	}
}

function setup_ereceipt_defaults(frm) {
	// Configurar valores iniciales si están vacíos
	if (frm.doc.fm_ereceipt_mode === "E-Receipt") {
		handle_ereceipt_mode_change(frm);
	}
}

function handle_ereceipt_warnings(frm) {
	// Mostrar warning si ya hay E-Receipt generado
	if (frm.doc.fm_ereceipt_doc) {
		frm.dashboard.add_comment(
			__("E-Receipt generado: {0}", [frm.doc.fm_ereceipt_doc]),
			"blue",
			true
		);

		if (frm.doc.fm_ereceipt_url) {
			frm.add_web_link(frm.doc.fm_ereceipt_url, __("Ver E-Receipt"));
		}
	}

	// Warning si está en modo E-Receipt pero no se ha generado
	if (
		frm.doc.fm_ereceipt_mode === "E-Receipt" &&
		!frm.doc.fm_ereceipt_doc &&
		frm.doc.docstatus === 1
	) {
		frm.dashboard.add_comment(
			__("Sales Invoice en modo E-Receipt pero no se ha generado el recibo"),
			"red",
			true
		);
	}
}

// Exportar funciones para uso externo
window.EReceiptHandler = {
	toggle_ereceipt_warning,
	add_ereceipt_styling,
	remove_ereceipt_styling,
	set_ereceipt_defaults,
};
