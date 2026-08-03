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
		frm.remove_custom_button(__("Crear Factura Fiscal"));
		frm.remove_custom_button(__("Abrir Factura Fiscal"));

		if (frm.doc.docstatus !== 1) return;

		// Estado fiscal centralizado — decide Timbrar y Ver Factura Fiscal
		frappe.call({
			method: "facturacion_mexico.fiscal_state.api.get_fiscal_ui_state",
			args: { doctype: "Sales Invoice", name: frm.doc.name },
			callback(r) {
				if (!r.message) return;
				const { actions } = r.message;
				// Estado autoritativo del servidor: guardarlo en el frm para que cualquier vía
				// (incluidas las asíncronas) respete can_stamp al decidir dibujar el botón.
				frm.__fm_can_stamp = actions.can_stamp === true;
				// Limpiar SIEMPRE la acción primaria antes de decidir.
				frm.page.clear_primary_action();
				if (actions.can_view_ffm) add_view_fiscal_button(frm);
				// can_stamp: condiciones técnicas OK — RFC check decide si mostrar o avisar
				if (actions.can_stamp) _check_rfc_and_show_timbrar(frm);
			},
		});
	},
});

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
	// Guard de choke-point: nunca colocar el botón si el estado fiscal autoritativo del servidor
	// no permite timbrar. Bloquea cualquier vía (síncrona o asíncrona) que intente dibujarlo
	// cuando can_stamp es false (p. ej. FFM en Draft ya vinculada).
	if (frm.__fm_can_stamp !== true) return;
	// Botón único y prominente: Timbrar Factura que redirije a Factura Fiscal Mexico
	frm.page.set_primary_action(__("Crear Factura Fiscal"), function () {
		redirect_to_fiscal_document(frm);
	});
}

function add_view_fiscal_button(frm) {
	frm.add_custom_button(__("Abrir Factura Fiscal"), function () {
		frappe.set_route("Form", "Factura Fiscal Mexico", frm.doc.fm_factura_fiscal_mx);
	}).addClass("btn-info");
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

	// SI devolución → resolver UUID antes de crear FFM tipo E
	if (frm.doc.is_return) {
		_resolve_uuid_for_return(frm, function (uuid) {
			if (uuid) {
				_do_create_ffm(frm, {
					fm_uuid_relacionado: uuid,
					// Physical merchandise return → TipoRelación 03 (Issue #116)
					// TipoRelación 01 (discounts/bonifications) handled in Issue #137
					fm_tipo_relacion_sat:
						"03 - Devolución de mercancía sobre facturas o traslados previos",
				});
			}
		});
		return;
	}

	_do_create_ffm(frm, {});
}

function _resolve_uuid_for_return(frm, callback) {
	if (!frm.doc.return_against) {
		_show_uuid_dialog(frm, callback);
		return;
	}

	frappe.db.get_value(
		"Sales Invoice",
		frm.doc.return_against,
		"fm_factura_fiscal_mx",
		function (si_data) {
			const ffm_name = si_data && si_data.fm_factura_fiscal_mx;
			if (!ffm_name) {
				_show_uuid_dialog(frm, callback);
				return;
			}

			frappe.db.get_value("Factura Fiscal Mexico", ffm_name, "fm_uuid", function (ffm_data) {
				const uuid = ffm_data && ffm_data.fm_uuid;
				if (uuid) {
					callback(uuid);
				} else {
					_show_uuid_dialog(frm, callback);
				}
			});
		}
	);
}

function _show_uuid_dialog(frm, callback) {
	frappe.prompt(
		{
			label: __("UUID del CFDI original"),
			fieldname: "uuid",
			fieldtype: "Data",
			reqd: 1,
			description: __(
				"UUID del CFDI que esta nota de crédito cancela o modifica (36 caracteres)"
			),
		},
		function (values) {
			const uuid = (values.uuid || "").trim();
			if (uuid.length !== 36) {
				frappe.msgprint({
					title: __("UUID inválido"),
					message: __(
						"El UUID debe tener 36 caracteres (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
					),
					indicator: "red",
				});
				return;
			}
			callback(uuid);
		},
		__("UUID relacionado requerido"),
		__("Continuar")
	);
}

