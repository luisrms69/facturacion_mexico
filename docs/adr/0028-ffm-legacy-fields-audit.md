# ADR 0028 — Auditoría campos legacy FFM + desmantelamiento Sistema Resiliente

**Fecha:** 2026-05-17
**Actualizado:** 2026-05-18
**Estado:** Implementado — PR #142 mergeado + PR 4 en progreso
**Autor:** Luis Montanaro / Claude Sonnet 4.6

---

## Contexto

El DocType `Factura Fiscal Mexico` (FFM) acumuló campos a lo largo de múltiples iteraciones.
En agosto 2025 (PR #51 v15) se introdujo la arquitectura "Sistema Resiliente" — un sistema
de recovery automático de estados fiscales consultando al PAC en background. Ese sistema
**nunca se completó** y contiene defectos críticos documentados (escritura en /tmp que se
pierde en reinicio). Se migró íntegro a v16 en mayo 2026 sin que la decisión de mantenerlo
fuera explícita.

La decisión arquitectónica actual: **el único proceso automático con el PAC permitido**
es verificar cancelaciones pendientes (PENDIENTE_CANCELACION → CANCELADO). No hay más
reconciliación de estados en background.

---

## Sites analizados

| Site | Total campos FFM | Diferencias |
|---|---|---|
| `llantascs-v16.dev` | 59 | — |
| `facturacion-v16.dev` | 62 | 3 campos extra: `uuid`, `fm_fiscal_status`, `fm_uuid_fiscal` |

---

## Origen de los campos legacy

Los campos del Sistema Resiliente fueron introducidos en:
- **v15, PR #51, 11 agosto 2025** — `feat: arquitectura resiliente estados fiscales`
- **Migrados a v16, PR #80, 1 mayo 2026** — primer commit de migración (sin revisión)

---

## Grupo 1 — Sistema Resiliente (desmantelar completo)

### Campos FFM a eliminar del DocType JSON

| Campo | Motivo |
|---|---|
| `fm_document_type` | Select con default "invoice" — 0 referencias funcionales. Concepto de diferenciar tipos en un mismo DocType nunca prosperó |
| `fm_manual_override` | Guard de protección que bloquea updates automáticos de estado. Solo tiene efecto si el scheduler de recovery corre — que no corre |
| `fm_override_reason` | 0 referencias en v15 y v16 — metadato del override nunca implementado |
| `fm_override_by` | 0 referencias — ídem |
| `fm_override_timestamp` | 0 referencias — ídem |
| `fm_sub_status` | Sub-estado del sistema resiliente — sin UI ni lógica de negocio real |
| `section_break_sistema_resiliente` | Sección contenedora — eliminar con sus campos |
| `column_break_resiliente` | Column break de la sección — ídem |

### Archivos Python/JS para ELIMINAR completamente

| Archivo | Líneas | Función |
|---|---|---|
| `facturacion_fiscal/api_backup.py` | 589 | API de backup/recovery — escribe en /tmp, defecto crítico documentado |
| `facturacion_fiscal/doctype/fiscal_recovery_task/` | — | DocType "Fiscal Recovery Task" completo |
| `facturacion_fiscal/doctype/recovery_operations/` | — | DocType "Recovery Operations" completo |
| `config/fiscal_states_config.py` | — | Config estados resiliente: `FiscalStates`, `PROCESANDO`, `ARCHIVADO`, maquinaria de estados |

### Archivos que requieren CIRUGÍA (útil mezclado con resiliente)

| Archivo | Qué quitar | Qué conservar |
|---|---|---|
| `facturacion_fiscal/utils.py` | `should_override_status()`, `calculate_current_status()`, funciones que leen `fm_sync_status` para recovery | Utilidades fiscales no relacionadas con recovery |
| `facturacion_fiscal/tasks.py` | `_attempt_sync_recovery()` y scheduler de recovery | Verificación de cancelaciones pendientes (PENDIENTE_CANCELACION → CANCELADO) |
| `facturacion_fiscal/api/admin_tools.py` | Todo lo relacionado con `Fiscal Recovery Task` | Resto de herramientas admin |
| `validation/architecture_validator.py` | Validaciones de `fm_sync_status`, `fm_last_pac_sync`, `Fiscal Recovery Task` | Validaciones fiscales básicas |
| `public/js/fm_enums.js` | Estados `PROCESANDO`, `ARCHIVADO` | `BORRADOR`, `TIMBRADO`, `ERROR`, `CANCELADO`, `PENDIENTE_CANCELACION` |
| `public/js/fm_policy.js` | Referencias a `ARCHIVADO`, `CANCELACIÓN_PENDIENTE` legacy | Política de estados activos |

---

## Grupo 2 — Campos duplicados (decisión pendiente)

| Campo 1 | Campo 2 | Diagnóstico |
|---|---|---|
| `pdf_file` (Attach) | `fm_pdf_url` (Data URL) | **NO son duplicados** — `pdf_file` es adjunto real en tabFile; `fm_pdf_url` es URL temporal firmada FacturAPI. Conservar ambos. |
| `xml_file` (Attach) | `fm_xml_url` (Data URL) | Ídem |
| `cancellation_reason` (Select, texto completo) | `fm_motivo_cancelacion` (Select, código corto) | Redundancia real — mismo dato en dos formatos. Pendiente consolidar. |

---

## Grupo 3 — Campos solo en facturacion-v16.dev

| Campo | Diagnóstico |
|---|---|
| `uuid` | Campo original del UUID antes de `fm_uuid`. Marcado como eliminado en hooks.py. Pendiente limpiar fixtures de ese site. |
| `fm_fiscal_status` (en FFM) | Fue el campo original antes de migrar a `status`. Marcado como "Estado Fiscal (legacy)" en PR #102. |
| `fm_uuid_fiscal` | Comentado en hooks.py como "ELIMINADO". Artifact de migración. |

---

## Lo que SÍ se conserva

| Campo/Sistema | Razón |
|---|---|
| `PENDIENTE_CANCELACION` como estado | Flujo real de cancelaciones SAT |
| `fm_sync_status`, `fm_last_pac_sync`, `fm_sync_error` | Evaluar si el scheduler de cancelaciones los necesita; si no, eliminar también |
| `FacturAPI Response Log` DocType | Trazabilidad legítima — no es parte del Sistema Resiliente |
| `factura_fiscal_mexico.py` + `timbrado_api.py` | Core del sistema — cirugía puntual para quitar referencias al sistema resiliente |

---

## Alcance estimado del desmantelamiento

- **2 DocTypes a eliminar:** `Fiscal Recovery Task`, `Recovery Operations`
- **1 archivo a eliminar:** `api_backup.py` (589 líneas)
- **1 archivo a eliminar:** `config/fiscal_states_config.py`
- **8 campos a eliminar** del DocType JSON de FFM
- **5 archivos con cirugía** para remover funciones/secciones específicas
- **Fixtures:** exportar después de cambios al DocType

---

## Implementado — PR #142 mergeado

**PR 1:** Código recovery automático eliminado — `api_backup.py`, schedulers, funciones en `utils.py`/`tasks.py`, `admin_tools.py`, estados `PROCESANDO`/`ARCHIVADO`. Conservados: `cleanup_old_logs()`, `fm_sync_*`, `PENDIENTE_CANCELACION`.

**PR 2:** 8 campos legacy removidos del DocType JSON de FFM: `fm_document_type`, `fm_manual_override`, `fm_override_reason`, `fm_override_by`, `fm_override_timestamp`, `fm_sub_status`, section/column breaks. DocType: 64 → 56 campos. Columnas físicas en BD no eliminadas.

**PR 3:** `Fiscal Recovery Task` y `Recovery Operations` eliminados. Sin patch necesario — nunca existieron en producción.

**Fixes CodeRabbit/Semgrep:** type hint, normalización `operation_type` (bug activo), cleanup docstring y workspace.

## En progreso — PR 4 (cancelación canónica)

**Decisión:** `fm_motivo_cancelacion` = campo canónico código SAT. `cancellation_reason` = campo descriptivo/UI.

- `timbrado_api.py`: escribe `fm_motivo_cancelacion = motivo` al confirmar CANCELADO (antes se borraba)
- `fiscal_operations.py`: lee `fm_motivo_cancelacion` primero; fallback a `_extract_motive_code_from_reason()` para datos legacy
- `_extract_motive_code_from_reason()` conservada como compatibilidad

## Pendientes futuros

- [ ] `config/fiscal_states_config.py` — evaluar simplificación o eliminación
- [ ] Columnas físicas en BD de campos eliminados — cleanup opcional en release futuro
- [ ] `cancellation_reason` — evaluar eliminar cuando no haya datos legacy
- [ ] `fm_sync_status`, `fm_last_pac_sync`, `fm_sync_error` — conservar mientras exista scheduler de cancelaciones

---

## Referencias

- PR #142 mergeado — desmantelamiento Sistema Resiliente (PR 1+2+3+fixes)
- v15 PR #51 (2025-08-11): `feat: arquitectura resiliente estados fiscales`
- v16 PR #80 (2026-05-01): primer commit migración (campos heredados sin revisión)
- CLAUDE.md: "Recovery/resiliencia PAC — defecto crítico (datos en /tmp)"
- Issue #135 — refactor FFM JS (deuda técnica relacionada)
