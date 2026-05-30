# Módulo CFDI Recibidos / Compras
## Arquitectura v4.1 — Cerrada para implementación

**Versión:** 4.1 — FINAL  
**Fecha:** 2026-05-22  
**Estado:** Arquitectura cerrada — lista para épica/issues  
**Revisiones:** v1 (concepción) → v2 (batch + pagos) → v3 (separación fiscal/financiera) → v4 (correcciones bloqueantes) → v4.1 (decisiones pendientes cerradas)

---

## 1. Introducción — Contexto para el lector externo

### 1.1 El sistema fiscal mexicano

En México, toda transacción comercial que implique un comprobante fiscal debe emitirse como un **CFDI** (Comprobante Fiscal Digital por Internet), un documento XML firmado digitalmente ante el **SAT** (Servicio de Administración Tributaria). Existen dos perspectivas del mismo documento:

- **CFDI emitido:** la empresa genera cuando vende. Factura a sus clientes.
- **CFDI recibido:** la empresa recibe cuando compra. Factura de sus proveedores.

Toda empresa mexicana debe guardar y registrar los CFDIs recibidos como respaldo de sus deducciones fiscales. El SAT puede solicitar en cualquier momento demostrar que cada gasto deducido tiene un CFDI válido de respaldo.

### 1.2 La plataforma tecnológica

La solución se construye sobre **Frappe Framework** y **ERPNext**: un ERP de código abierto con contabilidad, compras, ventas, inventario y más. Las empresas en México usan ERPNext como su sistema operativo de negocio, pero ERPNext no fue diseñado para la fiscalidad mexicana específica.

### 1.3 El proyecto facturacion_mexico

`facturacion_mexico` es una app personalizada que extiende ERPNext con todo lo que México requiere: emisión de CFDIs con timbrado digital via FacturAPI.io, complementos de pago, catálogos SAT, configuración fiscal multi-empresa.

Hasta ahora el proyecto cubre únicamente **ventas** (CFDI emitidos). Este módulo incorpora el lado de **compras** (CFDI recibidos).

---

## 2. Problema y objetivo

### El proceso hoy (manual, lento, riesgoso)
1. Contabilidad descarga XMLs del correo / portal del proveedor
2. Alguien revisa cada XML y crea la Purchase Invoice manualmente
3. Sin deduplicación: una factura puede registrarse dos veces
4. Sin trazabilidad: no hay vínculo estructurado entre XML y ERPNext

### Lo que queremos lograr
```
Usuario sube 50 XMLs
Sistema procesa automáticamente todo lo que puede
Usuario corrige solo las excepciones
Genera Purchase Invoices en lote
Trazabilidad completa: XML → Purchase Invoice → contabilidad
```

---

## 3. Principios de diseño — No cambian

| # | Principio |
|---|---|
| P1 | Sencillez operativa: flujo entendible para usuario administrativo |
| P2 | Batch desde Fase 1 — no diseñar para XML individual |
| P3 | Resolución automática máxima — intervención manual solo en excepciones |
| P4 | No autocrear Items desde conceptos XML |
| P5 | XML como fuente de verdad fiscal — conservar íntegro |
| P6 | ERPNext como fuente de verdad financiera — no duplicar pagos/saldos |
| P7 | CFDI Recibido = datos fiscales del XML. Purchase Invoice = operación financiera |

---

## 4. Decisiones cerradas en v4

### D-A: Quitar campos de destino del child fiscal

**Decisión:** `CFDI Recibido Concepto` guarda **únicamente datos extraídos del XML**. Los campos `mapped_item`, `mapped_account`, `mapped_cost_center`, `mapped_warehouse`, `mapped_type`, `mapping_rule` y `classification_status` se eliminan del child.

**Motivo:** Estos campos duplican la línea de la `Purchase Invoice Item` antes de generarla. Una vez creada la PI, la copia en el concepto queda desincronizable — exactamente la deuda que los principios buscan evitar. El destino de clasificación es estado transitorio del proceso; vive en `CFDI Concepto Mapping` (la regla) y se aplica al generar la PI, sin persistirse en el child.

**Impacto:** El child es solo lectura fiscal. El estado "¿todos los conceptos están clasificados?" se deriva en el servidor consultando `CFDI Concepto Mapping` — no se almacena en cada fila.

---

