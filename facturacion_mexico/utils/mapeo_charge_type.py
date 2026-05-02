# facturacion_mexico/utils/mapeo_charge_type.py
"""
Single source of truth para mapeo regla_base → charge_type ERPNext.

Este módulo centraliza la configuración de charge_types para generación de
Sales Taxes and Charges Templates (STCT), eliminando hardcode en generador.

Arquitectura:
- Tabla de constantes (no DocType) - consistente con reglas_calculo_fiscal.py
- Migrable con código (zero-config deployment)
- Versionable con git
- Usado por: generador_templates_fiscal.py

Versión: E4 (2025-10-27)
Cambio principal E4: "cantidad" mapea a "On Item Quantity" (antes "Actual")
"""

# =============================================================================
# CONSTANTE PRINCIPAL: MAPEO REGLA_BASE → CHARGE_TYPE
# =============================================================================

MAPEO_CHARGE_TYPE_REGLA_BASE = {
	# IVA/Impuestos sobre monto neto (base común)
	"monto_neto": "On Net Total",
	# IEPS Cuotas: por cantidad en UOM canónica
	# E4 MIGRATION: Cambio de "Actual" a "On Item Quantity"
	# RAZÓN: "Actual" inestable en submit (pérdida valores post-amend)
	# "On Item Quantity" es nativo ERPNext, estable en lifecycle completo
	"cantidad": "On Item Quantity",
	# IVA cascada sobre IEPS (monto de fila previa)
	"fila_previa_monto": "On Previous Row Amount",
	# Casos especiales (total fila previa, no solo monto impuesto)
	"fila_previa_total": "On Previous Row Total",
	# IVA trasladado (mismo comportamiento que fila_previa_monto)
	"iva_trasladado": "On Previous Row Amount",
}

# =============================================================================
# METADATA MAPEO
# =============================================================================

# Versión del mapeo (formato YYYY.MM para tracking cambios)
VERSION_MAPEO = "2025.10"

# Changelog versiones
CHANGELOG_MAPEO = {
	"2025.10": "E4 Migration - 'cantidad' cambió de 'Actual' a 'On Item Quantity'",
	"2024.01": "Versión inicial - mapeo hardcoded en generador_templates_fiscal.py",
}

# =============================================================================
# FUNCIÓN HELPER
# =============================================================================


def obtener_charge_type(regla_base: str, fallback: str = "On Net Total") -> str:
	"""
	Obtiene charge_type ERPNext desde regla_base.

	Función helper para obtener el charge_type ERPNext correspondiente a una
	regla_base definida en la tabla maestra reglas_calculo_fiscal.py.

	Args:
		regla_base: Regla base desde tabla maestra (e.g., "cantidad", "monto_neto")
		fallback: Valor por defecto si regla_base no encontrada (default: "On Net Total")

	Returns:
		str: charge_type ERPNext (e.g., "On Item Quantity", "On Net Total")

	Ejemplos:
		>>> obtener_charge_type("cantidad")
		"On Item Quantity"

		>>> obtener_charge_type("monto_neto")
		"On Net Total"

		>>> obtener_charge_type("desconocido")
		"On Net Total"  # Fallback

	Uso típico:
		from facturacion_mexico.utils.mapeo_charge_type import obtener_charge_type
		from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo

		regla = obtener_regla_calculo(ROL_IEPS_AZU)
		charge_type = obtener_charge_type(regla["regla_base"])
		# charge_type = "On Item Quantity"
	"""
	return MAPEO_CHARGE_TYPE_REGLA_BASE.get(regla_base, fallback)


# =============================================================================
# VALIDACIONES
# =============================================================================


def validar_mapeo() -> dict:
	"""
	Valida integridad del mapeo charge_type.

	Verifica que todas las reglas_base conocidas tengan mapeo definido.
	Útil para tests y auditorías.

	Returns:
		dict: {
			"valido": bool,
			"reglas_base_definidas": int,
			"errores": list[str]
		}

	Ejemplo:
		>>> validar_mapeo()
		{
			"valido": True,
			"reglas_base_definidas": 5,
			"errores": []
		}
	"""
	from facturacion_mexico.utils.reglas_calculo_fiscal import TABLA_MAESTRA_REGLAS_CALCULO

	errores = []
	reglas_base_unicas = set()

	# Extraer todas las reglas_base de la tabla maestra
	for regla in TABLA_MAESTRA_REGLAS_CALCULO:
		rol_fiscal, regla_base = regla[0], regla[1]
		reglas_base_unicas.add(regla_base)

		# Verificar que tenga mapeo
		if regla_base not in MAPEO_CHARGE_TYPE_REGLA_BASE:
			errores.append(f"regla_base '{regla_base}' (rol {rol_fiscal}) sin mapeo charge_type")

	return {
		"valido": len(errores) == 0,
		"reglas_base_definidas": len(reglas_base_unicas),
		"reglas_base_sin_mapeo": errores,
	}


# =============================================================================
# CONSTANTES DERIVADAS (UTILIDADES)
# =============================================================================

# Mapeo inverso: charge_type → reglas_base que lo usan
CHARGE_TYPES_POR_USO = {}
for regla_base, charge_type in MAPEO_CHARGE_TYPE_REGLA_BASE.items():
	if charge_type not in CHARGE_TYPES_POR_USO:
		CHARGE_TYPES_POR_USO[charge_type] = []
	CHARGE_TYPES_POR_USO[charge_type].append(regla_base)

# Lista de todos los charge_types válidos
CHARGE_TYPES_VALIDOS = list(MAPEO_CHARGE_TYPE_REGLA_BASE.values())

# Lista de todas las reglas_base conocidas
REGLAS_BASE_CONOCIDAS = list(MAPEO_CHARGE_TYPE_REGLA_BASE.keys())
