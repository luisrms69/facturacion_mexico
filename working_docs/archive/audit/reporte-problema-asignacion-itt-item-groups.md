# Reporte: Problema Asignación Automática ITT a Item Groups

**Fecha:** 2025-10-08
**Severidad:** ALTA - Bloquea funcionalidad E2/E3 en producción
**Contexto:** E2-E3 IEPS + Retenciones

---

## 📋 Problema Identificado

### Descripción
Los Item Groups creados por fixtures no reciben asignación automática de ITT después de que el usuario genera templates desde la UI.

**Situación actual:**
1. Usuario activa `enable_ret_resico` en Configuracion Fiscal Mexico
2. Usuario genera templates desde UI (botón "Generate Templates")
3. ITT "ITT ISR + IVA Ret RESICO - ACC" se crea correctamente
4. **PERO:** Item Group "RESICO" NO recibe asignación del ITT
5. Usuario debe ejecutar `bench migrate` manualmente para que funcione

### Impacto
- ❌ **Zero-config deployment roto:** Usuarios no pueden usar sistema sin intervención técnica
- ❌ **UX deficiente:** Funcionalidad aparentemente completa pero no funcional
- ❌ **No escalable:** En producción usuarios no tienen acceso a `bench migrate`

---

## 🔍 Análisis Técnico

### Arquitectura Actual

**Módulo:** `facturacion_mexico/setup/item_groups.py`

**Función crítica:** `assign_itt_to_groups()`
- **Propósito:** Asignar ITT a Item Groups según mapeo predefinido
- **Idempotente:** Puede ejecutarse múltiples veces sin duplicar asignaciones
- **Hook actual:** `after_migrate` únicamente

**Código relevante:**
```python
def assign_itt_to_groups():
    """
    Hook idempotente para asignar ITT a todos los grupos raíz.
    - Llamar desde after_migrate y desde el cierre del wizard E0.5.
    - Si los ITT aún no existen, loguea y sale sin error (se reintenta en próxima ejecución).
    """
    try:
        # Asegurar que todos los grupos existen
        for group_name in ITEM_GROUP_ITT_MAP.keys():
            _ensure_item_group(group_name)

        # Obtener todas las compañías activas
        companies = frappe.get_all("Company", fields=["name", "company_name", "abbr"])
        changes = []
        missing_log = []

        for c in companies:
            company = frappe._dict(c)

            # Iterar sobre todos los grupos del mapa
            for group_name, itt_pattern in ITEM_GROUP_ITT_MAP.items():
                itt_name = _resolve_itt_name(itt_pattern, company)

                # Si no existe aún el ITT, log y continuar (reintento posterior)
                if not itt_name:
                    missing_log.append(f"{group_name} (pattern: {itt_pattern.format(suffix=company.abbr)})")
                    continue

                # Asignar solo si cambia
                if _assign_group_itt(group_name, itt_name):
                    changes.append((company.name, group_name, itt_name))

        # Log de ITT faltantes
        if missing_log:
            frappe.logger().info(
                f"[FMX][ItemGroups] ITT faltantes: {', '.join(missing_log[:5])}"
                + (f" (+{len(missing_log) - 5} más)" if len(missing_log) > 5 else "")
            )

        # Log de asignaciones realizadas
        if changes:
            for comp, grp, itt in changes:
                frappe.logger().info(
                    f"[FMX][ItemGroups] Asignado ITT '{itt}' a grupo '{grp}' (Company={comp})."
                )
            frappe.db.commit()
        else:
            frappe.logger().info("[FMX][ItemGroups] Sin cambios (ITT ya asignados o faltantes).")

    except Exception:
        frappe.log_error(frappe.get_traceback(), "[FMX][ItemGroups] Error assign_itt_to_groups")
        raise
```

### Hooks Actuales

**Archivo:** `facturacion_mexico/hooks.py`

```python
after_migrate = [
    "facturacion_mexico.setup.item_groups.assign_itt_to_groups",
]

after_install = [
    "facturacion_mexico.setup.item_groups.ensure_groups_after_install",
]
```

**Problema:** `assign_itt_to_groups()` solo se ejecuta en `after_migrate`, NO después de generar templates desde UI.

---

## 💡 Propuesta de Solución

### Opción A: Llamar desde Wizard (RECOMENDADA)

**Cambio:** Agregar llamada a `assign_itt_to_groups()` en `generador_templates_fiscal.py`

**Ubicación:** Función `generar_templates_completos()` después de generar ITT

**Código propuesto:**
```python
def generar_templates_completos(self) -> dict:
    """
    Generar templates completos basado en configuración y mapeo.

    Returns:
        Dict con resultados de generación
    """
    mapeo_cuentas = self._obtener_mapeo_cuentas()
    self._validar_mapeo_completo(mapeo_cuentas)

    # Crear Tax Categories necesarias primero
    self._crear_tax_categories()

    resultados = {
        "stct_generados": self._generar_stct(mapeo_cuentas),
        "itt_generados": self._generar_itt(mapeo_cuentas),
        "company": self.company,
        "timestamp": frappe.utils.now(),
        "version_esquema": self.config_fiscal.version_esquema,
    }

    # Actualizar estado configuración
    self._actualizar_estado_configuracion(resultados)

    # NUEVO: Asignar ITT a Item Groups automáticamente
    try:
        from facturacion_mexico.setup.item_groups import assign_itt_to_groups
        assign_itt_to_groups()
        frappe.logger().info("[FMX][Wizard] ITT asignados a Item Groups automáticamente.")
    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "[FMX][Wizard] Error asignando ITT a Item Groups (no crítico)"
        )
        # No bloquear wizard si falla asignación (se puede corregir con migrate)

    return resultados
```