### D-B: Agregar campos fiscales críticos faltantes

**Decisión:** Los siguientes campos son obligatorios desde Fase 1. Sin ellos el módulo no sirve para deducibilidad ni auditoría SAT.

Campos agregados a `CFDI Recibido`:
- `uso_cfdi` — código de uso (G01, G03, P01...) del receptor en el XML
- `fecha_timbrado` — fecha del TimbreFiscalDigital (distinta de `issue_date`)
- `rfc_pac` — RFC del PAC que timbró
- `no_certificado_sat` — número de certificado SAT del timbre
- `no_certificado_emisor` — número de certificado del emisor
- `total_impuestos_trasladados` — suma total de IVA/IEPS trasladados
- `total_impuestos_retenidos` — suma total de ISR/IVA retenidos
- `impuestos_json` — estructura completa de impuestos del comprobante (JSON)

**Motivo:** El TimbreFiscalDigital prueba validez ante el SAT. Los totales de retención son los que más se capturan mal manualmente y los que más afectan la contabilidad. Sin `uso_cfdi` no puede verificarse que el comprobante aplica a la deducción declarada.

**Impacto:** El parser debe extraer el nodo `TimbreFiscalDigital` del complemento. Los totales de impuestos son accesibles directo en el XML (`cfdi:Impuestos`).

---

### D-C: Validar receiver_rfc contra la Company

**Decisión:** Si el `receiver_rfc` del XML no coincide con el RFC fiscal de la `Company` seleccionada, el CFDI queda en estado **Error** con mensaje: _"El receptor del CFDI no corresponde a esta empresa — no es deducible"_.

**Motivo:** Un XML donde el receptor no es tu empresa no es deducible para ti. Es un error crítico que no debe pasar silenciosamente.

**Impacto:** Durante el parseo, verificar `receiver_rfc == company.tax_id`. El RFC de la empresa está en `Company.tax_id`.

---

### D-D: Simplificar CFDI Concepto Mapping para MVP

**Decisión:** Para MVP, el mapping usa únicamente: `company`, `supplier`, `supplier_rfc`, `sat_product_key`, `target_type`, `target_item`, `target_account`, `target_cost_center`, `is_active`.

Diferidos a versión posterior: `description_pattern`, regex, `priority`, reglas complejas.

**Motivo:** El matching por regex de texto libre es un motor de reglas declarativo complejo que viola P1 (sencillez) y que en la práctica cubre pocos casos — la mayoría de proveedores recurrentes se resuelven con `supplier + sat_product_key`. Construir un motor complejo antes de validar el flujo principal es deuda anticipada.

---

### D-E: Batch best-effort con reporte por XML

**Decisión:** Al generar PIs en lote, el sistema crea las que pasan validaciones y deja pendientes las que fallan. Cada XML recibe un resultado individual: Creada / Error (con motivo). El batch nunca es all-or-nothing.

**Motivo:** En lotes de 50 XMLs, que 3 tengan error no debe bloquear las 47 restantes. La UX de la bandeja debe incluir columna de resultado post-batch.

**Impacto:** El builder retorna `dict` por XML: `{uuid: "...", status: "ok"|"error", pi: "PI-XXX"|None, message: "..."}`. La bandeja actualiza el estado de cada CFDI Recibido individualmente.

---

### D-F: Parser nuevo, no heredado de CFDIParser

**Decisión:** `CFDIRecibidoParser` es una clase nueva independiente. Reutiliza `utils/secure_xml.py` (parseo seguro) y catálogos SAT, pero **no hereda de `CFDIParser`** (que fue diseñado para insertar addendas en XMLs de emisión).

**Motivo:** Heredar una clase con propósito opuesto produce acoplamiento indeseable. El parser de addendas opera sobre XMLs que la empresa emite; el parser de recibidos opera sobre XMLs que la empresa recibe. Comparten utilidades, no clase base.

---

### D-G: CFDI 3.3 rechazado con error controlado

**Decisión:** El sistema soporta únicamente CFDI versión 4.0. Un XML con `Version="3.3"` produce error controlado: _"CFDI versión 3.3 no soportada. Solo se aceptan CFDIs versión 4.0."_ El CFDI Recibido queda en estado Error.

