// Form controller — CFDI Recibido
// List view settings: cfdi_recibido_list.js

frappe.ui.form.on("CFDI Recibido", {
	refresh(frm) {
		_set_item_code_query(frm);
		if (!frm.is_new()) {
			if (frm.doc.status === "Convertido a PI") {
				frm.disable_form();
				return;
			}
			_add_no_procesar_button(frm);
			if (frm.doc.status === "Falta clasificación") {
				_add_resolver_button(frm);
			}
			if (
				(frm.doc.status === "Clasificado" || frm.doc.status === "Error conversión") &&
				!frm.doc.no_procesar
			) {
				_add_generar_pi_button(frm);
			}
		}
	},
});

frappe.ui.form.on("CFDI Recibido Concepto", {
	item_code(frm, cdt, cdn) {
		_derive_item_group(frm, cdt, cdn);
	},
});

function _set_item_code_query(frm) {
	// Solo ítems de compra, no de inventario, no de venta, grupo hoja bajo "Gastos"
	frm.set_query("item_code", "conceptos", function () {
		return {
			query: "facturacion_mexico.cfdi_recibidos.queries.get_expense_items",
		};
	});
}

function _add_no_procesar_button(frm) {
	const label = frm.doc.no_procesar ? __("Reactivar CFDI") : __("Marcar No Procesar");
	frm.add_custom_button(label, () => {
		frm.set_value("no_procesar", frm.doc.no_procesar ? 0 : 1);
		frm.save();
	});
}

function _add_resolver_button(frm) {
	frm.add_custom_button(__("Resolver Items pendientes"), () => {
		const pendientes = (frm.doc.conceptos || []).filter((c) => !c.item_code);
		if (!pendientes.length) {
			frappe.msgprint({
				title: __("Sin pendientes"),
				message: __("Todos los conceptos tienen Item asignado."),
				indicator: "green",
			});
			return;
		}
		_open_resolver_flow(frm, pendientes, 0);
	});
}

function _add_generar_pi_button(frm) {
	frm.add_custom_button(__("Generar Purchase Invoice"), () => {
		frappe.call({
			method: "facturacion_mexico.cfdi_recibidos.api.build_purchase_invoice",
			args: { cfdi_recibido: frm.doc.name },
			freeze: true,
			freeze_message: __("Generando Purchase Invoice..."),
			callback(r) {
				if (!r.message) return;
				const { status, purchase_invoice, message } = r.message;
				if (status === "error") {
					frappe.msgprint({
						title: __("Error al generar PI"),
						message: message,
						indicator: "red",
					});
					frm.reload_doc();
					return;
				}
				frappe.msgprint({
					title: __("Purchase Invoice generada"),
					message:
						`<p>${message}</p>` +
						`<p><a href="/app/purchase-invoice/${purchase_invoice}">${purchase_invoice}</a></p>`,
					indicator: "green",
				});
				frm.reload_doc();
			},
		});
	});
}

function _derive_item_group(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row.item_code) {
		frappe.model.set_value(cdt, cdn, "item_group", "");
		frappe.model.set_value(cdt, cdn, "item_resolution", "");
		return;
	}
	frappe.db.get_value("Item", row.item_code, "item_group", (r) => {
		if (r && r.item_group) {
			frappe.model.set_value(cdt, cdn, "item_group", r.item_group);
		}
		frappe.model.set_value(cdt, cdn, "item_resolution", "Manual");
	});
}

// ---------------------------------------------------------------------------
// Motor de resolución de Items — diálogo por concepto
// ---------------------------------------------------------------------------

function _open_resolver_flow(frm, pendientes, idx) {
	if (idx >= pendientes.length) {
		frm.reload_doc();
		frappe.show_alert({
			message: __("Resolución completada"),
			indicator: "green",
		});
		return;
	}

	const concepto = pendientes[idx];
	const total = pendientes.length;

	frappe.call({
		method: "facturacion_mexico.cfdi_recibidos.api.get_item_resolution_options",
		args: { cfdi_recibido: frm.doc.name, concepto_name: concepto.name },
		freeze: true,
		freeze_message: __("Cargando opciones..."),
		callback(r) {
			if (!r.message) {
				_open_resolver_flow(frm, pendientes, idx + 1);
				return;
			}
			_show_resolver_dialog(frm, concepto, r.message, idx, total, () =>
				_open_resolver_flow(frm, pendientes, idx + 1)
			);
		},
	});
}

