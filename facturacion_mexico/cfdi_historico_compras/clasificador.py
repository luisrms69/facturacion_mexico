# Copyright (c) 2026, Buzola and contributors
"""Clasificador determinista ClaveProdServ SAT -> item_code, para la carga histórica de
CFDI de compra. NO usa BD ni frappe: es una función pura y determinista sobre la
**taxonomía autorizada de Gastos** (Código Agrupador SAT) ya presente en el catálogo.

Objetivo: que TODO concepto resuelva a un `item_code` existente ANTES de
`build_purchase_invoice()`, sin depender del mecanismo de aprendizaje/reglas.

Estrategia (determinista, sin ambigüedad):
  1. Coincidencia por **prefijo más largo** de la ClaveProdServ (8→6→4→2 dígitos) contra
     `PREFIX_TO_ITEM` (segmentos SAT + overrides finos).
  2. Si NINGÚN prefijo coincide -> item_code vacío (sin mapping). El concepto queda **sin
     resolver** y `build_purchase_invoice()` lo reporta como `ERROR_ITEM`. **No hay fallback
     arbitrario**: ningún concepto desconocido se fuerza a un Item.

Los `item_code` destino son Items **existentes** del catálogo autorizado (backbone `GASTO-*`
+ `INFRA-0002` para equipo de cómputo). No se crea un Item por concepto/proveedor/XML.
"""

# item_code destino por prefijo de ClaveProdServ SAT. La resolución usa el prefijo MÁS LARGO
# que exista aquí (8,6,4,2 dígitos), de modo que un override específico gana al segmento.
PREFIX_TO_ITEM = {
	# --- Segmentos SAT (2 dígitos) — familia autorizada de gasto ---
	"80": "GASTO-SRV-001",  # Servicios de gestión/profesionales/administrativos
	"81": "GASTO-SRV-001",  # Servicios de ingeniería/investigación/tecnología (consultoría/TI)
	"82": "GASTO-VNT-001",  # Servicios editoriales/diseño/marketing -> publicidad
	"83": "GASTO-OPR-001",  # Servicios públicos (telecom) -> teléfono/internet
	"84": "GASTO-FIN-001",  # Servicios financieros -> comisiones bancarias
	"85": "GASTO-NOM-017",  # Servicios de salud -> servicio médico
	"86": "GASTO-OPR-009",  # Servicios educativos -> capacitación
	"90": "GASTO-MOV-002",  # Viajes/alimentos/entretenimiento -> viáticos
	"78": "GASTO-LOG-001",  # Transporte/almacenaje/correo -> fletes y acarreos
	"72": "GASTO-OPR-006",  # Servicios de edificación/mantenimiento -> mantenimiento
	"94": "GASTO-SRV-017",  # Organizaciones/servicios jurídicos -> honorarios PM
	"93": "GASTO-SEG-002",  # Servicios gubernamentales -> otros impuestos y derechos
	"95": "GASTO-OBR-003",  # Terrenos/edificios/estructuras -> otros gastos generales
	"15": "GASTO-MOV-003",  # Combustibles/lubricantes
	"10": "GASTO-MOV-002",  # Animales/plantas/alimentos -> viáticos/consumos
	"50": "GASTO-MOV-002",  # Alimentos/bebidas -> viáticos/consumos
	"52": "GASTO-OPR-007",  # Muebles/enseres domésticos -> papelería/oficina
	"56": "GASTO-OPR-007",  # Muebles industriales/oficina -> papelería/oficina
	"44": "GASTO-OPR-007",  # Equipo/insumos de oficina -> papelería/oficina
	"14": "GASTO-OPR-007",  # Papel/productos de papel -> papelería/oficina
	"43": "INFRA-0002",  # Tecnología de información / hardware -> equipo de cómputo
	"32": "INFRA-0002",  # Componentes/suministros electrónicos -> equipo de cómputo
	"26": "GASTO-OPR-006",  # Maquinaria/accesorios -> mantenimiento
	"60": "GASTO-OBR-003",  # Instrumentos musicales/arte/manualidades -> otros gastos
	"49": "GASTO-OBR-003",  # Equipo de deportes/recreo -> otros gastos
	"01": "GASTO-OBR-003",  # Clave "sin clasificar" -> otros gastos generales
	# --- Overrides de 4 dígitos (subfamilia) ---
	"8012": "GASTO-SRV-017",  # Servicios legales -> honorarios PM legales/contables
	"8014": "GASTO-VNT-001",  # Servicios de publicidad/mercadotecnia
	"8310": "GASTO-OPR-003",  # Energía eléctrica
	"8411": "GASTO-SRV-017",  # Servicios contables/auditoría -> honorarios PM
	"8413": "GASTO-SEG-001",  # Seguros y fianzas
	"8116": "GASTO-OPR-008",  # Software/licencias/servicios en la nube -> cuotas y suscripciones
	"7811": "GASTO-MOV-010",  # Transporte de pasajeros (buses/vuelos/pensión) -> movilidad
	"7818": "GASTO-MOV-011",  # Estacionamiento/servicios de terminal -> estacionamiento
	"4323": "GASTO-OPR-008",  # Software por suscripción -> cuotas y suscripciones
	"5216": "INFRA-0002",  # Equipo audiovisual/pantallas/bocinas -> equipo de cómputo
	# --- Overrides de 6 dígitos ---
	"841216": "GASTO-VNT-002",  # Comisiones sobre ventas
	"851017": "GASTO-NOM-026",  # Cuotas obrero-patronales (IMSS)
	"781318": "GASTO-ARR-002",  # Arrendamiento de espacios de almacenamiento (storage)
	# --- Overrides de 8 dígitos (clave exacta puntual) ---
	"95111602": "GASTO-MOV-010",  # Peaje y cruce carretero
	"81161501": "GASTO-OPR-008",  # Sistema en línea de facturación -> suscripciones
	"81161800": "GASTO-OPR-008",  # Infraestructura de software -> suscripciones
}


def resolve_item_code(sat_product_key, description=None):
	"""Resuelve (item_code, motivo) de forma determinista por ClaveProdServ SAT.

	Si NINGÚN prefijo mapea, retorna ("", "sin_mapping"): el concepto queda sin resolver
	(provoca ERROR_ITEM en build). **No hay fallback**.
	motivo: "clave:<prefijo>" del match usado, o "sin_mapping".
	`description` se acepta por compatibilidad futura; hoy la resolución es por ClaveProdServ SAT.
	"""
	key = (sat_product_key or "").strip()
	if key:
		for length in (8, 6, 4, 2):
			pref = key[:length]
			if len(pref) == length and pref in PREFIX_TO_ITEM:
				return PREFIX_TO_ITEM[pref], f"clave:{pref}"
	return "", "sin_mapping"


def classify_many(claves):
	"""Utilidad para reporte/tests: dada una lista de ClaveProdServ, devuelve
	{clave: (item_code, motivo)} y agrega el conteo de resueltos/sin resolver."""
	out = {}
	sin_item = 0
	for cl in claves:
		item, motivo = resolve_item_code(cl)
		out[cl] = (item, motivo)
		if not item:
			sin_item += 1
	return out, sin_item