**Motivo:** CFDI 3.3 dejó de poderse emitir en 2022. Para MVP no vale la complejidad de soportar ambas versiones con namespaces distintos. Si aparecen XMLs 3.3 en el futuro, se evalúa entonces.

---

## 5. Modelo de datos v4

### 5.1 `CFDI Recibido` — campos definitivos

| Campo | Tipo | Fuente | Notas |
|---|---|---|---|
| `uuid` | Data (único) | XML | Identificador fiscal único |
| `xml_file` | Attach | Ingesta | XML original — inmutable |
| `xml_hash` | Data | Ingesta | SHA256 para deduplicación |
| `company` | Link → Company | Usuario | Empresa receptora |
| `status` | Select | Sistema | Estado de procesamiento |
| `error_message` | Text | Sistema | Detalle de error |
| `cfdi_type` | Data | XML | I / E / P / N |
| `version` | Data | XML | Debe ser "4.0" |
| `issue_date` | Date | XML | Fecha emisión del XML |
| `fecha_timbrado` | Datetime | XML/Timbre | Del TimbreFiscalDigital (**nuevo**) |
| `serie` | Data | XML | Serie del comprobante |
| `folio` | Data | XML | Folio del comprobante |
| `currency` | Link → Currency | XML | Moneda |
| `exchange_rate` | Float | XML | TipoCambio |
| `subtotal` | Currency | XML | SubTotal |
| `discount` | Currency | XML | Descuento |
| `total_impuestos_trasladados` | Currency | XML | Total IVA/IEPS (**nuevo**) |
| `total_impuestos_retenidos` | Currency | XML | Total ISR/IVA retenido (**nuevo**) |
| `total` | Currency | XML | Total |
| `impuestos_json` | JSON | XML | Estructura completa impuestos (**nuevo**) |
| `uso_cfdi` | Data | XML | UsoCFDI del receptor (**nuevo**) |
| `supplier_rfc` | Data | XML | RFC emisor |
| `supplier_name` | Data | XML | Nombre emisor |
| `supplier_tax_regime` | Data | XML | Régimen fiscal emisor |
| `receiver_rfc` | Data | XML | RFC receptor |
| `receiver_name` | Data | XML | Nombre receptor |
| `rfc_pac` | Data | XML/Timbre | RFC del PAC (**nuevo**) |
| `no_certificado_sat` | Data | XML/Timbre | Cert SAT del timbre (**nuevo**) |
| `no_certificado_emisor` | Data | XML | Cert del emisor (**nuevo**) |
| `fm_payment_method_sat` | Link → Metodo Pago SAT | XML | PUE / PPD |
| `fm_payment_form_sat` | Link → Forma Pago SAT | XML | 01, 03, 04... |
| `supplier` | Link → Supplier | Resuelto | Proveedor ERPNext resuelto |
| `purchase_invoice` | Link → Purchase Invoice | Generado | PI creada |
| `conceptos` | Table | XML | CFDI Recibido Concepto |

**Estados del flujo:**
```
Cargado           → XML almacenado, pendiente parseo
Parseado          → datos extraídos, resolviendo proveedor
Falta proveedor   → RFC no encontrado en Suppliers
Falta clasif.     → al menos un concepto sin regla de mapping aplicable (estado derivado en servidor, no almacenado en child)
Listo             → proveedor + todos los conceptos clasificables
Factura creada    → Purchase Invoice generada y ligada
Duplicado         → UUID ya existe en el sistema
Error             → ver error_message (incl. receiver_rfc ≠ Company, CFDI 3.3, etc.)
```

---

### 5.2 `CFDI Recibido Concepto` — solo datos XML

**Eliminados vs v3:** `mapped_type`, `mapped_item`, `mapped_account`, `mapped_cost_center`, `mapped_warehouse`, `mapping_rule`, `classification_status`.

| Campo | Tipo | Fuente |
|---|---|---|
| `sat_product_key` | Data | XML — ClaveProdServ |
| `description` | Text | XML — Descripción |
| `quantity` | Float | XML — Cantidad |
| `unit_key` | Data | XML — ClaveUnidad |
| `unit` | Data | XML — Unidad |
| `unit_price` | Currency | XML — ValorUnitario |
| `amount` | Currency | XML — Importe |
| `discount` | Currency | XML — Descuento |
| `tax_object` | Data | XML — ObjetoImp |
| `taxes_json` | JSON | XML — impuestos del concepto |

