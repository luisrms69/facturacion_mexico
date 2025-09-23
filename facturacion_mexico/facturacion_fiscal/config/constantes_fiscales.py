"""
Constantes Fiscales México - Centralización de tasas y configuraciones SAT.
Reemplaza hardcode disperso por punto único de configuración.
"""

from typing import Any

# =============================================================================
# TASAS IVA - IMPUESTO AL VALOR AGREGADO
# =============================================================================

TASAS_IVA = {
	"general": {
		"tasa": 16.0,
		"descripcion": "Impuesto al Valor Agregado 16%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
	},
	"frontera": {
		"tasa": 8.0,
		"descripcion": "Impuesto al Valor Agregado 8% Frontera",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
	},
	"exportacion": {
		"tasa": 0.0,
		"descripcion": "Impuesto al Valor Agregado 0% (Exportación)",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
	},
	"exento": {
		"tasa": 0.0,
		"descripcion": "IVA Exento",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
	},
}

# =============================================================================
# TASAS IEPS - IMPUESTO ESPECIAL SOBRE PRODUCCIÓN Y SERVICIOS
# =============================================================================

TASAS_IEPS = {
	"alcohol": {
		"tasa": 26.5,
		"descripcion": "IEPS Alcohol 26.5%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
		"iva_aplicable": True,  # IEPS + IVA en cascada
	},
	"azucar": {
		"tasa": 1.0,
		"descripcion": "IEPS Azúcar/Bebidas 1 peso por litro",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
		"iva_aplicable": True,
	},
	"combustibles": {
		"tasa": 4.58,
		"descripcion": "IEPS Combustibles 4.58 pesos por litro",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
		"iva_aplicable": True,
	},
	"tabaco": {
		"tasa": 160.0,
		"descripcion": "IEPS Tabaco 160%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
		"iva_aplicable": True,
	},
}

# =============================================================================
# TASAS RETENCIONES - ISR E IVA RETENIDOS
# =============================================================================

TASAS_RETENCIONES = {
	# ISR Retenciones
	"isr_honorarios": {
		"tasa": 10.0,
		"descripcion": "ISR Retenido Honorarios 10%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
	},
	"isr_arrendamiento": {
		"tasa": 10.0,
		"descripcion": "ISR Retenido Arrendamiento 10%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
	},
	"isr_autotransporte": {
		"tasa": 4.0,
		"descripcion": "ISR Retenido Autotransporte 4%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
	},
	# IVA Retenciones
	"iva_servicios": {
		"tasa": 10.67,
		"descripcion": "IVA Retenido Servicios Profesionales 10.67%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
	},
	"iva_arrendamiento": {
		"tasa": 10.67,
		"descripcion": "IVA Retenido Arrendamiento 10.67%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
	},
	"iva_autotransporte": {
		"tasa": 4.0,
		"descripcion": "IVA Retenido Autotransporte 4%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
	},
}

# =============================================================================
# MAPEO ROLES FISCALES → CONFIGURACIONES
# =============================================================================

MAPEO_ROLES_CONFIGURACION = {
	# IVA
	"IVA por Pagar (16%)": ("iva", "general"),
	"IVA por Pagar (8% frontera)": ("iva", "frontera"),
	"IVA por Pagar (0% exportación)": ("iva", "exportacion"),
	"IVA Exento": ("iva", "exento"),
	# IEPS
	"IEPS por Pagar (Alcohol)": ("ieps", "alcohol"),
	"IEPS por Pagar (Azúcar/Bebidas)": ("ieps", "azucar"),
	"IEPS por Pagar (Combustibles)": ("ieps", "combustibles"),
	"IEPS por Pagar (Tabaco)": ("ieps", "tabaco"),
	# Retenciones ISR
	"ISR Retenido (Honorarios)": ("retenciones", "isr_honorarios"),
	"ISR Retenido (Arrendamiento)": ("retenciones", "isr_arrendamiento"),
	"ISR Retenido (Autotransporte)": ("retenciones", "isr_autotransporte"),
	# Retenciones IVA
	"IVA Retenido (Servicios Profesionales)": ("retenciones", "iva_servicios"),
	"IVA Retenido (Arrendamiento)": ("retenciones", "iva_arrendamiento"),
	"IVA Retenido (Autotransporte)": ("retenciones", "iva_autotransporte"),
}

# =============================================================================
# COMBINACIONES POR ALCANCE EMPRESARIAL
# =============================================================================

