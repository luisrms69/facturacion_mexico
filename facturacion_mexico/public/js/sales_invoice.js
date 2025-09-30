// Sales Invoice customizations for Facturacion Mexico - ARQUITECTURA MIGRADA
// Funcionalidad fiscal centralizada en Factura Fiscal Mexico

// Helper de normalización y diagnóstico
function norm(x) {
	return (x || "").toString().trim().toUpperCase();
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
		// Limpiar botones previos
		frm.remove_custom_button(__("Timbrar Factura"));
		frm.remove_custom_button(__("Ver Factura Fiscal")); // evitar duplicados

		if (frm.doc.docstatus === 1) {
			// Mostrar botón de navegación si existe vínculo, independiente del estado
			if (frm.doc.fm_factura_fiscal_mx) {
				add_view_fiscal_button(frm);
			}

			has_customer_rfc(frm, function (has_rfc) {
				if (has_rfc) {
					// NUEVO: Verificar RFC validado
					frappe.db
						.get_value("Customer", frm.doc.customer, ["fm_rfc_validated"])
						.then((r) => {
							const is_validated = !!(
								r.message &&
								(r.message.fm_rfc_validated === 1 ||
									r.message.fm_rfc_validated === "1")
							);
							if (is_validated) {
								if (should_show_timbrar_button(frm)) {
									add_timbrar_button(frm);
								} else if (is_already_timbrada(frm)) {
									add_view_fiscal_button(frm);
								}
							} else {
								frm.dashboard.set_headline_alert(
									__(
										"No puedes timbrar: el RFC del cliente no está validado con SAT."
									),
									"orange"
								);
							}
						});
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
	// Función "no-op" segura para evitar referencias a campos obsoletos.
	// Mantiene compatibilidad con tests que verifican su existencia/uso.
	const ffm_link = (frm.doc.fm_factura_fiscal_mx || "").trim();
	const status = (frm.doc.fm_fiscal_status || "").trim().toUpperCase();
	// Considera "timbrada" si hay vínculo al FFM; si además quieres
	// respetar el estado, deja la segunda condición:
	return !!ffm_link && status === "TIMBRADO";
}

function should_show_timbrar_button(frm) {
	const status = norm(frm.doc.fm_fiscal_status);
	const allowed_statuses = ["BORRADOR", "ERROR", ""]; // Incluir vacío como válido
	const should_show = frm.doc.docstatus === 1 && allowed_statuses.includes(status);

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
				// fm_payment_method_sat será asignado por validate_payment_method() usando settings
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

// =============================
// AUTOMATED TAX SYSTEM - Sales Invoice - PASO 2 COMPLETO
// Sistema Automatizado de Impuestos
// =============================

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		// Visibilidad: que el usuario vea que es obligatorio desde el form
		frm.set_df_property("cost_center", "reqd", 1);
	},

	// Al cambiar Customer: proponer CC (servidor lo hará en before_validate)
	// Aquí solo UX inmediato: preguntar si quiere cargar defaults ahora.
	customer(frm) {
		if (!frm.doc.customer) return;

		// Para UX, mostramos aviso. La asignación definitiva vive en server (before_validate).
		frappe.show_alert({
			message: __("Se propondrá Centro de Costos, Sucursal y Price List según el cliente."),
			indicator: "blue",
		});
	},

	// Si el usuario cambia el cost_center manualmente, refrescar Branch/Price List en UI
	cost_center: async function (frm) {
		const cc = frm.doc.cost_center;
		if (!cc) return;

		// 1) Branch desde CC
		try {
			const branch = await frappe.db.get_value("Cost Center", cc, "fm_mapped_branch");
			if (branch && branch.message && branch.message.fm_mapped_branch) {
				if (frm.fields_dict.fm_branch) {
					frm.set_value("fm_branch", branch.message.fm_mapped_branch);
				}
			}
		} catch (e) {
			// silencio: el server-side hará la asignación de todos modos
		}

		// 2) Price List por prioridad (Customer → CC → Company)
		try {
			// Customer.default_price_list
			let picked = null;
			let source = null;

			if (frm.doc.customer) {
				const cust = await frappe.db.get_value(
					"Customer",
					frm.doc.customer,
					"default_price_list"
				);
				if (cust && cust.message && cust.message.default_price_list) {
					picked = cust.message.default_price_list;
					source = "Customer.default_price_list";
				}
			}

			// CC.fm_default_selling_price_list
			if (!picked) {
				const ccpl = await frappe.db.get_value(
					"Cost Center",
					cc,
					"fm_default_selling_price_list"
				);
				if (ccpl && ccpl.message && ccpl.message.fm_default_selling_price_list) {
					picked = ccpl.message.fm_default_selling_price_list;
					source = "Cost Center.fm_default_selling_price_list";
				}
			}

			// Selling Settings.selling_price_list
			if (!picked) {
				const ss = await frappe.db.get_single_value(
					"Selling Settings",
					"selling_price_list"
				);
				if (ss) {
					picked = ss;
					source = "Selling Settings.selling_price_list";
				}
			}

			if (picked && frm.doc.selling_price_list !== picked) {
				await frm.set_value("selling_price_list", picked);
				frappe.show_alert({
					message: __(`Price List seleccionado: <b>${picked}</b> (fuente: ${source}).`),
					indicator: "green",
				});
			}
		} catch (e) {
			// silencio
		}
	},

	// Bloqueos UI (refuerzo — el bloqueo real también está en validate server-side)
	validate(frm) {
		if (!frm.doc.cost_center) {
			frappe.msgprint(__("No se puede guardar: <b>Centro de Costos</b> es obligatorio."));
			frappe.validated = false;
			return;
		}

		// Validación SAT: verificar items tienen fm_producto_servicio_sat en Item
		const items = frm.doc.items || [];
		for (let i = 0; i < items.length; i++) {
			const row = items[i];
			if (!row.item_code) {
				frappe.msgprint(__(`Línea ${i + 1} sin <b>Item Code</b>. No se puede guardar.`));
				frappe.validated = false;
				return;
			}
			// Nota: Validación completa de SAT se hace en server-side via Item.fm_producto_servicio_sat
		}
	},
});
