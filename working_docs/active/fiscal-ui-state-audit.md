# Audit: Estado Fiscal UI — Inventario de botones, mensajes y banderas

**Fecha:** 2026-05-10  
**Alcance:** SI, FFM, PE, Complemento Pago MX  
**Objetivo:** Inventariar toda la lógica de mostrar/ocultar/habilitar para diseñar una fuente única de verdad (`get_fiscal_ui_state`)

---

## SALES INVOICE

### Botones

| Botón | Archivo:línea | Condición de visibilidad | Campos que lee | Acción |
|---|---|---|---|---|
| Timbrar Factura | sales_invoice.js:96 | `docstatus===1` AND `fm_fiscal_status` ∈ {BORRADOR,ERROR,""} AND RFC validado | `docstatus`, `fm_fiscal_status`, `fm_factura_fiscal_mx`, `customer` | Crea FFM o redirige si existe |
| Ver Factura Fiscal | sales_invoice.js:102 | `docstatus===1` AND `fm_factura_fiscal_mx` vinculada | `fm_factura_fiscal_mx` | Navega a FFM |
| 🔄 Nueva factura fiscal | si_post_fiscal_actions.js:66 | `docstatus===1` AND `fm_fiscal_status==="CANCELADO"` AND NO hay PE activo | `fm_fiscal_status`, `fm_factura_fiscal_mx` | Desvincula SI de FFM cancelada |
| ❌ Cancelar documento | si_post_fiscal_actions.js:132 | `docstatus===1` AND `fm_fiscal_status==="CANCELADO"` AND `can_cancel()` | `fm_fiscal_status` | Cancela SI y limpia vínculos |
| 🔄 Sustituir CFDI (01) | si_post_fiscal_actions.js:181 | `docstatus===1` AND `fm_fiscal_status==="TIMBRADO"` | `fm_fiscal_status` | Crea SI sustituto TipoRelación 04 |

### Mensajes / Alerts

| Mensaje | Archivo:línea | Condición | Campos que lee | Color |
|---|---|---|---|---|
| "No puedes timbrar: RFC no validado" | sales_invoice.js:631 | RFC no validado con SAT | `fm_rfc_validated` en Customer | orange/headline |
| "Ya Timbrada" | sales_invoice.js:122 | Intento retimbrar FFM en TIMBRADO | `fm_fiscal_status` FFM | orange/msgprint |
| "Centro de Costos asignado" | sales_invoice.js:327 | Customer tiene `fm_customer_default_cost_center` | `fm_customer_default_cost_center` | green/alert 6s |
| "Cliente sin Centro de Costos" | sales_invoice.js:339 | Customer sin cost center | `fm_customer_default_cost_center` | orange/alert 6s |
| "CC limpiado: no pertenece a Company" | sales_invoice.js:485 | Company cambia y CC no pertenece | `company` en Cost Center | orange/alert 6s |
| "Lista de precios asignada" | sales_invoice.js:429 | Autoasignación desde Customer o CC | `selling_price_list` | green/alert 6s |
| "Centro de Costos obligatorio" | sales_invoice.js:449 | `validate()` sin `cost_center` | `cost_center` | frappe.validated=false |
| "Factura cancelada ante el SAT" | sales_invoice_block_cancel.js:76 | FFM con `fm_fiscal_status==="CANCELADO"` | `fm_factura_fiscal_mx`, `fm_fiscal_status` | red/headline |
| "Cancelación bloqueada" | sales_invoice_block_cancel.js:23 | `can_cancel_sales_invoice()` → `allowed:false` | resultado API | orange/headline |
| "Documento fiscal creado exitosamente" | sales_invoice.js:257 | FFM creada OK | resultado insert | green/alert 3s |

### Banderas (flags)

