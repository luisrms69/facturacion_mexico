# Changelog

Todos los cambios importantes a este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es/), y este proyecto se adhiere al [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Added
- Sistema tipo de comprobante CFDI (I=Ingreso, E=Egreso, T=Traslado bloqueado)
- Configuración SAT para tipos de comprobante y relaciones fiscales
- Validaciones automáticas tipo comprobante basadas en contexto Sales Invoice
- API SAT options para obtener catálogos fiscales dinámicamente
- Soporte relaciones fiscales para notas de crédito (tipo E)
- Sistema completo cancelaciones fiscales CFDI
- Workflows 01/02/03/04 según normativa SAT
- Override class para múltiples FFMs (LinkExistsError)
- Testing framework simplificado y eficaz
- Documentación oficial estructura docs/
- Armonización direcciones FFM-ERPNext para consistencia completa

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

### Removed
- SQL directo en tests (reemplazado por rollback transaccional)
- Layer 4 config testing (over-engineering)
- setUpClass/tearDownClass SQL cleanup patterns

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