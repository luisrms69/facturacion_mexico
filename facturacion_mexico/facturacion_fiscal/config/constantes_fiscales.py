"""
Constantes Fiscales México - Centralización de tasas y configuraciones SAT.
Reemplaza hardcode disperso por punto único de configuración.
"""

from typing import Any

# Importar constantes roles fiscales - Single source of truth
from facturacion_mexico.utils.roles_fiscales import (
	ROL_IEPS_ALC,
	ROL_IEPS_AZU,
	ROL_IEPS_COMB,
	ROL_IEPS_TAB,
	ROL_IEPS_TABQ,
	ROL_IVA_CERO,
	ROL_IVA_EXENTO,
	ROL_IVA_FRO,
	ROL_IVA_NAC,
	ROL_RET_ISR_ARR,
	ROL_RET_ISR_AUTO,
	ROL_RET_ISR_HON,
	ROL_RET_ISR_RESICO,
	ROL_RET_IVA_ARR,
	ROL_RET_IVA_AUTO,
	ROL_RET_IVA_HON,
	ROL_RET_IVA_RESICO,
)

# =============================================================================
# CONSTANTES FISCALES SAT - NORMATIVA FISCAL
# =============================================================================

# Proporción IVA retenido según normativa SAT (2/3 del IVA trasladado)
# Aplicable a TODOS los tipos de retención (Honorarios, Arrendamiento, Autotransporte, RESICO)
# Precisión 4 decimales para cálculos exactos en montos grandes
PROPORCION_IVA_RETENIDO_SAT = 66.6667  # 2/3 = 0.666667 → 66.6667%

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
		"tasa": 0.0,  # IEPS Cuota: rate=0, cálculo automático por hook desde tabla IEPS Cuota SAT
		"descripcion": "IEPS Azúcar/Bebidas (Cuota variable por litro)",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
		"iva_aplicable": True,
	},
	"combustibles": {
		"tasa": 0.0,  # IEPS Cuota: rate=0, cálculo automático por hook desde tabla IEPS Cuota SAT
		"descripcion": "IEPS Combustibles (Cuota variable por litro)",
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
	"tabaco_cuota": {
		"tasa": 0.0,  # IEPS Cuota: rate=0, cálculo automático por hook desde tabla IEPS Cuota SAT
		"descripcion": "IEPS Tabaco (Cuota variable por cigarro)",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Add",
		"iva_aplicable": True,
	},
}

# =============================================================================
# TASAS RETENCIONES - ISR E IVA RETENIDO (LEGACY - PRE E3)
# =============================================================================
# DEPRECATED: Este diccionario usa enfoque antiguo (retención IVA como % del neto)
# USAR: RETENCIONES_CONFIG para sistema E3 actual (retención IVA como % del IVA trasladado)
# MANTENER: Solo para compatibilidad con tests antiguos y sistema install.py legacy

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
	# IVA Retenciones (DEPRECATED: 10.67% del neto ≠ sistema E3 correcto: 66.67% del IVA trasladado)
	"iva_servicios": {
		"tasa": 10.67,  # DEPRECATED: Usar RETENCIONES_CONFIG["honorarios"]["proporcion_iva_retenido"]
		"descripcion": "IVA Retenido Servicios Profesionales 10.67%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
		"deprecated": True,  # Marcado para remoción futura
	},
	"iva_arrendamiento": {
		"tasa": 10.67,  # DEPRECATED: Usar RETENCIONES_CONFIG["arrendamiento"]["proporcion_iva_retenido"]
		"descripcion": "IVA Retenido Arrendamiento 10.67%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
		"deprecated": True,  # Marcado para remoción futura
	},
	"iva_autotransporte": {
		"tasa": 4.0,
		"descripcion": "IVA Retenido Autotransporte 4%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
		"deprecated": True,  # Marcado para remoción futura
	},
	# RESICO (Régimen Simplificado de Confianza) - Tasas configurables
	"isr_resico": {
		"tasa": 1.25,  # Fallback default
		"descripcion": "ISR Retenido RESICO 1.25%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
		"configurable": True,  # Indica que puede tomar valor de settings
	},
	"iva_resico": {
		"tasa": 10.67,  # DEPRECATED: Usar RETENCIONES_CONFIG["resico"]["proporcion_iva_retenido"]
		"descripcion": "IVA Retenido RESICO 10.67%",
		"charge_type": "On Net Total",
		"add_deduct_tax": "Deduct",
		"configurable": True,
		"deprecated": True,  # Marcado para remoción futura
	},
}

# =============================================================================
# MAPEO ROLES FISCALES → CONFIGURACIONES
# =============================================================================