| Bandera | Archivo:línea | Cómo se calcula | Campos que lee | Qué controla |
|---|---|---|---|---|
| `is_already_timbrada()` | sales_invoice.js:76 | `!!fm_factura_fiscal_mx` AND `fm_fiscal_status==="TIMBRADO"` | `fm_factura_fiscal_mx`, `fm_fiscal_status` | "Ver" vs "Timbrar" |
| `should_show_timbrar_button()` | sales_invoice.js:86 | `docstatus===1` AND estado ∈ {BORRADOR,ERROR,""} | `docstatus`, `fm_fiscal_status` | Mostrar "Timbrar Factura" |
| RFC validado | sales_invoice.js:619 | `fm_rfc_validated===1` en Customer | `fm_rfc_validated` | Visibilidad botón timbrar |
| FFM vinculada | si_post_fiscal_actions.js:13 | `!!fm_factura_fiscal_mx` | `fm_factura_fiscal_mx` | Ocultar Cancel nativo |
| `fiscal_status===CANCELADO` | si_post_fiscal_actions.js:47 | `norm(fm_fiscal_status)==="CANCELADO"` | `fm_fiscal_status` | Mostrar acciones post-cancelación |

### Campos ocultos/mostrados (set_df_property)

| Campo | Archivo:línea | Condición | Propiedad | Valor |
|---|---|---|---|---|
| cost_center | sales_invoice.js:296 | refresh() | reqd | 1 |
| cost_center | sales_invoice.js:508 | refresh() (duplicado) | reqd | 1 |

### Permisos modificados en runtime

| Permiso | Archivo:línea | Condición | Valor | Efecto |
|---|---|---|---|---|
| amend | si_post_fiscal_actions.js:221 | `docstatus===2` AND `fm_fiscal_status==="CANCELADO"` | 0 | Bloquea enmiendas SI canceladas |

### Realtime events

| Evento | Archivo:línea | Qué hace |
|---|---|---|
| `fiscal_status_changed` | sales_invoice_block_cancel.js:40 | Recarga SI si cambia estado fiscal de FFM vinculada |

### setTimeouts

| Archivo:línea | Delay | Qué hace |
|---|---|---|
| sales_invoice.js:265 | 1000ms | Navega a FFM recién creada |
| sales_invoice_block_cancel.js:56 | 300ms | Sobrescribe headline con mensaje rojo |
| sales_invoice_block_cancel.js:29 | 0ms | Limpia headline si se permite cancelar |

---

## FACTURA FISCAL MEXICO

### Botones

| Botón | Archivo:línea | Condición de visibilidad | Campos que lee | Acción |
|---|---|---|---|---|
| Timbrar / Reintentar | factura_fiscal_mexico.js:151 | `docstatus===1` AND status ∈ `timbrable_states` AND `fm_tax_system` válido | `docstatus`, `status`, `fm_tax_system` | Llama `timbrar_factura(frm)` |
| Cancelar en FacturAPI | factura_fiscal_mexico.js:229 | `docstatus===1` AND status ∈ `cancelable_states` AND `fm_sync_status!=="pending"` AND NO PE bloqueante | `docstatus`, `status`, `fm_sync_status`, PE activo | Abre diálogo motivos SAT |
| Revisar Estatus Cancelación | factura_fiscal_mexico.js:330 | `docstatus===1` AND `status==="PENDIENTE_CANCELACION"` | `docstatus`, `status` | Consulta estado en PAC |
| Descargar PDF+XML | factura_fiscal_mexico.js:244 | `docstatus===1` AND `fm_uuid` | `docstatus`, `fm_uuid` | Descarga archivos del SAT |
| Enviar por email | factura_fiscal_mexico.js:269 | `docstatus===1` AND `fm_uuid` | `docstatus`, `fm_uuid` | Envía CFDI por email |
| ¿Cómo sustituir? | factura_fiscal_mexico.js:307 | `sales_invoice` vinculada AND `docstatus===1` AND `fm_uuid` | `sales_invoice`, `docstatus`, `fm_uuid` | Muestra ayuda sustitución |
| Ver Sales Invoice | factura_fiscal_mexico.js:355 | `sales_invoice` vinculada | `sales_invoice` | Navega a SI |
| Cancelar FFM (liberar SI) | factura_fiscal_mexico.js:2671 | `docstatus===1` AND sin `fm_uuid` (deadlock) | `docstatus`, `fm_uuid` | Cancela FFM liberando SI |

### Mensajes / Alerts

