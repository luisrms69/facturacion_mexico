# REPORTE: ITT 0% vs STCT Mixto - Sistema E1

**Fecha:** 2025-10-01
**Caso:** ACC-SINV-2025-01566
**Investigador:** Claude Code

## ✅ **ESTADO: PROBLEMA RESUELTO**

**Fecha resolución:** 2025-10-01
**Commit solución:** `58c3f64` - feat(e1): implementar sistema mixto ITT 0% + IVA normal en misma factura
**Validación exitosa:** ACC-SINV-2025-01572 (capacitación 0% + material oficina 8% funcionando)

**Solución implementada:** Propuesta ChatGPT - STCT con 3 filas + ITT override con 3 entradas
**Resultado:** ERPNext Item-wise Tax Detail calcula distribución automática correctamente

---

**NOTA:** Este reporte documenta el proceso de investigación que llevó a la solución exitosa. El problema original está completamente resuelto.

## RESUMEN EJECUTIVO

**PROBLEMA:** Sales Invoice con productos mixtos (0% IVA + tasa normal) no respeta ITT 0% en líneas individuales.

**OBJETIVO:** Combinar en la MISMA factura:
- Productos con ITT 0% (exentos) → deben calcular 0% IVA
- Productos normales → deben calcular 8%/16% IVA según zona

**SITUACIÓN ACTUAL:** STCT de cabecera (8%) ignora ITT 0% en líneas, aplicando 8% a TODOS los productos.

## EVIDENCIA DEL PROBLEMA

### Sales Invoice: ACC-SINV-2025-01566

**Configuración:**
- Company: _Test Company
- STCT: IVA 8% Frontera - México - _TC
- Tax Category: Zero 0

**Líneas:**
1. **MATERIAL OFICINA** - Sin ITT → Debería aplicar 8% ✅
2. **capaication** - ITT IVA 0% → Debería aplicar 0% ❌ (aplica 8%)
3. **capaication** - ITT IVA 0% → Debería aplicar 0% ❌ (aplica 8%)

**Resultado Incorrecto:**
- Total productos 0%: $2,000.00
- Impuesto aplicado: $160.00 (8% sobre todo)
- **Debería ser:** $80.00 (8% solo sobre $1,000.00)
- **SOBRECOBRO:** $160.00

## ANÁLISIS TÉCNICO

### ¿Por qué falla ERPNext?

1. **STCT de cabecera** se aplica a Net Total completo
2. **ITT de línea** no override el cálculo de STCT
3. **Tax Category** presente pero no efectiva para este caso
4. **ERPNext logic:** STCT cabecera > ITT línea (diseño del framework)

### Flujo Problemático

```
1. Sales Invoice creado
2. Sistema E1 asigna STCT 8% (zona fronteriza)
3. ERPNext calcula: 8% × $3,000 = $240
4. ITT 0% en líneas 2 y 3 IGNORADO
5. Resultado: Sobrecobro $160
```

### Lo que necesitamos

```
1. Sales Invoice creado
2. Línea 1 (sin ITT) → aplica STCT 8% = $80
3. Línea 2 (ITT 0%) → aplica 0% = $0
4. Línea 3 (ITT 0%) → aplica 0% = $0
5. Total correcto: $80
```

## ANÁLISIS DE SOLUCIONES

### OPCIÓN A: Tax Rules + Tax Category (ERPNext Nativo)

**Concepto:** Usar Tax Rules para override STCT cuando hay ITT específico

**Implementación:**
1. Crear Tax Category "Mixto"
2. Configurar Tax Rules por Item Tax Template
3. Cuando ITT = 0% → override a STCT 0%
4. Cuando ITT = normal → usar STCT zona

**Pros:**
- Usa funcionalidad nativa ERPNext
- No modifica código core

**Contras:**
- Complejo de configurar
- Requiere mantenimiento manual

### OPCIÓN B: Custom Hooks Override (Recomendado)

**Concepto:** Modificar sistema E1 para detectar ITT 0% y calcular mixto

**Implementación en hooks E1:**
```python
def calculate_mixed_taxes(doc):
    """Calcular impuestos mixtos respetando ITT por línea"""

    # 1. Detectar líneas con ITT 0%
    # 2. Separar líneas normales vs exentas
    # 3. Aplicar STCT solo a líneas normales
    # 4. Override tax calculation manual
```

**Pros:**
- Automático, sin configuración manual
- Integrado con sistema E1
- Flexible para casos futuros

**Contras:**
- Modifica lógica core
- Requiere testing extensivo

### OPCIÓN C: Mixed STCT Template

**Concepto:** Crear STCT que combine tasas múltiples

**Pros:**
- Un solo template

**Contras:**
- No resuelve el problema core
- ERPNext seguirá aplicando a Net Total

## RECOMENDACIÓN

**IMPLEMENTAR OPCIÓN B:** Custom Hooks Override en sistema E1

### Plan de Implementación

1. **Modificar `sales_invoice_automated_tax.py`:**
   - Detectar líneas con ITT 0%
   - Calcular base imponible por separado
   - Override cálculo de taxes

2. **Lógica propuesta:**
   ```python
   def calculate_taxes_respecting_itt(doc):
       normal_lines_total = 0
       exempt_lines_total = 0

       for item in doc.items:
           if has_itt_zero_percent(item):
               exempt_lines_total += item.amount
           else:
               normal_lines_total += item.amount

       # Aplicar STCT solo a normal_lines_total
       # Dejar exempt_lines_total sin impuesto
   ```

3. **Testing:**
   - Validar caso ACC-SINV-2025-01566
   - Verificar no regresión casos normales
   - Testear diferentes combinaciones ITT

## SIGUIENTE PASOS

**Fase 1: Investigación Adicional**
- [ ] Revisar cómo ERPNext calcula taxes internamente
- [ ] Identificar hook point exacto para override
- [ ] Validar si `validate()` o `before_save()` es mejor punto

**Fase 2: Implementación**
- [ ] Desarrollar función `calculate_mixed_taxes()`
- [ ] Integrar en hooks existentes
- [ ] Testing con caso problema

**Fase 3: Validación**
- [ ] Verificar ACC-SINV-2025-01566 se corrige
- [ ] Confirmar casos normales siguen funcionando
- [ ] Documentar nuevo comportamiento

## URGENCIA

**ALTA** - Afecta cálculo fiscal correcto en facturas mixtas

**Estimación:** 4-6 horas investigación + implementación + testing

**Riesgo:** Medio (modifica lógica de cálculo de impuestos)