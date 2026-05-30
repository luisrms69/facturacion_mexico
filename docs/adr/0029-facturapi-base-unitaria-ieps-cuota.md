# ADR 0029 — FacturAPI multiplica `base` × cantidad: enviar valores unitarios para IEPS Cuota

**Fecha:** 2025-10-21
**Estado:** Implementado — PR #83 (`78d4606`)
**Autor:** Luis Montanaro / Claude Sonnet 4.6

---

## Contexto

Al integrar IEPS Cuota con FacturAPI, se detectó que el campo `base` del payload
se comporta diferente al esperado: **FacturAPI multiplica automáticamente `base` × `Cantidad`**
al generar el XML SAT.

Enviar el valor total en `base` produce montos multiplicados dos veces:

```python
# Payload enviado (incorrecto)
{"quantity": 50, "taxes": [{"type": "IEPS", "base": 50, "rate": 5.49}]}

# XML SAT generado por FacturAPI
# Base="2500.000000"  ← 50 × 50 = 2,500 (debería ser 50)
# Importe="13725.000000" ← debería ser $274.50
```

Diferencia resultante: **+$23,250.50** por documento — SAT rechaza cualquier diferencia
mayor a $0.05 pesos.

---

## Decisión

Enviar **valores unitarios** (por unidad del ítem) en el campo `base`, permitiendo que
FacturAPI los multiplique por `Cantidad` y obtenga los totales correctos en XML.

### IEPS Cuota — base = factor de conversión UOM → unidad canónica

La UOM canónica no es siempre litros — es la que define el registro en `IEPS Cuota SAT`
(puede ser LTR para bebidas/combustibles, H87 para tabaco por pieza, etc.).

```python
# FIX E4.1: Obtener cuota ORIGINAL de tabla SAT (no calcularla desde amount)
# RAZÓN: amount ya está multiplicado por qty, dividirlo causa error de precisión
cuota_por_uom_base = self._get_cuota_from_tabla_sat(item_doc, tax_data["account_head"])

# Obtener UOM base dinámica desde tabla IEPS Cuota SAT (LTR, H87, etc.)
uom_base = self._get_uom_base_from_tabla_sat(item_doc, tax_data["account_head"])

# Factor conversión: item.uom → uom_base
# Ejemplo: Combustible LTR→LTR factor=1.0, Refresco 600ml→LTR factor=0.6, Tabaco H87→H87 factor=1.0
factor_conversion = self._get_uom_conversion_factor(item_doc, item.uom, uom_base)

tax_item["rate"] = flt(cuota_por_uom_base, 6)  # TasaOCuota (cuota/unidad base)
tax_item["base"] = flt(factor_conversion, 6)    # Factor conversión (FacturAPI × qty = unidades base)
```

### IVA con IEPS Cuota — base = precio unitario ± IEPS unitario

La integración del IEPS en la base IVA depende del tipo de producto (Art. 2-A LIEPS):

```python
if integra_base:  # Bebidas, tabaco, alcohol → IEPS sí computa para IVA
    ieps_unitario = flt(tax_check["amount"]) / flt(item.qty)
    base_iva_unitaria = flt(item.rate) + ieps_unitario
else:  # Combustibles (Art. 2-A LIEPS) → IEPS NO computa para IVA
    base_iva_unitaria = flt(item.rate)

tax_item["base"] = flt(base_iva_unitaria, 6)
```

---

## Consecuencias

**Resultado:** $0.00 diferencia con totales SAT — cumple tolerancia legal ≤ $0.05.

### Validaciones con datos reales

| Producto | Cantidad | Base enviada | Base XML | IEPS XML | Diferencia |
|---|---|---|---|---|---|
| Gasolina Magna (LTR) | 50 L | 1.0 | 50.0 L ✅ | $274.50 ✅ | $0.00 |
| Refresco 600ml | 40 botellas | 0.6 | 24.0 L ✅ | $30.48 ✅ | $0.00 |

### Regla para agregar nuevos productos con IEPS Cuota

Todo ítem con IEPS Cuota cuya UOM de venta sea distinta a la UOM base de
`IEPS Cuota SAT` requiere configurar `UOM Conversion Factor` en el DocType Item:

| Ejemplo | UOM venta | UOM base SAT | Factor | Equivalencia |
|---|---|---|---|---|
| Cerveza 355ml | Lata | LTR | 0.355 | 355 ml |
| Whisky 750ml | Botella | LTR | 0.75 | 750 ml |
| Agua mineral 600ml | Botella | LTR | 0.6 | 600 ml |
| Cigarros | Cajetilla 20 pzas | H87 (pieza) | 20.0 | 20 piezas |

Si falta la conversión o el registro en `IEPS Cuota SAT`, `_get_uom_conversion_factor`
lanza `ValidationError` antes del timbrado — nunca timbra con valores incorrectos.

### Alternativas descartadas

| Alternativa | Problema |
|---|---|
| Enviar total en `base` | FacturAPI lo multiplica × qty → valor ×N |
| Calcular y enviar el total SAT directamente | No disponible en API de FacturAPI — el campo `base` es el insumo, no el resultado |

---

## Implementación

**Archivo:** `facturacion_mexico/facturacion_fiscal/timbrado_api.py`

- Línea 533: `# FIX E4.1: Para IVA, enviar base UNITARIA (FacturAPI multiplica x qty)`
- Líneas 549–573: lógica integración IEPS en base IVA (combustibles vs. resto)
- Línea 581: `# FIX E4.1: Obtener cuota ORIGINAL de tabla SAT (no calcularla desde amount)`
- Líneas 586–633: obtención de cuota y factor desde `IEPS Cuota SAT` + `_get_uom_conversion_factor`
- Línea 2123: docstring del método `_get_uom_conversion_factor`

**PR:** #83 — `feat(fiscal): sistema automatizado impuestos E0-E4 + fix timbrado v16`
commit `78d4606` (squash merge)

---

## Notas de normativa

- **LIEPS Art. 2-A (Combustibles):** IEPS Cuota **no** forma parte de la base IVA.
- **LIEPS General (Bebidas, Alcohol, Tabaco):** IEPS **sí** forma parte de la base IVA.
- La distinción se controla vía `integra_base_iva` en el mapeo de cuenta SAT.
