# ADR 0027 — Migración facturacion_mx → facturacion_mexico

**Fecha:** 2026-05-16
**Estado:** En definición — script de datos pendiente de implementación
**Autor:** Luis Montanaro / Claude Sonnet 4.6

---

## Contexto

Cualquier site que tenga instalada `facturacion_mx` (app legacy) y deba migrar a
`facturacion_mexico` (app nueva) enfrenta una convivencia temporal de dos sistemas
de facturación sobre los mismos DocTypes de ERPNext.

La migración tiene dos fases distintas:
1. **Configuración del nuevo sistema** — setup de `facturacion_mexico` desde cero
2. **Migración de datos históricos** — trasladar documentos fiscales legacy al nuevo esquema

Este ADR documenta ambas fases, el orden correcto de ejecución y las características
del script de migración de datos.

---

## Alcance

- **Referencia:** Site llantascs (dev → producción)
- **Empresa:** Una empresa por site (puede adaptarse a multi-empresa)
- **Volumen de documentos:** a determinar por site antes de ejecutar

---

## Fase 1 — Setup del nuevo sistema (orden obligatorio)

Los pasos siguientes deben ejecutarse en este orden exacto. Cada paso tiene
dependencias con el anterior.

### Paso 1 — Facturacion Mexico Settings

Configurar credenciales FacturAPI y modo de operación:

| Campo | Descripción | Requerido |
|---|---|---|
| API Key FacturAPI | Credencial sandbox o producción | ✅ |
| Modo operación | Sandbox (pruebas) / Producción | ✅ |
| Certificado CSD | Archivos .cer / .key / contraseña | ✅ producción |
| Organization ID | ID organización en FacturAPI | ✅ |

### Paso 2 — System Settings

Agregar `json` a los tipos de archivo permitidos:

1. Ir a **System Settings** (barra de búsqueda o menú Configuración)
2. Buscar el campo **"Tipos de archivo permitidos"**
3. Agregar `json` a la lista
4. Guardar

**Por qué:** `facturacion_mexico` adjunta la respuesta JSON de FacturAPI al
`FacturAPI Response Log`. Sin esto el timbrado ocurre pero el log queda incompleto.

### Paso 3 — Configuracion Fiscal Mexico

Ejecutar el wizard de configuración fiscal para la empresa:
- Mapear cuentas contables por rol fiscal (IVA, IEPS, retenciones)
- Roles mínimos: IVA Nacional, IVA Acreditable
- Roles adicionales según régimen: IEPS, retenciones ISR/IVA, IVA Frontera

**Este paso es prerequisito para generar templates.**

### Paso 4 — Generar templates fiscales (STCT e ITT)

Desde `Configuracion Fiscal Mexico` ejecutar "Generar Templates Fiscales":
- Genera 8 STCT (Nacional/Frontera × Básico/IEPS/Retenciones/Total)
- Genera ITT por categoría fiscal (IVA 0%, Exento, IEPS, Retenciones)
- Elimina `is_default` de todos los STCT anteriores de la empresa
- Asigna ITT a grupos fiscales correspondientes

### Paso 5 — Configurar Branches fiscalmente

Para cada Branch de la empresa, completar datos fiscales:

| Campo | Descripción |
|---|---|
| `fm_enable_fiscal` | Activar branch para facturación fiscal |
| `fm_lugar_expedicion` | Código postal del lugar de expedición CFDI |
| `fm_is_border_zone` | ¿Es zona fronteriza? (IVA 8%) |
| RFC, Régimen Fiscal | Datos del emisor por sucursal si aplica |

### Paso 6 — Mapear Cost Centers a Branches

Para cada Cost Center, asignar el Branch correspondiente:
- Campo: `Cost Center.fm_mapped_branch`
- **Sin este mapeo, el STCT no se asigna automáticamente en facturas**

### Paso 7 — Configuracion Reclasificacion Fiscal Mexico (MRFPE)

Ejecutar el wizard `Configuracion Reclasificacion Fiscal Mexico` por empresa.
Este wizard genera automáticamente los registros `Mapeo Reclasificacion Fiscal
Payment Entry (MRFPE)` que definen el traspaso de IVA no cobrado → cobrado
en cada Payment Entry PPD.

**Sin este paso, los pagos PPD no generan el traspaso fiscal correcto.**

### Paso 8 — Validación de RFC en Customers

`facturacion_mexico` requiere RFC validado ante SAT para timbrar.

Opciones:
- **Individual:** validar manualmente antes del primer timbrado de cada cliente
- **Masiva:** usar `bulk_validate_customers` respetando los límites de rate de la API del PAC

**Considerar límites del API del PAC antes de correr validación masiva.**

---

## Fase 2 — Migración de datos históricos

### Items y grupos fiscales

