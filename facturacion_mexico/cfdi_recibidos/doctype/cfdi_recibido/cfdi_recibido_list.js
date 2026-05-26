frappe.listview_settings["CFDI Recibido"] = {
	onload(listview) {
		listview.page.add_button(__("Cargar XML"), () => {
			_select_company_then_upload(listview);
		});
		listview.page.add_button(__("Generar proveedores faltantes"), () => {
			_generate_missing_suppliers(listview);
		});
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
