# ADR 0009 — CHECKLIST ESTADOS Y FLUJO DE TIMBRADO
====================================================
Fecha: 2026-05-02
Site: facturacion-v16.dev
Fuente: Análisis de timbrado_api.py, factura_fiscal_mexico.py, overrides.py,
        sales_invoice_cancel_guard.py, sales_invoice_block_cancel.js

---

## Estado del último timbrado verificado

**FFM:** `FFMX-2026-00002`

| Campo | Valor |
|-------|-------|
| `sales_invoice` | ACC-SINV-2026-00001 |
| `fm_uuid` | AC82DF3E-89FE-4F14-9AFB-D9D417C62964 |
| `fm_fiscal_status` | TIMBRADO |
| `serie` | F |
| `folio` | 270 |
| `total_fiscal` | $498.80 |
| `fecha_timbrado` | 2026-05-02 12:03:21 |
| `facturapi_id` | 69f63c6914917afe07e4bdb3 |

**SI vinculada:** `ACC-SINV-2026-00001`
- `status`: Unpaid | `docstatus`: 1 | `fm_fiscal_status`: TIMBRADO
- `fm_factura_fiscal_mx`: FFMX-2026-00002

**Response Log:** `FAPI-LOG-2026-00002`
- `operation_type`: Timbrado | `success`: 1 | `status_code`: 200

**Archivos adjuntos:**
- PDF: `FFMX-2026-000024ecfaf.pdf` (155,572 bytes)
- XML: `FFMX-2026-000029c848e.xml` (5,093 bytes)

---

## Diagrama de estados

```
                    ┌─────────────────────────────────────────────┐
                    │         FACTURA FISCAL MEXICO                │
                    └─────────────────────────────────────────────┘

  [nuevo]──submit──▶ BORRADOR ──timbrar_factura()──▶ PROCESANDO
                        ▲                                │
                        │                       ┌───────┴───────┐
                        │                    éxito PAC       error PAC
                        │                       │               │
                  reintento                      ▼               ▼
                        │                    TIMBRADO ◀────── ERROR
                        └────────────────────────┤
                                                 │ cancelar_factura()
                                        ┌────────┴────────┐
                                   PAC acepta       PAC pendiente
                                        │               │
                                        ▼               ▼
                                    CANCELADO   PENDIENTE_CANCELACION
                                   [FINAL]          │
                                                     │ SAT confirma / rechaza
                                            ┌────────┴────────┐
                                       confirma           rechaza
                                            │               │
                                            ▼               ▼
                                        CANCELADO       TIMBRADO
```

```
                    ┌─────────────────────────────────────────────┐
                    │            SALES INVOICE                     │
                    └─────────────────────────────────────────────┘

  Draft ──submit──▶ Submitted (fm_fiscal_status vacío)
                         │
                    timbrar_factura()
                         │
                    fm_fiscal_status = TIMBRADO
                         │
                    [BLOQUEADA para cancelar hasta que FFM = CANCELADO]
                         │
                    FFM cancelada en PAC + Frappe
                         │
                    SI puede cancelarse ──▶ Cancelled
```

---

## Transiciones de estado FFM

### BORRADOR → PROCESANDO → TIMBRADO (flujo normal)

**Cuándo:** llamada a `timbrar_factura(sales_invoice_name)`

**Validaciones previas (FASE 1):**
- `SI.docstatus == 1` (submitted) — si no: throw
- `SI.fm_fiscal_status != TIMBRADO` — si ya timbrado: throw
- `SI.customer` existe
- `Customer.tax_id` (RFC) no vacío — si no: throw
- Address primaria existe — si no: throw
- `Address.country` válido (México/MEX/MX) — si no: throw
- `Factura Fiscal Mexico` existe y está submitted — si no: throw
- `FFM.fm_cfdi_use` no vacío — si no: throw
- `SI.items` no vacío — si no: throw

**Transición:**
```
BORRADOR → PROCESANDO  (set_value al iniciar llamada PAC)
         → TIMBRADO    (set_value en _process_timbrado_success)
         → ERROR       (set_value si falla PAC o Frappe post-PAC)
```

**Campos actualizados al TIMBRADO:**