function _do_create_ffm(frm, extra_fields) {
	// Corrección 3: la creación del FFM se centraliza en servidor mediante
	// get_or_create_active_ffm. El cliente ya NO usa frappe.client.insert ni un
	// set_value separado para vincular; el servidor crea (o reutiliza) el FFM,
	// lo vincula a la Sales Invoice y devuelve su nombre.
	frappe.call({
		method: "facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico.get_or_create_active_ffm",
		args: {
			sales_invoice: frm.doc.name,
			extra_fields: extra_fields || {},
		},
		callback: function (r) {
			if (r.message) {
				const ffm_name = r.message;
				frappe.show_alert(
					{
						message: __("Documento fiscal listo"),
						indicator: "green",
					},
					3
				);

				setTimeout(() => {
					window.location.href = `/app/factura-fiscal-mexico/${ffm_name}`;
				}, 1000);
			} else {
				frappe.msgprint({
					title: __("Error"),
					message: __("No se pudo preparar el documento fiscal"),
					indicator: "red",
				});
			}
		},
		error: function (r) {
			frappe.msgprint({
				title: __("Error al preparar documento"),
				message: r.message || __("Error desconocido al preparar Factura Fiscal Mexico"),
				indicator: "red",
			});
		},
	});
}

// =============================
// AUTOMATED TAX SYSTEM - Sales Invoice - PASO 2 + PASO 3 COMPLETO
// Sistema Automatizado de Impuestos
// =============================

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		// Visibilidad: que el usuario vea que es obligatorio desde el form
		frm.set_df_property("cost_center", "reqd", 1);

		// FIX #2: Filtrar Cost Centers por Company actual
		frm.set_query("cost_center", function () {
			return {
				filters: {
					company: frm.doc.company,
					disabled: 0,
				},
			};
		});
	},

	// NOTA: el handler `customer` duplicado se consolidó en `apply_customer_defaults()`
	// (ver bloque inferior). Aquí solo queda la lógica de cost_center.

	// Si el usuario cambia el cost_center manualmente, refrescar Branch/Price List en UI
	cost_center: async function (frm) {
		const cc = frm.doc.cost_center;
		if (!cc) return;

		// 1) Branch desde CC
		let derived_branch = null;
		try {
			const branch = await frappe.db.get_value("Cost Center", cc, "fm_mapped_branch");
			if (branch && branch.message && branch.message.fm_mapped_branch) {
				derived_branch = branch.message.fm_mapped_branch;
				if (frm.fields_dict.fm_branch) {
					frm.set_value("fm_branch", derived_branch);
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
					{ name: frm.doc.customer },
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
				// Mensaje negocio sin referencias técnicas, 6-7 segundos
				frappe.show_alert(
					{
						message: __("Lista de precios asignada automáticamente."),
						indicator: "green",
					},
					6
				);
			}
		} catch (e) {
			// silencio
		}

		// PASO 3: STCT autoselección ahora manejada 100% por Python hook
		// Ver: facturacion_mexico/hooks_handlers/sales_invoice_automated_tax.py
		// El hook Python muestra mensaje correcto después de clasificar items
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

	// FIX #2: Al cambiar Company, limpiar Cost Center si no pertenece a la nueva Company
	async company(frm) {
		if (!frm.doc.company || !frm.doc.cost_center) return;

		// Verificar si el Cost Center actual pertenece a la nueva Company
		try {
			const cc_company = await frappe.db.get_value(
				"Cost Center",
				frm.doc.cost_center,
				"company"
			);
			if (
				cc_company &&
				cc_company.message &&
				cc_company.message.company !== frm.doc.company
			) {
				// Cost Center no pertenece a la nueva Company, limpiarlo
				frm.set_value("cost_center", "");
				frappe.show_alert(
					{
						message: __(
							"Centro de Costos limpiado: no pertenece a la nueva Company seleccionada."
						),
						indicator: "orange",
					},
					6
				);
			}
		} catch (e) {
			// silencio: en caso de error, dejamos que el usuario maneje manualmente
		}
	},
});

// =============================
// AUTOMATED TAX SYSTEM - Sales Invoice (UI helpers)
// =============================

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		// Requerido en UI; server valida también
		frm.set_df_property("cost_center", "reqd", 1);
	},

	customer: async function (frm) {
		// Handler único de cliente: carga de defaults consolidada (antes duplicada en dos bloques).
		await apply_customer_defaults(frm);
	},

	// NOTA: el handler `cost_center` de este bloque se eliminó por ser un duplicado redundante
	// del handler `cost_center` del bloque superior (que ya resuelve fm_branch + Price List con
	// cascada Customer → Cost Center → Selling Settings). Su única acción propia era un no-op
	// (_fm_apply_branch_tax_template); su cascada Price List era subconjunto de la otra.

	before_save(frm) {
		if (!frm.doc.cost_center) {
			frappe.msgprint("No se puede guardar sin <b>Cost Center</b> en el encabezado.");
			frappe.validated = false;
		}
	},
});

