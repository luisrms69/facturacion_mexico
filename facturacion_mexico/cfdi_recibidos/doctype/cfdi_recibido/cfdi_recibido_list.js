frappe.listview_settings["CFDI Recibido"] = {
	onload(listview) {
		const g = __("Flujo CFDI");
		listview.page.add_inner_button(
			__("1. Cargar XML"),
			() => {
				_select_company_then_upload(listview);
			},
			g
		);
		listview.page.add_inner_button(
			__("2. Generar proveedores faltantes"),
			() => {
				_generate_missing_suppliers(listview);
			},
			g
		);
		listview.page.add_inner_button(
			__("3. Asignar Departamentos"),
			() => {
				_assign_departments_flow(listview);
			},
			g
		);
		listview.page.add_inner_button(
			__("4. Clasificar automáticamente"),
			() => {
				_classify_all_flow(listview);
			},
			g
		);
	},
};

function _select_company_then_upload(listview) {
	const dialog = new frappe.ui.Dialog({
		title: __("Cargar XMLs CFDI"),
		fields: [
			{
				fieldname: "company",
				fieldtype: "Link",
				label: __("Empresa"),
				options: "Company",
				reqd: 1,
				default: frappe.defaults.get_default("company"),
			},
		],
		primary_action_label: __("Seleccionar archivos..."),
		primary_action(values) {
			if (!values.company) return;
			dialog.hide();
			_open_file_picker(values.company, listview);
		},
	});

	dialog.show();
}

function _open_file_picker(company, listview) {
	const input = document.createElement("input");
	input.type = "file";
	input.accept = ".xml";
	input.multiple = true;

	input.onchange = () => {
		const files = Array.from(input.files);
		if (!files.length) return;

		const formData = new FormData();
		formData.append("company", company);
		files.forEach((f) => formData.append("files", f));

		fetch(`/api/method/facturacion_mexico.cfdi_recibidos.api.upload_xml`, {
			method: "POST",
			headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
			body: formData,
		})
			.then((r) => r.json())
			.then((data) => {
				_show_results(data.message || [], listview);
			})
			.catch((err) => {
				frappe.msgprint({
					title: __("Error al cargar"),
					message: String(err),
					indicator: "red",
				});
			});
	};

	input.click();
}

function _show_results(results, listview) {
	if (!results.length) {
		frappe.msgprint(__("No se procesó ningún archivo."));
		return;
	}

	const _icon = (status) => {
		if (status === "Proveedor encontrado") return "✅";
		if (status === "Falta proveedor") return "⚠️";
		if (status === "duplicado") return "🔵";
		if (status === "No aplicable") return "⬜";
		if (status === "XML inválido") return "❌";
		return "⚠️";
	};

	const rows = results.map((r) => {
		const docLink = r.cfdi_recibido
			? `<a href="/app/cfdi-recibido/${r.cfdi_recibido}">${r.cfdi_recibido}</a>`
			: "—";
		const rfc = r.supplier_rfc || "—";
		const candidato = r.candidato_generar_proveedor ? "✔" : "";
		const hint = r.next_action ? `<i>${r.next_action}</i>` : r.message || "";
		return `<tr>
			<td>${_icon(r.status)}</td>
			<td>${r.file_name}</td>
			<td>${docLink}</td>
			<td>${rfc}</td>
			<td>${r.status}</td>
			<td>${candidato}</td>
			<td style="color:#888;font-size:0.9em">${hint}</td>
		</tr>`;
	});

	const table = `
		<table style="width:100%;border-collapse:collapse;font-size:0.9em">
			<thead>
				<tr style="border-bottom:1px solid #ddd;text-align:left">
					<th></th>
					<th>${__("Archivo")}</th>
					<th>${__("CFDI")}</th>
					<th>${__("RFC Proveedor")}</th>
					<th>${__("Estado")}</th>
					<th title="${__("Candidato para generar proveedor")}">👤?</th>
					<th>${__("Detalle")}</th>
				</tr>
			</thead>
			<tbody>${rows.join("")}</tbody>
		</table>`;

	const hasFaltaProveedor = results.some((r) => r.status === "Falta proveedor");
	const hasError = results.some((r) => r.status === "XML inválido");
	const hasOk = results.some((r) => r.status === "Proveedor encontrado");
	const indicator = hasError && !hasOk ? "red" : hasFaltaProveedor ? "orange" : "green";

	frappe.msgprint({
		title: __("Resultado de carga — {0} archivo(s)", [results.length]),
		message: table,
		indicator,
	});

	const created = results.filter((r) => r.cfdi_recibido);
	if (created.length) listview.refresh();
}

