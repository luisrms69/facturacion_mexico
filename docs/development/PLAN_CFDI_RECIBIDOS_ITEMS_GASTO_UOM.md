# PLAN — Items de Gasto y UOM para CFDI Recibidos

**Fecha:** 2026-05-26  
**Estado:** En implementación — Bloque A completado  
**Rama:** feature/cfdi-recibidos-fase3-pi  
**Módulo:** cfdi_recibidos

---

## 1. Resumen ejecutivo

El módulo CFDI Recibidos tiene ingesta, parser y DocTypes funcionales. El siguiente paso
es vincular los conceptos XML a Items de ERPNext para poder generar Purchase Invoices.
Se crearán 84 Items genéricos (uno por cada Item Group hoja bajo "Gastos"), se agregarán
3 campos de clasificación en CFDI Recibido Concepto, y se construirá un `ItemResolver`
que propone Items automáticamente. La UI de clasificación permite que el usuario confirme
o ajuste la propuesta. El Bloque E (diagnóstico UOM no-SAT) es prerequisito hard del hito
de PI/facturación.

---

## 2. Alcance

**Dentro:**
- Items de gasto: `is_stock_item=0`, `is_purchase_item=1`, `is_sales_item=0`
- 84 Items genéricos, uno por Item Group hoja bajo "Gastos"
- UOM SAT semánticamente correctas por categoría
- ClaveProdServ por categoría (con nivel de confianza explícito)
- Campos `item_group`, `item_code`, `item_resolution` en CFDI Recibido Concepto
- ItemResolver con 3 niveles de matching (Mapeado → Específico → Genérico)
- UI de clasificación de conceptos
- Diagnóstico y limpieza de UOM no-SAT (prerequisito PI)

**Fuera:**
- Costos, inventario, reventa, Items que también se venden
- Purchase Invoice Builder (hito posterior)
- TaxResolver y resolución de cuentas contables (hito posterior)
- Cuenta contable: `f(familia SAT del Department, Item Group) → Account` — no se define aquí
- CFDI de tipo distinto a gasto (complementos de pago, nómina tipo N)

---

## 3. Decisiones cerradas

**DC-01 — Department ≠ resolutor de Item Group**  
Department solo determina familia SAT (601/602/603/604). Es una dimensión contable
para el momento en que se construya la PI. Item Group define naturaleza del gasto y
es una dimensión independiente asignada manualmente por el usuario en la UI.

**DC-02 — 84 Items genéricos, uno por hoja**  
No existe un único "Gasto CFDI". No 11 Items. No un Item por línea XML. No un Item
por proveedor como regla principal.

**DC-03 — E48 no es UOM universal**  
`E48 - Servicio` solo se usa donde aplica genuinamente: honorarios de personas morales
(la empresa factura "1 servicio"), honorarios aduanales, fletes por envío, gastos de
importación por operación, servicios de construcción/urbanización por proyecto.
No como comodín para cubrir categorías sin UOM clara.

**DC-04 — ClaveProdServ del Item ≠ ClaveProdServ del XML**  
El XML trae la ClaveProdServ que el emisor eligió. El Item genérico lleva la ClaveProdServ
que el receptor considera correcta para ese tipo de gasto. Son datos independientes.

**DC-05 — Bloqueo (no advertencia) en selección inconsistente**  
Si `item_group` del concepto no coincide con `item_group` del Item seleccionado → 
`frappe.throw()`. No `frappe.msgprint`. No es una advertencia.

**DC-06 — Cuatro valores fijos de `item_resolution`**  
`Genérico` / `Específico` / `Mapeado` / `Manual`. Solo el ItemResolver asigna los tres
primeros. La UI asigna `Manual` cuando el usuario selecciona un Item diferente al sugerido.

**DC-07 — Cuenta contable es futura**  
`f(familia SAT, Item Group) → Account` se definirá en el hito de PI/TaxResolver.
No se diseña en estos Bloques.

**DC-08 — Bloque E es prerequisito hard de PI**  
La limpieza de UOM no-SAT no es opcional ni postergable. El hito "Generar PI"
está bloqueado hasta que Bloque E esté completo y la limpieza ejecutada y aprobada.

**DC-09 — KWH pendiente validación SAT**  
`KWH - Kilowatt hora` no se agrega al fixture hasta validar contra `c_ClaveUnidad.xls`
oficial. Es un bloqueante antes de PI/facturación. El ítem #51 (Energía eléctrica)
usa `MON - Mes` como UOM provisional documentada.

---

## 4. Arquitectura final

