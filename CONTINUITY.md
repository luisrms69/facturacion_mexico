# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-11
**Rama activa:** `fix/mode-of-payment-formato-legacy`
**Tarea actual:** PR abierto — fix Mode of Payment formato legacy

---

## Recuperación rápida

Estoy trabajando en:
Estandarización del formato de Mode of Payment a "NN Descripción" (sin guion) para
alinear el app con el formato real de los datos históricos migrados desde facturacion_mx.

Plan que estoy siguiendo:
Merge del PR → deploy en staging ActiGlobal → verificación funcional → deploy producción →
cleanup one_off en producción.

Objetivo inmediato:
Merge de este PR. Los cambios ya fueron limpiados en todos los sites de desarrollo.

Criterio de avance:
main con el fix. Complementos PPD funcionan con mode_of_payment "03 Transferencia".

---

## Estado actual

### Ya cerrado
- ✅ PR #190 — UOM legacy + precios IVA incluido

### En progreso
- PR fix/mode-of-payment-formato-legacy — abierto

### Pendiente inmediato post-merge
1. Restore backup ActiGlobal producción → actiglobal-restore.dev
2. Deploy nuevo código en restore.dev + migrate + build
3. Dry-run cleanup_mop_canonical en restore.dev
4. Cleanup real en restore.dev
5. Verificación funcional (PE + complemento PPD)
6. Si pasa → deploy producción ActiGlobal
7. Subir one_off al servidor producción vía SCP
8. Dry-run + cleanup en producción
9. Backup nuevo post-cambio

### No repetir
- "99 - Por definir" (con guion) ya no es el estándar — usar "99 Por definir"
- cleanup_mop_canonical.py requiere dry_run primero antes de ejecución real
- LlantasCS staging: "99 - Por definir" conservado (tiene 6 FFMs referenciándolo)
- ignore_links=True nunca en delete_doc de Mode of Payment

---

## Decisiones vigentes

- Estándar único: "NN Descripción" sin guion para Mode of Payment
- Regex: `^(\d{2}) (?!-).+$` rechaza explícitamente el guion
- one_off cleanup_mop_canonical.py es el mecanismo para sitios existentes
- UOM NO cambia fixture — normalización en código ya funciona para ambos formatos

---

## Riesgos

- LlantasCS-v16.dev: "99 - Por definir" tiene 6 FFMs referenciándolo — no se puede
  eliminar hasta que esas FFMs sean sustituidas o canceladas
- ActiGlobal producción: requiere SCP del one_off script antes de poder ejecutar cleanup
