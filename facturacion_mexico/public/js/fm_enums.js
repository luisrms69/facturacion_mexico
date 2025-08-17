// public/js/fm_enums.js
(function () {
	function norm(s) {
		if (!s) return s;
		const t = ("" + s).trim().toUpperCase();
		return t === "CANCELACION_PENDIENTE" ? "CANCELACIÓN_PENDIENTE" : t;
	}

	const FiscalStates = {
		BORRADOR: "BORRADOR",
		TIMBRADO: "TIMBRADO",
		CANCELADO: "CANCELADO",
		CANCELACIÓN_PENDIENTE: "CANCELACIÓN_PENDIENTE",
		RECHAZADO: "RECHAZADO",
		ERROR: "ERROR",
		PROCESANDO: "PROCESANDO",
		ARCHIVADO: "ARCHIVADO",
	};

	const StatusColor = {
		BORRADOR: "gray",
		TIMBRADO: "green",
		CANCELADO: "red",
		CANCELACIÓN_PENDIENTE: "orange",
		RECHAZADO: "red",
		ERROR: "red",
		PROCESANDO: "blue",
		ARCHIVADO: "purple",
	};

	const StatusLabel = {
		BORRADOR: "BORRADOR",
		TIMBRADO: "TIMBRADO",
		CANCELADO: "CANCELADO",
		CANCELACIÓN_PENDIENTE: "CANCELACIÓN PENDIENTE",
		RECHAZADO: "RECHAZADO",
		ERROR: "ERROR",
		PROCESANDO: "PROCESANDO",
		ARCHIVADO: "ARCHIVADO",
	};

	function indicatorFor(state) {
		const s = norm(state);
		const label = StatusLabel[s] || s || __("Sin estado");
		const color = StatusColor[s] || "gray";
		const filter = `fm_fiscal_status,=,${s}`;
		return [label, color, filter];
	}

	window.FM_ENUMS = { FiscalStates, StatusColor, StatusLabel, norm, indicatorFor };
})();