El child es inmutable una vez parseado. El mapeo se aplica al vuelo al generar la PI.

---

### 5.3 `CFDI Concepto Mapping` — simplificado para MVP

**Eliminados vs v3:** `description_pattern`, `priority`, `notes`.

| Campo | Tipo | Descripción |
|---|---|---|
| `company` | Link → Company | Vacío = aplica a todas |
| `supplier` | Link → Supplier | Vacío = aplica a todos |
| `supplier_rfc` | Data | Alternativa a supplier Link |
| `sat_product_key` | Data | Vacío = cualquier clave SAT |
| `target_type` | Select | Item / ExpenseAccount (GroupedItem diferido) |
| `target_item` | Link → Item | Si target_type = Item |
| `target_account` | Link → Account | Si target_type = ExpenseAccount |
| `target_cost_center` | Link → Cost Center | |
| `is_active` | Check | |

**Lógica de matching para MVP:**
1. Buscar regla exacta: `supplier_rfc + sat_product_key`
2. Fallback: `supplier_rfc + sat_product_key vacío` (cualquier clave del proveedor)
3. Fallback: `sat_product_key + supplier vacío` (cualquier proveedor con esa clave)
4. Sin match → concepto sin clasificar

**Derivación del estado del CFDI Recibido (calculado en servidor):**
```
Si todos los conceptos tienen match en CFDI Concepto Mapping → "Listo"
Si al menos uno no tiene match → "Falta clasif."
```
Este estado **no se almacena en el child** `CFDI Recibido Concepto`. Lo calcula el servidor al llamar `ConceptClassifier.classify_all()` o al consultar si el CFDI está listo para PI.

---

## 6. Especificación del PurchaseInvoiceBuilder

Esta es la pieza de mayor riesgo contable. Se especifica aquí para que no quede a interpretación del implementador.

### 6.1 Validaciones previas (bloquean generación)

| Validación | Error si falla |
|---|---|
| `supplier` resuelto | "Proveedor no asignado" |
| Todos los conceptos tienen regla de mapping aplicable | "Hay conceptos sin clasificar" |
| `uuid` no existe en otra PI | "Factura duplicada" |
| `receiver_rfc == company.tax_id` | "Receptor no corresponde a esta empresa" |
| `version == "4.0"` | "Versión CFDI no soportada" |
| `cfdi_type == "I"` | Para MVP solo tipo Ingreso (proveedor vende) |

### 6.2 Construcción de líneas (Purchase Invoice Items)

Para cada concepto en `CFDI Recibido Concepto`, obtener la regla de mapping:

```
Si target_type == "Item":
    PI Item: item_code = target_item, qty = concepto.quantity,
             rate = concepto.unit_price, cost_center = target_cost_center

Si target_type == "ExpenseAccount":
    PI Item: item_code = None, expense_account = target_account,
             qty = 1, rate = concepto.amount,
             cost_center = target_cost_center
```

`GroupedItem` (acumulación de múltiples conceptos en un solo item destino) queda **diferido**. No entra en MVP. Si se necesita agrupar, el usuario mapea cada concepto a `ExpenseAccount` individualmente.

Regla: **nunca usar `update_stock = True`** para CFDI recibidos de servicios/gastos. Solo si el item_code tiene `is_stock_item = True` y el CFDI corresponde a compra de mercancía (fuera del MVP).

### 6.3 Construcción de impuestos (tabla `taxes` nativa ERPNext)

Este es el punto más crítico. No usar `tax_total` como número libre — construir la tabla nativa.

**Para IVA trasladado:**
```
Por cada traslado en impuestos_json donde impuesto = "002" (IVA):
    Agregar fila a Purchase Taxes and Charges:
      charge_type = "Actual"
      tax_amount = traslado.importe
      account_head = cuenta_iva_acreditable_compras (de Configuracion Fiscal Mexico, sección compras)
      description = "IVA {tasa}% trasladado"
      cost_center = company.cost_center
```

**Para IEPS trasladado (impuesto = "003"):**
```
    account_head = cuenta_ieps_compras (de Configuracion Fiscal Mexico, sección compras)
```

