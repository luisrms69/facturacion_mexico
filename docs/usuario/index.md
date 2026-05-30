# Guía de Usuario

Esta app permite emitir, cancelar y gestionar CFDIs desde ERPNext, integrado con FacturAPI.io como PAC certificado ante el SAT.

---

## ¿Por dónde empezar?

Si es la primera vez que configuras el sistema: [Primeros Pasos](getting-started.md)

Si el sistema ya está configurado y quieres **emitir una factura**: [Emitir un CFDI](emitir-cfdi.md)

---

## Flujo principal de facturación

```
Sales Invoice (submit)
  → Factura Fiscal Mexico (BORRADOR)
  → Timbrar con FacturAPI
  → CFDI timbrado ante el SAT
```

El flujo completo — incluyendo qué campos se necesitan, cómo opera el timbrado, estados fiscales y cómo revisar errores — está documentado en [Emitir un CFDI](emitir-cfdi.md).

---

## Todas las funciones

| Función | Guía |
|---|---|
| Configuración inicial | [Primeros Pasos](getting-started.md) |
| Emitir un CFDI | [Emitir un CFDI](emitir-cfdi.md) |
| Cancelar un CFDI | [Cancelar un CFDI](cancelar-cfdi.md) |
| Registrar pagos PPD | [Complemento de Pago](complemento-pago.md) |
| Recibir facturas de proveedores | [CFDI Recibidos](cfdi-recibidos.md) |
| Addendas para clientes corporativos | [Addendas](addendas.md) |
| Sucursales con series y folios propios | [Multi-sucursal](multisucursal.md) |
| Errores frecuentes | [Troubleshooting](troubleshooting.md) |
