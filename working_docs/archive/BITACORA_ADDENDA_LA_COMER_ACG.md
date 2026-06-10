# Bitácora: Prueba real Addenda La Comer — Company ACG

**Fecha inicio:** 2026-05-30
**Objetivo:** Configurar desde cero Company ALIMENTOS DEL CAMPO Y GANADERIA
en facturacion-v16.dev y ejecutar prueba real de factura con Addenda La Comer.
**Site:** facturacion-v16.dev
**Rama:** feature/addenda-la-comer
**Propósito secundario:** Detectar gaps/errores en la documentación existente
comparando esta bitácora contra docs/usuario/.

---

## Datos de referencia

### Company emisora
| Campo | Valor |
|---|---|
| Razón social | ALIMENTOS DEL CAMPO Y GANADERIA |
| RFC | ACG090430DF5 |
| Código Postal fiscal | 52787 |
| Régimen fiscal | 601 - General de Ley Personas Morales |
| Domicilio | AVENIDA LA PALMA 8 INT 504, COL. SAN FERNANDO LA HERRADURA |
| Municipio/Estado | HUIXQUILUCAN, MEXICO |

### Cliente receptor
| Campo | Valor |
|---|---|
| Nombre | COMERCIAL CITY FRESKO |
| RFC | CCF121101KQ4 |
| fm_buyer_gln | 7505000350009 |
| fm_seller_gln | 0000000905551 |
| fm_seller_id | 905551 |
| fm_invoice_creator_gln | 7505000350009 |
| fm_dias_credito_addenda | 25 |

### Sucursal destino (Address)
| Campo | Valor |
|---|---|
| Nombre | CITY FRESKO SUC. 403 CITY MARKET PLAZA CARSO |
| fm_gln | 7505000354038 |
| address_line1 | LAGO ZURICH 245 AMPLIACION GRANADA |
| city | MEXICO DF |
| pincode | 11529 |

---

## Pasos ejecutados

### Paso 1 — Verificación previa Company ✅
**Fecha:** 2026-05-30
**Resultado:** No existía. Creada con datos ACG.

---

### Paso 2 — Crear Company ALIMENTOS DEL CAMPO Y GANADERIA ✅
**Fecha:** 2026-05-30
**Resultado:** Company creada. ERPNext generó Chart of Accounts automáticamente.

---

### Paso 2b — Establecer Company default ✅
**Fecha:** 2026-05-30
**Acción:** Setup → Global Defaults → Default Company → ALIMENTOS DEL CAMPO Y GANADERIA
**Resultado:** ✅ Confirmado por usuario.

---

### Paso 3 — GAP-01 resuelto: Facturacion Mexico Company Settings ✅
**Fecha:** 2026-06-01
**Problema original:** `Facturacion Mexico Settings` era Single — compartido entre companies.
**Solución implementada:** PR #172 + eliminación completa del Single.
Nuevo DocType: `Facturacion Mexico Company Settings` (por Company).
**Estado:** Single eliminado de código y BD. Company Settings pendiente de crear
para ALIMENTOS DEL CAMPO Y GANADERIA en GUI.

---

### Paso 4 — Customer COMERCIAL CITY FRESKO ✅
**Fecha:** 2026-06-01
**Resultado:** Customer existe en BD con todos los campos EDI configurados:
- fm_buyer_gln, fm_dias_credito_addenda
- fm_seller_gln, fm_seller_id, fm_invoice_creator_gln (nuevos campos de arquitectura)
- fm_requires_addenda = 1, fm_default_addenda_type = La Comer

---

### Paso 5 — Address sucursal destino (City Fresko Plaza Carso) ✅
**Fecha:** 2026-06-01
**Resultado:** Address COMERCIAL CITY FRESKO-Billing con fm_gln = 7505000354038 configurada.

---

### Paso 6 — Addenda Type La Comer — template Jinja2 ✅
**Fecha:** 2026-06-01
**Resultado:** Template XML capturado en campo xml_template del Addenda Type "La Comer".
Usa nueva arquitectura: datos EDI desde Customer y Address, no desde Addenda Configuration.
Variables pendientes: `importe_letras` (número a letras), `emisor_calle`, `emisor_ciudad`
(requieren Address de Company configurada).

---