```
CFDI Recibido
  ├── company
  ├── Department → familia SAT (601/602/603/604)  [solo para PI, no para Item Group]
  └── conceptos (child table: CFDI Recibido Concepto)
        ├── sat_product_key    — clave SAT del emisor
        ├── no_identificacion  — código interno del proveedor
        ├── description        — texto libre del emisor (≠ descripción oficial SAT)
        ├── quantity, unit_key, unit, unit_price, amount
        ├── tax_object, taxes_json
        ├── item_group         ← nuevo (Bloque B)
        ├── item_code          ← nuevo (Bloque B)
        └── item_resolution    ← nuevo (Bloque B)

ItemResolver (Bloque C) — propone, no escribe BD directamente
  Prioridad 1 (Mapeado):   CFDI Concepto Mapping activo
                           company + supplier_rfc + sat_product_key → target_item
                           (solo cuando target_type = 'Item' y is_active = 1)
  Prioridad 2 (Específico): Item Supplier
                           supplier + no_identificacion → item
  Prioridad 3 (Genérico):  item_group → Item genérico GASTO-{CAT}-NNN
  Sin match:               item_code = vacío, item_resolution = nulo

UI de clasificación (Bloque D):
  - Grid de conceptos con item_code/item_group vacíos
  - Usuario asigna item_group por línea
  - Sistema llama ItemResolver → muestra item_code sugerido
  - Validación: item_group concepto ≠ item_group del Item → bloqueo
  - Usuario confirma o selecciona otro (item_resolution = Manual)

Estado CFDI Recibido — flujo completo:
  Falta proveedor
  → Proveedor encontrado
  → Falta departamento
  → Departamento asignado
  → Falta clasificación     ← nuevo
  → Clasificado             ← nuevo
  → Convertido a PI         (hito posterior, requiere Bloque E completado)
```

---

## 5. Matriz de 84 Items genéricos

Convenciones:
- UOM: código SAT (ver sección 6 para nombres completos)
- ClaveProdServ: 8 dígitos UNSPSC
- 🟢 Alta confianza | 🟡 Media — requiere validación SAT | 🔴 Baja — requiere validación SAT

### 5.1 Nómina y prestaciones (31 items)

> Nota: Estos Items raramente tienen CFDI de proveedor externo directo (nómina es interna;
> IMSS/Infonavit se pagan vía SUA/SIPARE, no CFDI). Los Items existen para consistencia
> del catálogo. `fm_producto_servicio_sat` se carga si el código existe en SAT Producto
> Servicio; si no, queda vacío y se completa cuando se cargue el catálogo completo.

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 1 | Sueldos y salarios | GASTO-NOM-001 | MON | 80141600 🟡 | HR management services |
| 2 | Compensaciones | GASTO-NOM-002 | H87 | 80141600 🟡 | Pago único por persona |
| 3 | Tiempos extras | GASTO-NOM-003 | HUR | 80141600 🟡 | Se factura por hora |
| 4 | Premios de asistencia | GASTO-NOM-004 | H87 | 80141600 🟡 | Pago discreto |
| 5 | Premios de puntualidad | GASTO-NOM-005 | H87 | 80141600 🟡 | Pago discreto |
| 6 | Vacaciones | GASTO-NOM-006 | DAY | 80141600 🟡 | Días de goce |
| 7 | Prima vacacional | GASTO-NOM-007 | H87 | 80141600 🟡 | Pago único |
| 8 | Prima dominical | GASTO-NOM-008 | DAY | 80141600 🟡 | Por día domingo |
| 9 | Días festivos | GASTO-NOM-009 | DAY | 80141600 🟡 | Por día |
| 10 | Gratificaciones | GASTO-NOM-010 | H87 | 80141600 🟡 | Pago único |
| 11 | Primas de antigüedad | GASTO-NOM-011 | H87 | 80141600 🟡 | Pago único |
| 12 | Aguinaldo | GASTO-NOM-012 | H87 | 80141600 🟡 | Pago anual único |
| 13 | Indemnizaciones | GASTO-NOM-013 | H87 | 80141600 🟡 | Pago único por evento |
| 14 | Destajo | GASTO-NOM-014 | H87 | 80141600 🟡 | Por unidad producida |
| 15 | Despensa | GASTO-NOM-015 | H87 | 80141600 🟡 | Por trabajador |
| 16 | Transporte | GASTO-NOM-016 | MON | 78101600 🟡 | Subsidio transporte mensual |
| 17 | Servicio médico | GASTO-NOM-017 | MON | 85100000 🟡 | Prima mensual |
| 18 | Ayuda en gastos funerarios | GASTO-NOM-018 | H87 | 80141600 🟡 | Pago único por evento |
| 19 | Fondo de ahorro | GASTO-NOM-019 | MON | 80141600 🟡 | Aportación mensual |
| 20 | Cuotas sindicales | GASTO-NOM-020 | MON | 80141600 🟡 | Mensual |
| 21 | PTU | GASTO-NOM-021 | H87 | 80141600 🟡 | Distribución anual |
| 22 | Estímulo al personal | GASTO-NOM-022 | H87 | 80141600 🟡 | Pago único |
| 23 | Previsión social | GASTO-NOM-023 | MON | 80141600 🟡 | Mensual |
| 24 | Aportaciones para el plan de jubilación | GASTO-NOM-024 | MON | 80141600 🟡 | Mensual |
| 25 | Otras prestaciones al personal | GASTO-NOM-025 | MON | 80141600 🟡 | Genérico |
| 26 | Cuotas al IMSS | GASTO-NOM-026 | MON | 84121500 🟡 | Aportación mensual seguridad social |
| 27 | Aportaciones al Infonavit | GASTO-NOM-027 | MON | 84121500 🟡 | Mensual |
| 28 | Aportaciones al SAR | GASTO-NOM-028 | MON | 84121500 🟡 | Mensual |
| 29 | Impuesto estatal sobre nóminas | GASTO-NOM-029 | MON | 93121800 🔴 | Impuesto mensual estatal |
| 30 | Otras aportaciones | GASTO-NOM-030 | MON | 80141600 🟡 | Genérico |
| 31 | Asimilados a salarios | GASTO-NOM-031 | MON | 80141600 🟡 | Mensual |