function _generate_missing_suppliers(listview) {
	const selected = listview.get_checked_items().map((r) => r.name);

	if (selected.length) {
		frappe.confirm(
			__("Se generarán proveedores para {0} CFDI seleccionados. ¿Continuar?", [
				selected.length,
			]),
			() => _do_generate(selected, listview)
		);
	} else {
		frappe.call({
			method: "frappe.client.get_count",
			args: {
				doctype: "CFDI Recibido",
				filters: { status: "Falta proveedor", no_procesar: 0 },
			},
			callback(r) {
				const count = r.message || 0;
				if (!count) {
					frappe.msgprint(__("No hay CFDI con estado 'Falta proveedor'."));
					return;
				}
				frappe.confirm(
					__(
						"Se generarán proveedores para {0} CFDI con 'Falta proveedor'. ¿Continuar?",
						[count]
					),
					() => _do_generate(null, listview)
				);
			},
		});
	}
}

function _do_generate(cfdi_names, listview) {
	frappe.call({
		method: "facturacion_mexico.cfdi_recibidos.api.generate_missing_suppliers",
		args: { cfdi_names: cfdi_names ? JSON.stringify(cfdi_names) : null },
		freeze: true,
		freeze_message: __("Generando proveedores..."),
		callback(r) {
			if (r.message) {
				_show_generate_summary(r.message);
				listview.refresh();
			}
		},
	});
}

function _show_generate_summary(result) {
	const { creados, ya_existian_y_asignados, omitidos, errores } = result;
	const errCount = errores ? errores.length : 0;
	const indicator = errCount > 0 ? "orange" : "green";
	const errDetail = errCount
		? `<details style="margin-top:8px"><summary style="cursor:pointer">${__(
				"Ver errores ({0})",
				[errCount]
		  )}</summary>
			<ul style="margin-top:4px">${errores
				.map((e) => `<li><b>${e.name}</b>: ${e.message}</li>`)
				.join("")}</ul>
		   </details>`
		: "";

	const actionable = creados + ya_existian_y_asignados;
	const reviewNote =
		actionable > 0
			? `<p style="margin-top:10px;padding:8px;background:#fff8e1;border-left:3px solid #f9a825;font-size:0.9em;color:#555">${__(
					"Proveedores creados/asignados correctamente. Revise y complete los datos fiscales, grupo de proveedor, cuenta por pagar y condiciones de pago cuando sea necesario."
			  )}</p>`
			: "";

	frappe.msgprint({
		title: __("Resultado — Generar proveedores"),
		message: `
			<p>${__("Proveedores creados")}: <strong>${creados}</strong></p>
			<p>${__("Existentes asignados")}: <strong>${ya_existian_y_asignados}</strong></p>
			<p>${__("Omitidos")}: <strong>${omitidos}</strong></p>
			<p>${__("Errores")}: <strong>${errCount}</strong></p>
			${reviewNote}
			${errDetail}
		`,
		indicator,
	});
}

// ─── Department assignment flow ──────────────────────────────────────────────

function _assign_departments_flow(listview) {
	const companyDialog = new frappe.ui.Dialog({
		title: __("Asignar Departamentos"),
		fields: [
			{
				fieldname: "company",
				fieldtype: "Link",
				options: "Company",
				label: __("Empresa"),
				reqd: 1,
				default: frappe.defaults.get_default("company"),
			},
		],
		primary_action_label: __("Cargar candidatos"),
		primary_action(values) {
			if (!values.company) return;
			companyDialog.hide();
			_load_department_candidates(values.company, listview);
		},
	});
	companyDialog.show();
}

function _load_department_candidates(company, listview) {
	frappe.call({
		method: "facturacion_mexico.cfdi_recibidos.api.get_department_candidates",
		args: { company },
		callback(r) {
			const candidates = r.message || [];
			if (!candidates.length) {
				frappe.msgprint({
					title: __("Sin candidatos"),
					message: __(
						"No hay CFDIs con proveedor asignado y sin departamento para la empresa seleccionada."
					),
					indicator: "blue",
				});
				return;
			}
			_load_departments_then_show(candidates, company, listview);
		},
	});
}

