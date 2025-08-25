// facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico_list.js
/* global FM_ENUMS */
frappe.listview_settings["Factura Fiscal Mexico"] = {
	get_indicator: function (doc) {
		return window.FM_ENUMS && FM_ENUMS.indicatorFor
			? FM_ENUMS.indicatorFor(doc.fm_fiscal_status)
			: [doc.fm_fiscal_status || __("Sin estado"), "gray", ""];
	},
};
