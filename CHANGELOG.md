# Changelog

Todos los cambios importantes a este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es/), y este proyecto se adhiere al [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Changed
- **Documentación sincronización JSON-Python roles fiscales** - Guía explícita proceso modificación roles
  - Agregada sección ⚠️ IMPORTANTE en `roles_fiscales.py` documentando limitación Frappe framework
  - Proceso 5 pasos: actualizar Python → actualizar JSON manualmente → migrate → script migración → tests validación
  - Referencia test sincronización: test_sync_roles_fiscales_json_python.py falla si JSON ≠ Python
  - Razón técnica: Select field en JSON DocType no puede importar constantes Python (framework limitation)
  - Archivo afectado: mapeo_cuenta_fiscal_mexico.json campo rol_fiscal.options
- **Reglas docs/instructions/ en CLAUDE.md** - Prohibición absoluta modificación por Claude
  - Sección nueva: "⚠️ REGLA ABSOLUTA: docs/instructions/"
  - Prohibido: crear/modificar/eliminar archivos en docs/instructions/
  - Permitido: solo lectura de archivos que usuario coloque
  - Clarificación: reportes → docs/development/, planes → docs/development/, análisis → docs/development/

### Added
- **Sistema single source of truth roles fiscales** - Eliminación completa hardcoded strings nomenclatura fiscal
  - Archivo `facturacion_mexico/utils/roles_fiscales.py` con TABLA_MAESTRA_ROLES_FISCALES (18 roles)
  - Constantes auto-generadas: ROL_IVA_NAC, ROL_IVA_FRO, ROL_IEPS_ALC, ROL_RET_ISR_HON, etc.
  - Nomenclatura semántica SAT: "IVA Nacional/Frontera" (NO hardcoded "16%/8%")
  - Retenciones unificadas: "IVA Retenido (Honorarios/Arrendamiento/Autotransporte/RESICO)"
  - Diccionarios derivados automáticos: ROLES_POR_CATEGORIA, TODOS_LOS_ROLES, ROL_TO_CONST
  - Pattern consistente con TABLA_MAESTRA_GRUPOS_FISCALES existente
- **Constantes roles fiscales completas** - Soporte matriz completa 8 retenciones + 5 IEPS
  - Agregadas 6 constantes retenciones: RET_IVA_ARR, RET_ISR_ARR, RET_IVA_AUTO, RET_ISR_AUTO, RET_IVA_RESICO, RET_ISR_RESICO
  - Total 18 constantes: 4 IVA + 5 IEPS + 8 Retenciones (IVA+ISR) + 1 Exento
  - Preparación para generación templates parcial (commit separado)
- **Sistema IEPS parcial - Generación templates con mapeos disponibles** - Soporte empresas con configuración fiscal incompleta
  - Función `_verificar_mapeos_disponibles()` - Verificación granular por cada IEPS/Retención (performance cache)
  - Generación parcial templates: solo filas con mapeos configurados (no bloqueo all-or-nothing)
  - Función `_build_rows()` retorna tuple `(rows, omitted)` - tracking filas omitidas por template
  - Función `_mostrar_resumen_generacion()` - Reporte consolidado: creados/omitidos/parciales
  - Autoselección fallback: si template específico no existe → usa "Básico" de misma zona
  - Try-catch per template: errores individuales no detienen batch generación
  - Validación IVA Nacional obligatorio (bloqueo temprano si falta mapeo crítico)
  - Caso uso: Licorería con solo IEPS Alcohol → template "IEPS" con 2 filas (IVA + Alcohol)
- **Testing E1 IEPS parcial** - Suite completa 6 casos verificados
  - Script test_ieps_parcial_e1.py: verificación mapeos/generación/idempotencia/naming/tax_rows
  - Validado: 8 templates generados sin errores, tax rows cargadas correctamente
  - Idempotencia verificada: re-ejecución no crea duplicados
  - Naming format: sin guiones largos "–", formato estándar " - "
- **Autoselección inteligente STCT** - Sistema automático según clasificación items y zona fiscal
  - Función `_determinar_variante_stct()` clasifica documento y retorna variante apropiada
  - Función `_find_stct_by_variant()` busca STCT exacto por zona + variante
  - Matriz decisión 2×4 = 8 combinaciones: Nacional/Frontera × Básico/IEPS/Retenciones/Total
  - Integración con hook `before_validate()` en Sales Invoice
  - Mensajes informativos: "Impuestos configurados automáticamente: IVA {tasa} - {variante}"
  - Eliminación completa filas $0 en facturas (solo filas necesarias según items)
  - Workflow: Sales Invoice → clasificar items → determinar zona → seleccionar STCT específico
- **Suite tests autoselección STCT** - Cobertura completa (7 tests - 0.420s)
  - Archivo facturacion_mexico/tests/test_autoseleccion_stct.py
  - Tests variantes: Básico, IEPS, Retenciones, Total
  - Tests búsqueda STCT por zona y variante
  - Test matriz decisión completa (8 combinaciones)
  - Determinista: sin red, sin reloj real, setUp() único
- **Documentación caso base templates fiscales** - Referencia completa templates generados post-migración nomenclatura
  - Archivo `docs/development/CASO_BASE_TEMPLATES_FISCALES.md` con estructura validada
  - Tabla detallada templates críticos: 0%, exentos, IEPS (4), Retenciones (4 categorías)
  - Análisis completo 14 STCT + 21 ITT generados
  - Detección 4 STCT + 3 ITT obsoletos (nomenclatura antigua pre-migración)
  - Resumen estadístico: 10 STCT habilitados, clasificación ITT por propósito
  - Guía uso recomendado templates según tipo documento
  - Notas técnicas: Rate 0% intencional, Tipo Factor SAT, Integra Base IVA, Withholding flag
  - Integración Sistema E1 Automated Tax: prelación templates vs cálculo dinámico
  - Procedimientos mantenimiento futuro: regeneración, validación, migración roles
- **Documentación validación generación parcial** - Tabla comparativa antes/después corrección checkboxes
  - Archivo `docs/development/TABLA_COMPARATIVA_GENERACION_PARCIAL.md` con validación completa
  - Comparación detallada: caso base (14 filas) vs generación parcial (8 filas)
  - Estado actual checkboxes: 4 IEPS disabled, 2 retenciones disabled
  - Validación 8/8 casos: checkbox disabled → fila omitida correctamente
  - Análisis ITT: generación independiente de checkboxes (decisión arquitectónica pendiente)
  - Resumen ejecutivo: 24 filas omitidas correctamente en templates Total/IEPS/Retenciones

### Fixed
- **Generación parcial templates - Lectura checkboxes incorrecta** - FIX CRÍTICO función `_verificar_mapeos_disponibles()`
  - Problema: Función leía solo `mapeo_cuentas` (child table) sin verificar checkboxes `enable_*`
  - Impacto: Templates generaban TODAS las filas aunque checkboxes disabled
  - Causa raíz: Implementación original no consideraba workflow UI (checkboxes → mapeos)
  - Corrección: Helper `_disponible(checkbox, rol)` valida `checkbox=True AND mapeo existe`
  - Archivo modificado: `generador_templates_fiscal.py:79-186`
  - Lógica correcta: IVA Nacional obligatorio, resto requiere checkbox enabled + mapeo
  - Validación: STCT "Total" redujo de 14 a 8 filas (6 omitidas según checkboxes disabled)
  - Testing: Script validación confirma 100% consistencia checkboxes ↔ templates generados
- **Fuente de verdad única Item Groups fiscales** - Consolidación TABLA_MAESTRA_GRUPOS_FISCALES
  - Tabla maestra única (10 filas): Item Group + ITT Pattern + Categoría Fiscal + Tipo
  - 5 constantes auto-generadas: ITEM_GROUP_ITT_MAP, ITEM_GROUP_CATEGORIA, CATEGORIAS_IEPS, CATEGORIAS_RETENCION, ITEM_GROUPS_FISCALES
  - Eliminadas 20+ constantes dispersas (IG_*, ITT_*_TITLE)
  - Código fallback legacy removido (búsqueda por title en _resolve_itt_name)
  - Mantenimiento simplificado: un solo lugar para modificar mapeos fiscales
- **Función clasificación items por categoría fiscal** - Preparación autoselección STCT
  - Función `clasificar_items_documento()` en facturacion_mexico/utils/clasificacion_items.py
  - Lee item.item_group directo (con cache Frappe)
  - Mapea Item Group → Categoría fiscal vía ITEM_GROUP_CATEGORIA
  - Detecta flags: tiene_ieps, tiene_retenciones
  - Retorna clasificación agregada: categorias[], items_por_categoria{}
  - Workflow: Sales Invoice items → categorías → preparado para matriz decisión STCT
- **Suite tests clasificación items** - Cobertura completa (7 tests - 0.455s)
  - Archivo facturacion_mexico/tests/test_clasificacion_items.py
  - Tests categorías: IEPS (4 tipos), Retenciones, Resto, documentos mixtos
  - Verificación constantes derivadas correctas
  - Determinista: sin red, sin reloj real, setUp() único
- **Sistema 8 STCT específicos para eliminar filas $0 en facturas** - Reemplazo templates consolidados
  - 8 templates nuevos: Nacional/Frontera × Básico/IEPS/Retenciones/Total
  - Template "IVA Nacional – Básico" (1 fila): solo IVA para facturas simples
  - Template "IVA Nacional – IEPS" (6 filas): IVA + 4 IEPS con cascada IVA
  - Template "IVA Nacional – Retenciones" (3 filas): IVA + ISR Ret + IVA Ret
  - Template "IVA Nacional – Total" (8 filas): todas las filas fiscales
  - Templates Frontera (4 variantes) con IVA 8% zona fronteriza
  - Deshabilitados 2 templates consolidados viejos (19 filas cada uno)
  - Naming semántico sin porcentajes hardcoded en títulos
  - Objetivo: eliminación completa de filas en $0.00 en Sales Invoices
- **Generación automática 18 Item Tax Templates (ITT)** - Desde Configuracion Fiscal Mexico
  - Función `generate_itt_for_company()` genera ITT basándose en mapeo cuentas
  - ITT Base IVA: 16%, 0%, Exento, 8% Frontera (4 templates)
  - ITT IEPS: Alcohol, Azúcar, Combustibles, Tabaco (4 templates)
  - ITT Retenciones: Honorarios, Arrendamiento, Autotransporte, RESICO (10 templates combinados)
  - Actualización automática al cambiar mapeo de cuentas
  - Asignación automática ITT a Item Groups después de generación
- **Resolución fuzzy de roles fiscales** - Mapeo flexible cuentas impuestos
  - Función `_get_account_head_by_role()` con match exacto + fuzzy fallback
  - Soporta nombres genéricos ("IVA Nacional") y legacy ("IVA 16%")
  - Keywords matching para variaciones: ["IVA por Pagar", "16"] → "IVA por Pagar (16%)"
  - Evita errores por diferencias nomenclatura entre sitios
- **Reescritura completa generador_templates_fiscal.py** - Simplificación arquitectura (-546 líneas)
  - Eliminada clase GeneradorTemplatesFiscales (arquitectura compleja)
  - Sistema funcional directo con 3 funciones principales
  - Sin dependencias constantes_fiscales.py
  - Código más mantenible y testeable
- **Suite tests completa E4 puente SI→PAC** - Testing E4.1-E4.8 (17 tests passing)
  - Archivo `facturacion_mexico/tests/test_e4_puente_si_pac.py` (510 líneas)
  - Tests unitarios E4.1: _read_taxes_from_sales_invoice_item() (2 tests)
  - Tests unitarios E4.2: _get_tax_amount_for_item_robust() fallback (3 tests)
  - Tests unitarios E4.3: _resolve_objeto_impuesto() (1 test)
  - Tests unitarios E4.4: _map_tax_account_to_sat() (1 test)
  - Tests unitarios E4.6: _validate_objeto_imp_consistency() (3 tests)
  - Tests unitarios E4.7: _validate_currency_consistency() (2 tests)
  - Tests unitarios E4.8: _validate_payload_completeness_ro() (4 tests)
  - Test smoke integración: validaciones E4.7 + E4.8 con payload completo (1 test)
  - Tiempo ejecución: 0.058s (cumple RG-003: ≤ 5 min)
  - Determinista: sin red, sin reloj real, mock solo gateway FacturAPI
  - Aislamiento: cada test crea datos únicos con setUp()
  - Cumplimiento RG-003: simplicidad, determinismo, pirámide testing
- **Documentación setup mapeos SAT** - Guía completa configuración sitios nuevos
  - Archivo `docs/user-guide/setup-mapeos-sat.md` (~600 líneas)
  - 5 ejemplos comunes: IVA 16%, ISR Ret 10%, IVA Ret 10.66%, IEPS Cuota, IVA 0%
  - Troubleshooting 3 casos frecuentes con soluciones
  - Script verificación: `verificar_mapeos_sat.py` uso documentado
  - Checklist setup sitio nuevo (8 pasos)
  - Campos requeridos tabla Mapeos Cuentas Fiscales explicados
  - Validaciones E4.8 explicadas (bloqueo timbrado sin mapeos)
- **Constante fiscal global PROPORCION_IVA_RETENIDO_SAT** - Precisión mejorada retenciones IVA
  - Constante global `PROPORCION_IVA_RETENIDO_SAT = 66.6667` (4 decimales) para 2/3 del IVA trasladado
  - Documentación SAT: proporción aplicable a TODOS los tipos de retención (Honorarios, Arrendamiento, Autotransporte, RESICO)
  - Precisión 4 decimales reduce error redondeo 10x vs 66.67% (2 decimales) en montos grandes
  - Principio DRY: single source of truth para cálculo IVA retenido (4 referencias unificadas)
  - Normativa SAT: IVA retenido SIEMPRE 2/3 del IVA trasladado (no varía por tipo retención)
- **Sistema completo retenciones RESICO (ISR + IVA)** - Soporte régimen fiscal simplificado
  - Checkbox `enable_ret_resico` en Configuracion Fiscal Mexico
  - Generación automática 2 roles fiscales: "ISR Retenido (RESICO)" + "IVA Retenido (RESICO)"
  - Trigger JavaScript para sincronización automática tabla mapeo cuentas
  - Validación roles mejorada con substring match para RESICO/Arrendamiento/Autotransporte
  - Integrado en STCT Opción B con rate 0 (tasa real vía ITT por ítem)
- **Sistema IEPS granular + Retenciones E2-E3 (Opción B)** - Arquitectura consolidada para supermercados y acreditamiento IEPS
  - Función `_obtener_stct_opcion_b()` genera STCT consolidados sin tax_category
  - Estructura 13 filas por STCT: pares IEPS+IVA cascada + IVA base + retenciones + mixto E1
  - Extracción dinámica tipos IEPS de MAPEO_ROLES_CONFIGURACION (4 tipos: Alcohol, Azúcar, Combustibles, Tabaco)
  - Cascada fiscal explícita: IVA "On Previous Row Amount" sobre cada tipo IEPS
  - Retenciones IVA/ISR con rate 0 (tasa real vía ITT por ítem)
  - Compatible mixto E1: filas IVA 0% y Exento neutralizan IVA por ítem
  - Flexibilidad única: granular (cuentas separadas IEPS) o consolidado (misma cuenta) según mapeo GL
  - Cumple requisito legal SAT: acreditamiento IEPS por tipo separado para supermercados
- **Sistema automatizado Item Groups con ITT assignment** - Garantía estructura fiscal en todos los sites
  - Módulo `facturacion_mexico/setup/item_groups.py` con funciones idempotentes
  - Creación automática grupos raíz: "Artículos con IVA al 0%" y "Artículos Exentos"
  - Hook after_install: ensure_groups_after_install() crea estructura base
  - Hook after_migrate: assign_itt_to_groups() asigna ITT por compañía
  - Búsqueda inteligente ITT por company suffix con fallback múltiple
  - Fixture `item_group_fiscal_structure.json` para zero-config deployment
  - Integración wizard E0.5: asignación ITT post-generación templates
  - Sistema multi-company: soporta múltiples empresas con ITT específicos
  - Idempotencia garantizada: re-ejecución sin duplicados ni errores
- **Sistema mixto ITT 0% + IVA normal en misma factura E1** - Implementación completa propuesta ChatGPT
  - Wizard E0.5 generador templates modificado: STCT con 3 filas fijas (16%/8%, 0%, exento)
  - ITT override con 3 entradas todas tax_rate=0 para anular STCT y dirigir base
  - ERPNext Item-wise Tax Detail funciona automáticamente con distribución correcta por línea
  - Validación real ACC-SINV-2025-01572: capacitación 0% + material oficina 8% funcionando
  - Hooks mejorados con integración get_item_tax_template() nativo ERPNext
  - JavaScript corregido: eliminado filtro for_selling problemático en búsqueda STCT

### Changed
- **Migración nomenclatura fiscal a constantes centralizadas** - Eliminación ~134 hardcoded strings
  - Archivo `constantes_fiscales.py`: 3 dicts principales usan constantes como keys
    - MAPEO_ROLES_CONFIGURACION: 18 roles con constantes (era strings hardcoded)
    - COMBINACIONES_ALCANCE: 10 alcances con listas de constantes
    - RETENCIONES_CONFIG: 4 tipos retención con campos rol_iva/rol_isr usando constantes
  - Archivo `sat_tipo_factor.py`: Dict CONFIGURACION con 16 constantes como keys
  - Archivo `configuracion_fiscal_mexico.py`: Todas las comparaciones rol_fiscal usan constantes
    - Método `_rol_requerido_por_alcance()`: 12 condiciones con constantes
    - Método `_obtener_roles_requeridos()`: Sets y adds con constantes
    - Variables roles_base usando constantes (era strings)
  - Tests actualizados (3 archivos): 51 líneas cambiadas de strings a constantes
    - test_hito1_constantes.py: 22 reemplazos
    - test_wizard_mapeo_fiscal.py: 26 reemplazos
    - test_e3_retenciones_precision.py: 3 reemplazos
  - Beneficio: Type safety en dicts, autocomplete IDE, refactoring seguro
  - BREAKING: Bases de datos existentes requieren migración datos (rol_fiscal strings → nuevos nombres)
- **UI Configuracion Fiscal Mexico** - Botón "Generate Templates" en toolbar principal
  - Eliminado botón "Preview Templates" (funcionalidad innecesaria)
  - Botón principal sin submenu para acceso directo
  - Mensaje éxito detallado muestra: STCT generados/deshabilitados + ITT actualizados
- **Estructura documentación** - Separación clara instrucciones usuario vs documentación técnica
  - `docs/instructions/` EXCLUSIVAMENTE para instrucciones usuario
  - `docs/development/` para planes implementación y reportes técnicos
  - Plan completo FASE 1-4 en `docs/development/PLAN_IMPLEMENTACION_8_STCT_AUTOSELECCION.md`
- **Sistema legacy TASAS_RETENCIONES deprecated** - Migración a arquitectura E3 moderna
  - Diccionario `TASAS_RETENCIONES` marcado como deprecated (sistema legacy pre-E3)
  - Sistema legacy calculaba IVA retención como % del neto (10.67% = 2/3 de 16%)
  - Sistema E3 actual calcula como % del IVA trasladado (66.6667% proporcional)
  - Comentarios documentan: "DEPRECATED: Usar RETENCIONES_CONFIG para sistema E3 actual"
  - Mantener solo para compatibilidad tests antiguos y sistema install.py legacy
  - Flag `deprecated: True` en entradas IVA retención para remoción futura
- **Arquitectura templates STCT migrada a Opción B consolidada** - Reemplazo completo arquitectura Hito 1 separada
  - Eliminadas 3 funciones obsoletas: `_obtener_templates_iva_base()`, `_obtener_templates_ieps_cascada()`, `_obtener_templates_retenciones()`
  - Función `_generar_stct()` modificada: usa solo `_obtener_stct_opcion_b()` como fuente única
  - Templates con tax_category (arquitectura separada Hito 1) no se generan más
  - BREAKING: Sites existentes requieren regeneración templates con wizard E0.5
  - Beneficio: un solo STCT consolidado por tasa IVA (16% y 8% frontera) en lugar de múltiples templates separados
- **Eliminación definitiva Tax Categories SAT obsoletas** - Sistema completamente limpio de dependencias SAT legacy
  - 20/20 Tax Categories formato SAT (patrón ^\d{3}\s-\s) eliminadas definitivamente
  - 6 Tax Categories normales conservadas (Retenciones, Exempt, Zero 0, General 16, _Test 1, _Test 2)
  - 131 referencias históricas Sales Invoice.tax_category limpiadas antes de eliminación
  - Customer.fm_tax_regime establecido como fuente canónica única para régimen fiscal
- **Optimización arquitectura régimen fiscal** - Eliminación redundancias y simplificación flujo datos
  - Custom field Sales Invoice.fm_tax_regime eliminado (redundante - FFM siempre usa Customer.fm_tax_regime)
  - Arquitectura optimizada: Customer.fm_tax_regime → FFM.fm_tax_system → CFDI/PAC
  - DocType Regimen Fiscal SAT disponible para futuras mejoras

### Fixed
- **Generación templates STCT** - Corrección método creación templates para carga correcta tax rows en UI
  - Fix root cause: pre-establecer 'name' impedía inicialización child tables en Frappe framework
  - Implementado método install.py: title SIN abbr, Frappe auto-naming agrega abbr automáticamente
  - Cambio generador línea 304: `title = f"IVA {zona} - {variant}"` (SIN abbr)
  - Cambio generador línea 234: Eliminado `"name": title` (NO pre-establecer 'name')
  - Búsqueda templates existentes ajustada para `title_with_abbr = f"{title} - {company_abbr}"`
  - Templates generados ahora cargan tax rows completas en UI correctamente
  - Eliminado doble sufijo " - _TC - _TC" en templates (ahora solo " - _TC")
  - Evidencia: Template "IVA 0% - México - _TC" (install.py) funcionaba, nuevos templates (name pre-establecido) no funcionaban
- **Carga automática tax rows en autoselección STCT** - Hook Python ahora carga filas completas desde template
  - Agregado `get_taxes_and_charges()` nativo ERPNext en `_set_stct_by_branch()`
  - Líneas 202-208 sales_invoice_automated_tax.py: import función + limpiar taxes + extend tax_rows
  - Fix crítico: antes solo seteaba `doc.taxes_and_charges` (campo template name), ahora carga tabla `taxes` completa
  - Resultado: autoselección STCT funcional con todas las filas de impuestos visibles en UI
  - Workflow completo: clasificar items → determinar STCT → asignar template → cargar tax rows
- **Código JavaScript legacy eliminado** - Limpieza completa lógica duplicada y mensajes legacy
  - Eliminada función `_fm_apply_branch_tax_template()` completa (68 líneas código legacy)
  - Eliminados mensajes duplicados "Impuestos configurados automáticamente: IVA 16% (México)"
  - Eliminada lógica búsqueda templates viejos (`like '%IVA 16%'`) en JavaScript
  - Función reemplazada por stub vacío con documentación delegación a Python hook
  - JavaScript 100% delegado a Python hook `before_validate()` en sales_invoice_automated_tax.py
  - Sin búsquedas duplicadas, sin mensajes legacy, sin conflictos Python ↔ JavaScript
  - Resultado: Sistema limpio, mensajes únicos, autoselección 100% server-side
- **IEPS Cuota item_wise_tax_detail con keys incorrectas** - Corregido uso de item.name en lugar de item.item_code
  - Problema: Función `_corregir_item_wise_tax_detail_ieps_cuota()` y `_ajustar_item_wise_tax_detail_iva_combustibles()` usaban `item.name` (ID interno como "svk1s4kt7p") en lugar de `item.item_code` (código legible como "TEST-IEPS-AZUCAR-001") como keys del diccionario
  - Impacto: ERPNext UI Tax Breakup mostraba datos inconsistentes, aunque payload PAC era correcto
  - Solución: 9 correcciones de `item.name` → `item.item_code` en funciones `calcular_ieps_cuota()`, `_congelar_iva_sobre_ieps_cuota()`, `_corregir_item_wise_tax_detail_ieps_cuota()`, y `_ajustar_item_wise_tax_detail_iva_combustibles()`
  - Validación PAC exitosa: Sales Invoice ACC-SINV-2025-01619, FFM FFMX-2025-00166, UUID 3B66AB8C-50E8-4E0A-A5EE-15B74C25EA95 (status: valid, timbrado exitoso)
  - Mejoras adicionales: agregar items no aplicables con [0.0, 0.0] para completitud UI, ensure_ascii=False en JSON dumps, precisión flt() para redondeo, verificación descripción IVA
  - Resultado: item_wise_tax_detail completo (4/4 items), keys correctas (item.item_code), montos correctos (IEPS Azúcar $7.62, IEPS Combustibles $219.60)
- **Fix crítico generación templates ITT/STCT** - Solución `DoesNotExistError` al crear templates nuevos
  - Método `_crear_o_actualizar_itt()` corregido: usa `frappe.new_doc()` + `doc.name = title` para nuevos
  - Método `_crear_o_actualizar_stct()` corregido: mismo patrón consistente
  - Lógica condicional: `insert()` para nuevos vs `save()` para existentes
  - Evita doble sufijo company en nombres templates (mantiene `name == title`)
  - Soluciona error framework Frappe intentando cargar documentos inexistentes
- **Fix row_id requerido para cascada fiscal** - STCT con "On Previous Row Amount" ahora funcionales
  - Agregado campo `row_id` automático cuando `charge_type` requiere referencia fila anterior
  - Soporta tanto "On Previous Row Amount" como "On Previous Row Total"
  - Soluciona ValidationError en save de STCT con impuestos cascada (IEPS → IVA)
- **Wrapper `_obtener_itt_granular()`** - Función helper consolidada para preview templates
  - Consolida llamadas a `_obtener_itt_base()`, `_obtener_itt_ieps()`, `_obtener_itt_retenciones()`
  - Protección `or []` previene errores si métodos devuelven None
  - Mejora mantenibilidad y reutilización código preview
- **Corrección `is_default` reintroducido** - STCT "IVA 16% - México" ya no marca como default automático
  - Valor corregido de `is_default: 1` → `is_default: 0` en `_obtener_stct_opcion_b()`
  - Previene aplicación automática incorrecta de template
  - Sistema usa Tax Rules con prioridades automáticas según contexto
- **Validación roles ampliada** - Mejora detección roles fiscales con substring match
  - Roles Arrendamiento, Autotransporte, RESICO ahora detectados correctamente
  - Función `_es_rol_requerido_segun_alcance()` usa substring en lugar de match exacto
  - Soluciona problema roles no reconocidos por variaciones nombre
- **Función extracción SAT régimen fiscal** - Corregida `_extract_tax_system_from_customer()` para usar `fm_tax_regime` en lugar de `tax_category` deprecado
  - factura_fiscal_mexico.py líneas 1178-1194 actualizadas
  - Auto-población FFM.fm_tax_system ahora funciona con campo migrado
  - Lógica extracción código SAT ("601") mantiene compatibilidad total
  - Test específico agregado: `test_extract_tax_system_function_uses_fm_tax_regime()`
  - Coverage testing función crítica CFDI completado (6/6 tests pasando)
- **Tests migration compatibility** - Actualizado para reflejar eliminación Sales Invoice custom field redundante
  - test_sales_invoice_custom_field_removed() verifica eliminación exitosa
  - Comentarios explicativos sobre razón eliminación (FFM no usa Sales Invoice.fm_tax_regime)

### Added
- **Testing migración tax_category → fm_tax_regime** - Test específico función `_extract_tax_system_from_customer()`
  - Validación fm_tax_regime usado correctamente en extracción código SAT
  - Verificación código "601" extraído de "601 - General de Ley Personas Morales"
  - Test customer vacío retorna None correctamente
- **Sistema automatizado de impuestos Sales Invoice Paso 2 completo** para automatización fiscal
  - Custom field Cost Center.fm_default_selling_price_list via fixture con filtro selling=1
  - Handlers Python completos con funciones helper robustas en sales_invoice_automated_tax.py
  - Prioridad Price List: Customer.default_price_list → Cost Center.fm_default_selling_price_list → Selling Settings.selling_price_list
  - Validación SAT corregida via Item.fm_producto_servicio_sat (no Sales Invoice Item)
  - JavaScript moderno async/await para UX inmediato en cambios cost_center
  - Bloqueos duales UI/servidor: obligatorio Cost Center y SAT configurado en Items
  - Arquitectura sin tax_category (ERPNext resuelve impuestos via STCT/Tax Rules)
  - Mapeo 1:1 Cost Center → Branch respetado con recálculo automático
  - Zero-config deployment con fixtures para campos custom
  - Testing checklist 6 casos aceptación + verificación automática campos
- **Wizard mapeo fiscal México E0.5 - Sistema mapeo manual completo** para configuración empresarial
  - DocType `Configuracion Fiscal Mexico`: configuración principal con checkboxes alcance fiscal
  - DocType `Mapeo Cuenta Fiscal Mexico`: tabla mapeo cuentas con validaciones y auditoría
  - UI inteligente: sincronización automática tabla ↔ checkboxes, filtrado cuentas por empresa
  - Matriz roles SAT completa: IVA (16%/8%/0%), IEPS, Retenciones ISR/IVA
  - Sistema read-only roles auto-generados, cannot_add_rows, validación Tax accounts
  - **Botón Preview Templates funcional** con diálogo preview de STCT/ITT a generar
  - **Manual usuario completo** 6 pasos detallados con troubleshooting (48 páginas)
- **Reportes técnicos sistema templates** para análisis y refactoring futuro
  - Reporte AS-IS estado actual: 29% implementación (4/14 templates)
  - Reporte técnico ChatGPT: propuesta refactoring arquitectura parametrizada
- **Sistema constantes centralizadas fiscales México** - Hito 1 refactoring templates
  - Módulo `constantes_fiscales.py`: punto único configuración tasas SAT (IVA, IEPS, retenciones)
  - Templates IEPS completos: 4 tipos con cascada IVA automática (alcohol, azúcar, combustibles, tabaco)
  - Templates retenciones completos: 6 tipos ISR/IVA con behavior "Deduct"
  - Funciones helper: obtener_tasa(), obtener_configuracion_por_rol(), es_impuesto_cascada()
  - Cobertura 14/14 templates (era 4/14): 100% sistema funcional

### Changed
- **Eliminación auto-detección cuentas** - Sistema 100% mapeo manual para mayor control
- **Menú botones cambiado** de "Acciones" a "Templates" para mayor claridad
- **Manual simplificado** eliminando Step 3.1 y 3.2 de auto-detección
- **Plan implementación fiscal mexicano E0-E8** para Issues #65 y #66
  - Documentación completa 8 etapas: Items SAT, IVA automático, IEPS, Retenciones, CFDI 4.0, Anticipos/Pagos 2.0
  - Análisis arquitectura SAT Items existente: ClaveProdServ, ClaveUnidad (UOM nativo), ObjetoImp
  - Decisión arquitectónica fundamentada: ObjetoImp por ClaveProdServ suficiente según normativa SAT
  - E0 completado: arquitectura actual es correcta, casos edge manejados vía Tax Rules
- **Generador templates fiscales refactorizado** - Arquitectura modular sin hardcode
  - Métodos especializados por tipo impuesto: IVA base, IEPS cascada, retenciones
  - Eliminado 100% hardcode tasas dispersas por constantes centralizadas
  - Cascada IEPS → IVA implementada con "On Previous Row Amount"
  - Retenciones configuradas correctamente como "Deduct" vs "Add"
  - Plan autocontenido en `docs/testing/planes/plan-fiscal-implementacion-mx-e0-e8/`
  - Branch `feat/mx-fiscal-E0-E3-issues-65-66` preparado para desarrollo
  - Reporte técnico completo con matriz decisión y ejemplos SAT oficiales
- **Testing unitario completo PR #68** - Suite de 11 test cases para sistema email automático CFDI
  - Cobertura 100% métodos nuevos: `send_invoice_email()`, `_resolve_recipient_email()`, `_resolve_auto_email_flag()`, `_send_fiscal_email()`
  - Tests determinísticos con mocks solo de gateway externo (FacturAPI)
  - Casos cubiertos: happy path, edge cases, error handling, lógica cascade customer tri-estado
  - Cumplimiento RG-003 CLAUDE.md: suite rápida (0.030s), sin dependencias externas
  - Archivo: `facturacion_mexico/tests/test_pr68_email_system.py`
- **Sistema completo envío automático CFDI por email** con configuración cascada Settings → Customer → FFM
  - Custom field Customer `fm_envio_email_cliente` (tri-estado: Default/Enviar/No enviar)
  - Custom field FFM `fm_enviar_email_timbrado` (check auto-configurado por cascada)
  - Lógica Python completa: resolución destinatario, envío FacturAPI, manejo errores
  - Botones JavaScript agrupados en dropdown "Comprobantes": "Descargar PDF+XML" y "Enviar por email"
  - Integración automática post-timbrado: envío email al asignar UUID exitosamente
  - Auto-configuración campo `fm_enviar_email_timbrado` en before_insert() con lógica cascade
  - Gestión centralizada botones UI en `applyFFMUi()` para comportamiento consistente
  - Método `send_invoice_email()` en FacturAPIClient para integración completa

### Fixed
- **Problema doble sufijo templates fiscales** - Normalización completa 23 templates (15 ITT + 8 STCT)
  - Root cause identificado: ERPNext autoname() concatenaba company_abbr al title que YA incluía sufijo
  - FASE 1: Generador modificado `frappe.new_doc()` → `frappe.get_doc(dict)` con name pre-establecido
  - FASE 2: Script normalización `normalize_template_names.py` ejecutado exitosamente
  - FASE 3: Búsqueda Item Groups optimizada con preferencia name exacto + fallback title
  - Resultado: name == title en 100% templates, Item Groups funcionales con ITT assignment
  - Archivos modificados: `generador_templates_fiscal.py`, `item_groups.py`
  - Scripts one-off: `normalize_template_names.py`, `verificar_solucion_completa.py`
  - Documentación: `docs/audit/reporte-problema-doble-sufijo-templates-2025-10-02.md`
- **Error crítico "Tax Template is mandatory"** en generación Tax Rules del wizard fiscal E0.5
  - Root cause: campo incorrecto `sales_taxes_and_charges_template` → `sales_tax_template` (ERPNext core validation)
  - Fix aplicado: corrección nombre campo + prioridades jerárquicas Tax Rules (General 16% máxima prioridad)
  - Resultado: generación exitosa 9 templates (4 STCT + 5 ITT + 4 Tax Rules) sin errores validación
- **Envío automático email CFDI** corregido problema resolución destinatario
  - Unificada lógica email recipient: eliminada función duplicada `_resolve_email_recipient()`
  - Envío automático ahora usa misma función que botón manual (`_resolve_recipient_email()`)
  - Prioridad correcta: `FFM.fm_email_facturacion` → `Settings.customer_email_fallback`
  - Agregada notificación usuario cuando falta configuración email
  - Eliminado código obsoleto de trigger duplicado y logs debugging
  - Corregidos errores sintaxis después de limpieza código
- Corregida indentación `on_successful_stamp()` (era función independiente, ahora método de clase)
- **Sistema templates incompleto** - IEPS y retenciones prometidas por wizard ahora generadas
- **Hardcode tasas fiscales** - Centralización permite mantenimiento sencillo
- **Testing inconsistente** - Suite 22 tests validando constantes y generación completa
- Eliminado prompt innecesario en botón "Enviar CFDI por email" - ahora envía directamente
- Persistencia botones UI después de refresh (Ctrl+Shift+R) mediante gestión centralizada
- Comportamiento consistente botones custom siguiendo patrón "Cancelar en FacturAPI"

### Changed
- Reposicionado campo `fm_enviar_email_timbrado` a sección principal (después de customer)
- Botones "Descargar" y "Enviar" agrupados en dropdown "Comprobantes" para mejor UX
- Todos los botones custom gestionados centralizadamente en `applyFFMUi()` en lugar de `refresh()`
- Títulos botones simplificados: "Descargar PDF+XML" y "Enviar por email" (más concisos)

### Removed
- Botón "Test Conexión PAC" (ya no requerido según especificaciones)
- Código duplicado gestión botones en función `refresh()`
- Función `addHelpButtonForSubstitution()` (lógica movida inline para consistencia)

- Validación RFC SAT automática con integración FacturAPI
- Sistema deadlock resolution para FFM sin timbre (cancel_ffm_keep_si)
- Filtro guard cancelación SI: solo FFM submitted bloquean cancelación
- Descarga automática acuse de cancelación CFDI (PDF + XML) tras cancelación exitosa

### Changed
- Normalización Unicode NFC para preservar caracteres especiales (Ñ) en validación RFC
- Guard cancelación Sales Invoice: docstatus != 2 → docstatus = 1 (solo submitted)

### Fixed
- Bug crítico mapeo estados fiscales cancelación: sistema forzaba "CANCELADO" sin leer respuesta PAC real
- Botón "Cancel/Cancelar" nativo aparecía indebidamente en FFM causando confusión de usuarios
- Mensaje persistente "Cancelación bloqueada" por FFM en borrador vinculadas
- Sanitización caracteres especiales (Ñ) en payload RFC validation y timbrado
- Error AttributeError cfdi_uuid → fm_uuid en funciones cancelación
- Bypass controlado cancelación FFM local sin timbre con flags.allow_local_cancel

## [0.5.1] - 2025-09-17

### Added
- Sistema tipo de comprobante CFDI (I=Ingreso, E=Egreso, T=Traslado bloqueado)
- Configuración SAT para tipos de comprobante y relaciones fiscales
- Validaciones automáticas tipo comprobante basadas en contexto Sales Invoice
- API SAT options para obtener catálogos fiscales dinámicamente
- Soporte relaciones fiscales para notas de crédito (tipo E)
- Armonización direcciones FFM-ERPNext para consistencia completa
- Sistema unificado validación RFC/CSF Customer con banner único y sección oculta
- Eliminación definitiva campos duplicados "Régimen Fiscal" en Customer DocType

### Changed
- RG-003 simplificado: eliminadas 4 capas complejas por 3 niveles prácticos
- Testing approach: unit → service(DB) → smoke integración
- Mocking strategy: solo gateway externo, NO framework core
- Comandos parametrizados con variables SITE/APP

### Fixed
- Arquitectura resiliente estados fiscales
- API structure conflict resolution
- Critical State Fixes migración categorías fiscales
- Inconsistencia direcciones entre Customer UI y FFM ("Dirección Principal Formateada" vacía)
- Mensajes contradictorios validación RFC/CSF (múltiples indicadores con estados diferentes)
- Duplicación confusa campos "Régimen Fiscal" en Customer (eliminados fm_regimen_fiscal, fm_informacion_fiscal_mx_section, fm_column_break_fiscal_customer)

### Removed
- SQL directo en tests (reemplazado por rollback transaccional)
- Layer 4 config testing (over-engineering)
- setUpClass/tearDownClass SQL cleanup patterns
- Sección "Información Fiscal México" completa en Customer (limpieza arquitectónica)

## [5.0.0] - 2025-09-16

### Added
- Sistema completo cancelaciones fiscales CFDI - Milestone 4 workflow 02/03/04
- API structure conflict resolution y UX mejoras PAC
- Arquitectura resiliente estados fiscales - sistema completo
- Fiscal Architecture: Complete Tax Category Migration + Critical State Fixes
- Sistema logging fiscal + restauración módulos Custom Fields

### Changed
- Framework: Migración a Frappe v15
- Sistema Control: Claude Code + Sistema Buzola Integrado
- Testing: Layer 4 SPRINT6 testing complete

### Security
- Multi-layer security: 3 capas (Permisos + Backend + UI)
- Defense in depth operaciones críticas
- Validaciones server-side obligatorias

## [4.x.x] - Versiones Anteriores

Ver commits históricos para cambios de versiones anteriores al sistema de control actual.

---

**Convenciones:**
- `Added` - Nuevas funcionalidades
- `Changed` - Cambios en funcionalidades existentes
- `Deprecated` - Funcionalidades que serán removidas
- `Removed` - Funcionalidades removidas
- `Fixed` - Corrección de bugs
- `Security` - Cambios relacionados con seguridad