**Para retenciones (ISR = "001", IVA = "002" en retenciones):**
```
⚠️ PENDIENTE DE VALIDACIÓN EN ERPNext v16:
La estructura correcta de `Purchase Taxes and Charges` para impuestos retenidos
(si usar `add_deduct_tax = "Deduct"`, `charge_type = "Actual"` con importe negativo,
o una combinación específica de v16) debe validarse con un XML real de servicios
profesionales (honorarios) antes de implementar Fase 3. No asumir que el
comportamiento de v15 se mantiene igual.

Placeholder para implementación:
    account_head = cuenta_isr_retenido_compras / cuenta_iva_retenido_compras
    (fuente: Configuracion Fiscal Mexico, sección compras)
    estructura exacta: a definir en Fase 3 tras prueba con XML real
```

**Fuente de cuentas:** `Configuracion Fiscal Mexico` — **sección específica de compras** (nueva, a agregar al DocType). Las cuentas actuales de ese DocType corresponden a emisión. Nunca hardcodear nombres de cuentas.

### 6.4 Validación de totales y tolerancia de redondeo

```
xml_total = CFDI Recibido.total
erp_total = PI.grand_total  (calculado por ERPNext)

diferencia = abs(xml_total - erp_total)
tolerancia = frappe.db.get_single_value(
    "Facturacion Mexico Settings", "cfdi_recibido_rounding_tolerance"
) or 0.02  # default 2 centavos si no configurado

Si diferencia <= tolerancia:
    Aceptar. Registrar en log si diferencia > 0.
Si diferencia > tolerancia:
    Error bloqueante: "Diferencia de totales: XML={xml_total}, ERPNext={erp_total}"
    El CFDI Recibido queda en estado Error.
    No se guarda la PI.
```

**Regla:** Confiar en el cálculo de ERPNext. No sobreescribir `grand_total`. Solo validar que la diferencia esté dentro de tolerancia.

### 6.5 Campos de cabecera de la PI

```python
pi.supplier = cfdi_recibido.supplier
# bill_no robusto — evitar colisiones por proveedor
if cfdi_recibido.serie and cfdi_recibido.folio:
    candidate = f"{cfdi_recibido.serie}-{cfdi_recibido.folio}"
elif cfdi_recibido.folio:
    candidate = cfdi_recibido.folio
else:
    candidate = cfdi_recibido.uuid  # UUID completo como fallback

# Validar colisión supplier + bill_no
existing = frappe.db.exists("Purchase Invoice", {
    "supplier": cfdi_recibido.supplier,
    "bill_no": candidate
})
pi.bill_no = candidate if not existing else cfdi_recibido.uuid

pi.bill_date = cfdi_recibido.issue_date
# posting_date: default today() como fecha de registro contable.
# Dejar preparado para hacerlo configurable por empresa o seleccionable
# en UI batch (pendiente de confirmar con contabilidad piloto en Fase 3).
pi.posting_date = today()
pi.currency = cfdi_recibido.currency
pi.conversion_rate = cfdi_recibido.exchange_rate
pi.buying_price_list = "Standard Buying"
pi.company = cfdi_recibido.company

# Referencia fiscal
pi.remarks = f"CFDI UUID: {cfdi_recibido.uuid}"

# No crear pago automático
pi.is_paid = 0
pi.payment_terms_template = None
```

### 6.6 Trazabilidad XML desde Purchase Invoice

El XML original vive como adjunto del `CFDI Recibido` y no se duplica físicamente en la PI. Duplicar el archivo crea riesgo de deduplicación/borrado por el hash de Frappe y acopla los ciclos de vida de dos documentos.

**Mecanismo de trazabilidad:**
1. `CFDI Recibido.purchase_invoice` (Link → PI) — ya definido.
2. Custom Field `fm_cfdi_recibido` (Link → CFDI Recibido) en `Purchase Invoice` — navegación inversa desde PI.
3. Custom Field `fm_cfdi_uuid` (Data, read_only, indexed) en `Purchase Invoice` — UUID consultable para deduplicación y reportes.

```python
# Después de pi.submit():
pi.db_set("fm_cfdi_recibido", cfdi_recibido.name)
pi.db_set("fm_cfdi_uuid", cfdi_recibido.uuid)
# El XML se accede desde PI → link fm_cfdi_recibido → CFDI Recibido → xml_file
```

**Decisión de Fase 3:** Si el cliente requiere ver el XML directamente desde la PI, implementar un botón "Ver XML" que cargue el archivo desde el `CFDI Recibido` ligado — no copiar el archivo.

