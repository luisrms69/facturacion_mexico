(function () {
	const S = (window.FM_ENUMS || {}).FiscalStates || {};
	function norm(s) {
		if (!s) return s;
		const t = ("" + s).trim().toUpperCase();
		return t === "CANCELACION_PENDIENTE" ? "CANCELACIÓN_PENDIENTE" : t;
	}

	const states = {
		cancelable: new Set([S.TIMBRADO]),
		timbrable: new Set([S.BORRADOR, S.ERROR]),
		readonly_cancel: new Set([S.CANCELADO, "CANCELACIÓN_PENDIENTE", S.ARCHIVADO]),
	};

	function canCancel({ status, docstatus, sync }) {
		return (
			docstatus === 1 &&
			states.cancelable.has(norm(status)) &&
			("" + (sync || "")).toLowerCase() !== "pending"
		);
	}

	window.FiscalPolicy = { states, canCancel, normStatus: norm };
})();