function _show_resolver_dialog(frm, concepto, opts, idx, total, on_next) {
	const { primary, alternatives, generic } = opts;

	// Construir lista de todas las opciones disponibles
	const all_opts = [];
	if (primary) all_opts.push(primary);
	if (alternatives && alternatives.length) all_opts.push(...alternatives);
	if (generic) all_opts.push(generic);

	// HTML de sugerencias (chips clickeables)
	let chips_html = "";
	if (all_opts.length) {
		const badge = (opt) => {
			const color =
				opt.match_confidence === "Alta"
					? "green"
					: opt.match_confidence === "Media"
					? "orange"
					: "gray";
			const label = frappe.utils.escape_html(opt.item_name || opt.item_code);
			const tooltip = frappe.utils.escape_html(
				`${opt.item_code}${opt.match_reason ? " — " + opt.match_reason : ""} [${
					opt.item_resolution
				}]`
			);
			return (
				`<span class="indicator-pill ${color}" ` +
				`style="cursor:pointer;font-size:11px;padding:2px 8px;margin:2px" ` +
				`data-item="${opt.item_code}" ` +
				`title="${tooltip}">` +
				`${label}` +
				`</span>`
			);
		};
		chips_html = `<div style="margin-bottom:8px">${all_opts.map(badge).join("")}</div>`;
	} else {
		chips_html = `<p class="text-muted small">${__("Sin sugerencias automáticas")}</p>`;
	}

	const info_html = `
		<div style="margin-bottom:12px">
			<p style="font-weight:600;margin-bottom:4px">
				${frappe.utils.escape_html(concepto.description || "(sin descripción)")}
			</p>
			<small class="text-muted">
				SAT: ${concepto.sat_product_key || "—"}
				${concepto.no_identificacion ? " | No.Ident: " + concepto.no_identificacion : ""}
			</small>
			<div style="margin-top:10px;border-top:1px solid #eee;padding-top:8px">
				<p style="font-weight:700;font-size:1em;margin:0 0 6px 0">${__(
					"Sugerencias (clic para seleccionar)"
				)}</p>
				${chips_html}
			</div>
		</div>`;

	const dialog = new frappe.ui.Dialog({
		title: __("Concepto {0} / {1}")
			.replace("{0}", idx + 1)
			.replace("{1}", total),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "concepto_info",
				options: info_html,
			},
			{
				fieldtype: "Link",
				fieldname: "item_code",
				label: __("Item a asignar"),
				options: "Item",
				default: primary ? primary.item_code : "",
				get_query() {
					return {
						query: "facturacion_mexico.cfdi_recibidos.queries.get_expense_items",
					};
				},
			},
		],
		primary_action_label:
			idx + 1 < total ? __("Asignar y siguiente →") : __("Asignar y cerrar"),
		primary_action(values) {
			dialog.hide();
			if (!values.item_code) {
				on_next();
				return;
			}
			// Determinar resolución desde la opción elegida
			let resolution = "Manual";
			let reason = "";
			let confidence = "Alta";
			for (const opt of all_opts) {
				if (opt.item_code === values.item_code) {
					resolution = opt.item_resolution;
					reason = opt.match_reason || "";
					confidence = opt.match_confidence || "Alta";
					break;
				}
			}
			frappe.call({
				method: "facturacion_mexico.cfdi_recibidos.api.assign_item_to_concepto",
				args: {
					concepto_name: concepto.name,
					item_code: values.item_code,
					item_resolution: resolution,
					match_reason: reason,
					match_confidence: confidence,
				},
				freeze: true,
				freeze_message: __("Asignando..."),
				callback() {
					on_next();
				},
			});
		},
		secondary_action_label: __("Omitir"),
		secondary_action() {
			dialog.hide();
			on_next();
		},
	});

	dialog.show();

	// Conectar chips con el campo Link
	dialog.$wrapper.find("[data-item]").on("click", function () {
		dialog.set_value("item_code", $(this).data("item"));
	});

	// Botón "Crear Item específico" en el footer
	const $footer = dialog.$wrapper.find(".modal-footer");
	$("<button>")
		.addClass("btn btn-default btn-sm")
		.css("margin-right", "8px")
		.text(__("+ Crear Item específico"))
		.on("click", () => {
			dialog.hide();
			_show_create_item_dialog(frm, concepto, "Nuevo especifico", on_next);
		})
		.prependTo($footer);
}

function _show_create_item_dialog(frm, concepto, resolution_type, on_done) {
	const dialog = new frappe.ui.Dialog({
		title: __("Crear Item — {0}").replace("{0}", resolution_type),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "item_group",
				label: __("Grupo de Gasto"),
				options: "Item Group",
				reqd: 1,
				default: concepto.item_group || "",
				get_query() {
					return { filters: { is_group: 0 } };
				},
			},
			{
				fieldtype: "Data",
				fieldname: "item_code",
				label: __("Código del Item"),
				reqd: 1,
				description: __(
					"Se genera automáticamente al seleccionar el grupo — puedes modificarlo"
				),
			},
			{
				fieldtype: "Data",
				fieldname: "item_name",
				label: __("Nombre del Item"),
				reqd: 1,
				default: concepto.description || "",
			},
		],
		primary_action_label: __("Crear y asignar"),
		primary_action(values) {
			dialog.hide();
			const method =
				resolution_type === "Nuevo agrupador"
					? "facturacion_mexico.cfdi_recibidos.api.create_grouping_item_from_concepto"
					: "facturacion_mexico.cfdi_recibidos.api.create_specific_item_from_concepto";
			frappe.call({
				method,
				args: {
					cfdi_recibido: frm.doc.name,
					concepto_name: concepto.name,
					item_code: values.item_code,
					item_name: values.item_name,
					item_group_name: values.item_group,
				},
				freeze: true,
				freeze_message: __("Creando item..."),
				callback(r) {
					if (r.message && r.message.status === "ok") {
						frappe.show_alert({
							message: __("Item {0} creado y asignado").replace(
								"{0}",
								r.message.item_code
							),
							indicator: "green",
						});
					}
					on_done();
				},
			});
		},
	});

	// Auto-generar código cuando se selecciona el grupo
	dialog.fields_dict.item_group.df.onchange = () => {
		const group = dialog.get_value("item_group");
		if (!group) return;
		frappe.call({
			method: "facturacion_mexico.cfdi_recibidos.api.get_next_item_code_for_group",
			args: { item_group: group },
			callback(r) {
				if (r.message) {
					dialog.set_value("item_code", r.message);
				}
			},
		});
	};

	dialog.show();

	// Auto-generar código si ya hay grupo predeterminado
	if (concepto.item_group) {
		frappe.call({
			method: "facturacion_mexico.cfdi_recibidos.api.get_next_item_code_for_group",
			args: { item_group: concepto.item_group },
			callback(r) {
				if (r.message) {
					dialog.set_value("item_code", r.message);
				}
			},
		});
	}
}
