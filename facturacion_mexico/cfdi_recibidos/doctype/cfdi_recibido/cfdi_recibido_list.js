frappe.listview_settings["CFDI Recibido"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Cargar XML"), () => {
			_select_company_then_upload(listview);
		});

		const g = __("Flujo Manual");
		listview.page.add_inner_button(
			__("Generar proveedores faltantes"),
			() => {
				_generate_missing_suppliers(listview);
			},
			g
		);
		listview.page.add_inner_button(
			__("Asignar Departamentos"),
			() => {
				_assign_departments_flow(listview);
			},
			g
		);
		listview.page.add_inner_button(
			__("Clasificar automáticamente"),
			() => {
				_classify_all_flow(listview);
			},
			g
		);
		listview.page.add_inner_button(
			__("Generar PIs pendientes"),
			() => {
				_batch_generate_pis(listview);
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
				_show_results(data.message || [], listview, company);
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

function _show_results(results, listview, company) {
	if (!results.length) {
		frappe.msgprint(__("No se procesó ningún archivo."));
		return;
	}

	const _icon = (r) => {
		if (r.supplier_created) return "🆕";
		if (r.status === "Proveedor encontrado") return "✅";
		if (r.status === "Falta departamento") return "📋";
		if (r.status === "Falta proveedor") return "⚠️";
		if (r.status === "duplicado") return "🔵";
		if (r.status === "No aplicable") return "⬜";
		if (r.status === "XML inválido") return "❌";
		return "⚠️";
	};

	const rows = results.map((r) => {
		const docLink = r.cfdi_recibido
			? `<a href="/app/cfdi-recibido/${r.cfdi_recibido}">${r.cfdi_recibido}</a>`
			: "—";
		const rfc = r.supplier_rfc || "—";
		const supplierCell = r.supplier
			? `<a href="/app/supplier/${encodeURIComponent(r.supplier)}" target="_blank">
				${frappe.utils.escape_html(r.supplier_name || r.supplier)}
			   </a>`
			: `<span class="text-muted">${frappe.utils.escape_html(r.supplier_rfc || "—")}</span>`;
		let hint = r.next_action ? `<i>${r.next_action}</i>` : r.message || "";
		if (r.supplier_created) {
			hint = `<span style="color:#e67e22;font-weight:600">⚠️ ${__(
				"Proveedor nuevo — da clic en su nombre para completar sus datos"
			)}</span>`;
		}
		return `<tr>
			<td>${_icon(r)}</td>
			<td>${frappe.utils.escape_html(r.file_name)}</td>
			<td>${docLink}</td>
			<td>${supplierCell}</td>
			<td>${r.status}</td>
			<td style="font-size:0.9em">${hint}</td>
		</tr>`;
	});

	const newSupplierCount = results.filter((r) => r.supplier_created).length;
	const newSupplierNote =
		newSupplierCount > 0
			? `<p style="margin-top:10px;color:#e67e22">
				⚠️ ${__(
					"{0} proveedor(es) nuevo(s) creado(s) automáticamente. Revisa y completa sus datos antes de procesar.",
					[newSupplierCount]
				)}
			   </p>`
			: "";

	const table = `
		<table style="width:100%;border-collapse:collapse;font-size:0.9em">
			<thead>
				<tr style="border-bottom:1px solid #ddd;text-align:left">
					<th></th>
					<th>${__("Archivo")}</th>
					<th>${__("CFDI")}</th>
					<th>${__("Proveedor")}</th>
					<th>${__("Estado")}</th>
					<th>${__("Detalle")}</th>
				</tr>
			</thead>
			<tbody>${rows.join("")}</tbody>
		</table>
		${newSupplierNote}`;

	const hasFaltaDepartamento = results.some((r) => r.status === "Falta departamento");
	const hasFaltaProveedor = results.some((r) => r.status === "Falta proveedor");
	const hasError = results.some((r) => r.status === "XML inválido");
	const hasOk = results.some(
		(r) => r.status === "Proveedor encontrado" || r.status === "Falta departamento"
	);
	const hasNewSupplier = newSupplierCount > 0;
	const indicator =
		hasError && !hasOk ? "red" : hasFaltaProveedor || hasNewSupplier ? "orange" : "green";

	const primaryLabel =
		hasFaltaDepartamento && company ? __("Continuar → Asignar departamento") : __("Cerrar");

	const d = new frappe.ui.Dialog({
		title: __("Resultado de carga — {0} archivo(s)", [results.length]),
		fields: [{ fieldtype: "HTML", fieldname: "content" }],
		primary_action_label: primaryLabel,
		primary_action() {
			d.hide();
			if (hasFaltaDepartamento && company) {
				_load_department_candidates(company, listview);
			}
		},
		secondary_action_label: hasFaltaDepartamento ? __("Detener aquí") : null,
		secondary_action() {
			d.hide();
		},
	});

	d.show();
	d.fields_dict.content.$wrapper.html(table);

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
				.map(
					(e) =>
						`<li><b>${frappe.utils.escape_html(
							e.name
						)}</b>: ${frappe.utils.escape_html(e.message)}</li>`
				)
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
				["disabled", "=", 0],
			],
			fields: ["name"],
			limit: 500,
			order_by: "name asc",
		},
		callback(r) {
			const departments = r.message || [];
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Cost Center",
					filters: [
						["company", "=", company],
						["is_group", "=", 0],
						["disabled", "=", 0],
					],
					fields: ["name"],
					limit: 500,
					order_by: "name asc",
				},
				callback(r2) {
					const cost_centers = r2.message || [];
					// Cargar Proyectos filtrados por empresa
					frappe.call({
						method: "frappe.client.get_list",
						args: {
							doctype: "Project",
							filters: [
								["company", "=", company],
								["status", "=", "Open"],
							],
							fields: ["name"],
							limit: 500,
							order_by: "name asc",
						},
						callback(r3) {
							let projects = r3.message || [];
							if (!projects.length) {
								// Fallback sin filtro company si no hay resultados
								frappe.call({
									method: "frappe.client.get_list",
									args: {
										doctype: "Project",
										filters: [["status", "=", "Open"]],
										fields: ["name"],
										limit: 500,
										order_by: "name asc",
									},
									callback(r4) {
										_show_department_dialog(
											candidates,
											departments,
											cost_centers,
											r4.message || [],
											listview
										);
									},
								});
							} else {
								_show_department_dialog(
									candidates,
									departments,
									cost_centers,
									projects,
									listview
								);
							}
						},
					});
				},
			});
		},
	});
}