| Mensaje | Archivo:línea | Condición | Campos que lee | Color |
|---|---|---|---|---|
| "No se puede cancelar: Pago activo" | factura_fiscal_mexico.js:222 | PE activo bloqueante | PE activo | orange/headline |
| "Error cargando motivos SAT" | factura_fiscal_mexico.js:956 | `get_sat_cancellation_motives()` falla | error | red/msgprint |
| "Factura timbrada exitosamente" | factura_fiscal_mexico.js:905 | Timbrado OK | `success` | green/alert 6s |
| "Error al Timbrar" | factura_fiscal_mexico.js:914 | Fallo timbrado | `user_error` o `error` | red/msgprint |
| "✅ Factura cancelada exitosamente" | factura_fiscal_mexico.js:1054 | Cancelación OK | `ok` | green/alert 6s |
| "Cancelación exitosa (detalles)" | factura_fiscal_mexico.js:1077 | Cancelación completada | `ffm`, `status_ffm`, `uuid`, `cancellation_date` | green/msgprint |
| "✅ DATOS FISCALES VALIDADOS" | factura_fiscal_mexico.js:1829 | RFC validado en Customer | `fm_rfc_validated` | green |
| "🔴 FALTA: [campos]" | factura_fiscal_mexico.js:1839 | Campos obligatorios vacíos | `fm_cp_cliente`, `fm_rfc_cliente`, `fm_direccion_principal_display` | red |
| "🟡 LISTO PARA VALIDAR RFC/CSF" | factura_fiscal_mexico.js:1843 | Datos completos sin RFC validado | campos rellenados | yellow |
| "🔴 SELECCIONA UN CLIENTE" | factura_fiscal_mexico.js:1804 | Sin `customer` | `customer` | red |
| "⚠️ Cliente Fiscal Diferente" | factura_fiscal_mexico.js:2331 | `customer` != customer de SI | `customer`, `sales_invoice` | yellow/HTML |
| "No puede cambiar PUE/PPD en enviados" | factura_fiscal_mexico.js:1342 | Radio cambia con `docstatus===1` | `docstatus` | alert/msgprint |
| "✅ Método cambiado a PPD" | factura_fiscal_mexico.js:1429 | Usuario selecciona PPD | radio change | orange/alert 6s |
| "✅ Método cambiado a PUE" | factura_fiscal_mexico.js:1438 | Usuario selecciona PUE | radio change | green/alert 6s |
| "Forma de pago asignada: 99" | factura_fiscal_mexico.js:1477 | Cambio a PPD | `fm_forma_pago_timbrado` | orange/alert 6s |

### Banderas (flags)

| Bandera | Archivo:línea | Cómo se calcula | Campos que lee | Qué controla |
|---|---|---|---|---|
| `isValidTaxSystem()` | factura_fiscal_mexico.js:135 | !startsWith("⚠️") AND !startsWith("❌") | `fm_tax_system` | Habilitar/deshabilitar timbrado |
| `canTimbrar` | factura_fiscal_mexico.js:189 | `docstatus===1` AND status ∈ `timbrable_states` AND tax system válido | `docstatus`, `status`, `fm_tax_system` | Mostrar botón timbrar |
| `showCancel` | factura_fiscal_mexico.js:194 | status ∈ `cancelable_states` OR `final_states` | `status` | Mostrar/ocultar sección cancelación |
| `canCancelar` | factura_fiscal_mexico.js:209 | `docstatus===1` AND status ∈ `cancelable_states` AND `fm_sync_status!=="pending"` | `docstatus`, `status`, `fm_sync_status` | Mostrar botón cancelar |
| `is_stamped` | factura_fiscal_mexico.js:240 | `!!frm.doc.fm_uuid` | `fm_uuid` | Mostrar botones descarga/email |
| `current_value==="PUE"` | factura_fiscal_mexico.js:1303 | Lectura directa | `fm_payment_method_sat` | Resaltado visual radio PUE (verde) |
| `current_value==="PPD"` | factura_fiscal_mexico.js:1303 | Lectura directa | `fm_payment_method_sat` | Resaltado visual radio PPD (naranja) |

