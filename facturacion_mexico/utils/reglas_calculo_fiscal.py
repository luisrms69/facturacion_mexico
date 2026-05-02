"""
SINGLE SOURCE OF TRUTH - Reglas Cálculo Fiscal México
======================================================
Define CÓMO se calculan los impuestos por cada rol_fiscal.

Fuente canónica: TABLA_MAESTRA_REGLAS_CALCULO
NUNCA modificar reglas directamente en otro archivo.

⚠️ IMPORTANTE - SINCRONIZACIÓN CON ROLES FISCALES:
--------------------------------------------------
Este archivo depende de roles_fiscales.py (fuente canónica de roles).
TODA regla debe tener un rol_fiscal correspondiente.

PROCESO AL MODIFICAR REGLAS:
1. Verificar que rol_fiscal existe en roles_fiscales.py
2. Actualizar TABLA_MAESTRA_REGLAS_CALCULO aquí
3. Tests de sincronización validan que todos los roles tienen regla

TEST VALIDACIÓN: test_reglas_calculo_fiscal.py
Falla automáticamente si faltan reglas o roles huérfanos.

Nomenclatura Campos:
- regla_base: De dónde sale la base (monto_neto, cantidad, fila_previa_*, iva_trasladado)
- regla_calculo: Cómo calcular (porcentual, cuota, retención)
- cascada: Boolean - incluye impuestos previos en base
- alcance: Granularidad (por_item, fila_previa)
- habilitada: Boolean - deshabilitar sin borrar
- version: Control cambios SAT (formato YYYY.MM)
- deprecada_desde: Fecha deprecación (None si vigente)

Uso:
	from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo

	regla = obtener_regla_calculo("IVA por Pagar (Nacional)")
	if regla and regla["habilitada"]:
		base = obtener_base(doc, regla["regla_base"])
		monto = calcular_monto(base, regla["regla_calculo"])
"""

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

