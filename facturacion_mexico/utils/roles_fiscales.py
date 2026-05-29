"""
SINGLE SOURCE OF TRUTH - Roles Fiscales México
==============================================
Todos los roles fiscales definidos en UN SOLO LUGAR.
NUNCA modificar roles directamente en otro archivo.

Nomenclatura:
- IVA: Nacional/Frontera (SIN porcentajes hardcoded)
- IEPS: Por categoría producto
- Retenciones: IVA/ISR por tipo servicio

⚠️ IMPORTANTE - SINCRONIZACIÓN CON JSON DOCTYPE:
--------------------------------------------------
Este archivo es la FUENTE CANÓNICA de roles fiscales.
Sin embargo, el campo Select en DocType JSON requiere duplicación:

Archivo: facturacion_mexico/facturacion_fiscal/doctype/mapeo_cuenta_fiscal_mexico/mapeo_cuenta_fiscal_mexico.json
Campo: rol_fiscal.options

RAZÓN: Frappe framework requiere opciones Select en JSON (no puede importar Python).

PROCESO AL MODIFICAR ROLES:
1. Actualizar TABLA_MAESTRA_ROLES_FISCALES aquí
2. Actualizar opciones Select en JSON DocType manualmente
3. Ejecutar bench migrate
4. Ejecutar script migración datos (one_offs/)
5. Tests de sincronización validan que JSON == constantes Python

TEST VALIDACIÓN: test_sync_roles_fiscales_json_python.py
Falla automáticamente si JSON y Python se desincronizaron.

Uso:
    from facturacion_mexico.utils.roles_fiscales import ROL_IVA_NAC, ROL_IVA_FRO, ...
"""

# Tabla maestra: (constante, rol_fiscal_exacto, categoria, descripcion)
TABLA_MAESTRA_ROLES_FISCALES = [
	# IVA - Nombres semánticos SIN porcentajes variables
	("IVA_NAC", "IVA por Pagar (Nacional)", "IVA", "IVA Nacional"),
	("IVA_FRO", "IVA por Pagar (Frontera)", "IVA", "IVA Frontera"),
	("IVA_CERO", "IVA por Pagar (0% exportación)", "IVA", "IVA 0% Exportación"),
	("IVA_EXENTO", "IVA Exento", "IVA", "IVA Exento"),
	# IEPS por categoría
	("IEPS_ALC", "IEPS por Pagar (Alcohol)", "IEPS", "IEPS Alcohol"),
	("IEPS_AZU", "IEPS por Pagar (Azúcar/Bebidas)", "IEPS", "IEPS Azúcar/Bebidas"),
	("IEPS_COMB", "IEPS por Pagar (Combustibles)", "IEPS", "IEPS Combustibles"),
	("IEPS_TAB", "IEPS por Pagar (Tabaco)", "IEPS", "IEPS Tabaco Tasa"),
	("IEPS_TABQ", "IEPS por Pagar (Tabaco Cuota)", "IEPS", "IEPS Tabaco Cuota"),
	# Retenciones IVA
	("RET_IVA_HON", "IVA Retenido (Honorarios)", "RETENCION", "Retención IVA Honorarios"),
	("RET_IVA_ARR", "IVA Retenido (Arrendamiento)", "RETENCION", "Retención IVA Arrendamiento"),
	("RET_IVA_AUTO", "IVA Retenido (Autotransporte)", "RETENCION", "Retención IVA Autotransporte"),
	("RET_IVA_RESICO", "IVA Retenido (RESICO)", "RETENCION", "Retención IVA RESICO"),
	# Retenciones ISR
	("RET_ISR_HON", "ISR Retenido (Honorarios)", "RETENCION", "Retención ISR Honorarios"),
	("RET_ISR_ARR", "ISR Retenido (Arrendamiento)", "RETENCION", "Retención ISR Arrendamiento"),
	("RET_ISR_AUTO", "ISR Retenido (Autotransporte)", "RETENCION", "Retención ISR Autotransporte"),
	("RET_ISR_RESICO", "ISR Retenido (RESICO)", "RETENCION", "Retención ISR RESICO"),
	# IVA acreditable — compras (traslados recibidos de proveedores)
	("IVA_ACR_NAC", "IVA Acreditable (Nacional)", "IVA_COMPRAS", "IVA 16% acreditable en compras"),
	("IVA_ACR_FRO", "IVA Acreditable (Frontera)", "IVA_COMPRAS", "IVA 8% acreditable en compras"),
	("IVA_ACR_CERO", "IVA Acreditable (0% exportación)", "IVA_COMPRAS", "IVA 0% exportación acreditable"),
	("IEPS_ACR", "IEPS Acreditable", "IEPS_COMPRAS", "IEPS acreditable en compras"),
]

# Auto-generar constantes ROL_* desde tabla maestra
for const_name, rol_exacto, _, _ in TABLA_MAESTRA_ROLES_FISCALES:
	globals()[f"ROL_{const_name}"] = rol_exacto

# Diccionarios útiles auto-generados
ROLES_POR_CATEGORIA = {}
for _, rol_exacto, categoria, _ in TABLA_MAESTRA_ROLES_FISCALES:
	if categoria not in ROLES_POR_CATEGORIA:
		ROLES_POR_CATEGORIA[categoria] = []
	ROLES_POR_CATEGORIA[categoria].append(rol_exacto)

TODOS_LOS_ROLES = [rol for _, rol, _, _ in TABLA_MAESTRA_ROLES_FISCALES]

# Mapeo inverso: rol_exacto -> constante
ROL_TO_CONST = {rol: const for const, rol, _, _ in TABLA_MAESTRA_ROLES_FISCALES}

# Nota: __all__ no es necesario aquí - todas las constantes ROL_* se exportan automáticamente
# Python exporta automáticamente todo lo que no empiece con underscore