### 5.2 Servicios administrativos y profesionales (14 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 32 | Servicios administrativos | GASTO-SRV-001 | MON | 80111500 🟡 | Retainer mensual |
| 33 | Servicios administrativos partes relacionadas | GASTO-SRV-002 | MON | 80111500 🟡 | Retainer mensual |
| 34 | Honorarios a personas físicas residentes nacionales | GASTO-SRV-003 | HUR | 80111500 🟡 | PF cobra por hora |
| 35 | Honorarios a personas físicas residentes nacionales partes relacionadas | GASTO-SRV-004 | HUR | 80111500 🟡 | PF cobra por hora |
| 36 | Honorarios a personas físicas residentes del extranjero | GASTO-SRV-005 | HUR | 80111500 🟡 | PF extranjero, hora |
| 37 | Honorarios a personas físicas residentes del extranjero partes relacionadas | GASTO-SRV-006 | HUR | 80111500 🟡 | PF extranjero, hora |
| 38 | Honorarios a personas morales residentes nacionales | GASTO-SRV-007 | E48 | 80111500 🟡 | PM factura "1 servicio" |
| 39 | Honorarios a personas morales residentes nacionales partes relacionadas | GASTO-SRV-008 | E48 | 80111500 🟡 | PM factura "1 servicio" |
| 40 | Honorarios a personas morales residentes del extranjero | GASTO-SRV-009 | E48 | 80111500 🟡 | PM factura "1 servicio" |
| 41 | Honorarios a personas morales residentes del extranjero partes relacionadas | GASTO-SRV-010 | E48 | 80111500 🟡 | PM factura "1 servicio" |
| 42 | Honorarios aduanales personas físicas | GASTO-SRV-011 | E48 | 78181500 🟡 | Por operación aduanal; customs clearance |
| 43 | Honorarios aduanales personas morales | GASTO-SRV-012 | E48 | 78181500 🟡 | Por operación aduanal |
| 44 | Honorarios al consejo de administración | GASTO-SRV-013 | MON | 80111500 🟡 | Mensual |
| 45 | Asistencia técnica | GASTO-SRV-014 | HUR | 80111501 🟡 | Por hora de asesoría técnica |

### 5.3 Arrendamientos (3 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 46 | Arrendamiento a personas físicas residentes nacionales | GASTO-ARR-001 | MON | 80131501 🟡 | Renta mensual, PF |
| 47 | Arrendamiento a personas morales residentes nacionales | GASTO-ARR-002 | MON | 80131501 🟡 | Renta mensual, PM |
| 48 | Arrendamiento a residentes del extranjero | GASTO-ARR-003 | MON | 80131501 🟡 | Renta mensual, extranjero |