# Tabla maestra: (
#   rol_fiscal,
#   regla_base,
#   regla_calculo,
#   cascada,
#   alcance,
#   habilitada,
#   fundamento_legal,
#   notas_calculo,
#   version,
#   deprecada_desde
# )
TABLA_MAESTRA_REGLAS_CALCULO = [
	# ==========================================
	# IVA - Traslado porcentual sobre monto neto
	# ==========================================
	(
		ROL_IVA_NAC,
		"monto_neto",
		"porcentual",
		False,
		"por_item",
		True,
		"Ley IVA Art. 1",
		"16% sobre monto neto del item. Base = net_amount. No integra impuestos previos.",
		"2025.01",
		None,
	),
	(
		ROL_IVA_FRO,
		"monto_neto",
		"porcentual",
		False,
		"por_item",
		True,
		"Ley IVA Art. 1",
		"8% zona frontera sobre monto neto. Base = net_amount. No integra impuestos previos.",
		"2025.01",
		None,
	),
	(
		ROL_IVA_CERO,
		"monto_neto",
		"porcentual",
		False,
		"por_item",
		True,
		"Ley IVA Art. 2-A",
		"0% exportación sobre monto neto. Base = net_amount. Tasa 0% genera CFDI con IVA 0%.",
		"2025.01",
		None,
	),
	(
		ROL_IVA_EXENTO,
		"monto_neto",
		"porcentual",
		False,
		"por_item",
		True,
		"Ley IVA Art. 9",
		"Exento de IVA. Base = net_amount, tasa = 0%. NO genera tax_row en CFDI (diferente a 0%).",
		"2025.01",
		None,
	),
	# ==========================================
	# IEPS Tasa - Porcentual sobre monto neto
	# ==========================================
	(
		ROL_IEPS_ALC,
		"monto_neto",
		"porcentual",
		False,
		"por_item",
		True,
		"LIEPS Art. 2 I-A",
		"IEPS Alcohol tasa. Base = net_amount. Tasa variable según graduación (26.5%, 30%, 53%).",
		"2025.01",
		None,
	),
	(
		ROL_IEPS_TAB,
		"monto_neto",
		"porcentual",
		False,
		"por_item",
		True,
		"LIEPS Art. 2 I-B",
		"IEPS Tabaco tasa. Base = net_amount. Tasa 160% sobre precio de enajenación.",
		"2025.01",
		None,
	),
	# ==========================================
	# IEPS Cuota - Cuota unitaria por cantidad
	# ==========================================
	# IMPORTANTE: integra_base_iva controlado en Mapeo Cuenta Fiscal Mexico
	# - Combustibles: integra_base_iva=0 (NO integra, ajuste en hook ajustar_base_iva_combustibles)
	# - Bebidas/Tabaco: integra_base_iva=1 (SÍ integra, regla general LIEPS)
	#
	# E4 MIGRATION: Cambiamos regla_base de "monto_neto" a "cantidad"
	# ANTES (Pre-E4): "monto_neto" generaba charge_type="On Net Total", hooks mutaban a "Actual"
	# DESPUÉS (E4): "cantidad" genera charge_type="On Item Quantity" (nativo ERPNext)
	# - ERPNext calcula automáticamente: rate x qty en UOM canónica
	# - No requiere hooks para mutar charge_type o calcular tax_amount
	# - Estable en Draft ↔ Submit (sin mutaciones)
	(
		ROL_IEPS_AZU,
		"cantidad",  # E4: Cambio de "monto_neto" a "cantidad"
		"cuota",
		False,
		"por_item",
		True,
		"LIEPS Art. 2 I-G",
		"IEPS Bebidas azucaradas cuota. Base = cantidad en UOM canónica. ERPNext calcula: cuota_unitaria x qty_canónica. Cuota $1.27/litro (2025). INTEGRA base IVA.",
		"2025.01",
		None,
	),
	(
		ROL_IEPS_COMB,
		"cantidad",  # E4: Cambio de "monto_neto" a "cantidad"
		"cuota",
		False,
		"por_item",
		True,
		"LIEPS Art. 2-A",
		"IEPS Combustibles cuota. Base = cantidad en UOM canónica. ERPNext calcula: cuota_unitaria x qty_canónica. Cuota $5.49/litro (2025). NO INTEGRA base IVA (ajuste especial Art. 2-A).",
		"2025.01",
		None,
	),
	(
		ROL_IEPS_TABQ,
		"cantidad",  # E4: Cambio de "monto_neto" a "cantidad"
		"cuota",
		False,
		"por_item",
		True,
		"LIEPS Art. 2-A",
		"IEPS Tabaco cuota. Base = cantidad en UOM canónica. ERPNext calcula: cuota_unitaria x qty_canónica. Cuota $0.35/pieza (2025). INTEGRA base IVA.",
		"2025.01",
		None,
	),
	# ==========================================
	# Retenciones IVA - Retención sobre monto neto
	# ==========================================
	# NOTA E1: Aunque fiscalmente las retenciones IVA se calculan sobre IVA trasladado,
	# legacy usaba "On Net Total" en generador templates. Mantener "monto_neto" para
	# compatibilidad con STCT legacy hasta implementar cálculo correcto con row_id.
	(
		ROL_RET_IVA_HON,
		"monto_neto",
		"retención",
		False,
		"por_item",
		True,
		"Ley IVA Art. 1-A III",
		"Retención IVA Honorarios. Base = monto neto (legacy). Tasa retención 2/3 (66.67%).",
		"2025.01",
		None,
	),
	(
		ROL_RET_IVA_ARR,
		"monto_neto",
		"retención",
		False,
		"por_item",
		True,
		"Ley IVA Art. 1-A II",
		"Retención IVA Arrendamiento. Base = monto neto (legacy). Tasa retención 10%.",
		"2025.01",
		None,
	),
	(
		ROL_RET_IVA_AUTO,
		"monto_neto",
		"retención",
		False,
		"por_item",
		True,
		"Ley IVA Art. 1-A IV",
		"Retención IVA Autotransporte. Base = monto neto (legacy). Tasa retención 4%.",
		"2025.01",
		None,
	),
	(
		ROL_RET_IVA_RESICO,
		"monto_neto",
		"retención",
		False,
		"por_item",
		True,
		"Ley IVA Art. 1-A",
		"Retención IVA RESICO. Base = monto neto (legacy). Tasa retención según régimen.",
		"2025.01",
		None,
	),
	# ==========================================
	# Retenciones ISR - Retención sobre monto neto
	# ==========================================
	(
		ROL_RET_ISR_HON,
		"monto_neto",
		"retención",
		False,
		"por_item",
		True,
		"LISR Art. 106",
		"Retención ISR Honorarios. Base = net_amount. Tasa retención 10%.",
		"2025.01",
		None,
	),
	(
		ROL_RET_ISR_ARR,
		"monto_neto",
		"retención",
		False,
		"por_item",
		True,
		"LISR Art. 116",
		"Retención ISR Arrendamiento. Base = net_amount. Tasa retención 10%.",
		"2025.01",
		None,
	),
	(
		ROL_RET_ISR_AUTO,
		"monto_neto",
		"retención",
		False,
		"por_item",
		True,
		"LISR Art. 154",
		"Retención ISR Autotransporte. Base = net_amount. Tasa retención variable según régimen.",
		"2025.01",
		None,
	),
	(
		ROL_RET_ISR_RESICO,
		"monto_neto",
		"retención",
		False,
		"por_item",
		True,
		"LISR Art. 113-E",
		"Retención ISR RESICO. Base = net_amount. Tasa retención 1.25% (configurable en CFM).",
		"2025.01",
		None,
	),
]

# -----------------------------------------------------------
# CONSTANTES DERIVADAS (generadas automáticamente)
# -----------------------------------------------------------

# Diccionario rol_fiscal → reglas completas
REGLAS_POR_ROL = {
	row[0]: {
		"regla_base": row[1],
		"regla_calculo": row[2],
		"cascada": row[3],
		"alcance": row[4],
		"habilitada": row[5],
		"fundamento_legal": row[6],
		"notas_calculo": row[7],
		"version": row[8],
		"deprecada_desde": row[9],
	}
	for row in TABLA_MAESTRA_REGLAS_CALCULO
}

