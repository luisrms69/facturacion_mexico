# Changelog

Todos los cambios importantes a este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es/), y este proyecto se adhiere al [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Added
- **Wizard mapeo fiscal México E0.5 - DocTypes fundacionales** para resolver Chart of Accounts empresariales
  - DocType `Configuracion Fiscal Mexico`: configuración principal con checkboxes alcance fiscal
  - DocType `Mapeo Cuenta Fiscal Mexico`: tabla mapeo cuentas con validaciones y auditoría
  - UI inteligente: sincronización automática tabla ↔ checkboxes, filtrado cuentas por empresa
  - Matriz roles SAT completa: IVA (16%/8%/0%), IEPS, Retenciones ISR/IVA
  - Sistema read-only roles auto-generados, cannot_add_rows, validación Tax accounts
  - Base sólida para auto-detección y generación templates (Puntos 2-5 pendientes)
- **Plan implementación fiscal mexicano E0-E8** para Issues #65 y #66
  - Documentación completa 8 etapas: Items SAT, IVA automático, IEPS, Retenciones, CFDI 4.0, Anticipos/Pagos 2.0
  - Análisis arquitectura SAT Items existente: ClaveProdServ, ClaveUnidad (UOM nativo), ObjetoImp
  - Decisión arquitectónica fundamentada: ObjetoImp por ClaveProdServ suficiente según normativa SAT
  - E0 completado: arquitectura actual es correcta, casos edge manejados vía Tax Rules
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
- **Envío automático email CFDI** corregido problema resolución destinatario
  - Unificada lógica email recipient: eliminada función duplicada `_resolve_email_recipient()`
  - Envío automático ahora usa misma función que botón manual (`_resolve_recipient_email()`)
  - Prioridad correcta: `FFM.fm_email_facturacion` → `Settings.customer_email_fallback`
  - Agregada notificación usuario cuando falta configuración email
  - Eliminado código obsoleto de trigger duplicado y logs debugging
  - Corregidos errores sintaxis después de limpieza código
- Corregida indentación `on_successful_stamp()` (era función independiente, ahora método de clase)
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