# ¡ÚNICO lugar a actualizar si cambia el SAT!

TIPO_COMPROBANTE = {
	"I": "Ingreso",
	"E": "Egreso",
	# "T": "Traslado",  # NO implementado. No exponer.
	# "P": "Pago",     # Se cubrirá con CPMX, fuera de este alcance.
	# "N": "Nómina",
}

TIPO_RELACION = {
	"01": "Nota de crédito de los documentos relacionados",
	"03": "Devolución de mercancía sobre facturas o traslados previos",
	"04": "Sustitución de CFDI previos",
	"05": "Traslados de mercancías facturados posteriormente (novación/otros)",
}


def select_options_tipo_comprobante():
	# Solo I/E (T se deja fuera)
	return [f"{k} - {v}" for k, v in TIPO_COMPROBANTE.items() if k in ("I", "E")]


def select_options_tipo_relacion():
	# Las que operaremos en E
	return [f"{k} - {v}" for k, v in TIPO_RELACION.items()]


def parse_select_code(text: str) -> str:
	# "01 - Nota..." -> "01" ; "I - Ingreso" -> "I"
	return (text or "").split(" - ", 1)[0].strip()