function _load_departments_then_show(candidates, company, listview) {
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Department",
			filters: [
				["company", "=", company],
				["is_group", "=", 0],
				["disabled", "=", 0],
			],
			fields: ["name"],
			limit: 500,
			order_by: "name asc",
		},
		callback(r) {
			const departments = r.message || [];
			_show_department_dialog(candidates, departments, listview);
		},
	});
}

function _show_department_dialog(candidates, departments, listview) {
	const dept_options = departments
		.map(
			(d) =>
				`<option value="${frappe.utils.escape_html(d.name)}">${frappe.utils.escape_html(
					d.name
				)}</option>`
		)
		.join("");

	const rows = candidates
		.map((c) => {
			const safe_id = c.name.replace(/[^a-zA-Z0-9]/g, "_");
			const total_fmt = frappe.format(c.total || 0, { fieldtype: "Currency" });
			return `<tr style="border-bottom:1px solid #f0f0f0">
				<td style="padding:4px 8px;white-space:nowrap">
					<a href="/app/cfdi-recibido/${encodeURIComponent(c.name)}" target="_blank"
					   style="font-size:0.85em">${frappe.utils.escape_html(c.name)}</a>
				</td>
				<td style="padding:4px 8px;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
				    title="${frappe.utils.escape_html(c.supplier_name || c.supplier || "")}">
					${frappe.utils.escape_html(c.supplier_name || c.supplier || "—")}
				</td>
				<td style="padding:4px 8px;white-space:nowrap">${c.issue_date || "—"}</td>
				<td style="padding:4px 8px;text-align:right;white-space:nowrap">${total_fmt}</td>
				<td style="padding:4px 8px;min-width:180px">
					<select id="dept_${safe_id}"
					        data-cfdi="${frappe.utils.escape_html(c.name)}"
					        style="width:100%;border:1px solid #d1d8dd;border-radius:4px;padding:3px 6px;font-size:0.9em">
						<option value="">${__("— Sin asignar —")}</option>
						${dept_options}
					</select>
				</td>
			</tr>`;
		})
		.join("");

	const d = new frappe.ui.Dialog({
		title: __("Asignar Departamentos — {0} candidato(s)", [candidates.length]),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "table_html",
			},
		],
		primary_action_label: __("Guardar asignaciones"),
		primary_action() {
			const assignments = {};
			d.$wrapper.find("select[data-cfdi]").each(function () {
				const cfdi_name = $(this).data("cfdi");
				const dept = $(this).val();
				if (dept) assignments[cfdi_name] = dept;
			});

			if (!Object.keys(assignments).length) {
				frappe.msgprint(__("Seleccione al menos un departamento para continuar."));
				return;
			}

			d.hide();
			_do_assign_departments(assignments, listview);
		},
	});

	d.show();

	d.fields_dict.table_html.$wrapper.html(`
		<div style="max-height:420px;overflow-y:auto;margin:-4px">
			<table style="width:100%;border-collapse:collapse;font-size:0.9em">
				<thead style="position:sticky;top:0;background:#fff;z-index:1">
					<tr style="border-bottom:2px solid #ddd;text-align:left">
						<th style="padding:6px 8px">${__("CFDI")}</th>
						<th style="padding:6px 8px">${__("Proveedor")}</th>
						<th style="padding:6px 8px">${__("Fecha")}</th>
						<th style="padding:6px 8px">${__("Total")}</th>
						<th style="padding:6px 8px">${__("Departamento")}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		</div>
	`);
}

function _do_assign_departments(assignments, listview) {
	frappe.call({
		method: "facturacion_mexico.cfdi_recibidos.api.assign_departments",
		args: { assignments: JSON.stringify(assignments) },
		freeze: true,
		freeze_message: __("Asignando departamentos..."),
		callback(r) {
			if (r.message) {
				_show_assign_departments_summary(r.message);
				listview.refresh();
			}
		},
	});
}

