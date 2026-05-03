# MÓDULO 2 — VERIFICACIÓN FLUJO DE TIMBRADO CFDI
==================================================
Fecha: 2026-05-01  
Site: facturacion-v16.dev  
Bench: /home/erpnext/frappe-bench-v16  

---

## Resultados

| # | Check | Estado | Detalle |
|---|-------|--------|---------|
| 1 | Sales Invoices submitted disponibles | ✓ | 200 submitted — 60 sin timbrar, 0 timbradas, 0 canceladas |
| 2 | FacturAPI sandbox responde | ✓ | HTTP 200 — `{"success": true, "message": "Conexión exitosa con FacturAPI"}` |
| 3 | DocType Factura Fiscal Mexico carga | ✓ | 64 fields |
| 4 | Método `timbrar_factura` existe | ✓ | `facturacion_mexico.facturacion_fiscal.timbrado_api.timbrar_factura` — `@frappe.whitelist` |

---

## Detalle: Sales Invoices submitted

| Estado fiscal | Cantidad |
|---------------|---------|
| Sin timbrar (`fm_fiscal_status` vacío) | **60** |
| Timbradas | 0 |
| Canceladas | 0 |
| **Total submitted** | **200** |

Muestra de las 3 más recientes (todas del mismo cliente, sin `fm_fiscal_status`):

| Factura | Cliente | Total | Fiscal Status |
|---------|---------|-------|---------------|
| ACC-SINV-2025-01676 | CONCESIONARIA VUELA COMPAÑIA DE AVIACION | 8,020.82 | — |
| ACC-SINV-2025-01675 | CONCESIONARIA VUELA COMPAÑIA DE AVIACION | 8,020.82 | — |
| ACC-SINV-2025-01674 | CONCESIONARIA VUELA COMPAÑIA DE AVIACION | 8,020.82 | — |

---

## Detalle: Métodos whitelisted en timbrado_api.py

| Método | Descripción |
|--------|-------------|
| `timbrar_factura(sales_invoice)` | Timbrado principal |
| `cancelar_factura(sales_invoice, uuid, ffm_name, motivo, substitution_uuid)` | Cancelación |
| `create_substitution_si(si_name)` | Refacturación (sustitución) |
| `get_sat_cancellation_motives()` | Catálogo de motivos SAT |
| `test_connection()` | Prueba de conectividad al PAC |

---

## Advertencia heredada del Módulo 1

21 de 37 ítems no tienen `fm_producto_servicio_sat` asignado. Si alguna de las 60
facturas sin timbrar usa esos ítems, el proceso fallará en la construcción del XML
por `ClaveProdServ` vacía. Verificar antes de la primera prueba qué ítems usan las
facturas candidatas.

---

## LISTO PARA PRUEBA MANUAL: **Sí**

Toda la infraestructura de timbrado está operativa:
- FacturAPI sandbox conecta y autentica correctamente
- El método `timbrar_factura` existe y está expuesto como whitelist
- El DocType `Factura Fiscal Mexico` carga con 64 campos
- Hay 60 facturas submitted disponibles como candidatas

**Precaución antes de ejecutar:** confirmar que la factura de prueba elegida
no usa ítems sin código SAT (ver Módulo 1 — 21 ítems pendientes).

---

## SIGUIENTE PASO

1. Elegir una factura de prueba cuyo(s) ítem(s) tengan `fm_producto_servicio_sat` configurado
2. Ejecutar `timbrar_factura("<nombre_factura>")` desde consola o UI
3. Verificar que se crea el documento `Factura Fiscal Mexico` con UUID y XML adjunto
4. Continuar con **Módulo 3: Cancelación y flujo de errores**
