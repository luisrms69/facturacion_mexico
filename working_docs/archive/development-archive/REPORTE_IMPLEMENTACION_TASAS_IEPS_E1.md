# REPORTE IMPLEMENTACIÓN: TASAS IEPS DESDE CONSTANTES (E1)

**Fecha:** 2025-10-26
**Branch:** feature/e1-automated-tax-system
**Objetivo:** Corregir tasas IEPS Tasa (Alcohol/Tabaco) desde constantes_fiscales.py

---

## RESUMEN EJECUTIVO

**CAMBIOS IMPLEMENTADOS:**
✅ Modificado `generador_templates_fiscal.py` para leer tasas IEPS desde constantes
✅ ITT regenerados con tasas correctas (Alcohol 26.5%, Tabaco 160%)
✅ IEPS Tasa ahora calcula correctamente ($874.50 + $800.00 = $1,674.50)
❌ **PROBLEMA BLOQUEANTE:** Filas IVA del STCT se pierden con múltiples items

**PROGRESO:**
- Grand Total: $6,432.02 (antes) → $7,149.34 (ahora)
- **Mejora: +$717.32** gracias a IEPS Tasa
- **Falta:** $1,050.76 para alcanzar PAC ($8,200.10)

**CAUSA PROBLEMA:** Setting ERPNext `add_taxes_from_item_tax_template=1` reemplaza taxes del STCT cuando hay múltiples items con ITT

---

## 1. CAMBIOS IMPLEMENTADOS EN CÓDIGO

### 1.1 Archivo: `generador_templates_fiscal.py`

**Líneas modificadas: 28-29, 1052, 1063, 1074, 1085**

```python
# LÍNEA 28-29: Import tasas IEPS
from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import TASAS_IEPS

# LÍNEA 1052: ITT IEPS Alcohol - tasa desde constantes
if cfg.enable_ieps_alcohol:
    created.append(
        _crear_o_actualizar_itt(
            company, abbr,
            "ITT IEPS Alcohol",
            [{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": TASAS_IEPS["alcohol"]["tasa"]}],  # 26.5%
            mapeo_cuentas,
        )
    )

# LÍNEA 1085: ITT IEPS Tabaco - tasa desde constantes
if cfg.enable_ieps_tabaco:
    created.append(
        _crear_o_actualizar_itt(
            company, abbr,
            "ITT IEPS Tabaco",
            [{"rol_fiscal": "IEPS por Pagar (Tabaco)", "tax_rate": TASAS_IEPS["tabaco"]["tasa"]}],  # 160%
            mapeo_cuentas,
        )
    )

# LÍNEAS 1063, 1074: Comentarios aclarados para IEPS Cuota
# Rate 0 correcto: hook calcular_ieps_cuota() asigna monto dinámicamente
```

**ANTES:**
```python
[{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": 0}],  # Tasa se fija en ITT del item
```

**DESPUÉS:**
```python
[{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": TASAS_IEPS["alcohol"]["tasa"]}],  # Tasa desde constantes - heredada por items vía Item Group
```

### 1.2 Archivo: `hooks.py`

**PRUEBA TEMPORAL realizada (NO committeada):**

Movió `corregir_ieps_cuota_final` de `before_save` a `before_submit` para confirmar si era la causa del problema.

**Resultado:** NO es la causa. El problema persiste en ambas configuraciones.

---

## 2. REGENERACIÓN TEMPLATES

### 2.1 ITT Regenerados

**Comando ejecutado:**
```bash
bench --site facturacion.dev execute "facturacion_mexico.one_offs.regenerar_itt_tasas_ieps.run"
```

**Resultado:**
```
ITT IEPS Alcohol - _TC:     26.50% ✅ (antes: 0%)
ITT IEPS Tabaco - _TC:      160.00% ✅ (antes: 0%)
ITT IEPS Azúcar - _TC:      0.00% ✅ (correcto - hook dinámico)
ITT IEPS Combustibles - _TC: 0.00% ✅ (correcto - hook dinámico)
```

### 2.2 STCT Regenerados

**Comando ejecutado:**
```bash
bench --site facturacion.dev execute "facturacion_mexico.one_offs.regenerar_stct_completo.run"
```

**Resultado:**
- STCT "IVA Nacional - IEPS - _TC": **11 filas** generadas correctamente
- Incluye 5 filas IVA cascada (una después de cada IEPS)

**Estructura STCT:**
```
1.  IVA Nacional - Base (Resto)
2.  IEPS Alcohol - Tasa (via ITT)
3.  IVA sobre IEPS Alcohol
4.  IEPS Azúcar - Cuota (via ITT)
5.  IVA sobre IEPS Azúcar
6.  IEPS Combustibles - Cuota (via ITT)
7.  IVA sobre IEPS Combustibles
8.  IEPS Tabaco - Tasa (via ITT)
9.  IVA sobre IEPS Tabaco Tasa
10. IEPS Tabaco - Cuota (via ITT)
11. IVA sobre IEPS Tabaco Cuota
```

---

## 3. RESULTADOS TESTING

### 3.1 Comparación SI Creados