COMBINACIONES_ALCANCE = {
	"basico": ["IVA por Pagar (16%)", "IVA por Pagar (0% exportación)", "IVA Exento"],
	"frontera": [
		"IVA por Pagar (16%)",
		"IVA por Pagar (8% frontera)",
		"IVA por Pagar (0% exportación)",
		"IVA Exento",
	],
	"ieps_alcohol": [
		"IEPS por Pagar (Alcohol)",
		"IVA por Pagar (16%)",  # Cascada IEPS → IVA
	],
	"ieps_azucar": ["IEPS por Pagar (Azúcar/Bebidas)", "IVA por Pagar (16%)"],
	"ieps_combustibles": ["IEPS por Pagar (Combustibles)", "IVA por Pagar (16%)"],
	"ieps_tabaco": ["IEPS por Pagar (Tabaco)", "IVA por Pagar (16%)"],
	"retenciones_honorarios": ["ISR Retenido (Honorarios)", "IVA Retenido (Servicios Profesionales)"],
	"retenciones_arrendamiento": ["ISR Retenido (Arrendamiento)", "IVA Retenido (Arrendamiento)"],
	"retenciones_autotransporte": ["ISR Retenido (Autotransporte)", "IVA Retenido (Autotransporte)"],
}

# =============================================================================
# TAX CATEGORIES Y TEMPLATES NAMES
# =============================================================================

TAX_CATEGORIES = {
	"General 16": {"title": "General 16", "descripcion": "IVA General 16%"},
	"Zero 0": {"title": "Zero 0", "descripcion": "IVA 0% Exportación"},
	"Exempt": {"title": "Exempt", "descripcion": "Exento de impuestos"},
	"Border 8": {"title": "Border 8", "descripcion": "IVA Frontera 8%"},
}

# Templates STCT base names
STCT_TEMPLATES = {
	"iva_general": "IVA 16% - México",
	"iva_frontera": "IVA 8% Frontera - México",
	"iva_exportacion": "IVA 0% - México",
	"sin_impuestos": "Sin Impuestos - México",
}

# Templates ITT base names
ITT_TEMPLATES = {
	"iva_general": "ITT IVA 16%",
	"iva_frontera": "ITT IVA 8% Frontera",
	"iva_exportacion": "ITT IVA 0%",
	"exento": "ITT Exento",
}

# =============================================================================
# FUNCIONES HELPER PARA ACCESO A CONFIGURACIÓN
# =============================================================================


def obtener_tasa(categoria: str, tipo: str | None = None) -> dict[str, Any]:
	"""
	Obtener configuración de tasa por categoría y tipo.

	Args:
	    categoria: 'iva', 'ieps', 'retenciones'
	    tipo: subtipo específico (ej. 'general', 'alcohol', 'isr_honorarios')

	Returns:
	    Dict con tasa, descripción y configuración

	Raises:
	    ValueError: Si no existe la configuración solicitada
	"""
	configuraciones = {"iva": TASAS_IVA, "ieps": TASAS_IEPS, "retenciones": TASAS_RETENCIONES}

	if categoria not in configuraciones:
		raise ValueError(f"Categoría '{categoria}' no válida. Opciones: {list(configuraciones.keys())}")

	if tipo is None:
		return configuraciones[categoria]

	if tipo not in configuraciones[categoria]:
		raise ValueError(
			f"Tipo '{tipo}' no válido para categoría '{categoria}'. Opciones: {list(configuraciones[categoria].keys())}"
		)

	return configuraciones[categoria][tipo]


def obtener_configuracion_por_rol(rol_fiscal: str) -> dict[str, Any]:
	"""
	Obtener configuración completa por rol fiscal.

	Args:
	    rol_fiscal: Nombre del rol (ej. "IVA por Pagar (16%)")

	Returns:
	    Dict con configuración completa del impuesto

	Raises:
	    ValueError: Si el rol fiscal no existe
	"""
	if rol_fiscal not in MAPEO_ROLES_CONFIGURACION:
		raise ValueError(f"Rol fiscal '{rol_fiscal}' no reconocido")

	categoria, tipo = MAPEO_ROLES_CONFIGURACION[rol_fiscal]
	return obtener_tasa(categoria, tipo)


def es_impuesto_cascada(rol_fiscal: str) -> bool:
	"""
	Verificar si un impuesto requiere cascada (IEPS + IVA).

	Args:
	    rol_fiscal: Nombre del rol fiscal

	Returns:
	    True si requiere IVA en cascada, False en caso contrario
	"""
	try:
		config = obtener_configuracion_por_rol(rol_fiscal)
		return config.get("iva_aplicable", False)
	except ValueError:
		return False


def obtener_roles_por_alcance(alcance: str) -> list[str]:
	"""
	Obtener lista de roles fiscales por alcance empresarial.

	Args:
	    alcance: Tipo de alcance empresarial

	Returns:
	    Lista de roles fiscales requeridos

	Raises:
	    ValueError: Si el alcance no existe
	"""
	if alcance not in COMBINACIONES_ALCANCE:
		raise ValueError(f"Alcance '{alcance}' no válido. Opciones: {list(COMBINACIONES_ALCANCE.keys())}")

	return COMBINACIONES_ALCANCE[alcance].copy()