### 5.4 Servicios básicos y operación (10 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 49 | Teléfono, internet | GASTO-OPR-001 | MON | 83111500 🟢 | Factura mensual telecom |
| 50 | Agua | GASTO-OPR-002 | MTQ | 83111700 🟡 | Metro cúbico, recibo SACMEX/CMAS |
| 51 | Energía eléctrica | GASTO-OPR-003 | MON | 81101500 🟢 | **UOM PROVISIONAL** — KWH pendiente validación c_ClaveUnidad SAT (DC-09). Bloqueante antes de PI. |
| 52 | Vigilancia y seguridad | GASTO-OPR-004 | MON | 92101500 🟡 | Contrato mensual |
| 53 | Limpieza | GASTO-OPR-005 | MON | 76111501 🟡 | Contrato mensual |
| 54 | Mantenimiento y conservación | GASTO-OPR-006 | MON | 72101500 🟡 | Contrato mensual de mantenimiento |
| 55 | Papelería y artículos de oficina | GASTO-OPR-007 | H87 | 44121700 🟡 | Por pieza/paquete |
| 56 | Cuotas y suscripciones | GASTO-OPR-008 | MON | 80141600 🔴 | ⚠️ Catch-all: software→43231500; gremios/colegios→sin código mejor confirmado. Validar con fiscalista. |
| 57 | Capacitación al personal | GASTO-OPR-009 | ACT | 86101500 🟡 | Por evento/curso |
| 58 | Uniformes | GASTO-OPR-010 | H87 | 53101600 🟡 | Por pieza de ropa de trabajo |

### 5.5 Movilidad, viáticos y combustibles (2 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 59 | Combustibles y lubricantes | GASTO-MOV-001 | LTR | 15101500 🟢 | Litro de gasolina/diesel |
| 60 | Viáticos y gastos de viaje | GASTO-MOV-002 | DAY | 90111501 🔴 | Por día; validar si existe este código en c_ClaveProdServ |

### 5.6 Comercialización y ventas (3 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 61 | Propaganda y publicidad | GASTO-VNT-001 | MON | 82101500 🟢 | Retainer agencia mensual |
| 62 | Comisiones sobre ventas | GASTO-VNT-002 | MON | 80141600 🔴 | ⚠️ Comisiones a agentes de venta. Sin código específico confirmado. Pendiente validación. |
| 63 | Comisiones por tarjetas de crédito | GASTO-VNT-003 | MON | 84111500 🔴 | Cobro mensual del banco; validar código |

### 5.7 Seguros, impuestos y cumplimiento (4 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 64 | Seguros y fianzas | GASTO-SEG-001 | ANN | 84121500 🟢 | Prima anual |
| 65 | Otros impuestos y derechos | GASTO-SEG-002 | H87 | 93121800 🔴 | Pago único por derecho |
| 66 | Recargos fiscales | GASTO-SEG-003 | H87 | 93121800 🔴 | Pago único de recargo |
| 67 | Prediales | GASTO-SEG-004 | ANN | 93121800 🔴 | Pago anual predial |

### 5.8 Donativos y no deducibles (2 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 68 | Donativos y ayudas | GASTO-DON-001 | H87 | 93141500 🔴 | Por evento de donativo |
| 69 | Gastos no deducibles (sin requisitos fiscales) | GASTO-DON-002 | H87 | 80141600 🔴 | ⚠️ Catch-all; sin clasificación SAT útil para gastos no deducibles |

### 5.9 Regalías y propiedad intelectual (8 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 70 | Regalías sujetas a otros porcentajes | GASTO-REG-001 | MON | 80141800 🔴 | License fee mensual; validar código |
| 71 | Regalías sujetas al 5% | GASTO-REG-002 | MON | 80141800 🔴 | License fee mensual |
| 72 | Regalías sujetas al 10% | GASTO-REG-003 | MON | 80141800 🔴 | License fee mensual |
| 73 | Regalías sujetas al 15% | GASTO-REG-004 | MON | 80141800 🔴 | License fee mensual |
| 74 | Regalías sujetas al 25% | GASTO-REG-005 | MON | 80141800 🔴 | License fee mensual |
| 75 | Regalías sujetas al 30% | GASTO-REG-006 | MON | 80141800 🔴 | License fee mensual |
| 76 | Regalías sin retención | GASTO-REG-007 | MON | 80141800 🔴 | License fee mensual |
| 77 | Patentes y marcas | GASTO-REG-008 | ANN | 80141800 🔴 | Renovación anual; buscar código IMPI específico |

### 5.10 Logística, fletes e importación (4 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 78 | Fletes y acarreos | GASTO-LOG-001 | E48 | 78101800 🟡 | Por envío nacional |
| 79 | Gastos de importación | GASTO-LOG-002 | E48 | 78181500 🟡 | Por operación de importación |
| 80 | Fletes del extranjero | GASTO-LOG-003 | E48 | 78101800 🟡 | Por envío internacional |
| 81 | Recolección de bienes del sector agropecuario y/o ganadero | GASTO-LOG-004 | E48 | 78102200 🔴 | Por servicio de recolección |

### 5.11 Construcción, urbanización y otros (3 items)