### Campos ocultos/mostrados

| Campo | Archivo:línea | Condición | Propiedad | Valor |
|---|---|---|---|---|
| fm_tipo_comprobante | factura_fiscal_mexico.js:523 | refresh() | read_only | 1 |
| fm_forma_pago_timbrado | factura_fiscal_mexico.js:1468 | `payment_method==="PPD"` | hidden | 1 |
| fm_forma_pago_timbrado | factura_fiscal_mexico.js:1486 | `payment_method==="PUE"` | hidden | 0 |
| fiscal_fields (grupo) | factura_fiscal_mexico.js:383 | `docstatus===1` | read_only | 1 |
| uuid, serie, folio | factura_fiscal_mexico.js:1624 | status ∈ `timbrable_states` | hidden | 1 |
| uuid, serie, folio | factura_fiscal_mexico.js:1631 | status ∈ `cancelable_states` | hidden | 0 |
| cancellation_fields | factura_fiscal_mexico.js:1633 | status ∈ `cancelable_states` | hidden | 1 |
| cancellation_fields | factura_fiscal_mexico.js:1640 | status ∈ `final_states` | hidden | 0 |
| fm_lugar_expedicion, fm_branch | factura_fiscal_mexico.js:1734 | multi-sucursal enabled | hidden | 0 |
| fm_lugar_expedicion, fm_branch | factura_fiscal_mexico.js:1762 | multi-sucursal disabled | hidden | 1 |

### Permisos modificados en runtime

| Permiso | Archivo:línea | Condición | Valor | Efecto |
|---|---|---|---|---|
| cancel | factura_fiscal_mexico.js:455 | refresh() | 0 | Bloquea cancelación nativa FFM |
| amend | factura_fiscal_mexico.js:456 | refresh() | 0 | Bloquea enmiendas FFM |

### setTimeouts

| Archivo:línea | Delay | Qué hace |
|---|---|---|
| factura_fiscal_mexico.js:542 | 1500ms | Verifica y colorea sección datos |
| factura_fiscal_mexico.js:544 | 1500ms | Verifica si cliente fiscal es diferente |
| factura_fiscal_mexico.js:1266 | 500ms | Convierte Select a Radio en DOM |
| factura_fiscal_mexico.js:568 | 1000ms | Verifica Payment Entry existente |
| factura_fiscal_mexico.js:2254 | 500ms | Aplica colores a campos |
| factura_fiscal_mexico.js:496 | 0ms | Remueve botón Cancel nativo |

### Llamadas Python desde JS

| Endpoint | Archivo:línea | Para qué | Retorna |
|---|---|---|---|
| `timbrado_api.get_sat_cancellation_motives` | factura_fiscal_mexico.js:952 | Motivos SAT | `{select_options:[]}` |
| `facturacion_fiscal.api.get_fiscal_states` | factura_fiscal_mexico.js:123 | Config estados | estados y transiciones |
| `timbrado_api.timbrar_factura` | factura_fiscal_mexico.js:898 | Timbrar | `{success, user_error, error}` |
| `timbrado_api.cancelar_factura` | factura_fiscal_mexico.js:1027 | Cancelar CFDI | `{ok, ffm, status_ffm, uuid, cancellation_date}` |
| `timbrado_api.revisar_estatus_cancelacion` | factura_fiscal_mexico.js:336 | Verificar cancelación | `{message, indicator}` |
| `timbrado_api.create_substitution_si` | factura_fiscal_mexico.js:192 | Crear SI sustituto | `{new_si}` |
| `doctype.factura_fiscal_mexico.check_si_customer_rfc_validated` | factura_fiscal_mexico.js:1150 | Validar RFC | `{ok}` |
| `doctype.factura_fiscal_mexico.get_payment_entry_for_javascript` | factura_fiscal_mexico.js:2416 | PE para auto-cargar forma pago | `{success, data[]}` |
| `doctype.factura_fiscal_mexico.cancel_ffm_keep_si` | factura_fiscal_mexico.js:2675 | Cancelar FFM (deadlock) | success message |
| `complementos_pago.api.get_active_pe_for_si` | factura_fiscal_mexico.js (interno) | PE bloqueante | nombre PE o null |

