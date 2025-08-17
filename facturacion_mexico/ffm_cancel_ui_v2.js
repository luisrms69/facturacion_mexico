// ffm_cancel_ui_v2.js
/* global FM_ENUMS */
(function () {
	const S = (window.FM_ENUMS || {}).FiscalStates || {};
	const P = window.FiscalPolicy;

	function set_readonly(frm) {
		const st = P.normStatus(frm.doc.fm_fiscal_status || "");
		const ro = P.states.readonly_cancel.has(st);
		["cancellation_reason", "cancellation_date"].forEach((f) =>
			frm.set_df_property(f, "read_only", ro ? 1 : 0)
		);
	}

	// Limpieza SOLO de nuestro propio botón si alguna vez se agregó
	function cleanup_cancel_button(frm) {
		try {
			frm.remove_custom_button(__("Cancelar en FacturAPI"), __("Acciones Fiscales"));
		} catch (e) {
			// Silenciar error si botón no existe
		}
		$(frm.page.wrapper).find(".btn-ffm-cancelar").remove(); // nuestra clase
	}

	frappe.ui.form.on("Factura Fiscal Mexico", {
		refresh(frm) {
			set_readonly(frm);
			cleanup_cancel_button(frm); // no crear botón nuevo; solo limpiar residuo propio

			// Indicador en header, reutilizando FM_ENUMS (sin hardcode)
			const s = FM_ENUMS.norm(frm.doc.fm_fiscal_status || "");
			const color = FM_ENUMS.StatusColor[s] || "gray";
			const label = FM_ENUMS.StatusLabel[s] || s || __("Sin estado");
			if (frm.doc.fm_fiscal_status) frm.page.set_indicator(label, color);
		},
		fm_fiscal_status(frm) {
			set_readonly(frm);
			cleanup_cancel_button(frm);
		},
	});
})();