### 6.7 No crear Payment Entry — regla explícita

```python
# PROHIBIDO en PurchaseInvoiceBuilder:
# - frappe.call("make_payment_entry")
# - pi.make_payment_entry()
# - frappe.new_doc("Payment Entry")
# - cualquier operación de pago
```

El pago es responsabilidad del usuario, no del builder. ERPNext calcula `outstanding_amount` nativamente al hacer submit de la PI — no se asume ni establece manualmente.

### 6.8 Resultado por XML (batch best-effort)

```python
def build(self, cfdi_recibido_name: str) -> dict:
    try:
        # ... construcción ...
        return {
            "cfdi_recibido": cfdi_recibido_name,
            "status": "ok",
            "purchase_invoice": pi.name,
            "message": None
        }
    except Exception as e:
        return {
            "cfdi_recibido": cfdi_recibido_name,
            "status": "error",
            "purchase_invoice": None,
            "message": str(e)
        }
```

---

## 7. Estructura del módulo

```
facturacion_mexico/
├── cfdi_recibidos/                    ← Módulo nuevo
│   ├── __init__.py
│   ├── api.py                         # Endpoints: subir XML, procesar, generar PI
│   ├── doctype/
│   │   ├── cfdi_recibido/
│   │   ├── cfdi_recibido_concepto/
│   │   └── cfdi_concepto_mapping/
│   ├── parsers/
│   │   └── cfdi_recibido_parser.py    # Clase nueva — no hereda de CFDIParser
│   ├── services/
│   │   ├── xml_ingestion.py           # Carga, deduplicación, validación
│   │   ├── supplier_resolver.py       # RFC → Supplier
│   │   ├── concept_classifier.py      # Aplica CFDI Concepto Mapping
│   │   └── purchase_invoice_builder.py
│   └── tests/
│
└── utils/
    └── secure_xml.py                  # Compartido — parser seguro base
```

**Reutilización clara:**
- `utils/secure_xml.py` → reutilizado directamente
- Catálogos SAT → compartidos sin modificación
- `validaciones/api.py` → validación RFC si necesario
- `Configuracion Fiscal Mexico` → fuente de cuentas de impuestos
- `CFDIParser` de addendas → NO reutilizado. Propósito diferente.

---

## 8. Bandeja operativa

### Vista principal (Fase 1)

```
┌────────────────────────────────────────────────────────────────────┐
│  CFDI Recibidos                                   [Subir XMLs]     │
├────────────────────────────────────────────────────────────────────┤
│  Empresa: [Todas ▼]  Estado: [Todos ▼]  Fecha: [Mayo 2026 ▼]      │
├─────┬───────────────────┬──────────┬───────────────┬──────────────┤
│  ☐  │ Proveedor         │ Total    │ Estado        │ Resultado     │
├─────┼───────────────────┼──────────┼───────────────┼──────────────┤
│  ☑  │ Office Depot      │ $3,480   │ ✅ Listo      │              │
│  ☑  │ Pemex             │ $1,200   │ ✅ Listo      │              │
│  ☑  │ Telcel            │ $890     │ ✅ Listo      │              │
│  ☐  │ —                 │ $2,100   │ ⚠ Falta prov.│              │
│  ☐  │ Serv. General     │ $450     │ ⚠ Falta clas.│              │
│  ☐  │ —                 │ —        │ 🔴 Error      │ Ver detalle  │
│  ☐  │ Papelería Sur     │ $380     │ 🔁 Duplicado  │              │
├─────┴───────────────────┴──────────┴───────────────┴──────────────┤
│ Post-batch:  PI-0045 ✅  PI-0046 ✅  PI-0047 ❌ diferencia $0.05  │
├────────────────────────────────────────────────────────────────────┤
│                    [Crear Purchase Invoices]  3 seleccionadas       │
└────────────────────────────────────────────────────────────────────┘
```

La columna **Resultado** se puebla post-batch: muestra PI creada o error por XML. El batch no bloquea el lote completo si algunos fallan.

---

## 9. Plan de fases v4

### Fase 1 — Ingesta, parseo y bandeja