---

## PAYMENT ENTRY

### Botones

| Botón | Archivo:línea | Condición de visibilidad | Campos que lee | Acción |
|---|---|---|---|---|
| Crear Complemento de Pago | payment_entry.js:207 | `docstatus===1` AND `payment_type==="Receive"` AND SI PPD timbrada referenciada | `docstatus`, `payment_type`, `references`, `fm_es_ppd` (de SI) | Crea Complemento Pago MX |
| Ver Complemento de Pago | payment_entry.js:181 | `docstatus===1` AND `fm_complemento_pago` vinculado | `fm_complemento_pago` | Navega a Complemento |

### Mensajes / Alerts

| Mensaje | Archivo:línea | Condición | Campos que lee | Color |
|---|---|---|---|---|
| "Sin facturas vinculadas" | payment_entry.js:54 | `docstatus===1` AND sin references con allocated > 0 | `references` | grey/info (injection) |
| "Pago PUE — No requiere Complemento" | payment_entry.js:72 | SIs sin `fm_es_ppd===1` | `fm_es_ppd` en SI | grey/info (injection) |
| "Complemento de Pago pendiente" | payment_entry.js:77 | SIs con `fm_es_ppd===1` | `fm_es_ppd` en SI | orange/info (injection) |
| "Este PE tiene Complemento activo" | payment_entry.js:35 | `fm_complemento_pago` con status!=="Cancelado" | `fm_complemento_pago`, `status` | orange/headline |

### Banderas (flags)

| Bandera | Archivo:línea | Cómo se calcula | Campos que lee | Qué controla |
|---|---|---|---|---|
| Tiene SI PPD referenciada | payment_entry.js:196 | Consulta SI con `fm_es_ppd===1` en `references` | `references[].reference_name`, `fm_es_ppd` | "Crear" vs "Ver" Complemento |
| Complemento activo | payment_entry.js:28 | `!!fm_complemento_pago` AND status!=="Cancelado" | `fm_complemento_pago`, `status` | Ocultar botón Cancel |

### Campos ocultos

| Campo | Archivo:línea | Condición | Propiedad | Valor |
|---|---|---|---|---|
| fm_require_complement | payment_entry.js:22 | refresh() — siempre | hidden | 1 ⚠️ siempre oculto |
| fm_complement_generated | payment_entry.js:23 | refresh() — siempre | hidden | 1 ⚠️ siempre oculto |

### HTML injection de estado

| Ubicación | Archivo:línea | Contenido | Condición |
|---|---|---|---|
| `fm_comp_summary_html` | payment_entry.js:54-83 | Resumen estado complemento con colores | `docstatus===1` |

### Llamadas Python desde JS

| Endpoint | Archivo:línea | Para qué | Retorna |
|---|---|---|---|
| `complementos_pago.api.get_active_pe_for_si` | payment_entry.js:52 | Verificar PE activo para SI | nombre PE o null |
| `api.complemento_summary.get_complemento_summary` | payment_entry.js:92 | Resumen del Complemento | `{status, uuid_sat, fecha_timbrado, serie, folio}` |
| `complementos_pago.api.crear_complemento_pago_desde_pe` | payment_entry.js:211 | Crear Complemento | `{complemento_name}` |

### Python hooks

| Hook | Archivo:línea | Estado | Qué hace |
|---|---|---|---|
| `check_ppd_requirement()` | payment_entry_validate.py:12 | ⚠️ NO-OP | Nada — pendiente Bloque 3B |
| `create_complement_if_required()` | payment_entry_submit.py | ⚠️ NO-OP | Nada — pendiente Bloque 3B |
| `block_cancel_if_complemento_activo()` | payment_entry_cancel.py:13 | ✅ Activo | Bloquea cancel si complemento activo |
| `cancel_related_complement()` | payment_entry_cancel.py:33 | ⚠️ NO-OP | Nada — pendiente implementación |

---

## COMPLEMENTO PAGO MX

### Botones