### Paso 7 — Addenda Configuration ✅ (eliminado de arquitectura)
**Fecha:** 2026-06-01
**Decisión:** Addenda Configuration ya no es necesaria para datos EDI.
La nueva arquitectura mueve todos los IDs al Customer y Address.
Addenda Configuration permanece en el sistema pero opcional.

---

### Paso 8 — Rediseño arquitectura addendas ✅
**Fecha:** 2026-06-01
**Cambios:**
- Tab "Fiscal México" en Customer (entre Tax y Accounting)
- Customer: fm_seller_gln, fm_seller_id, fm_invoice_creator_gln, fm_buyer_gln, fm_dias_credito_addenda
- Address: fm_gln para GLN de tienda destino
- generic_addenda_generator.py: lee datos desde Customer/Address/Company address
- Addenda Type: template puro sin IDs de empresa

---

### Paso 9 — Company Address ALIMENTOS DEL CAMPO Y GANADERIA ✅
**Fecha:** 2026-06-01
**Resultado:** Address creada y vinculada via Dynamic Link. is_primary_address=1.
- address_line1: AV DE LA PALMA 8 504 SAN FERNANDO LA HERRADURA
- city: Huixquilucan
- pincode: 52787
emisor_cp, emisor_calle, emisor_ciudad ahora funcionan en el template de addenda.

---

### Paso 10 — Facturacion Mexico Company Settings para ACG ✅
**Fecha:** 2026-06-01
**Resultado:** Registro creado en GUI con API Key sandbox y modo sandbox activado.

---

### Paso 10b — Configuracion Fiscal Mexico para ACG ✅
**Fecha:** 2026-06-01
**Resultado:** Wizard ejecutado. 4 templates STCT generados (Nacional Básico/IEPS/Retenciones/Total).
Filtro de cuentas de impuesto corregido: ahora excluye grupos (is_group=0).
Templates ITT asignados a Item Groups fiscales automáticamente.

---

### Paso 10c — Esqueleto de Item Groups fiscales ampliado ✅
**Fecha:** 2026-06-01
**Resultado:** 38 subgrupos creados bajo los 6 grupos IEPS/IVA.
Implementación idempotente: solo crea si no existe, nunca modifica/borra.
Tests: test_setup_fiscal_item_groups.py (5 casos).
**GAP detectado:** Items son globales del site — empresa de consultoria ve productos de verduras.
Posible deal breaker para conglomerados multi-giro. Issue pendiente de abrir.

---

### Paso 11 — Items de prueba ACELGA PZA y ALBAHACA PZA ✅
**Fecha:** 2026-06-01
**Resultado:** Ambos items creados en GUI.
- Item Group: Artículos con IVA al 0% > Frutas y Verduras
- ObjetoImp: 02 (sí objeto de impuesto, tasa 0%)
- fm_producto_servicio_sat: 50402800 / 50404101

---

## Pasos pendientes

- [ ] Paso 12 — Crear Addenda Product Mapping
  - ACELGA-PZA → GTIN 45865, descripción "ACELGA PZA", UOM EA
  - ALBAHACA-PZA → GTIN 31943, descripción "ALBAHACAR   1 PZA", UOM EA
- [ ] Paso 13 — Crear Sales Invoice de prueba
- [ ] Paso 14 — Previsualizar XML de addenda sin timbrar
- [ ] Paso 15 — Timbrar (solo con autorización explícita del usuario)
- [ ] Paso 16 — Validar XML final contra ACG090430DF5FA0124810.xml

---

## Gaps detectados

### GAP-01 — Facturacion Mexico Settings Single (RESUELTO PR #172)
Multi-company requería configuración por Company. Resuelto con nuevo DocType.

### GAP-02 — importe_letras no automatizado
El campo `<ZZZ>` de la addenda requiere el monto total en letras (p.ej. "SEIS MIL...").
No hay helper de número-a-letras en el generador. Template usa `{{ importe_letras | default("") }}`.
Pendiente: implementar helper o que el usuario lo capture manualmente via addenda_values.

### GAP-03 — emisor_calle / emisor_ciudad desde Company Address
El generador lee estos datos de la dirección principal de Company via Dynamic Link.
Si la Company no tiene Address configurada, retorna cadena vacía.
Solución: capturar Address para ALIMENTOS DEL CAMPO Y GANADERIA en GUI (Paso 9).
