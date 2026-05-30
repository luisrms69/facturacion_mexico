# Facturación México

Facturación electrónica CFDI 4.0 para México integrada con ERPNext y FacturAPI.io.

---

## Emisión de CFDI

| Necesito... | Ir a |
|---|---|
| Configurar el sistema por primera vez | [Primeros pasos](usuario/getting-started.md) |
| Emitir una factura de ingreso (CFDI tipo I) | [Primeros pasos → Primera factura](usuario/getting-started.md#primer-cfdi) |
| Emitir una nota de crédito (CFDI tipo E) | [Cancelar CFDI → Sustitución](usuario/cancelar-cfdi.md#emitir-un-cfdi-sustituto-motivo-01) |
| Configurar serie y folios por sucursal | [Multi-sucursal](usuario/multisucursal.md) |
| Agregar addenda (Walmart, La Comer, etc.) | [Addendas](usuario/addendas.md) |

## Cancelación

| Necesito... | Ir a |
|---|---|
| Cancelar un CFDI | [Cancelar CFDI](usuario/cancelar-cfdi.md) |
| Elegir el motivo correcto (01-04) | [Motivos de cancelación](usuario/cancelar-cfdi.md#motivos-de-cancelación) |
| Emitir un CFDI sustituto | [CFDI sustituto](usuario/cancelar-cfdi.md#emitir-un-cfdi-sustituto-motivo-01) |

## Pagos

| Necesito... | Ir a |
|---|---|
| Registrar el cobro de una factura PPD | [Complemento de Pago](usuario/complemento-pago.md) |

## Compras (CFDI Recibidos)

| Necesito... | Ir a |
|---|---|
| Cargar XMLs de facturas de proveedores | [CFDI Recibidos](usuario/cfdi-recibidos.md) |
| Generar Purchase Invoice desde un XML | [Generar PI](usuario/cfdi-recibidos.md#paso-4--generar-purchase-invoice) |

## Resolver problemas

| Síntoma | Ir a |
|---|---|
| La factura no timbra al hacer Submit | [Troubleshooting](usuario/troubleshooting.md#timbrado-falla-al-hacer-submit) |
| Item sin clave SAT | [Troubleshooting](usuario/troubleshooting.md#item-sin-clave-sat) |
| El complemento de pago no se generó | [Troubleshooting](usuario/troubleshooting.md#complemento-de-pago-no-se-genera) |
| Error al generar PI desde CFDI recibido | [Troubleshooting](usuario/troubleshooting.md#cfdi-recibido-error-en-conversión-a-pi) |

---

## Para desarrolladores

- [Arquitectura](tecnico/arquitectura.md)
- [Setup de desarrollo](tecnico/setup.md)
- [Referencia técnica](referencia/index.md) — auto-generada desde código
- [ADRs](adr/index.md)
