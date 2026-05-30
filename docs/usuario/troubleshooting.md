# Troubleshooting

Solución a los problemas más comunes.

---

## Timbrado falla al hacer Submit

**Verificar en orden:**

1. **Credenciales FacturAPI** — abrir `Facturacion Mexico Settings` y verificar que `API Key` esté configurada y que el modo sandbox/producción sea el correcto.

2. **RFC de la empresa** — en `Setup > Company`, verificar que `Tax ID` tenga el RFC correcto.

3. **Clave SAT del item** — cada item debe tener `fm_producto_servicio_sat` configurado. Sin esta clave el timbrado se bloquea.

4. **Configuracion Fiscal Mexico** — debe existir para la empresa con el wizard completado (`wizard_completado = 1`).

5. **FacturAPI Response Log** — en el workspace Facturación México, abrir `FacturAPI Response Log` para ver el detalle del error devuelto por FacturAPI.

---

## Item sin clave SAT

El sistema bloquea el timbrado si algún item no tiene `fm_producto_servicio_sat`.

Para encontrar items sin clave:

```bash
bench --site tu-sitio.local console
```

```python
items = frappe.db.sql("""
    SELECT name, item_name FROM tabItem
    WHERE fm_producto_servicio_sat IS NULL OR fm_producto_servicio_sat = ""
    LIMIT 20
""", as_dict=True)
for i in items:
    print(i['name'], '-', i['item_name'])
```

Asignar la clave SAT en `Stock > Item`.

---

## Complemento de Pago no se genera

Al registrar un `Payment Entry` para una factura PPD, el complemento se genera automáticamente al hacer Submit.

Verificar:
1. La Sales Invoice tiene `fm_payment_method_sat = PPD`
2. El Payment Entry está en estado Submit (no Draft)
3. Revisar `FacturAPI Response Log` para errores de timbrado del complemento

---

## CFDI Recibido: proveedor no se resuelve

Si el CFDI queda en `Falta proveedor` y el proveedor sí existe:
- Verificar que el Supplier tiene el RFC correcto en el campo `Tax ID`
- El RFC debe coincidir exactamente con el del emisor en el XML (incluyendo mayúsculas)

---

## CFDI Recibido: error en conversión a PI

El campo `error_message` en el documento indica la causa. Los más comunes:

| Error | Causa | Solución |
|---|---|---|
| "No existe Configuracion CFDI Recibidos..." | Falta la config de la empresa | Crear `Configuracion CFDI Recibidos` y ejecutar el wizard |
| "No existe regla activa para impuesto..." | Falta regla de impuesto en la config | Agregar la regla (IVA 16%, etc.) y regenerar el template |
| "concepto(s) sin item_code" | Hay conceptos sin clasificar | Clasificar todos los conceptos antes de generar PI |
| "grand_total difiere del XML..." | Diferencia mayor a la tolerancia | Revisar impuestos o ajustar tolerancia en la configuración |

---

## Multi-sucursal: la factura no toma la serie del Branch

Verificar:
1. El Branch tiene `fm_enable_fiscal = 1`
2. El Branch tiene `fm_lugar_expedicion` configurado
3. La Sales Invoice tiene el campo **Branch** asignado

---

## Addenda no aparece en el CFDI

1. Verificar que el cliente tiene `fm_addenda_required` marcado
2. Verificar que existe una `Addenda Configuration` activa para ese cliente
3. Verificar que el `Addenda Type` tiene `is_active = 1` y un template XML configurado
4. Revisar `FacturAPI Response Log` para errores del template

---

## Ver logs de error del sistema

```bash
bench --site tu-sitio.local console
```

```python
logs = frappe.get_all("Error Log",
    filters={"method": ["like", "%facturacion%"]},
    fields=["name", "method", "error", "creation"],
    order_by="creation desc",
    limit=10)
for log in logs:
    print(log["creation"], "|", log["method"])
    print(log["error"][:300])
    print()
```