| Campo FFM | Fuente |
|-----------|--------|
| `fm_fiscal_status` | `"TIMBRADO"` |
| `fm_uuid` | `response["uuid"]` |
| `facturapi_id` | `response["id"]` |
| `fecha_timbrado` | `response["stamp"]["date"]` o `now_datetime()` |
| `serie` | `response["series"]` (si viene) |
| `folio` | `response["folio_number"]` (solo número, sin prefijo) |
| `total_fiscal` | `response["total"]` |
| `fm_xml_url` | `response["xml_url"]` (si viene) |
| `fm_pdf_url` | `response["pdf_url"]` (si viene) |

| Campo SI | Valor |
|----------|-------|
| `fm_fiscal_status` | `"TIMBRADO"` |

**Qué debe verse en UI:**
- FFM: estado `TIMBRADO` en badge
- FFM: UUID visible, folio y serie asignados
- FFM: PDF y XML adjuntos (si `download_files_default = 1`)
- SI: badge fiscal `TIMBRADO`, campo `fm_factura_fiscal_mx` con link a FFM

**Errores posibles:**
- `PROCESANDO` quedó sin resolver (timeout / Frappe caído post-PAC) → usar recovery worker
- `ERROR` con mensaje: ver `user_message` en respuesta y en FacturAPI Response Log

---

### TIMBRADO → CANCELADO / PENDIENTE_CANCELACION

**Cuándo:** llamada a `cancelar_factura(sales_invoice, motivo, [substitution_uuid])`

**Validaciones previas:**
- `SI.fm_fiscal_status == TIMBRADO` — si no: throw
- `FFM.fm_uuid` existe (hubo timbrado real) — si no: throw
- Motivo válido (01–04 SAT)
- Motivo 01 solo desde flujo de sustitución (requiere `substitution_uuid`)

**Transición según respuesta PAC:**

| Estado PAC devuelto | Estado FFM resultante |
|--------------------|----------------------|
| `"valid"` / `"canceled"` | `CANCELADO` |
| `"pending"` / `"in_process"` | `PENDIENTE_CANCELACION` |
| Respuesta inesperada | `PENDIENTE_CANCELACION` (fallback) |

**Campos actualizados:**

| Campo FFM | Valor |
|-----------|-------|
| `fm_fiscal_status` | `CANCELADO` o `PENDIENTE_CANCELACION` |
| `cancellation_reason` | motivo SAT |
| `cancellation_date` | fecha cancelación |

| Campo SI | Valor |
|----------|-------|
| `fm_fiscal_status` | mismo estado que FFM |

**Qué debe verse en UI:**
- FFM: badge `CANCELADO` o `PENDIENTE_CANCELACION`
- SI: botón Cancel visible (si FFM = CANCELADO) o bloqueado (si PENDIENTE)

---

### PENDIENTE_CANCELACION → CANCELADO o → TIMBRADO (resolución SAT)

**Cuándo:** SAT confirma o rechaza la cancelación (job `process_pending_complements` o acción manual)

**Sin validaciones activas** — el estado se actualiza cuando el PAC reporta resolución.

---

### TIMBRADO / ERROR → ERROR → BORRADOR (reintento)

**Cuándo:** el usuario corrige datos y reintenta timbrar después de un error.

**Matriz de transiciones permitidas** (validada en `validate_status_transitions`):

```python
None      → ["BORRADOR"]
""        → ["BORRADOR"]
BORRADOR  → ["PROCESANDO", "TIMBRADO", "CANCELADO", "ERROR"]
PROCESANDO→ ["TIMBRADO", "ERROR", "CANCELADO"]
TIMBRADO  → ["CANCELADO", "PENDIENTE_CANCELACION"]
ERROR     → ["BORRADOR", "PROCESANDO", "TIMBRADO"]   # puede reintentarse
CANCELADO → []                                        # FINAL — sin transición
PENDIENTE_CANCELACION → ["CANCELADO", "TIMBRADO"]
```

Cualquier transición fuera de esta matriz lanza `ValidationError`.

---

## Protección contra cancelación de Sales Invoice

Tres capas independientes — cualquiera puede bloquear:

### Capa 1 — Frontend (JS)

`public/js/sales_invoice_block_cancel.js` — se ejecuta en cada `refresh` de SI submitted:
1. Llama a `can_cancel_sales_invoice(si_name)` (endpoint whitelisted)
2. Si `allowed = False`: oculta botón Cancel + muestra headline naranja con razón
3. Si hay error de red: NO oculta (evita bloquear por error de red — el server-hook sigue protegiendo)

