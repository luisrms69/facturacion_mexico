# Plan técnico: Facturacion Mexico Company Settings

**Fecha:** 2026-05-30
**Estado:** PLAN AJUSTADO — pendiente de autorización para implementar
**Contexto:** GAP detectado — `Facturacion Mexico Settings` es Single, bloquea multi-company
**Safe point:** `20260530-223833-facturacion_mexico-facturacion-v16.dev`
**Rama de implementación:** pendiente de crear desde main

---

## 1. Problema exacto

`Facturacion Mexico Settings` es `issingle: 1`. Contiene en un solo registro global:
- `api_key` / `test_api_key` — credenciales FacturAPI.io
- `sandbox_mode` — modo producción/sandbox
- `rfc_emisor` — RFC del emisor (reqd: 1)
- `lugar_expedicion` — CP fiscal (reqd: 1)

No es posible timbrar con dos Companies distintas con sus propias credenciales PAC
cuando comparten el mismo bench.

---

## 2. Alcance de este PR

**Dentro:**
- Crear nuevo DocType `Facturacion Mexico Company Settings` (configuración por Company)
- Actualizar `api_client.py` para resolver credenciales con fallback
- Actualizar `timbrado_api.py` para pasar `company` al cliente
- Actualizar controllers que instancian el cliente (Complemento Pago, etc.)
- Crear helper `get_facturapi_settings(company)` con lógica de resolución

**Fuera — NO se toca en este PR:**
- `Facturacion Mexico Settings` (Single) queda exactamente igual — ningún campo eliminado
- Los campos legacy (`api_key`, `rfc_emisor`, etc.) siguen en el Single como fallback
- La limpieza de campos no implementados es un PR futuro independiente
- `Configuracion Fiscal Mexico` no se modifica
- No hay `bench migrate` más allá de crear la nueva tabla

---

## 3. DocType nuevo: `Facturacion Mexico Company Settings`

**Campos:**

| Fieldname | Fieldtype | Label | Notas |
|---|---|---|---|
| `company` | Link → Company | Company | reqd, unique — clave del documento |
| `api_key` | Password | API Key Producción | Credencial prod FacturAPI |
| `test_api_key` | Password | API Key Pruebas | Credencial sandbox FacturAPI |
| `sandbox_mode` | Check (default 1) | Modo Sandbox | Prod vs sandbox |
| `rfc_emisor` | Data | RFC Emisor | Override por Company |
| `lugar_expedicion` | Data | Lugar de Expedición | Override por Company |

**Naming:** `format:FMCS-{company}`
**Module:** Facturacion Fiscal
**Permisos:** igual a `Facturacion Mexico Settings`

---

## 4. Flujo de resolución de configuración por Company

```
get_facturapi_settings(company)
  │
  ├─ ¿Existe Facturacion Mexico Company Settings para esta Company?
  │   └─ SÍ → usar esos valores
  │
  └─ NO → fallback a Facturacion Mexico Settings (Single legacy)
```

**Regla explícita:**
- Si `Company Settings` existe pero tiene `api_key` vacío → igual se usa; no se cae al fallback
- Si `Company Settings` no existe → fallback al Single
- El Single nunca se modifica; siempre es el último recurso

**Helper propuesto (`facturacion_mexico/utils/settings.py`):**

```python
def get_facturapi_settings(company: str) -> dict:
    company_cfg = frappe.db.get_value(
        "Facturacion Mexico Company Settings",
        {"company": company},
        ["api_key", "test_api_key", "sandbox_mode", "rfc_emisor", "lugar_expedicion"],
        as_dict=True,
    )
    if company_cfg:
        return company_cfg

    # Fallback legacy
    s = frappe.get_single("Facturacion Mexico Settings")
    return {
        "api_key": s.api_key,
        "test_api_key": s.test_api_key,
        "sandbox_mode": s.sandbox_mode,
        "rfc_emisor": s.rfc_emisor,
        "lugar_expedicion": s.lugar_expedicion,
    }
```

---

## 5. Impacto por módulo

| Módulo | Archivo | Cambio |
|---|---|---|
| **Cliente API** | `api_client.py` | Recibir `company`, llamar `get_facturapi_settings` |
| **Timbrado** | `timbrado_api.py:__init__` | Recibir `company`, pasarlo al cliente |
| **Timbrado** | `timbrado_api.py:cancelar_factura` | Leer `company` desde el Sales Invoice |
| **Timbrado** | `timbrado_api.py:_map_tax_account_to_sat` | Usar `self.company` en vez de `settings.company` (que no existe) |
| **Complemento Pago** | controller del DocType | Instanciar `TimbradoAPI(company=self.company)` |
| **Factura Global** | controller | Ídem |
| **E-Receipt** | controller | Ídem |
| **Validaciones RFC** | `validaciones/api.py` | Verificar si usa credenciales — probable impacto menor |
| **Tests** | mocks de credenciales | Actualizar mocks de `get_single` → mockear `get_facturapi_settings` |
| **Addendas** | `addenda_service.py` | Sin impacto — no usa credenciales FacturAPI directamente |

---

## 6. Backward compatibility

| Escenario | Comportamiento |
|---|---|
| Instalación existente (LlantasCS, una Company) | Sin `Company Settings` → fallback al Single → cero impacto |
| Instalación nueva con una Company | Configura `Company Settings` o usa el Single — ambos funcionan |
| Multi-company (ACG + LlantasCS) | Cada Company con su `Company Settings`; si falta, usa el Single |
| Campo `company` vacío en TimbradoAPI | Fallback a `frappe.defaults.get_global_default("company")` |