MAPEO_ROLES_CONFIGURACION = {
	# IVA - Usar constantes como keys (single source of truth)
	ROL_IVA_NAC: ("iva", "general"),
	ROL_IVA_FRO: ("iva", "frontera"),
	ROL_IVA_CERO: ("iva", "exportacion"),
	ROL_IVA_EXENTO: ("iva", "exento"),
	# IEPS
	ROL_IEPS_ALC: ("ieps", "alcohol"),
	ROL_IEPS_AZU: ("ieps", "azucar"),
	ROL_IEPS_COMB: ("ieps", "combustibles"),
	ROL_IEPS_TAB: ("ieps", "tabaco"),
	ROL_IEPS_TABQ: ("ieps", "tabaco_cuota"),
	# Retenciones ISR
	ROL_RET_ISR_HON: ("retenciones", "isr_honorarios"),
	ROL_RET_ISR_ARR: ("retenciones", "isr_arrendamiento"),
	ROL_RET_ISR_AUTO: ("retenciones", "isr_autotransporte"),
	ROL_RET_ISR_RESICO: ("retenciones", "isr_resico"),
	# Retenciones IVA
	ROL_RET_IVA_HON: ("retenciones", "iva_servicios"),
	ROL_RET_IVA_ARR: ("retenciones", "iva_arrendamiento"),
	ROL_RET_IVA_AUTO: ("retenciones", "iva_autotransporte"),
	ROL_RET_IVA_RESICO: ("retenciones", "iva_resico"),
}

# =============================================================================
# COMBINACIONES POR ALCANCE EMPRESARIAL
# =============================================================================

COMBINACIONES_ALCANCE = {
	"basico": [ROL_IVA_NAC, ROL_IVA_CERO, ROL_IVA_EXENTO],
	"frontera": [
		ROL_IVA_NAC,
		ROL_IVA_FRO,
		ROL_IVA_CERO,
		ROL_IVA_EXENTO,
	],
	"ieps_alcohol": [
		ROL_IEPS_ALC,
		ROL_IVA_NAC,  # Cascada IEPS → IVA
	],
	"ieps_azucar": [ROL_IEPS_AZU, ROL_IVA_NAC],
	"ieps_combustibles": [ROL_IEPS_COMB, ROL_IVA_NAC],
	"ieps_tabaco": [
		ROL_IEPS_TAB,  # IEPS Tasa 160%
		ROL_IEPS_TABQ,  # IEPS Cuota $0.35/cigarro
		ROL_IVA_NAC,  # IVA sobre precio + ambos IEPS
	],
	"retenciones_honorarios": [ROL_RET_ISR_HON, ROL_RET_IVA_HON],
	"retenciones_arrendamiento": [ROL_RET_ISR_ARR, ROL_RET_IVA_ARR],
	"retenciones_autotransporte": [ROL_RET_ISR_AUTO, ROL_RET_IVA_AUTO],
	"retenciones_resico": [ROL_RET_ISR_RESICO, ROL_RET_IVA_RESICO],
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
# RETENCIONES - CONFIGURACIÓN PROPORCIONAL (E3)
# =============================================================================

RETENCIONES_CONFIG = {
	"honorarios": {
		"proporcion_iva_retenido": PROPORCION_IVA_RETENIDO_SAT,
		"rol_iva": ROL_RET_IVA_HON,
		"rol_isr": ROL_RET_ISR_HON,
		"tasa_isr": 10.0,
	},
	"arrendamiento": {
		"proporcion_iva_retenido": PROPORCION_IVA_RETENIDO_SAT,
		"rol_iva": ROL_RET_IVA_ARR,
		"rol_isr": ROL_RET_ISR_ARR,
		"tasa_isr": 10.0,
	},
	"autotransporte": {
		"proporcion_iva_retenido": PROPORCION_IVA_RETENIDO_SAT,
		"rol_iva": ROL_RET_IVA_AUTO,
		"rol_isr": ROL_RET_ISR_AUTO,
		"tasa_isr": 4.0,
	},
	"resico": {
		"proporcion_iva_retenido": PROPORCION_IVA_RETENIDO_SAT,
		"rol_iva": ROL_RET_IVA_RESICO,
		"rol_isr": ROL_RET_ISR_RESICO,
		"tasa_isr": 1.25,  # Configurable vía Configuracion Fiscal Mexico (tasa_isr_resico)
	},
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


def obtener_configuracion_por_rol(rol_fiscal: str, config_fiscal=None) -> dict[str, Any]:
	"""
	Obtener configuración completa por rol fiscal.

	Args:
	    rol_fiscal: Nombre del rol (ej. "IVA por Pagar (16%)")
	    config_fiscal: Documento Configuracion Fiscal Mexico (opcional, para tasas configurables)

	Returns:
	    Dict con configuración completa del impuesto

	Raises:
	    ValueError: Si el rol fiscal no existe
	"""
	import frappe
	from frappe.utils import flt

	if rol_fiscal not in MAPEO_ROLES_CONFIGURACION:
		raise ValueError(f"Rol fiscal '{rol_fiscal}' no reconocido")

	categoria, tipo = MAPEO_ROLES_CONFIGURACION[rol_fiscal]
	config = obtener_tasa(categoria, tipo).copy()

	# Resolver tasas configurables desde settings (solo ISR RESICO)
	if config.get("configurable") and config_fiscal:
		if tipo == "isr_resico" and hasattr(config_fiscal, "tasa_isr_resico"):
			tasa_custom = flt(config_fiscal.tasa_isr_resico)
			if tasa_custom > 0:
				config["tasa"] = tasa_custom

	return config


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