| Botón | Archivo:línea | Condición de visibilidad | Campos que lee | Acción |
|---|---|---|---|---|
| Timbrar Complemento | complemento_pago_mx.js:94 | `docstatus===0` AND status ∈ {Pendiente,Error} AND sin `uuid_sat` | `docstatus`, `status`, `uuid_sat` | Llama `timbrar_complemento_pago()` |
| Revisar Estatus Cancelación | complemento_pago_mx.js:148 | `docstatus===1` AND `status==="Pendiente Cancelación"` | `docstatus`, `status` | Consulta estado en PAC |
| Cancelar Complemento | complemento_pago_mx.js:181 | `docstatus===1` AND `status==="Timbrado"` AND roles específicos | `docstatus`, `status`, user roles | Diálogo motivo + cancela |
| Descargar PDF+XML | complemento_pago_mx.js:56 | `docstatus===1` AND status ∈ {Timbrado,Cancelado} AND `facturapi_id` | `docstatus`, `status`, `facturapi_id` | Descarga archivos fiscales |
| Ver Payment Entry | complemento_pago_mx.js:83 | `payment_entry` vinculado | `payment_entry` | Navega a PE |

### Mensajes / Alerts

| Mensaje | Archivo:línea | Condición | Campos que lee | Color |
|---|---|---|---|---|
| "Estado: [status]" | complemento_pago_mx.js:157 | Después de revisar estatus | `status` retornado | verde/naranja/rojo |
| "Complemento timbrado. UUID: [uuid]" | complemento_pago_mx.js:109 | Timbrado exitoso | `uuid` retornado | green/alert 8s |
| "PDF y XML adjuntados correctamente" | complemento_pago_mx.js:62 | Descarga exitosa | `success` retornado | green/alert 5s |
| "Error al descargar archivos" | complemento_pago_mx.js:70 | Fallo en descarga | error | red/alert 6s |

### Banderas (flags)

| Bandera | Archivo:línea | Cómo se calcula | Campos que lee | Qué controla |
|---|---|---|---|---|
| Puede timbrar | complemento_pago_mx.js:90 | `docstatus===0` AND status ∈ {Pendiente,Error} AND sin UUID | `docstatus`, `status`, `uuid_sat` | Mostrar "Timbrar" |
| Status ∈ {Timbrado,Cancelado} | complemento_pago_mx.js:53 | String matching | `status` | Mostrar "Descargar" |
| En cancelación pendiente | complemento_pago_mx.js:146 | `status==="Pendiente Cancelación"` | `status` | Mostrar "Revisar Estatus" |
| Puede cancelar | complemento_pago_mx.js:169 | `docstatus===1` AND `status==="Timbrado"` AND roles | `docstatus`, `status`, user roles | Mostrar "Cancelar" |

### Llamadas Python desde JS

| Endpoint | Archivo:línea | Para qué | Retorna |
|---|---|---|---|
| `complementos_pago.api.timbrar_complemento_pago` | complemento_pago_mx.js:100 | Timbrar | `{uuid}` |
| `complementos_pago.api.revisar_estatus_cancelacion_complemento` | complemento_pago_mx.js:150 | Verificar cancelación | `{status}` |
| `complementos_pago.api.cancelar_complemento_pago` | complemento_pago_mx.js:205 | Cancelar | `{status}` |
| `complementos_pago.api.descargar_archivos_complemento` | complemento_pago_mx.js:57 | Descargar PDF+XML | `{success}` |

---

## RESUMEN: Variables que aparecen en múltiples doctypes

| Variable | SI | FFM | PE | Complemento | Problema |
|---|---|---|---|---|---|
| `docstatus` | ✅ | ✅ | ✅ | ✅ | Consistente — nativo Frappe |
| Estado fiscal | `fm_fiscal_status` | `status` | — | `status` | ⚠️ **3 nombres para el mismo concepto** |
| Tiene UUID | via `fm_factura_fiscal_mx` | `fm_uuid` | — | `uuid_sat` | ⚠️ Fragmentado |
| Es PPD/PUE | `fm_es_ppd` | `fm_payment_method_sat` | (lee SI) | — | ⚠️ PE recalcula desde SI |
| Tiene PE activo | (llama API) | (llama API) | — | — | ⚠️ **Ambos llaman misma API independientemente** |
| Tiene complemento | — | — | `fm_complemento_pago` | `payment_entry` | Inversos del mismo link |
| Sync pendiente | — | `fm_sync_status` | — | — | Solo en FFM |

