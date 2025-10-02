# Changelog

Todos los cambios importantes a este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es/), y este proyecto se adhiere al [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Added
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