**Entregables:**
- DocTypes: `CFDI Recibido`, `CFDI Recibido Concepto`
- `CFDIRecibidoParser`: extrae todo del XML incluyendo timbre, retenciones, uso_cfdi
- `XMLIngestionService`: carga múltiple, hash, UUID, deduplicación, validación versión y receiver_rfc
- Bandeja operativa con filtros y estados
- API de carga (`/api/method/cfdi_recibidos.api.upload_xml`)

**No incluye:** resolución de proveedor, mapping, generación de PI.

**Criterio de éxito:** Subir 10 XMLs. Los parseados muestran emisor, receptor, timbre, totales de impuestos, método de pago SAT. Los que tienen receiver_rfc incorrecto quedan en Error.

---

### Fase 2 — Resolución de proveedor y clasificación

**Entregables:**
- `SupplierResolver`: `tax_id == RFC emisor` → Supplier
- DocType `CFDI Concepto Mapping` (simplificado MVP)
- `ConceptClassifier`: aplica reglas sobre conceptos
- UI inline en bandeja para asignar proveedor
- UI inline para clasificar concepto y crear regla de mapping

**Criterio de éxito:** XML en "Falta proveedor" se resuelve desde la bandeja sin cambiar de pantalla. La regla guardada se aplica automáticamente al siguiente XML del mismo proveedor con misma clave SAT.

---

### Fase 3 — Generación de Purchase Invoice

**Entregables:**
- `PurchaseInvoiceBuilder` completo (según sección 6)
- Construcción de tabla de impuestos nativa ERPNext
- Validación de totales con tolerancia configurable por empresa (default 0.02)
- Generación individual y en lote (best-effort)
- XML adjunto a la PI
- Liga `CFDI Recibido.purchase_invoice`

**Criterio de éxito:** 10 PIs generadas en lote. Cada PI tiene: impuestos en tabla nativa (IVA, retenciones en cuentas correctas), XML adjunto, `grand_total` dentro de tolerancia del XML, `outstanding_amount = total`.

---

### Fase 4 — Pagos (post-MVP)

**Alcance:** Botón "Registrar Pago" en CFDI Recibido que invoca `make_payment_entry` nativo de ERPNext. No guarda estado de pago en CFDI Recibido. El estado financiero vive en `PI.status` y `PI.outstanding_amount`.

Para gastos de empleados: definir cuando haya caso de negocio real (cuenta puente, Employee Advance, Journal Entry según diseño aprobado entonces).

---

### Fase 5 — Gastos de empleados (diferida)

Evaluar cuando haya requisito concreto: Purchase Invoice + cuenta puente del empleado o Expense Claim para el reembolso.

---

## 10. Temas diferidos — Lista definitiva

Estos temas **no se implementan** en ninguna fase del MVP. Quedan documentados para evaluación futura:

| Tema | Motivo del diferimiento |
|---|---|
| CFDI 3.3 | Sin emisión desde 2022. Rechazar con error controlado es suficiente |
| REP recibidos (complemento de pago) | Flujo distinto — requiere ligar con PI previa |
| Notas de crédito de proveedor (CFDI E recibido) | Requiere ligar con PI original y ajuste contable |
| Cancelaciones / sustituciones entre UUIDs | Relación UUID-anterior / UUID-nuevo no modelada aún |
| Consulta automática al SAT | API de descarga masiva requiere FIEL — fuera de alcance |
| Recepción por correo electrónico | Infraestructura distinta |
| OCR sobre PDFs | No CFDIs |
| Expense Claim integrado | Sin requisito concreto definido |
| Regex y prioridades en mapping | Motor de reglas complejo — diferir hasta validar flujo básico |
| GroupedItem en mapping | Acumulación de múltiples conceptos en un Item — diferir hasta validar flujo con Item y ExpenseAccount |
| Estructura nativa retenciones ERPNext v16 | Validar con XML real de honorarios antes de implementar — no asumir comportamiento v15 |
| CFDI tipo P recibido (pago de cliente) | Caso inverso — no aplica a compras |

---