Evaluar por cliente si los productos requieren clasificación fiscal especial:
- IVA 16% estándar: **no requiere migración** — el STCT lo maneja
- IVA 0%, Exento, IEPS, Retenciones: asignar items a los grupos fiscales correspondientes

### Campos en Customer

| Campo origen (`facturacion_mx`) | Campo destino (`facturacion_mexico`) | Transformación |
|---|---|---|
| `Customer.custom_uso_cfdi` | `Customer.fm_uso_cfdi_default` | **Directo** — mismo código SAT en ambos catálogos |
| `Customer.tax_category` | `Customer.fm_tax_regime` | **Extracción** — primeros 3 caracteres (`"601 General..."` → `"601"`) |

**Notas:**
- `custom_uso_cfdi` → DocType `Uso CFDI`; `fm_uso_cfdi_default` → DocType `Uso CFDI SAT`
- Los `name` coinciden en ambos catálogos (G03, S01, etc.)
- `tax_category` es texto libre; `fm_tax_regime` es Link a `Regimen Fiscal SAT`

### Facturas históricas — `tabFactura` → `Factura Fiscal Mexico`

**Volumen:** a determinar por site

| Campo origen | Campo destino | Transformación |
|---|---|---|
| `sales_invoice_id` | `sales_invoice` | Directo |
| `uuid` | `fm_uuid` | Directo |
| `status` | `fm_fiscal_status` | **Requiere tabla de equivalencias** |
| `tipo` | `tipo_comprobante` | Mapeo I/E/N → códigos CFDI |
| `fecha_timbrado` | `fm_fecha_timbrado` | Directo |
| `serie_de_la_factura` | `serie` | Directo |
| `folio_de_factura` | `folio` | Directo |
| `monto_total` | `grand_total` | Directo |
| `id_pac` | `fm_pac_response` | Revisar estructura |
| `usocfdi` | `fm_uso_cfdi` (en SI) | Revisar equivalencia |

**Pendientes:**
- Tabla de equivalencias de `status` legacy → `fm_fiscal_status`
- Tratamiento de facturas canceladas y sus relaciones
- Manejo de `amended_from` para facturas sustituidas
- Definir `docstatus` de documentos migrados

### Complementos de Pago — `tabComplemento de Pago PPD` → `Complemento Pago MX`

**Volumen:** a determinar por site

**Pendiente:** Mapeo detallado de campos (requiere análisis comparativo de schemas)

### Templates fiscales legacy

- Deshabilitar o eliminar templates `002 IVA...` una vez confirmado que no son referenciados
  en documentos activos ni en configuración contable

---

## Características del script de migración de datos

### Principios

1. **Idempotente** — puede correrse múltiples veces sin duplicar datos
2. **Dry-run obligatorio** — `dry_run=True` por defecto
3. **Por empresa** — parámetro `company` para limitar alcance
4. **Con reporte** — log de éxitos, errores y omisiones por sección
5. **Sin desinstalar** — no elimina `facturacion_mx` hasta validación completa
6. **Solo lectura en origen** — nunca modifica tablas de `facturacion_mx`
7. **Backup previo obligatorio** antes de correr con `dry_run=False`

### Estructura propuesta

```python
def run(company=None, dry_run=True, sections=None):
    """
    sections: None = todas | lista de secciones a correr
    Secciones disponibles: customers | items | facturas | complementos
    """
    report = {}
    if not sections or "customers" in sections:
        report["customers"] = migrate_customers(company, dry_run)
    if not sections or "items" in sections:
        report["items"] = migrate_items(company, dry_run)
    if not sections or "facturas" in sections:
        report["facturas"] = migrate_facturas(company, dry_run)
    if not sections or "complementos" in sections:
        report["complementos"] = migrate_complementos(company, dry_run)
    print_report(report)
```

---

## Pendientes para completar el ADR

- [ ] Tabla de equivalencias de `status` legacy → `fm_fiscal_status`
- [ ] Mapeo detallado `tabComplemento de Pago PPD` → `Complemento Pago MX`
- [ ] Definir `docstatus` de documentos migrados (submitted vs estado especial)
- [ ] Confirmar tratamiento de facturas canceladas y sustituidas
- [ ] Definir orden y criterios para desinstalación de `facturacion_mx`

---

## Referencias

- Issue: pendiente de crear (#TODO)
- Branch activo: `feature/fiscal-item-groups-multilenguaje`
- DocTypes destino: `Factura Fiscal Mexico`, `Complemento Pago MX`
- DocTypes origen: `Factura`, `Complemento de Pago PPD`
- ADR relacionado: `0019-primera-implementacion-rc-v0.1.md`
- Issue relacionado: #112 (MRFPE — Reclasificación Fiscal Payment Entry)
