// Configuración Fiscal México - JavaScript para manejo de checkboxes y tabla dinámica

frappe.ui.form.on("Configuracion Fiscal Mexico", {
	onload: function (frm) {
		// En documentos nuevos, agregar filas base cuando se selecciona empresa
		if (frm.doc.__islocal && frm.doc.company) {
			add_base_roles(frm);
		}
	},

	refresh: function (frm) {
		// Deshabilitar botón "Add Row" en tabla de mapeo - solo agregar filas automáticamente
		frm.fields_dict.mapeo_cuentas.grid.cannot_add_rows = true;

		// Filtrar cuentas de impuestos por empresa en tabla hija
		if (frm.doc.company) {
			frm.set_query("cuenta_impuesto", "mapeo_cuentas", function () {
				return {
					filters: {
						company: frm.doc.company,
						account_type: "Tax",
						is_group: 0,
					},
				};
			});
		}

		// Agregar botones solo para documentos guardados
		if (!frm.doc.__islocal && frm.doc.company) {
			// Botón para generar templates (solo si configuración completa)
			if (frm.doc.configuracion_completa) {
				frm.add_custom_button(__("⚙️ Generar Templates"), function () {
					// Simular call desde UI
					frappe.call({
						method: "aplicar_mapeo_y_generar_templates",
						doc: frm.doc,
						args: {
							from_ui: true,
						},
						callback: function (r) {
							if (r.message) {
								frappe.show_alert({
									message: "Templates fiscales generados exitosamente",
									indicator: "green",
								});
							}
						},
					});
				});
			}
		}
	},

	// Triggers para checkboxes de alcance - agregar filas inmediatamente
	enable_exento: function (frm) {
		update_roles_table(frm);
	},

	enable_frontera: function (frm) {
		update_roles_table(frm);
	},

	enable_exportacion: function (frm) {
		update_roles_table(frm);
	},

	enable_ret_honorarios: function (frm) {
		update_roles_table(frm);
	},

	enable_ret_arrendamiento: function (frm) {
		update_roles_table(frm);
	},

	enable_ret_autotransporte: function (frm) {
		update_roles_table(frm);
	},

	enable_ret_resico: function (frm) {
		update_roles_table(frm);
	},

	enable_ieps_alcohol: function (frm) {
		update_roles_table(frm);
	},

	enable_ieps_azucar: function (frm) {
		update_roles_table(frm);
	},

	enable_ieps_combustibles: function (frm) {
		update_roles_table(frm);
	},

	enable_ieps_tabaco: function (frm) {
		update_roles_table(frm);
	},

	company: function (frm) {
		// Configurar filtro de cuentas cuando cambia empresa
		if (frm.doc.company) {
			frm.set_query("cuenta_impuesto", "mapeo_cuentas", function () {
				return {
					filters: {
						company: frm.doc.company,
						account_type: "Tax",
						is_group: 0,
					},
				};
			});

			// Limpiar tabla cuando cambia empresa y agregar roles base
			frm.clear_table("mapeo_cuentas");
			frm.refresh_field("mapeo_cuentas");

			// Agregar roles base inmediatamente
			add_base_roles(frm);
		}
	},
});

function add_base_roles(frm) {
	// Agregar roles base (IVA Nacional, IVA Exento) inmediatamente
	if (!frm.doc.company) return;

	// Agregar solo si la tabla está vacía
	if (frm.doc.mapeo_cuentas && frm.doc.mapeo_cuentas.length > 0) return;

	// Roles siempre requeridos
	const base_roles = ["IVA por Pagar (Nacional)"];
	if (frm.doc.enable_exento) {
		base_roles.push("IVA Exento");
	}

	base_roles.forEach(function (rol) {
		let row = frm.add_child("mapeo_cuentas");
		row.rol_fiscal = rol;
		row.cuenta_impuesto = "";
		row.sugerido_automaticamente = 0;
		row.justificacion_sugerencia = "Mapeo manual requerido";
		row.estado_validacion = "Error";
	});

	frm.refresh_field("mapeo_cuentas");
	frappe.show_alert({
		message: "Roles base agregados. Configure alcance adicional si es necesario.",
		indicator: "blue",
	});
}

function update_roles_table(frm) {
	// Solo ejecutar si hay empresa seleccionada
	if (!frm.doc.company) {
		frappe.show_alert({
			message: "Seleccione una empresa antes de configurar alcance",
			indicator: "orange",
		});
		return;
	}

	// Llamar al método servidor para agregar/eliminar filas según alcance
	frappe.call({
		method: "sincronizar_tabla_con_alcance",
		doc: frm.doc,
		callback: function (r) {
			if (r.message) {
				// frappe.model.sync(r.docs) already updated frm.doc via run_doc_method
				// Just force the grid to re-render from the already-synced doc
				frm.fields_dict["mapeo_cuentas"].grid.refresh();
				let mensaje = "";
				if (r.message.filas_agregadas > 0) {
					mensaje += `${r.message.filas_agregadas} roles agregados. `;
				}
				if (r.message.filas_eliminadas > 0) {
					mensaje += `${r.message.filas_eliminadas} roles eliminados. `;
				}
				if (mensaje) {
					frappe.show_alert({
						message: mensaje + "Complete el mapeo de cuentas.",
						indicator: "blue",
					});
				}
			}
		},
	});
}

// Validación en tiempo real para tabla de mapeo
frappe.ui.form.on("Mapeo Cuenta Fiscal Mexico", {
	cuenta_impuesto: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		// Validar que la cuenta seleccionada sea tipo Tax
		if (row.cuenta_impuesto) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Account",
					filters: { name: row.cuenta_impuesto },
					fieldname: ["account_type", "company"],
				},
				callback: function (r) {
					if (r.message) {
						if (r.message.account_type !== "Tax") {
							frappe.msgprint({
								title: "Cuenta inválida",
								message: `La cuenta "${row.cuenta_impuesto}" no es tipo Tax. Seleccione una cuenta de impuestos.`,
								indicator: "red",
							});
							frappe.model.set_value(cdt, cdn, "cuenta_impuesto", "");
							frappe.model.set_value(cdt, cdn, "estado_validacion", "Error");
						} else if (r.message.company !== frm.doc.company) {
							frappe.msgprint({
								title: "Cuenta inválida",
								message: `La cuenta "${row.cuenta_impuesto}" pertenece a otra empresa.`,
								indicator: "red",
							});
							frappe.model.set_value(cdt, cdn, "cuenta_impuesto", "");
							frappe.model.set_value(cdt, cdn, "estado_validacion", "Error");
						} else {
							// Cuenta válida
							frappe.model.set_value(cdt, cdn, "estado_validacion", "Válido");
							frappe.model.set_value(
								cdt,
								cdn,
								"justificacion_sugerencia",
								"Cuenta válida seleccionada manualmente"
							);
						}
					}
				},
			});
		} else {
			frappe.model.set_value(cdt, cdn, "estado_validacion", "Error");
		}
	},
});