## 11. Riesgos — v4

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Tabla de impuestos PI mal construida | Alta | Crítico | Sección 6.3 especifica cada escenario; pruebas con XMLs reales antes de Fase 3 |
| receiver_rfc ≠ Company silencioso | Alta | Alto | Validación obligatoria en parseo — estado Error con mensaje claro |
| Diferencia de totales > tolerancia | Media | Alto | Tolerancia configurable por empresa (default 0.02); error bloqueante si excede |
| Items basura en catálogo | Alta | Alto | No autocrear Items nunca — solo mediante mapping explícito |
| Duplicados silenciosos | Media | Alto | Deduplicación por UUID y hash desde Fase 1 |
| Proveedor no encontrado por RFC | Alta | Bajo | Estado "Falta proveedor" — resolución manual desde bandeja |
| Batch lento con 100+ XMLs | Media | Medio | Best-effort por XML; evaluar cola de trabajos si necesario |
| XMLs CFDI 3.3 en lote | Media | Bajo | Rechazar con error controlado individual — no bloquea el lote |

---

## 12. Decisiones cerradas en v4.1

Las siguientes decisiones estaban pendientes en v4 y quedan cerradas:

| # | Decisión |
|---|---|
| DP-1 | El DocType se llamará **`CFDI Recibido`** |
| DP-2 | Tolerancia de redondeo: **configurable por empresa en `Facturacion Mexico Settings`**, campo `cfdi_recibido_rounding_tolerance`, default `0.02` |
| DP-3 | Las cuentas de impuestos para compras viven en **`Configuracion Fiscal Mexico`**, en una sección específica de compras. Las cuentas actuales de esa configuración son para emisión (ventas); se agrega una sección hermana para recepción (compras). No hardcodear cuentas. |

---

## 13. Criterios de aceptación — v4

### Fase 1
- [ ] Subir 50 XMLs simultáneamente sin error técnico
- [ ] XML con `receiver_rfc ≠ company.tax_id` queda en Error con mensaje claro
- [ ] XML CFDI 3.3 queda en Error con mensaje claro
- [ ] UUID duplicado queda en estado Duplicado — no crea segundo registro
- [ ] Datos del TimbreFiscalDigital (fecha, RFC PAC, certificado) extraídos correctamente
- [ ] `total_impuestos_trasladados` y `total_impuestos_retenidos` extraídos correctamente
- [ ] `uso_cfdi` y `fm_payment_method_sat` extraídos correctamente
- [ ] `impuestos_json` contiene estructura completa de impuestos del comprobante
- [ ] Bandeja muestra estados operativos (no técnicos) con filtros funcionales

### Fase 2
- [ ] RFC emisor resuelve automáticamente a Supplier si `Supplier.tax_id` coincide
- [ ] Resolución de proveedor desde bandeja sin cambiar de pantalla
- [ ] Regla de mapping guardada aplica automáticamente en siguiente XML del mismo proveedor + clave SAT
- [ ] Conceptos sin regla aplicable: CFDI queda en "Falta clasif." con lista de conceptos pendientes

### Fase 3
- [ ] Purchase Invoice generada tiene impuestos en tabla nativa ERPNext (no texto libre)
- [ ] IVA trasladado en cuenta de IVA acreditable correcta
- [ ] ISR retenido en cuenta ISR retenido con estructura nativa correcta de ERPNext v16 (validada con XML real)
- [ ] IVA retenido en cuenta IVA retenido con estructura nativa correcta de ERPNext v16 (validada con XML real antes de implementar)
- [ ] `PI.grand_total` dentro de la tolerancia configurada en `Facturacion Mexico Settings` (default 0.02) respecto a `CFDI Recibido.total`
- [ ] Si diferencia > tolerancia configurada: error bloqueante, PI no guardada, CFDI en Error
- [ ] XML adjunto a la PI
- [ ] `CFDI Recibido.purchase_invoice` ligado correctamente
- [ ] Batch de 45 XMLs: los que pasan → PI creada, los que fallan → Error con motivo, sin bloquear los demás
- [ ] Columna de resultado en bandeja post-batch muestra estado por XML
- [ ] No se crea Payment Entry — ERPNext calcula `outstanding_amount` nativamente al submit de la PI
- [ ] Catálogo de Items no recibe ningún Item nuevo por el proceso

---

*Versión 4.1 — 2026-05-22. Decisiones DP-1/DP-2/DP-3 cerradas. `GroupedItem` diferido. Retenciones ERPNext v16 marcadas para validación con XML real antes de Fase 3. Adjunto XML corregido a File nativo. Tolerancia de redondeo configurable. No hay decisiones pendientes — arquitectura lista para épica/issues.*