### Capa 2 — Server hook (before_cancel de SI)

`validaciones/sales_invoice_cancel_guard.py` → hook `before_cancel` en Sales Invoice:
1. Busca FFM vinculada (por `sales_invoice` en FFM o por `fm_factura_fiscal_mx` en SI)
2. Si FFM existe con `docstatus=1` y `fm_fiscal_status` ∉ `{CANCELADO, CANCELADA, CANCELLED, CANCELLED_OK, CANCELED}` → `raise ValidationError`
3. Si no hay FFM vinculada → permite cancelar

### Capa 3 — Override class FFM (before_cancel de FFM)

`factura_fiscal_mexico.py → before_cancel()`:
- Si `fm_uuid` existe y `fm_fiscal_status != "CANCELADO"` → throw con instrucciones de secuencia correcta
- Solo bypass si `fm_uuid` es None y `flags.allow_local_cancel = True` (para FFMs sin timbrado)

`overrides.py → cancel()`:
- Verifica que `fm_fiscal_status` esté en `CANCELADO_FISCAL` antes de proceder
- Si no → throw "Primero cancela en el PAC"
- Si sí → `flags.ignore_links = True` para evitar `LinkExistsError` al cancelar con SI vinculada

---

## Secuencia de cancelación correcta

```
1. Botón "Cancelar en FacturAPI" en FFM
   → cancelar_factura() → PAC procesa → FFM.fm_fiscal_status = CANCELADO

2. Botón "Cancel" en FFM (Frappe)
   → before_cancel: verifica fm_fiscal_status = CANCELADO ✓
   → overrides.cancel: flags.ignore_links = True
   → FFM.docstatus = 2

3. Botón "Cancel" en Sales Invoice
   → before_cancel guard: FFM docstatus=2 → permite ✓
   → SI.docstatus = 2
```

**Si el PAC responde PENDIENTE_CANCELACION:**
- FFM queda en `PENDIENTE_CANCELACION`
- SI sigue bloqueada para cancelar
- Esperar que el SAT procese (job nocturno o acción manual)
- Cuando PAC confirme → FFM → `CANCELADO` → continúa secuencia

---

## Checklist verificación post-timbrado

```
☐ FFM.fm_fiscal_status = TIMBRADO
☐ FFM.fm_uuid poblado (36 chars UUID)
☐ FFM.facturapi_id poblado
☐ FFM.fecha_timbrado poblado
☐ FFM.total_fiscal = SI.grand_total (validar discrepancia)
☐ FFM tiene PDF adjunto (si download_files_default = 1)
☐ FFM tiene XML adjunto (si download_files_default = 1)
☐ FacturAPI Response Log: operation_type=Timbrado, success=1, status_code=200
☐ SI.fm_fiscal_status = TIMBRADO
☐ SI.fm_factura_fiscal_mx = FFM.name
☐ Botón Cancel en SI: oculto / headline "Cancelación bloqueada"
```

## Checklist verificación post-cancelación

```
☐ FFM.fm_fiscal_status = CANCELADO
☐ FFM.docstatus = 2 (cancelado en Frappe)
☐ FFM.cancellation_reason poblado
☐ FacturAPI Response Log: operation_type=Cancelación, success=1
☐ SI.fm_fiscal_status = CANCELADO
☐ Botón Cancel en SI: visible
☐ SI.docstatus = 2 (si se completó cancelación en Frappe)
```

---

## Errores críticos y cómo identificarlos

| Error | Causa | Dónde buscar |
|-------|-------|-------------|
| FFM queda en PROCESANDO | Timeout o Frappe caído post-PAC | FacturAPI Response Log + recovery worker |
| FFM en ERROR con UUID | PAC timbró pero Frappe falló al guardar | Response Log tiene UUID — recuperar con `process_sync_errors` |
| FFM en PENDIENTE_CANCELACION mucho tiempo | SAT no procesa | Verificar en portal SAT con UUID |
| SI bloqueada para cancelar sin FFM visible | FFM existe en docstatus=1 pero no en UI | Buscar FFM directamente por sales_invoice |
| LinkExistsError al cancelar FFM | Bug pre-override | Ya corregido en overrides.py via `flags.ignore_links` |
| Amend de FFM bloqueado | Correcto por diseño | Crear nueva FFM en lugar de corregir |