// DEPRECADO: Autoselección STCT ahora manejada por Python hook before_validate()
// Ver: facturacion_mexico/hooks_handlers/sales_invoice_automated_tax.py
async function _fm_apply_branch_tax_template(frm) {
	// Función vacía - lógica migrada a Python hook
	// Python hook maneja:
	// 1. Cost Center → Branch derivación
	// 2. Clasificación items (IEPS, Retenciones)
	// 3. Autoselección 8 STCT específicos (Nacional/Frontera × 4 variantes)
	return;
}

// Carga de defaults del Customer (Centro de Costos + Price List) y resolución STCT.
// Consolida los dos handlers `customer` que antes ejecutaban esta misma lógica por separado.
// Usa filtro { name } para que docnames con comillas/caracteres especiales lleguen intactos
// al servidor (un string suelto lo mutila `get_safe_filters`/orjson).
async function apply_customer_defaults(frm) {
	if (!frm.doc.customer) return;

	try {
		const { message } = await frappe.db.get_value("Customer", { name: frm.doc.customer }, [
			"fm_customer_default_cost_center",
			"default_price_list",
		]);
		const cc = message ? message.fm_customer_default_cost_center : null;
		const pl = message ? message.default_price_list : null;

		// 1) Centro de Costos por defecto del cliente
		if (cc) {
			await frm.set_value("cost_center", cc);
			frappe.show_alert(
				{ message: __("Centro de Costos asignado automáticamente."), indicator: "green" },
				6
			);
		} else {
			frappe.show_alert(
				{
					message: __("El cliente no tiene Centro de Costos por defecto."),
					indicator: "orange",
				},
				6
			);
		}

		// 2) Price List del cliente si aún no hay una asignada
		if (!frm.doc.selling_price_list && pl) {
			await frm.set_value("selling_price_list", pl);
		}

		// 3) Resolver STCT por sucursal emisora (lógica en Python hook)
		await _fm_apply_branch_tax_template(frm);
	} catch (e) {
		console.log("apply_customer_defaults error", e);
		// Notificación visible ante fallo de lectura del Customer (conserva el aviso que daba
		// el handler previo; una sola alerta, no duplicada).
		frappe.show_alert(
			{
				message: __(
					"Error al cargar la configuración del cliente. Configúrala manualmente."
				),
				indicator: "red",
			},
			6
		);
	}
}

function cint(v) {
	try {
		return parseInt(v, 10) || 0;
	} catch (e) {
		return 0;
	}
}

// Verificar RFC validado y mostrar botón timbrar o mensaje de aviso.
// Llamado desde sales_invoice_block_cancel.js después de resolver estado de cancelación.
function _check_rfc_and_show_timbrar(frm) {
	if (!frm.doc || frm.doc.docstatus !== 1) return;
	if (!frm.doc.customer) return;

	// Una sola lectura del Customer: tax_id (RFC presente) + fm_rfc_validated (validado SAT).
	// Filtro { name } explícito: un docname con comillas (p. ej. un nombre entre comillas dobles) pasado
	// como string suelto es mutilado por get_safe_filters/orjson en el servidor y no encontraría
	// al cliente, mostrando falsamente "RFC no validado".
	frappe.db
		.get_value("Customer", { name: frm.doc.customer }, ["tax_id", "fm_rfc_validated"])
		.then((r) => {
			const msg = (r && r.message) || {};

			// Solo avisar/dibujar cuando el estado fiscal permite crear FFM (can_stamp autoritativo).
			// Evita avisos engañosos de "valida el RFC para crear la FFM" en SI que ya tienen una FFM
			// (can_stamp=false). No introduce lógica de FFM aquí: usa el flag fiscal ya calculado.
			if (frm.__fm_can_stamp !== true) return;

			// RFC válido = tiene tax_id Y está validado ante SAT (tolera 1 numérico o "1" string).
			// RFC vacío o no validado se tratan igual: no se dibuja botón y se muestra el mismo aviso.
			const is_validated =
				Boolean(msg.tax_id) &&
				(msg.fm_rfc_validated === 1 || msg.fm_rfc_validated === "1");
			if (is_validated) {
				if (should_show_timbrar_button(frm)) {
					add_timbrar_button(frm);
				} else if (is_already_timbrada(frm)) {
					add_view_fiscal_button(frm);
				}
			} else {
				frm.dashboard &&
					frm.dashboard.set_headline_alert(
						__("No puedes timbrar: el RFC del cliente no está validado con SAT."),
						"orange"
					);
			}
		})
		.catch(() => {
			// Error de servidor: no mostrar boton ni alerta (paridad con el manejo previo).
		});
}