**Ventajas:**
- ✅ Zero-config completo: Usuario no necesita ninguna acción técnica
- ✅ UX perfecto: Todo funciona inmediatamente después de "Generate Templates"
- ✅ Backward compatible: `after_migrate` sigue funcionando como fallback
- ✅ Idempotente: Función ya maneja duplicados correctamente
- ✅ No crítico: Si falla, loguea pero no rompe wizard (migrate arregla)

**Desventajas:**
- ⚠️ Agrega lógica adicional al wizard (mínima, 1 llamada)
- ⚠️ Requiere import cruzado (mitigado con try/except)

---

### Opción B: Hook Document Controller

**Cambio:** Agregar hook en `Item Tax Template` después de crear/actualizar

**Código propuesto:**
```python
# En hooks.py
doc_events = {
    "Item Tax Template": {
        "after_insert": "facturacion_mexico.setup.item_groups.on_itt_change",
        "after_save": "facturacion_mexico.setup.item_groups.on_itt_change",
    }
}

# En item_groups.py
def on_itt_change(doc, method):
    """Hook para asignar ITT cuando se crea/actualiza cualquier ITT."""
    # Solo procesar ITT que matcheen patterns conocidos
    for pattern in ITEM_GROUP_ITT_MAP.values():
        # Verificar si este ITT pertenece a algún pattern
        # Si sí, ejecutar asignación
        assign_itt_to_groups()
        break
```

**Ventajas:**
- ✅ Automático sin modificar wizard
- ✅ Funciona para cualquier creación de ITT (manual o wizard)

**Desventajas:**
- ❌ Hook se ejecuta para CADA ITT (overhead innecesario)
- ❌ Más complejo de debuggear
- ❌ Puede causar N asignaciones cuando wizard crea 10+ ITT
- ❌ Menos control sobre cuándo se ejecuta

---

### Opción C: Background Job

**Cambio:** Ejecutar `assign_itt_to_groups()` como background job después de wizard

**Ventajas:**
- ✅ No bloquea UI del wizard
- ✅ Manejo de errores independiente

**Desventajas:**
- ❌ Usuario no ve resultado inmediato
- ❌ Complejidad innecesaria para operación rápida (< 1 segundo)
- ❌ Más difícil debuggear para usuarios

---

## 🎯 Recomendación

**OPCIÓN A: Llamar desde Wizard**

**Razones:**
1. **Simplicidad:** 1 llamada, clara, directa
2. **Zero-config:** Cumple objetivo principal del sistema
3. **UX óptimo:** Usuario ve resultado inmediato
4. **Idempotente:** Función ya diseñada para ejecutarse múltiples veces
5. **Fallback:** `after_migrate` sigue funcionando como red de seguridad
6. **No crítico:** Si falla, no rompe wizard (migrate corrige)

**Implementación:**
1. Agregar llamada a `assign_itt_to_groups()` en `generar_templates_completos()` después de generar ITT
2. Envolver en try/except para no bloquear wizard si falla
3. Loguear resultado (éxito o error)
4. Mantener `after_migrate` hook como fallback

---

## 📊 Testing Requerido

### Casos a validar:

1. **Flujo normal:**
   - Activar `enable_ret_resico`
   - Generar templates
   - Verificar ITT asignado a Item Group "RESICO"
   - ✅ Sin necesidad de migrate

2. **Primera instalación:**
   - Install app
   - Configurar mapeo
   - Generar templates
   - ✅ Item Groups con ITT asignados

3. **Regeneración:**
   - Modificar tasas RESICO
   - Regenerar templates
   - ✅ Asignaciones existentes no duplicadas
   - ✅ Nuevas asignaciones creadas si hay nuevos ITT

4. **Fallback migrate:**
   - Desactivar/romper función en wizard (simulación error)
   - Ejecutar migrate
   - ✅ Item Groups reciben asignaciones vía hook

5. **Multiple companies:**
   - 2 companies con configuraciones diferentes
   - Generar templates para ambas
   - ✅ Cada company con sus ITT asignados correctamente

---

## 🔗 Archivos Involucrados

1. **`facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py`**
   - Función: `generar_templates_completos()` (línea ~55-80)
   - Cambio: Agregar llamada a `assign_itt_to_groups()`

2. **`facturacion_mexico/setup/item_groups.py`**
   - Función: `assign_itt_to_groups()` (línea ~134-186)
   - Sin cambios necesarios (ya idempotente)

3. **`facturacion_mexico/hooks.py`**
   - Hook: `after_migrate` (mantener como fallback)
   - Sin cambios necesarios

---

## ⚠️ Consideraciones Adicionales

### Performance
- ✅ Operación rápida (< 1 segundo típico)
- ✅ Solo asigna cambios nuevos (idempotente)
- ✅ No bloquea UI (síncrono pero rápido)

### Seguridad
- ✅ Función ya existe y está probada
- ✅ No modifica datos críticos (solo asigna ITT a grupos)
- ✅ Errores no bloquean wizard (logged pero no thrown)

### Mantenibilidad
- ✅ Lógica centralizada en `item_groups.py`
- ✅ Wizard solo hace 1 llamada simple
- ✅ Fácil de debuggear (logs claros)

---

## 📝 Próximos Pasos

1. **Revisión:** Usuario revisa propuesta
2. **Autorización:** Usuario aprueba Opción A (o sugiere alternativa)
3. **Implementación:** Modificar `generador_templates_fiscal.py`
4. **Testing:** Validar 5 casos de prueba listados
5. **Documentación:** Actualizar docs con nuevo flujo
6. **Commit:** feat(e2-e3): asignación automática ITT a Item Groups post-wizard

---

**Generado:** 2025-10-08
**Autor:** Claude Code
**Versión:** 1.0