function _show_department_dialog(candidates, departments, cost_centers, projects, listview) {
	const dept_options = departments
		.map(
			(d) =>
				`<option value="${frappe.utils.escape_html(d.name)}">${frappe.utils.escape_html(
					d.name
				)}</option>`
		)
		.join("");

	const cc_options = cost_centers
		.map(
			(cc) =>
				`<option value="${frappe.utils.escape_html(cc.name)}">${frappe.utils.escape_html(
					cc.name
				)}</option>`
		)
		.join("");

	const proj_options = projects
		.map(
			(p) =>
				`<option value="${frappe.utils.escape_html(p.name)}">${frappe.utils.escape_html(
					p.name
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
				<td style="padding:4px 8px;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
				    title="${frappe.utils.escape_html(c.supplier_name || c.supplier || "")}">
					${frappe.utils.escape_html(c.supplier_name || c.supplier || "—")}
				</td>
				<td style="padding:4px 8px;white-space:nowrap">${c.issue_date || "—"}</td>
				<td style="padding:4px 8px;text-align:right;white-space:nowrap">${total_fmt}</td>
				<td style="padding:4px 8px;min-width:160px">
					<select data-cfdi="${frappe.utils.escape_html(c.name)}" data-field="department"
					        style="width:100%;border:1px solid #d1d8dd;border-radius:4px;padding:3px 6px;font-size:0.9em">
						<option value="">${__("— Sin asignar —")}</option>
						${dept_options}
					</select>
				</td>
				<td style="padding:4px 8px;min-width:160px">
					<select data-cfdi="${frappe.utils.escape_html(c.name)}" data-field="cost_center"
					        style="width:100%;border:1px solid #d1d8dd;border-radius:4px;padding:3px 6px;font-size:0.9em">
						<option value="">${__("— Opcional —")}</option>
						${cc_options}
					</select>
				</td>
				<td style="padding:4px 8px;min-width:160px">
					<select data-cfdi="${frappe.utils.escape_html(c.name)}" data-field="project"
					        style="width:100%;border:1px solid #d1d8dd;border-radius:4px;padding:3px 6px;font-size:0.9em">
						<option value="">${__("— Opcional —")}</option>
						${proj_options}
					</select>
				</td>
			</tr>`;
		})
		.join("");

	const d = new frappe.ui.Dialog({
		title: __("Asignar Departamento, Centro de Costo y Proyecto — {0} candidato(s)", [
			candidates.length,
		]),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "table_html",
			},
		],
		primary_action_label: __("Guardar asignaciones"),
		primary_action() {
			const assignments = {};
			const rows_wrapper = d.$wrapper;

			// Collect per-cfdi values
			const cfdi_names = [
				...new Set([...rows_wrapper.find("[data-cfdi]")].map((el) => el.dataset.cfdi)),
			];

			cfdi_names.forEach((cfdi_name) => {
				const dept = rows_wrapper
					.find(`select[data-cfdi="${CSS.escape(cfdi_name)}"][data-field="department"]`)
					.val();
				if (!dept) return; // skip if no department selected
				const cc = rows_wrapper
					.find(`select[data-cfdi="${CSS.escape(cfdi_name)}"][data-field="cost_center"]`)
					.val();
				const project = rows_wrapper
					.find(`select[data-cfdi="${CSS.escape(cfdi_name)}"][data-field="project"]`)
					.val();
				assignments[cfdi_name] = {
					department: dept,
					cost_center: cc || "",
					project: project || "",
				};
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
						<th style="padding:6px 8px">${__("Centro de Costo")}</th>
						<th style="padding:6px 8px">${__("Proyecto")}</th>
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
				const assignedNames = Object.keys(assignments);
				_show_assign_departments_summary(r.message, assignedNames, listview);
				listview.refresh();
			}
		},
	});
}

