frappe.ui.form.on("Configuracion Reclasificacion Fiscal Mexico", {
	refresh(frm) {
		_setup_account_filters(frm);

		if (!frm.is_new()) {
			frm.add_custom_button(__("1. Cargar Reglas"), () => _cargar_reglas(frm)).addClass(
				"btn-default"
			);
			frm.add_custom_button(__("2. Generar Mapeos"), () => _aplicar(frm)).addClass(
				"btn-primary"
			);
		}

		_render_resumen(frm);
	},

	company(frm) {
		_setup_account_filters(frm);
	},
});

// ── Cargar Reglas ──────────────────────────────────────────────────────────

function _cargar_reglas(frm) {
	if (frm.is_dirty()) {
		frappe.confirm(__("Hay cambios sin guardar. ¿Guardar antes de cargar?"), () =>
			frm.save().then(() => _llamar_cargar(frm))
		);
		return;
	}
	_llamar_cargar(frm);
}

function _llamar_cargar(frm) {
	frappe.call({
		method: "cargar_reglas",
		doc: frm.doc,
		freeze: true,
		freeze_message: __("Cargando reglas..."),
		callback(r) {
			if (r.message) {
				frappe.show_alert({ message: r.message.message, indicator: "blue" }, 5);
				frm.reload_doc();
			}
		},
	});
}

// ── Aplicar ────────────────────────────────────────────────────────────────

function _aplicar(frm) {
	const reglas = frm.doc.reglas || [];
	if (!reglas.length) {
		frappe.msgprint(__("No hay reglas. Usa primero '1. Cargar Reglas'."));
		return;
	}

	const sinCuenta = reglas.filter((r) => !r.cuenta_destino);
	if (sinCuenta.length) {
		const lista = sinCuenta.map((r) => `<li>${r.cuenta_origen || r.rol_fiscal}</li>`).join("");
		frappe.msgprint({
			title: __("Faltan cuentas destino"),
			message: __(
				"Las siguientes cuentas no tienen Cuenta Destino asignada:<ul>{0}</ul>Asigna una cuenta a cada fila antes de continuar.",
				[lista]
			),
			indicator: "red",
		});
		return;
	}

	frappe.confirm(__("¿Generar {0} mapeo(s)?", [reglas.length]), () => {
		if (frm.is_dirty()) {
			frm.save().then(() => _llamar_aplicar(frm));
		} else {
			_llamar_aplicar(frm);
		}
	});
}

function _llamar_aplicar(frm) {
	frappe.call({
		method: "aplicar",
		doc: frm.doc,
		freeze: true,
		freeze_message: __("Aplicando mapeos..."),
		callback(r) {
			if (r.message) {
				const ok = r.message.creados > 0 || r.message.actualizados > 0;
				frappe.show_alert(
					{ message: r.message.message, indicator: ok ? "green" : "blue" },
					6
				);
				frm.reload_doc();
			}
		},
	});
}

// ── Resumen ────────────────────────────────────────────────────────────────

function _render_resumen(frm) {
	const reglas = frm.doc.reglas || [];
	if (!reglas.length) return;

	const total = reglas.length;
	const configuradas = reglas.filter((r) => r.mrfpe_ref).length;
	const pct = Math.round((configuradas / total) * 100);
	const color = pct === 100 ? "green" : pct >= 50 ? "orange" : "red";

	frm.dashboard.set_headline_alert(
		__("{0}/{1} cuentas con mapeo activo ({2}%)", [configuradas, total, pct]),
		color
	);
}

// ── Filtros de cuenta ──────────────────────────────────────────────────────

function _setup_account_filters(frm) {
	const base = { account_type: "Tax", is_group: 0, disabled: 0 };
	const filters = frm.doc.company ? { ...base, company: frm.doc.company } : base;
	frm.set_query("cuenta_destino", "reglas", () => ({ filters }));
}
