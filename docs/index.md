# Facturación México

App de facturación electrónica CFDI 4.0 para México integrada con ERPNext.

---

## ¿Qué necesito hacer?

### Emitir facturas

| Tarea | Guía |
|---|---|
| Configurar FacturAPI y emitir el primer CFDI | [Primeros pasos →](usuario/getting-started.md) |
| Cancelar un CFDI (motivos 01-04) | [Cancelar CFDI →](usuario/cancelar-cfdi.md) |
| Registrar un pago de factura PPD | [Troubleshooting →](usuario/troubleshooting.md#complemento-de-pago-no-se-genera) |
| Configurar addenda para Walmart, La Comer u otro retailer | [Addendas →](usuario/addendas.md) |
| Configurar sucursal con su propia serie y folios | [Multi-sucursal →](usuario/multisucursal.md) |

### Registrar facturas recibidas de proveedores

| Tarea | Guía |
|---|---|
| Cargar XML de proveedor y generar Purchase Invoice | [CFDI Recibidos →](usuario/cfdi-recibidos.md) |

### Resolver problemas

| Síntoma | Guía |
|---|---|
| La factura no timbra al hacer Submit | [Troubleshooting →](usuario/troubleshooting.md#timbrado-falla-al-hacer-submit) |
| Item sin clave SAT | [Troubleshooting →](usuario/troubleshooting.md#item-sin-clave-sat) |
| Error en CFDI Recibido al generar PI | [Troubleshooting →](usuario/troubleshooting.md#cfdi-recibido-error-en-conversión-a-pi) |

---

## Para desarrolladores

- [Arquitectura del sistema](tecnico/arquitectura.md) — módulos, flujos, DocTypes, integraciones
- [Setup de desarrollo](tecnico/setup.md) — entorno local, tests, linters
- [Referencia técnica](referencia/index.md) — DocTypes, hooks, API endpoints (auto-generada)
- [ADRs](adr/index.md) — decisiones arquitectónicas permanentes