function _show_assign_departments_summary(result) {
	const { asignados, omitidos, errores } = result;
	const errCount = errores ? errores.length : 0;
	const indicator = errCount > 0 ? "orange" : "green";
	const errDetail = errCount
		? `<details style="margin-top:8px"><summary style="cursor:pointer">${__(
				"Ver errores ({0})",
				[errCount]
		  )}</summary>
			<ul style="margin-top:4px">${errores
				.map(
					(e) =>
						`<li><b>${frappe.utils.escape_html(
							e.name
						)}</b>: ${frappe.utils.escape_html(e.message)}</li>`
				)
				.join("")}</ul>
		   </details>`
		: "";

	frappe.msgprint({
		title: __("Resultado — Asignar Departamentos"),
		message: `
			<p>${__("Asignados")}: <strong>${asignados}</strong></p>
			<p>${__("Omitidos")}: <strong>${omitidos}</strong></p>
			<p>${__("Errores")}: <strong>${errCount}</strong></p>
			${errDetail}
		`,
		indicator,
	});
}

// ─── Clasificar automáticamente ──────────────────────────────────────────────

function _classify_all_flow(listview) {
	const selected = listview.get_checked_items().map((r) => r.name);

	if (selected.length) {
		frappe.confirm(
			__("Se clasificarán conceptos de {0} CFDI seleccionados. ¿Continuar?", [
				selected.length,
			]),
			() => _do_classify_batch(selected, listview)
		);
	} else {
		frappe.call({
			method: "frappe.client.get_count",
			args: {
				doctype: "CFDI Recibido",
				filters: { status: "Falta clasificación", no_procesar: 0 },
			},
			callback(r) {
				const count = r.message || 0;
				if (!count) {
					frappe.msgprint(__("No hay CFDI con estado 'Falta clasificación'."));
					return;
				}
				frappe.confirm(
					__(
						"Se clasificarán conceptos de {0} CFDI en estado 'Falta clasificación'. ¿Continuar?",
						[count]
					),
					() => {
						frappe.call({
							method: "frappe.client.get_list",
							args: {
								doctype: "CFDI Recibido",
								filters: { status: "Falta clasificación", no_procesar: 0 },
								fields: ["name"],
								limit: 500,
							},
							callback(r2) {
								const names = (r2.message || []).map((x) => x.name);
								if (names.length) _do_classify_batch(names, listview);
							},
						});
					}
				);
			},
		});
	}
}

function _do_classify_batch(cfdi_names, listview) {
	const totals = { actualizados: 0, sin_match: 0 };
	const errores = [];
	let pending = cfdi_names.length;

	if (!pending) return;

	frappe.show_progress(__("Clasificando..."), 0, pending);

	cfdi_names.forEach((name) => {
		frappe.call({
			method: "facturacion_mexico.cfdi_recibidos.api.classify_all_concepts",
			args: { cfdi_recibido: name },
			callback(r) {
				if (r.message) {
					totals.actualizados += r.message.actualizados || 0;
					totals.sin_match += r.message.sin_match || 0;
				}
				pending--;
				frappe.show_progress(
					__("Clasificando..."),
					cfdi_names.length - pending,
					cfdi_names.length
				);
				if (pending === 0) {
					frappe.hide_progress();
					_show_classify_summary(totals, errores);
					listview.refresh();
				}
			},
			error(err) {
				errores.push({ name, message: (err && err.message) || "Error" });
				pending--;
				if (pending === 0) {
					frappe.hide_progress();
					_show_classify_summary(totals, errores);
					listview.refresh();
				}
			},
		});
	});
}

function _show_classify_summary(totals, errores) {
	const errCount = errores.length;
	const indicator = errCount > 0 ? "orange" : "green";
	const errDetail = errCount
		? `<details style="margin-top:8px"><summary style="cursor:pointer">${__(
				"Ver errores ({0})",
				[errCount]
		  )}</summary>
			<ul style="margin-top:4px">${errores
				.map(
					(e) =>
						`<li><b>${frappe.utils.escape_html(
							e.name
						)}</b>: ${frappe.utils.escape_html(e.message)}</li>`
				)
				.join("")}</ul>
		   </details>`
		: "";

	frappe.msgprint({
		title: __("Resultado — Clasificar automáticamente"),
		message: `
			<p>${__("Conceptos clasificados")}: <strong>${totals.actualizados}</strong></p>
			<p>${__("Sin coincidencia")}: <strong>${totals.sin_match}</strong></p>
			<p>${__("Errores")}: <strong>${errCount}</strong></p>
			${errDetail}
		`,
		indicator,
	});
}