**No hay migración destructiva.** El Single nunca se toca. Solo se crea la tabla nueva.

---

## 7. Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| `FacturAPIClient()` o `TimbradoAPI()` instanciado sin `company` en rutas no detectadas | Media | Grep exhaustivo de todos los puntos de instanciación antes de implementar |
| Tests que mockean `get_single("Facturacion Mexico Settings")` para credenciales | Alta | Identificar todos y actualizar mocks a `get_facturapi_settings` |
| `rfc_emisor` / `lugar_expedicion` leídos del Single directamente en código no detectado | Media | Grep de ambos campos como acceso a settings antes de implementar |
| `Company Settings` creado con campos vacíos bloquea el fallback | Baja | La regla es: si existe el doc → se usa (no hay doble fallback por campo vacío) |

---

## 8. Limpieza del Single — PR futuro (fuera de este alcance)

Los siguientes campos del Single son candidatos a eliminar en un PR posterior:
- `habilitar_traslado` — description: "No implementado"
- Toda la sección Dashboard Fiscal (KPIs siempre en 0)
- `auto_generate_global`, `global_generation_day`, `global_generation_time`
- Campos de E-Receipt no implementados
- `enable_global_invoices` y dependientes

**Condición para ese PR:** cuando los módulos correspondientes se implementen o se decida
oficialmente descartarlos.

---

## 9. Auditoría de impacto — resultados del grep exhaustivo

### Hallazgo clave
`rfc_emisor` y `lugar_expedicion` del Single **no se leen en el flujo activo de timbrado**.
El timbrado usa `Company.tax_id` y `fm_lugar_expedicion` del Branch.
Son campos decorativos en el Single — no requieren migración funcional.

**El problema real se reduce a 3 campos:** `api_key`, `test_api_key`, `sandbox_mode`.

### Archivos que requieren cambio

| Archivo | Línea | Cambio requerido |
|---|---|---|
| `utils/settings.py` (nuevo) | — | Crear helper `get_facturapi_settings(company)` |
| `facturacion_fiscal/api_client.py` | 11–40 | Recibir `company`, usar helper |
| `facturacion_fiscal/timbrado_api.py` | 101–102 | Recibir `company`, pasar a `get_facturapi_client` |
| `hooks_handlers/sales_invoice_submit.py` | 164 | `TimbradoAPI(company=doc.company)` |
| `complementos_pago/api.py` | 147 | Pasar `company` del Complemento al cliente |
| `ereceipts/api.py` | 53–54 | Usar `get_facturapi_settings` en lugar de `get_single` directo |

### Archivos que NO requieren cambio

| Archivo | Razón |
|---|---|
| `facturacion_mexico_settings.py` | Validaciones internas del Single propio — intacto por diseño |
| `factura_fiscal_mexico.py` | Lee `metodo_pago_default` — no es credencial |
| `install.py` | Setup inicial, no necesita multi-company |
| `timbrado_api.py` línea 852 | `fm_lugar_expedicion` del Branch, no del Single |

---

## 10. Orden de migración — campo por campo

### Paso 1 — Helper fundación
**Campo(s):** `api_key` + `test_api_key` + `sandbox_mode`
Crear `facturacion_mexico/utils/settings.py` con `get_facturapi_settings(company)`.
Sin este paso no se puede modificar ningún otro archivo.

### Paso 2 — DocType nuevo
Crear `Facturacion Mexico Company Settings` (JSON + controller).
Agregar a `hooks.py` fixtures.

### Paso 3 — `api_client.py`
Recibir `company=None` en `__init__`, usar helper.
Punto de entrada de credenciales — todos los demás dependen de este.

### Paso 4 — `timbrado_api.py`
Recibir `company=None` en `__init__`, pasar a `get_facturapi_client`.
Lee company desde el Sales Invoice en el flujo de timbrado y cancelación.

### Paso 5 — `hooks_handlers/sales_invoice_submit.py`
`TimbradoAPI(company=doc.company)` — una línea.

### Paso 6 — `complementos_pago/api.py`
Pasar `company` del Complemento Pago al cliente.

### Paso 7 — `ereceipts/api.py`
Reemplazar `get_single` directo de credenciales por `get_facturapi_settings(company)`.

### Paso 8 — Tests
Actualizar mocks: `get_single("Facturacion Mexico Settings")` → `get_facturapi_settings`.

### Paso 9 — `bench migrate`
Solo cuando los 8 pasos anteriores estén completos y los tests pasen.

### Paso 10 — Prueba en facturacion-v16.dev
Crear `Facturacion Mexico Company Settings` para ACG y verificar timbrado end-to-end.
11. Crear `Facturacion Mexico Company Settings` para ACG en UI
12. Prueba end-to-end en facturacion-v16.dev

---

## 10. Criterios de aceptación

- [ ] `Facturacion Mexico Settings` (Single) intacto — ningún campo eliminado
- [ ] LlantasCS timbra sin tocar ninguna configuración existente (fallback activo)
- [ ] ACG puede configurar sus propias credenciales en `Facturacion Mexico Company Settings`
- [ ] ACG puede timbrar con sus propias credenciales
- [ ] `bench migrate` limpio
- [ ] Tests existentes de addenda y servicio pasan sin modificación
- [ ] Grep de instanciaciones sin `company` = 0 activos post-implementación
