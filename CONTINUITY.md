# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-14
**Rama activa:** `feat/ffm-migracion-legacy-fase2`
**Tarea actual:** Migración histórica FFM legacy → facturacion_mexico (Fase 2 Grupo 1 completo)

---

## Recuperación rápida

Estoy trabajando en la migración de CFDIs históricos de `facturacion_mx` (legacy) a
`facturacion_mexico` (nuevo). El Grupo 1 (10,924 FFMs) está completamente migrado y auditado.

Plan que estoy siguiendo:
`working_docs/active/REPORTE_MIGRACION_GRUPO1_COMPLETO.md`

Objetivo inmediato:
Abrir PR para los cambios de código de la Fase 2. Luego procesar pendientes (Grupo 2, duplicados).

Criterio de avance:
PR mergeado + pendientes clasificados para próxima sesión.

---

## Estado actual

### Ya cerrado
- Fase 1: 1,790 items (fm_producto_servicio_sat) + 1,432 customers (fm_uso_cfdi_default)
- Grupo 1 Fase 2: 10,924 FFMs creadas — 0 errores — auditoría 14/14 OK
- Fix fm_xml_url → Small Text (URLs SAT >140 chars)
- Fix botón Descargar PDF+XML → descargar_archivos_cfdi() en timbrado_api.py
- +fm_creation_source en FFM DocType JSON
- +Método de Pago en widget fiscal de Sales Invoice

### En progreso
- PR feat/ffm-migracion-legacy-fase2 → pendiente push y apertura

### Pendiente inmediato
1. `/ship push` + `/ship pr`
2. Grupo 2 (46 dudosos) — procesar con `verify_api=True`
3. 636 SIs con múltiples Invoice Objects — revisión manual
4. 611 UUIDs duplicados en dataset — revisar si corresponde misma SI

### No repetir
- No correr bench migrate sin --site explícito en este bench compartido
- No commitear archivos de one_offs/ ni working_docs/
- No usar python3 directo para operaciones de BD — siempre bench execute

---

## Decisiones vigentes
- Opción D (A parcial estricta): solo Grupo 1 en primera corrida, Grupo 2 con verify_api después
- fm_lugar_expedicion = "03810" fijo para LlantasCS (único CSD, sin branches con ZIP)
- naming_series FFMs históricas: `FFM-HIST-.YYYY.-` para distinguir de timbrado normal
- db_insert() + docstatus=1 + ignore_validate/mandatory — no .submit() para evitar hooks
- Grupo 3 (cancelados): 0 detectados en dataset actual

---

## Archivos relevantes ahora

### Leer primero
- `working_docs/active/REPORTE_MIGRACION_GRUPO1_COMPLETO.md` — estado completo Fase 2
- `facturacion_mexico/one_offs/migrate_ffm_historicas.py` — script principal
- `facturacion_mexico/one_offs/test_migrate_ffm_historicas.py` — 37 tests + auditoría

### Probablemente editar
- `migrate_ffm_historicas.py` — para procesar Grupo 2 con verify_api=True

### No tocar
- `patches.txt` — vacío por diseño, no reactivar patches legacy
- Archivos en `one_offs/` — no commitear

---

## Riesgos / cuidados
- 636 SIs con múltiples Invoice Objects excluidas — si se migran manualmente, verificar
  que el UUID no ya exista en FFM antes de insertar
- fm_creation_source es Select sin reqd — si queda vacío en FFM nueva, no bloquea timbrado
  pero rompe la distinción de origen

---

## Información faltante
- Credenciales FacturAPI producción para llantascs-mig.local (necesarias para descarga PDF/XML)
- Decisión final sobre 46 casos Grupo 2 (verify_api o descarte)