# Set de roles con reglas definidas (para validación)
ROLES_CON_REGLA = set(REGLAS_POR_ROL.keys())

# Diccionario regla_base → roles que la usan (análisis)
ROLES_POR_BASE = {}
for rol, reglas in REGLAS_POR_ROL.items():
	base = reglas["regla_base"]
	if base not in ROLES_POR_BASE:
		ROLES_POR_BASE[base] = []
	ROLES_POR_BASE[base].append(rol)

# Diccionario regla_calculo → roles que la usan (análisis)
ROLES_POR_CALCULO = {}
for rol, reglas in REGLAS_POR_ROL.items():
	calculo = reglas["regla_calculo"]
	if calculo not in ROLES_POR_CALCULO:
		ROLES_POR_CALCULO[calculo] = []
	ROLES_POR_CALCULO[calculo].append(rol)


def obtener_regla_calculo(rol_fiscal: str) -> dict | None:
	"""
	Obtiene reglas de cálculo para un rol fiscal específico.

	Función principal para acceder a reglas fiscales desde cualquier parte del sistema.
	Retorna None si el rol no tiene regla definida (permite bypass graceful).

	Args:
		rol_fiscal: Nombre exacto del rol fiscal (ej: "IVA por Pagar (Nacional)")

	Returns:
		dict: Diccionario con las reglas de cálculo, o None si no existe
			{
				"regla_base": str,        # monto_neto, cantidad, fila_previa_*, iva_trasladado
				"regla_calculo": str,     # porcentual, cuota, retención
				"cascada": bool,          # Incluye impuestos previos en base
				"alcance": str,           # por_item, fila_previa
				"habilitada": bool,       # Regla activa
				"fundamento_legal": str,  # Referencia legal
				"notas_calculo": str,     # Notas informativas
				"version": str,           # Control versión SAT
				"deprecada_desde": str    # Fecha deprecación (None si vigente)
			}

	Examples:
		>>> from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo
		>>> regla = obtener_regla_calculo("IVA por Pagar (Nacional)")
		>>> print(regla["regla_base"])
		"monto_neto"
		>>> print(regla["regla_calculo"])
		"porcentual"
		>>> print(regla["habilitada"])
		True

		>>> # Uso en función rectora
		>>> regla = obtener_regla_calculo(rol_fiscal)
		>>> if not regla:
		>>>     frappe.logger().warning(f"Sin regla para {rol_fiscal}")
		>>>     return  # Bypass graceful
		>>> if not regla["habilitada"]:
		>>>     frappe.logger().info(f"Regla {rol_fiscal} deshabilitada")
		>>>     return
		>>> # Aplicar lógica según regla...
	"""
	return REGLAS_POR_ROL.get(rol_fiscal)


def validar_cobertura_reglas() -> tuple[list[str], list[str]]:
	"""
	Valida que todos los roles fiscales tengan regla definida.

	Función de validación usada en tests de sincronización.
	Detecta roles sin regla y reglas huérfanas.

	Returns:
		tuple[list, list]: (roles_sin_regla, reglas_huerfanas)

	Examples:
		>>> from facturacion_mexico.utils.reglas_calculo_fiscal import validar_cobertura_reglas
		>>> roles_sin_regla, reglas_huerfanas = validar_cobertura_reglas()
		>>> assert len(roles_sin_regla) == 0, f"Roles sin regla: {roles_sin_regla}"
		>>> assert len(reglas_huerfanas) == 0, f"Reglas sin rol: {reglas_huerfanas}"
	"""
	from facturacion_mexico.utils.roles_fiscales import TODOS_LOS_ROLES

	# Roles sin regla definida
	roles_sin_regla = [rol for rol in TODOS_LOS_ROLES if rol not in ROLES_CON_REGLA]

	# Reglas huérfanas (rol no existe en roles_fiscales.py)
	reglas_huerfanas = [rol for rol in ROLES_CON_REGLA if rol not in TODOS_LOS_ROLES]

	return roles_sin_regla, reglas_huerfanas


def obtener_reglas_activas() -> dict:
	"""
	Retorna solo reglas habilitadas (habilitada=True).

	Útil para cachear reglas activas en memoria durante request.

	Returns:
		dict: Diccionario rol_fiscal → reglas (solo habilitadas)

	Examples:
		>>> from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_reglas_activas
		>>> reglas_activas = obtener_reglas_activas()
		>>> # Cache en frappe.local
		>>> frappe.local.reglas_fiscales_cache = reglas_activas
	"""
	return {rol: reglas for rol, reglas in REGLAS_POR_ROL.items() if reglas["habilitada"]}


def obtener_reglas_por_version(version: str) -> dict:
	"""
	Retorna reglas de una versión específica.

	Útil para auditoría o comparativa entre versiones SAT.

	Args:
		version: Versión SAT (formato YYYY.MM, ej: "2025.01")

	Returns:
		dict: Diccionario rol_fiscal → reglas (solo versión especificada)

	Examples:
		>>> from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_reglas_por_version
		>>> reglas_2025 = obtener_reglas_por_version("2025.01")
	"""
	return {rol: reglas for rol, reglas in REGLAS_POR_ROL.items() if reglas["version"] == version}