## Problemas estructurales identificados

1. **Mismo dato computado en N lugares:** `fm_es_ppd` lo calcula JS de PE consultando SI por API, JS de SI lo tiene directo, JS de FFM tiene `fm_payment_method_sat`.

2. **8 setTimeouts como parche de sincronización:** 0ms, 300ms, 500ms, 1000ms, 1500ms. Indica que la UI no tiene fuente ordenada de verdad.

3. **Estado fiscal sin nombre canónico:** `fm_fiscal_status` (SI) ≠ `status` (FFM) ≠ `status` (Complemento) aunque representan lo mismo. JS normaliza con `norm()`.

4. **`fm_require_complement` — campo fantasma:** Existe en fixture y hooks filter, se escribe en 2 momentos (crear/cancelar complemento), nunca al crear PE. UI lo ignora completamente, siempre oculto.

5. **HTML injection para mostrar estado:** `_inject_complemento_summary()` inserta HTML directamente en el DOM en lugar de usar campos Frappe reales.

6. **Llamada duplicada a `get_active_pe_for_si`:** Tanto SI como FFM llaman este endpoint independientemente al hacer refresh.

---

## Set mínimo de variables centrales propuesto

```
UNIVERSALES:
├── is_submitted          ← docstatus == 1
├── is_cancelled          ← docstatus == 2
└── fiscal_status         ← BORRADOR/TIMBRADO/CANCELADO/ERROR/PENDIENTE_CANCELACION

ESTADO FISCAL:
├── has_uuid              ← fm_uuid o uuid_sat != null
├── has_xml               ← archivo xml adjunto
├── has_pdf               ← archivo pdf adjunto
└── sync_pending          ← fm_sync_status == "pending"

MÉTODO DE PAGO:
├── is_ppd                ← metodo_pago == "PPD"
└── is_pue                ← metodo_pago == "PUE"

VÍNCULOS CROSS-DOCUMENT:
├── has_ffm               ← fm_factura_fiscal_mx existe
├── ffm_fiscal_status     ← status de la FFM vinculada
├── has_active_pe         ← existe PE submitted vinculado a la SI
├── has_complement        ← fm_complemento_pago existe
└── complement_status     ← status del complemento vinculado

ACCIONES DERIVADAS (calcula el servidor):
├── can_stamp             ← is_submitted AND fiscal_status ∈ {BORRADOR,ERROR} AND NOT sync_pending
├── can_cancel_fiscal     ← has_uuid AND fiscal_status==TIMBRADO AND NOT has_active_pe
├── can_substitute        ← has_uuid AND fiscal_status==TIMBRADO (motivo 01)
├── can_refacturar        ← fiscal_status==CANCELADO AND motivo ∈ {02,03,04}
├── can_download          ← has_uuid AND (has_xml OR has_pdf)
├── can_generate_complement ← is_submitted AND is_ppd AND has_ffm AND NOT has_complement
└── can_cancel_complement ← has_complement AND complement_status==Timbrado
```

**Total: 17 variables.** El JS actual calcula implícitamente ~40+ condiciones dispersas en 6 archivos.

---

## Plan de implementación

| Fase | Alcance | Estimado |
|---|---|---|
| **Fase 0** | Fix `check_ppd_requirement()` — campo `fm_require_complement` consistente | 1-2 días |
| **Fase 1** | Crear `fiscal_state/payment_entry_state.py` + endpoint `get_fiscal_ui_state` para PE | 1 semana |
| **Fase 2** | Migrar `fiscal_state/` para SI | 1 semana |
| **Fase 3** | Migrar `fiscal_state/` para FFM y Complemento | 1 semana |
| **Fase 4** | Tests por estado, no por botón | 3-4 días |
| **Fase 5** | Eliminar setTimeouts, HTML injection, lógica duplicada | 2-3 días |