function _show_assign_departments_summary(result, assignedNames, listview) {
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

	const hasAssigned = asignados > 0 && assignedNames && assignedNames.length > 0;
	const multipleAssigned = asignados > 1;

	const d = new frappe.ui.Dialog({
		title: __("Resultado — Asignar Departamentos"),
		fields: [{ fieldtype: "HTML", fieldname: "content" }],
		primary_action_label: hasAssigned ? __("Continuar → Clasificar Items") : __("Cerrar"),
		primary_action() {
			d.hide();
			if (hasAssigned) {
				if (multipleAssigned) {
					// Múltiples CFDIs: ir a la lista filtrada por estado
					frappe.set_route("List", "CFDI Recibido", { status: "Falta clasificación" });
				} else {
					// Un solo CFDI: abrir el formulario directamente
					frappe.set_route("Form", "CFDI Recibido", assignedNames[0]);
				}
			}
		},
		secondary_action_label: hasAssigned ? __("Detener aquí") : null,
		secondary_action() {
			d.hide();
		},
	});
	d.show();
	d.fields_dict.content.$wrapper.html(`
		<p>${__("Asignados")}: <strong>${asignados}</strong></p>
		<p>${__("Omitidos")}: <strong>${omitidos}</strong></p>
		<p>${__("Errores")}: <strong>${errCount}</strong></p>
		${errDetail}
	`);
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

// ─── Batch Generar PIs pendientes ────────────────────────────────────────────

function _batch_generate_pis(listview) {
	frappe.call({
		method: "frappe.client.get_count",
		args: {
			doctype: "CFDI Recibido",
			filters: { status: ["in", ["Clasificado", "Error conversión"]], no_procesar: 0 },
		},
		callback(r) {
			const count = r.message || 0;
			if (!count) {
				frappe.msgprint({
					title: __("Sin CFDI elegibles"),
					message: __(
						"No hay CFDI en estado 'Clasificado' o 'Error conversión' pendientes de procesar."
					),
					indicator: "blue",
				});
				return;
			}
			frappe.confirm(
				__(
					"Se intentará generar PI para {0} CFDI en estado Clasificado o Error conversión que no estén marcados como No Procesar. ¿Continuar?",
					[count]
				),
				() => _do_batch_generate_pis(listview)
			);
		},
	});
}

function _do_batch_generate_pis(listview) {
	frappe.call({
		method: "facturacion_mexico.cfdi_recibidos.api.build_purchase_invoices_pending_batch",
		freeze: true,
		freeze_message: __("Generando Purchase Invoices..."),
		callback(r) {
			if (r.message) {
				_show_batch_pi_results(r.message, listview);
			}
		},
	});
}

function _show_batch_pi_results(result, listview) {
	const { total, ok, error, skipped, results } = result;

	if (total === 0) {
		frappe.msgprint({
			title: __("Sin resultados"),
			message: __("No se encontraron CFDI elegibles para procesar."),
			indicator: "blue",
		});
		return;
	}

	const rows = results
		.map((r) => {
			const cfdiLink = `<a href="/app/cfdi-recibido/${encodeURIComponent(
				r.cfdi_recibido
			)}" target="_blank" style="font-size:0.85em">${frappe.utils.escape_html(
				r.cfdi_recibido
			)}</a>`;
			const piLink = r.purchase_invoice
				? `<a href="/app/purchase-invoice/${encodeURIComponent(
						r.purchase_invoice
				  )}" target="_blank">${frappe.utils.escape_html(r.purchase_invoice)}</a>`
				: "—";
			const statusCell =
				r.status === "ok"
					? `<span style="color:green;font-weight:600">✔ ok</span>`
					: `<span style="color:red;font-weight:600">✖ error</span>`;
			const msg = frappe.utils.escape_html(r.message || "");
			return `<tr style="border-bottom:1px solid #f0f0f0">
				<td style="padding:4px 8px;white-space:nowrap">${cfdiLink}</td>
				<td style="padding:4px 8px;white-space:nowrap">${statusCell}</td>
				<td style="padding:4px 8px;white-space:nowrap">${piLink}</td>
				<td style="padding:4px 8px;font-size:0.85em;max-width:260px;word-break:break-word">${msg}</td>
			</tr>`;
		})
		.join("");

	const indicator = error > 0 && ok === 0 ? "red" : error > 0 ? "orange" : "green";

	const d = new frappe.ui.Dialog({
		title: __("Resultado — Generar PIs pendientes"),
		fields: [{ fieldtype: "HTML", fieldname: "content" }],
		primary_action_label: __("Cerrar"),
		primary_action() {
			d.hide();
		},
	});

	d.show();
	d.fields_dict.content.$wrapper.html(`
		<div style="margin-bottom:12px;padding:8px;background:#f8f9fa;border-radius:4px;display:flex;gap:16px;flex-wrap:wrap">
			<span>${__("Total encontrados")}: <strong>${total}</strong></span>
			<span style="color:green">${__("Exitosos")}: <strong>${ok}</strong></span>
			<span style="color:red">${__("Errores")}: <strong>${error}</strong></span>
			<span style="color:#888">${__("Omitidos")}: <strong>${skipped}</strong></span>
		</div>
		<div style="max-height:420px;overflow-y:auto">
			<table style="width:100%;border-collapse:collapse;font-size:0.9em">
				<thead>
					<tr style="border-bottom:2px solid #ddd;text-align:left;background:#fff;position:sticky;top:0">
						<th style="padding:6px 8px">${__("CFDI")}</th>
						<th style="padding:6px 8px">${__("Resultado")}</th>
						<th style="padding:6px 8px">${__("Purchase Invoice")}</th>
						<th style="padding:6px 8px">${__("Mensaje")}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		</div>
	`);

	listview.refresh();
}
