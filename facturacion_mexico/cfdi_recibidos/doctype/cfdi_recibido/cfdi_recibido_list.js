frappe.listview_settings["CFDI Recibido"] = {
	onload(listview) {
		listview.page.add_button(__("Cargar XML"), () => {
			_select_company_then_upload(listview);
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
