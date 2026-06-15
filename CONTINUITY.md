# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-15
**Rama activa:** `fix/facturapi-response-log-permissions`
**Tarea actual:** Fix urgente producción — PermissionError en insert de FacturAPI Response Log al timbrar FFM

---

## Recuperación rápida

Estoy trabajando en:
Migración de Complementos de Pago PPD del sistema legacy `facturacion_mx` al nuevo DocType `Complemento Pago MX` en `facturacion_mexico`. Site de trabajo: `llantascs-mig.local`.

Plan que estoy siguiendo:
`working_docs/active/PLAN_MIGRACION_COMPLEMENTOS_PPD.md`

Objetivo inmediato:
Pendiente decidir con el cliente los casos especiales (PUE, cancelados, mixtos, folios sin legacy).

Criterio de avance:
Todos los complementos PPD válidos migrados, pendientes documentados y entregados al cliente.

---

## Estado actual

### Ya cerrado
- 3,545 CPMX creados en `llantascs-mig.local` (`COMP-PAY-MX-HIST-2026-00001` a `03545`)
  - 3,363 Grupo Directo (1 IO, PPD, valid/none, con FFM)
  - 182 Grupo Multi-IO (PPD vigentes, mismo UUID, confirmados por FacturAPI)
- Auditoría aprobada: 0 duplicados, 0 errores, 0 PE inválidos
- Campo `fm_creation_source` en CPMX — commiteado en este turno
- Documentación actualizada: `arquitectura.md` + `complemento-pago.md`
- Análisis completo de los 346 multi-IO clasificados y documentados
- 7 folios faltantes vs FacturAPI investigados y documentados

### En progreso
- Nada en ejecución activa

### Pendiente inmediato
1. Entregar al cliente tabla de 25 PUE vigentes para cancelación ante SAT
2. Cliente decide los 10 PPD cancelados (¿sustituto o definitivo?)
3. Cliente decide los 5 mixtos PPD+PUE (¿cancelar o mantener?)
4. Cliente decide P-57, P-2595/2596, P-3235 (folios sin legacy)
5. Export de fixtures tras bench migrate (campo fm_creation_source en CPMX)
6. PR de esta rama cuando el cliente haya resuelto los pendientes

### No repetir
- NO crear CPMX sin verificar `fm_es_ppd=1` en todas las SIs del PE
- NO usar `COUNT(io.name)` para detectar multi-IO cuando hay múltiples SIs (da falso positivo)
- NO confiar en IO local para estado SAT — siempre verificar FacturAPI para casos con pending/verifying
- NO restaurar backup sin safe-point previo documentado
- NO crear archivos nuevos en working_docs/active — solo secciones adicionales al final

---

## Decisiones vigentes
- `fm_creation_source = "Migración legacy facturacion_mx"` en todos los CPMX creados por migración
- `can_cancel` bloqueado para complementos migrados — cancelación solo vía SAT/FacturAPI directa
- Los 24 PUE 1-IO + 1 PUE multi-IO = 25 en total para cancelación cliente
- Los 150 PUE multi-IO cancelados en SAT → no requieren acción
- Site de trabajo: `llantascs-mig.local` (site de migración, no producción)

---

## Archivos relevantes ahora

### Leer primero
- `working_docs/active/PLAN_MIGRACION_COMPLEMENTOS_PPD.md` — estado completo y pendientes

### Probablemente editar
- `facturacion_mexico/fiscal_state/complemento_state.py` — si se ajusta lógica can_cancel
- `facturacion_mexico/fixtures/custom_field.json` — si se exportan fixtures

### No tocar
- `facturacion_mexico/one_offs/` — scripts temporales, no commitear
- `patches.txt` — está vacío por diseño (RG-010b)

---

## Riesgos / cuidados
- `llantascs-mig.local` tiene 3,545 CPMX — cualquier `bench restore` los perdería
- El campo `fm_creation_source` existe en BD post-migrate pero fixtures aún no exportados
- P-2595 y P-2596 son posiblemente CFDIs duplicados en FacturAPI para el mismo PE

---

## Información faltante
- Estado de P-57: ¿quién lo emitió directamente en FacturAPI?
- Decisión del cliente sobre los 10 PPD cancelados sin sustituto
- Decisión del cliente sobre los 5 mixtos PPD+PUE