| SI | Fecha/Hora | Items | Filas Taxes | IEPS Tasa | IVA Base | IVA Cascada | Grand Total | vs PAC |
|----|------------|-------|-------------|-----------|----------|-------------|-------------|--------|
| ACC-SINV-2025-01647 | 18:27 | 4 | 11 | $0.00 | $838.40 | $48.78 | $6,432.02 | -$1,768.08 |
| ACC-SINV-2025-01649 | 19:30 | 4 | 4 | $1,674.50 | $0.00 | $0.00 | $7,149.34 | -$1,050.76 |
| ACC-SINV-2025-01654 | 19:45 | 4 | 4 | $1,674.50 | $0.00 | $0.00 | $7,149.34 | -$1,050.76 |

**Nota:** ACC-SINV-2025-01654 creado con hook en `before_submit` (config original) - mismo resultado.

### 3.2 Progreso Confirmado

**ÉXITO PARCIAL:**
- ✅ IEPS Alcohol: $0.00 → $874.50 (26.5% de $3,300)
- ✅ IEPS Tabaco: $0.00 → $800.00 (160% de $500)
- ✅ **Total IEPS Tasa agregado: $1,674.50**
- ✅ **Mejora grand total: +$717.32**

**PROBLEMA:**
- ❌ IVA Base: $838.40 → $0.00 (PERDIDO)
- ❌ IVA Cascada: $48.78 → $0.00 (PERDIDO)
- ❌ **Filas STCT reducidas: 11 → 4**

---

## 4. PROBLEMA BLOQUEANTE IDENTIFICADO

### 4.1 Causa Raíz

**Setting ERPNext:** `add_taxes_from_item_tax_template = 1` (ACTIVADO)

Este setting causa que ERPNext REEMPLACE el array completo de taxes del STCT con taxes construidas únicamente desde los ITT de los items.

**Comportamiento observado:**

| Escenario | Filas Taxes | Descripción |
|-----------|-------------|-------------|
| 1 item con ITT | 11 | ✅ STCT se mantiene completo |
| 2 items con ITT | 2 | ❌ Solo filas IEPS (una por ITT único) |
| 4 items con ITT | 4 | ❌ Solo filas IEPS (una por ITT único) |

**Evidencia:**
```bash
# Test 1 item: ACC-SINV-2025-01651
Filas: 11 ✅
- IVA Nacional - Base (Resto)
- IEPS Alcohol - Tasa (via ITT)
- IVA sobre IEPS Alcohol
[... todas las filas del STCT]

# Test 2 items: ACC-SINV-2025-01652
Filas: 2 ❌
- 2117001 - IEPS Alcohol - _TC
- 2117004 - IEPS Tabaco - _TC
[FALTAN: todas las filas IVA]
```

### 4.2 Por Qué NO Es Solución

**Desactivar el setting NO ES MIGRABLE:**
```python
# ❌ PROHIBIDO: Cambio manual BD
frappe.db.set_single_value("Accounts Settings", "add_taxes_from_item_tax_template", 0)
```

**Viola:**
- RC-009 (Zero-config deployment)
- No se replica en otros sites
- No hay fixture para Accounts Settings

---

## 5. ANÁLISIS ARQUITECTURAL

### 5.1 IEPS Cuota vs IEPS Tasa

**IEPS Cuota (Azúcar, Combustibles, Tabaco Cuota):**
- ✅ DocType `IEPS Cuota SAT` para lookup centralizado
- ✅ Hook `calcular_ieps_cuota()` calcula dinámicamente
- ✅ ITT con rate=0 es CORRECTO (hook asigna monto)
- ✅ charge_type: "Actual"

**IEPS Tasa (Alcohol, Tabaco Tasa):**
- ✅ Tasas en `constantes_fiscales.py` (single source of truth)
- ✅ ITT heredan tasas vía Item Group
- ✅ ERPNext calcula automáticamente: net_amount × rate
- ✅ charge_type: "On Net Total"
- ❌ ITT tenían rate=0 (CORREGIDO en esta implementación)

### 5.2 Diferencias Clave

| Aspecto | IEPS Cuota | IEPS Tasa |
|---------|-----------|-----------|
| **Fuente tasa** | DocType lookup | ITT rate |
| **Cálculo** | Hook dinámico | ERPNext nativo |
| **Variabilidad** | Por producto (clave SAT) | Fija por categoría |
| **Vigencias** | Soportadas (tabla SAT) | Estables (ley) |
| **Conversión UOM** | Requerida | No aplica |

---

## 6. INVESTIGACIÓN REALIZADA

### 6.1 Timeline Cambios

**Commits relevantes:**
```
26e8bc5 - refactor(e1): consolidar fuente verdad Item Groups
3fdb47b - feat(e1): implementar sistema 8 STCT específicos
```

**Hooks.py última modificación:**
```
2025-10-21 04:12:23 - wip(e4): commit seguridad - sistema IEPS Cuota parcial
```

**SI creados:**
```
18:27 - ACC-SINV-2025-01647 (ANTES de regenerar templates) - 11 filas ✅
19:23 - Regeneración ITT/STCT
19:30 - ACC-SINV-2025-01649 (DESPUÉS de regenerar) - 4 filas ❌
```

