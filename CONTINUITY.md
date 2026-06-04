# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-04
**Rama activa:** `feature/cfdi-recibidos-fase2-configuracion-fiscal`
**Tarea actual:** Configuración fiscal CFDI Recibidos — templates y reclasificación IVA compras

---

## Recuperación rápida

Estoy trabajando en:
Completar Fase 2 de configuración en actiglobal-restore.dev: wizard genera templates para compras
(XML/Actual + porcentuales por tasa), reclasificación de IVA al pagar extiende a compras.

Objetivo inmediato:
Commit de los cambios actuales → push → restore en producción (next.actiglobal.com)

Criterio de avance:
Commit creado, push hecho, backup de actiglobal-restore.dev disponible para restore.

---

## Estado actual

### Ya cerrado
- Fase 2 configurada en actiglobal-restore.dev ✅
- wizard genera PTCT Actual (para XML) + PTCT porcentual por tasa activa ✅
- cargar_reglas extiende a compras desde Configuracion CFDI Recibidos ✅
- source_type "Gastos / CFDI Recibidos" agregado al DocType ✅
- tests wizard_manual_templates 7/7 ✅
- bench migrate en actiglobal-restore.dev y test-facturacion.localhost ✅

### Pendiente inmediato
1. Commit + push de esta rama
2. Backup actiglobal-restore.dev → restore en next.actiglobal.com
3. install-app facturacion_mexico en producción + migrate
4. Verificar Fase 3 en producción (customers con RFC, items con clave SAT)

### No repetir
- No commitear en main
- Los tests de reclasificación fallaban porque test site no tenía migrate — ya se corrió
- account_number es número operativo, NO el Código Agrupador SAT

---

## Decisiones vigentes
- A partir de v1.0.0: facturacion_mexico es sistema en producción
- wizard genera DOS tipos de PTCT: Actual (para XML) + porcentual (para PIs manuales)
- template porcentual de mayor tasa queda con is_default=1
- cargar_reglas en Configuracion Reclasificacion lee de CFM (Cobros) Y CFDI Recibidos (Pagos)
- Cuota SAT no genera template porcentual (monto fijo/unidad, no porcentaje)

---

## Archivos relevantes ahora

### Probablemente editar (post-commit)
- ninguno — commit limpia el estado

### No tocar
- one_offs/ — no se commitean
- working_docs/active/addenda_la_comer_evidencia/ — evidencias cliente