| # | Item Group hoja | item_code | UOM | ClaveProdServ | Notas |
|---|---|---|---|---|---|
| 82 | Gastos generales de urbanización | GASTO-OBR-001 | E48 | 72131500 🟡 | Por proyecto/etapa |
| 83 | Gastos generales de construcción | GASTO-OBR-002 | E48 | 72131500 🟡 | Por proyecto/etapa |
| 84 | Otros gastos generales | GASTO-OBR-003 | E48 | 80141600 🔴 | ⚠️ Catch-all; sin clasificación SAT mejor disponible |

### 5.12 Resumen UOM

| UOM | Cantidad | Categorías típicas |
|---|---|---|
| MON - Mes | 35 | Nómina mensual, arrendamientos, servicios recurrentes, regalías |
| H87 - Pieza | 19 | Pagos únicos discretos (aguinaldo, papelería, uniformes) |
| E48 - Servicio | 13 | Honorarios PM, aduanales, fletes, construcción |
| HUR - Hora | 6 | Honorarios PF, tiempos extras, asistencia técnica |
| DAY - Día | 4 | Vacaciones, prima dominical, días festivos, viáticos |
| ANN - Año | 3 | Seguros, prediales, patentes |
| ACT - Actividad | 1 | Capacitación |
| LTR - Litro | 1 | Combustibles |
| MTQ - Metro cúbico | 1 | Agua |
| MON provisional | 1 | Energía eléctrica (#51) — KWH pendiente |
| **Total** | **84** | |

---

## 6. Lista de UOM SAT requeridas

| Código | Nombre | En fixture | Uso en Items |
|---|---|---|---|
| H87 | Pieza | ✅ | 19 Items |
| KGM | Kilogramo | ✅ | Sin uso en matriz actual |
| GRM | Gramo | ✅ | Sin uso en matriz actual |
| LTR | Litro | ✅ | Combustibles |
| MLT | Mililitro | ✅ | Sin uso en matriz actual |
| MTR | Metro | ✅ | Sin uso en matriz actual |
| CMT | Centímetro | ✅ | Sin uso en matriz actual |
| MMT | Milímetro | ✅ | Sin uso en matriz actual |
| MTK | Metro cuadrado | ✅ | Sin uso en matriz actual |
| MTQ | Metro cúbico | ✅ | Agua |
| HUR | Hora | ✅ | Honorarios PF, tiempos extras |
| MIN | Minuto | ✅ | Sin uso en matriz actual |
| SEC | Segundo | ✅ | Sin uso en matriz actual |
| DAY | Día | ✅ | Vacaciones, viáticos |
| E48 | Servicio | ✅ | Honorarios PM, fletes, construcción (13 Items) |
| ACT | Actividad | ✅ | Capacitación |
| E51 | Trabajo | ✅ | Sin uso en matriz actual |
| MON | Mes | ✅ | 35 Items |
| ANN | Año | ✅ | Seguros, prediales, patentes |
| NA | No Aplica | ✅ | Sin uso en matriz actual |
| **KWH** | **Kilowatt hora** | **❌ FALTA** | **⚠️ BLOQUEANTE ANTES DE PI — validar contra c_ClaveUnidad.xls SAT. Mientras: ítem #51 usa MON provisional.** |

---

## 7. Lista de ClaveProdServ requeridas (27 códigos únicos)

### 7.1 Por qué 27 (análisis de consolidación)

La sesión previa de diseño identificó 34 códigos únicos. El plan actual usa 27 porque:

- Los ítems de nómina (1–25, 30–31) comparten `80141600` (HR management services).
  Es defensible: la naturaleza del servicio es la misma aunque los conceptos contables
  sean distintos.
- IMSS, Infonavit y SAR (26–28) usan `84121500` (beneficios/seguridad social) — diferente
  de nómina general, más específico.
- Los 8 tramos de regalías (70–77) comparten `80141800` — mismo tipo de servicio con
  variación solo en la tasa de retención.
- Honorarios aduanales (42–43) usan `78181500` (customs clearance) — mismo código
  que Gastos de importación, semánticamente correcto.

Tres usos de `80141600` marcados como `⚠️` donde el código es un catch-all y debería
refinarse con el catálogo oficial:
- Ítem 56 (Cuotas y suscripciones): software → 43231500; otros → sin código mejor confirmado
- Ítem 62 (Comisiones sobre ventas): sin código de comisiones a agentes confirmado
- Ítems 69, 84 (catch-alls): sin alternativa SAT clara

### 7.2 Tabla de 27 códigos

| Código | Descripción propuesta | Ítems | Confianza |
|---|---|---|---|
| 15101500 | Combustibles derivados del petróleo | 59 | 🟢 |
| 44121700 | Material de oficina y papelería | 55 | 🟡 |
| 53101600 | Ropa de trabajo y uniformes | 58 | 🟡 |
| 72101500 | Mantenimiento de edificios | 54 | 🟡 |
| 72131500 | Construcción y obras civiles | 82, 83 | 🟡 |
| 76111501 | Servicios de limpieza | 53 | 🟡 |
| 78101600 | Transporte subsidio personal | 16 | 🟡 |
| 78101800 | Fletes nacionales e internacionales | 78, 80 | 🟡 |
| 78102200 | Recolección agropecuaria | 81 | 🔴 |
| 78181500 | Despacho aduanal / customs clearance | 42, 43, 79 | 🟡 |
| 80111500 | Consultoría y asesoría profesional | 32–41, 44 | 🟡 |
| 80111501 | Asistencia técnica | 45 | 🟡 |
| 80131501 | Arrendamiento de bienes inmuebles | 46, 47, 48 | 🟡 |
| 80141600 | Servicios de RRHH y administración | 1–25, 30, 31, 56⚠️, 62⚠️, 69⚠️, 84⚠️ | 🟡/🔴 |
| 80141800 | Gestión de propiedad intelectual | 70–77 | 🔴 |
| 81101500 | Distribución de energía eléctrica | 51 | 🟢 |
| 82101500 | Publicidad y mercadotecnia | 61 | 🟢 |
| 83111500 | Servicios de telecomunicaciones | 49 | 🟢 |
| 83111700 | Suministro de agua | 50 | 🟡 |
| 84111500 | Servicios financieros | 63 | 🔴 |
| 84121500 | Seguros y beneficios sociales | 26, 27, 28, 64 | 🟢/🟡 |
| 85100000 | Servicios de salud | 17 | 🟡 |
| 86101500 | Capacitación y formación | 57 | 🟡 |
| 90111501 | Viáticos y gastos de viaje | 60 | 🔴 |
| 92101500 | Vigilancia y seguridad | 52 | 🟡 |
| 93121800 | Derechos e impuestos gubernamentales | 29, 65, 66, 67 | 🔴 |
| 93141500 | Donativos | 68 | 🔴 |

**Gate de validación SAT:** Ningún código 🔴 (9 códigos) se carga como "validado" en
producción sin cruzar contra `c_ClaveProdServ.xls` oficial. Para Bloque A se crean como
placeholder documentado.

---

## 8. Estrategia UOM no-SAT (Bloque E — prerequisito PI)

### 8.1 Estado actual del sitio

- 20 UOMs SAT en fixture (`fixtures/uom.json`): correctas y garantizadas
- ~239 UOMs ERPNext creadas en setup wizard (`uom_data.json`): NO se recrean con `bench migrate`
- La mayoría de los 239 están en inglés sin clave SAT en el nombre: "Kg", "Nos", "Hour", etc.

### 8.2 Cuatro buckets de clasificación

**Bucket A — Conservar (SAT activos):**  
Los 20 del fixture actual + KWH cuando se valide. Son los únicos que se usan en Items
de gasto. No tocar.

**Bucket B — Borrar (sin referencias):**  
UOMs ERPNext sin ninguna referencia en Item, PI, PO, PR, SI ni UOM Conversion Factor.
Se borran con `frappe.delete_doc`. Requieren diagnóstico one-off previo para identificarlas.

**Bucket C — Inhabilitar (con referencias históricas):**  
UOMs ERPNext que tienen registros existentes. No se pueden borrar sin romper FK.
Se marca `enabled = 0`.  
Efecto: ya no aparecen en el selector de UOM en nuevos documentos. Los documentos
existentes conservan su valor sin error. Las conversiones UOM siguen activas.

**Bucket D — Protegido (proceso controlado requerido):**  
- `Nos`: Hardcodeado en `Stock Settings.stock_uom`. También referenciado en
  `install_fixtures.py` y `defaults_setup.py` de ERPNext.  
  Para inhabilitar: primero actualizar `Stock Settings.stock_uom → H87 - Pieza`,
  verificar que no tenga UOM Conversion Factor con ítems activos, luego mover a B o C.  
  Proceso requiere autorización explícita.

### 8.3 Impacto de `enabled = 0`

| Escenario | Impacto |
|---|---|
| Nuevo documento, campo UOM | No aparece en selector — no se puede seleccionar en nuevas líneas |
| Documento existente guardado | Sin impacto — el valor persiste en BD |
| Item con stock_uom inhabilitada | El ítem se muestra; el valor existe pero no aparece en selector al editar |
| UOM Conversion Factor | No afectado por `enabled` — las conversiones siguen activas |
| `bench migrate` con fixture | Frappe NO borra UOMs que no están en fixture (no es mecanismo delete-not-in-fixture) |

### 8.4 Checklist del diagnóstico (Bloque E)

Para cada UOM del sitio, el script one-off reporta:
- ¿Aparece en `tabItem` como `stock_uom`?
- ¿Aparece en `tabUOM Conversion Factor` (from_uom o to_uom)?
- ¿Aparece en `tabUOM Conversion Detail` (uom)?
- ¿Aparece en `tabPurchase Invoice Item`, `tabSales Invoice Item`, `tabPurchase Order Item`?
- ¿Es el valor de `Stock Settings.stock_uom`?
- ¿Está en el fixture `uom.json` (es SAT)?

Output: lista clasificada en buckets → ejecutar borrado/inhabilitación solo con
**autorización explícita** del usuario.

### 8.5 Prohibiciones

- No SQL directo (`DELETE FROM tabUOM`)
- No `frappe.db.sql` para borrar
- Usar `frappe.delete_doc("UOM", name)` para Bucket B
- Usar `frappe.db.set_value("UOM", name, "enabled", 0)` para Bucket C
- Toda ejecución requiere autorización explícita
- `bench execute` con escrituras requiere autorización previa

### 8.6 Dependencia con PI

**El hito "Generar PI" está bloqueado hasta que Bloque E esté completo.**  
Usar UOMs no-SAT en Purchase Invoice implica que el RFC del proveedor en el XML no
coincidirá con la UOM declarada en el ítem — problema de consistencia fiscal.

---

## 9. Flujo de clasificación de conceptos

```
1. CFDI Recibido llega al estado "Departamento asignado"
2. Usuario abre CFDI Recibido
3. Grid de conceptos muestra líneas con item_group/item_code vacíos
4. Para cada línea, usuario selecciona item_group (naturaleza del gasto)
5. Sistema llama ItemResolver.propose(concepto, item_group):
   Prioridad 1: CFDI Concepto Mapping activo
                company + supplier_rfc + sat_product_key → target_item
                (solo target_type = 'Item' y is_active = 1)
                → item_resolution = "Mapeado"
   Prioridad 2: Item Supplier
                supplier + no_identificacion → item
                → item_resolution = "Específico"
   Prioridad 3: Item genérico por item_group
                → item_resolution = "Genérico"
   Sin match: item_code = vacío, item_resolution = nulo
6. Sistema muestra item_code sugerido en la línea
7. Validación de consistencia:
   item_group del concepto ≠ item_group del Item seleccionado
   → frappe.throw() (bloquea guardado)
8. Usuario confirma → item_resolution conserva Genérico/Específico/Mapeado
   Usuario selecciona otro Item → item_resolution = "Manual"
9. Todos los conceptos tienen item_code
10. Estado CFDI Recibido → "Clasificado"
    Habilita: botón "Generar PI" (hito posterior, requiere Bloque E)
```

---

## 10. Campos nuevos en CFDI Recibido Concepto (Bloque B)

| fieldname | label | fieldtype | options | Notas |
|---|---|---|---|---|
| `item_group` | Grupo de Gasto | Link | Item Group | Filtro: solo hojas bajo "Gastos" |
| `item_code` | Item | Link | Item | Filtro: `is_purchase_item=1, is_stock_item=0` + validación item_group |
| `item_resolution` | Resolución | Select | Genérico\nEspecífico\nMapeado\nManual | Escrito por ItemResolver o por UI; Read-only directo en formulario |

**Regla de validación (controller):**
```python
if concepto.item_code:
    item_group_item = frappe.db.get_value("Item", concepto.item_code, "item_group")
    if item_group_item and concepto.item_group != item_group_item:
        frappe.throw(
            _(f"El Item {concepto.item_code} pertenece al grupo '{item_group_item}', "
              f"no a '{concepto.item_group}'.")
        )
```

---

## 11. Bloques de implementación

### Bloque A — Setup de Items genéricos, UOM y ClaveProdServ ✅ COMPLETADO

**Commit:** `30022f9` — feat(cfdi-recibidos): Bloque A — 84 Items genéricos de gasto + setup idempotente  
**Fecha:** 2026-05-26  
**Tests:** 10/10 ✅ (`facturacion_mexico/tests/test_setup_expense_items.py`)

**Lo que se implementó:**

1. `facturacion_mexico/setup/cfdi_received_expense_items.py`:
   - `ensure_cfdi_received_expense_items()` — idempotente, hard-skip en Items existentes
   - 84 Items según la matriz de sección 5 (item_code `GASTO-{CAT}-{NNN}`)
   - `fm_producto_servicio_sat`: asignado solo si el código existe en `SAT Producto Servicio`
   - Guard de compilación: `assert len(_ITEMS) == 84`
   - Retorna `{creados, existentes, sin_clave_prod_serv}`
2. `hooks.py`: `after_migrate` incluye la función
3. `install.py`: `after_install` incluye la función con try/except + log_error
4. Tests: idempotencia, campos clave (NOM-001, OPR-003, SRV-007, MOV-001, ARR-001, SEG-001), flags is_stock_item/is_purchase_item/is_sales_item

**UOM de ítem #51 (Energía eléctrica):** `MON - Mes` provisional. KWH es pendiente bloqueante (DC-09).

**No incluye:** UI, campos nuevos en Concepto, PI.

### Bloque B — Campos de clasificación en CFDI Recibido Concepto

1. Agregar `item_group`, `item_code`, `item_resolution` en `cfdi_recibido_concepto.json`
2. `bench migrate` para aplicar schema
3. Agregar validación de consistencia en controller (`frappe.throw()`)
4. Agregar estados "Falta clasificación" y "Clasificado" en flujo de CFDI Recibido
5. Tests para validación de consistencia

### Bloque C — ItemResolver

1. Crear `facturacion_mexico/cfdi_recibidos/services/item_resolver.py`
2. Clase `ItemResolver` con método `propose(concepto_doc, item_group) → {item_code, item_resolution}`
3. Tres niveles de matching (Mapeado → Específico → Genérico)
4. Tests unitarios exhaustivos (mock BD lookups — no `frappe.get_doc`)

### Bloque D — UI/API de clasificación

1. Endpoint de clasificación en `cfdi_recibidos/api.py`
2. JS en CFDI Recibido: trigger al cambiar `item_group` → llama ItemResolver → puebla `item_code`
3. Botón "Clasificar automáticamente" — aplica ItemResolver a todos los conceptos
4. Filtro en selector `item_code`: solo Items de gasto + bloqueo por item_group
5. Transición de estado automática al completar clasificación
6. Tests de integración

### Bloque E — Diagnóstico y limpieza UOM no-SAT

**Es prerequisito hard del hito de PI (DC-08).**

1. Crear `one_offs/diagnose_uom_non_sat.py` — solo lectura
2. Script clasifica cada UOM en los 4 buckets (A/B/C/D)
3. Reporta: conteo de referencias por UOM en tablas clave + Stock Settings
4. Output: lista de candidatos a borrar (B) y a inhabilitar (C)
5. Revisar output con usuario → **autorización explícita** antes de ejecutar limpieza
6. Ejecutar limpieza en one-off separado tras autorización

---

## 12. Riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| KWH no en c_ClaveUnidad SAT | Media | Medio | Usar MON provisional; KWH se agrega cuando se valide |
| Códigos ClaveProdServ 🔴 incorrectos | Alta | Bajo (metadatos, no bloquean operación) | Placeholders documentados; corregibles sin schema change |
| fm_producto_servicio_sat: código no existe en SAT Producto Servicio | Media | Bajo | Función usa `frappe.db.exists` antes de asignar; deja vacío si no existe |
| CFDI Concepto Mapping con target_type='ExpenseAccount' | Conocido | Bajo | ItemResolver ignora estos registros; documentado |
| UOM "Nos" en Stock Settings bloquea cleanup de Bucket D | Media | Bajo en esta fase | Bloque E solo diagnostica; cleanup de Nos requiere autorización explícita |
| ERPNext filtra Items con `is_purchase_item=0` en PI | Bajo (contemplado) | Alto si se omite | Verificar campo en función de setup |
| item_group vacío al llamar ItemResolver | Baja | Bajo | ItemResolver retorna `None` si item_group no está; UI muestra como pendiente |

---

## 13. Qué queda fuera

- Costos, inventario, reventa, ítems que también se venden
- Purchase Invoice Builder (hito posterior, requiere Bloque E previo)
- TaxResolver (hito posterior)
- Cuenta contable por línea — `f(familia SAT, Item Group) → Account`
- Validación de totales de impuestos vs PI
- Workflow de aprobación de PI
- Catálogo completo c_ClaveProdServ en BD (~54,000 registros)
- Limpieza de UOM "Nos" y Stock Settings (diagnosticada en Bloque E, ejecutada en hito separado)
- CFDI de tipo P (Complemento Pago) y nómina tipo N

---

## 14. Pendientes bloqueantes antes de PI/facturación

| Pendiente | Bloque | Gate |
|---|---|---|
| Validar KWH en c_ClaveUnidad SAT | A/fixture | Antes de PI — actualizar UOM ítem #51 |
| Validar 9 códigos ClaveProdServ 🔴 | A | Antes de producción |
| Completar Bloque E (diagnóstico + limpieza UOM) | E | Antes de habilitar "Generar PI" |