### 6.2 Pruebas Realizadas

**Test 1:** SI con 1 item
- **Resultado:** 11 filas se mantienen ✅
- **Conclusión:** STCT funciona correctamente

**Test 2:** SI con 2 items diferentes ITT
- **Resultado:** Solo 2 filas (una por ITT) ❌
- **Conclusión:** ERPNext reemplaza taxes con múltiples ITT

**Test 3:** Verificar Accounts Settings
- **Setting encontrado:** `add_taxes_from_item_tax_template = 1`
- **Comportamiento:** Reemplaza STCT con ITT cuando múltiples items

**Test 4:** Hook en before_submit vs before_save
- **Resultado:** Mismo problema en ambas configuraciones
- **Conclusión:** NO es el cambio de hook la causa

---

## 7. SOLUCIONES EVALUADAS

### 7.1 Desactivar Setting ❌

**Propuesta:** `add_taxes_from_item_tax_template = 0`

**Rechazo:**
- Cambio manual BD NO migrable
- Viola RC-009 (Zero-config deployment)
- No se replica en otros sites

### 7.2 Restaurar Hook Después de ERPNext ⚠️

**Propuesta:** Hook que detecte y restaure filas STCT faltantes

**Desafíos:**
- Complejidad alta
- Conflicto con lógica ERPNext nativa
- Mantenimiento difícil

### 7.3 Modificar Arquitectura ITT 🔍

**Propuesta:** Revisar si ITT deben incluir IVA además de IEPS

**Requiere:** Investigación adicional de arquitectura original

---

## 8. PRÓXIMOS PASOS

### 8.1 Investigación Pendiente

1. **Revisar STCT original (19 filas) que funcionaba**
   - ¿Qué era diferente en estructura?
   - ¿Cómo manejaba múltiples ITT?

2. **Analizar comportamiento ERPNext v15**
   - ¿Es bug o feature?
   - ¿Cambió entre versiones?

3. **Verificar si ITT deben incluir IVA**
   - Revisar arquitectura Item Groups
   - Determinar si IEPS Alcohol debería tener ITT con IEPS+IVA

### 8.2 Alternativas

**OPCIÓN A:** ITT combinados (IEPS + IVA)
- Generar ITT que incluyan ambas tasas
- Pros: ERPNext maneja todo nativamente
- Contras: Duplicación lógica, más ITT complejos

**OPCIÓN B:** Hook restaurador
- Hook que agregue filas IVA faltantes después de ERPNext
- Pros: Mantiene STCT como fuente verdad
- Contras: Complejo, posibles conflictos

**OPCIÓN C:** Deshabilitar ITT en items, solo STCT
- Remover ITT de items, usar solo STCT
- Pros: Simple, STCT se respeta
- Contras: Pierde flexibilidad por item

---

## 9. SCRIPTS CREADOS

### 9.1 Scripts Regeneración

- `regenerar_itt_tasas_ieps.py` - Regenerar ITT con tasas correctas
- `regenerar_stct_completo.py` - Regenerar STCT con 11 filas

### 9.2 Scripts Testing

- `crear_si_final_stct_actualizado.py` - Crear SI test
- `analizar_si_tasas_actualizadas.py` - Análisis detallado SI
- `comparar_tres_si.py` - Comparación evolución 3 SI
- `test_stct_sin_items.py` - Test STCT con 1 item
- `test_stct_dos_items.py` - Test STCT con 2 items
- `test_items_itt_con_tasas.py` - Test ITT con múltiples tasas

### 9.3 Scripts Investigación

- `investigar_si_timeline.py` - Timeline SI y cambios código
- `analizar_diferencia_stct.py` - Comparar STCT vs SI
- `verificar_accounts_settings.py` - Verificar settings ERPNext
- `diagnosticar_si_taxes.py` - Diagnóstico filas faltantes

### 9.4 Scripts Revertidos

- `desactivar_itt_setting.py` - ❌ Cambio no migrable (REVERTIDO)
- `revertir_itt_setting.py` - ✅ Reversión aplicada

---

## 10. ARCHIVOS DOCUMENTACIÓN

- `REPORTE_ARQUITECTURA_IEPS_CUOTA_VS_TASA.md` - Análisis arquitectural completo
- `INFORME_ANALISIS_IMPUESTOS_ON_SAVE.md` - Análisis comportamiento hooks
- `REPORTE_CAMBIOS_POST_SUBMIT_E1.md` - Análisis ACC-SINV-2025-01647 original

---

## CONCLUSIÓN

**ÉXITO PARCIAL:**
- ✅ Tasas IEPS implementadas correctamente desde constantes
- ✅ IEPS Tasa ahora calcula: +$1,674.50
- ✅ Grand total mejoró: +$717.32

**BLOQUEADOR:**
- ❌ Setting ERPNext causa pérdida filas IVA con múltiples items
- ❌ Solución directa (desactivar setting) NO es migrable
- ⚠️ Requiere solución arquitectural más profunda

**ESTADO:** En investigación - Requiere decisión arquitectural para proceder.

---

**🤖 Generated with [Claude Code](https://claude.com/claude-code)**
