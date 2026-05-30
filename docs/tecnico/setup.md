# Setup de Desarrollo

Guía para montar el entorno de desarrollo local del app.

---

## Entorno de referencia

| Componente | Versión |
|---|---|
| Frappe | v16 |
| ERPNext | v16 |
| Python | 3.12+ |
| Node | v24 (bench v16) |
| Bench path | `/home/erpnext/frappe-bench-v16` |

---

## Instalación del app en bench existente

```bash
cd /home/erpnext/frappe-bench-v16
bench get-app facturacion_mexico https://github.com/luisrms69/facturacion_mexico.git
bench --site facturacion-v16.dev install-app facturacion_mexico
bench --site facturacion-v16.dev migrate
```

---

## Sites de desarrollo

| Site | Uso |
|---|---|
| `facturacion-v16.dev` | Desarrollo activo — UI, demos, validación |
| `test-facturacion.localhost` | Tests unitarios — nunca modificar manualmente |

**Regla:** `bench migrate` y `bench export-fixtures` siempre con `--site` explícito. Nunca sin site en bench compartido.

---

## Servidor de desarrollo

El servidor se gestiona exclusivamente con `frappe-multisite` (script en `/home/erpnext/bin/frappe-multisite`). **No usar** `nohup`, `python -m frappe...` ni arrancar desde `sites/`.

```bash
# Reiniciar servidor de facturacion-v16.dev
frappe-multisite  # menú interactivo
# o
frappe-multisite --all
```

Puerto asignado: `facturacion-v16.dev → 8888`

---

## Tests

### Site de tests

```bash
# Seed de datos (obligatorio antes de cada run)
bench --site test-facturacion.localhost execute facturacion_mexico.tests.ci_pre_tests.run

# Correr módulo específico
bench --site test-facturacion.localhost run-tests \
  --module facturacion_mexico.cfdi_recibidos.tests.test_xml_ingestion \
  --lightmode

# Correr suite completa
bench --site test-facturacion.localhost run-tests \
  --app facturacion_mexico --lightmode
```

### Advertencias

- Tests siempre en `test-facturacion.localhost`, nunca en `facturacion-v16.dev`
- El seed `ci_pre_tests.run` es obligatorio antes de cada ejecución de la suite
- No modificar tests para hacer pasar el CI — actualizar tests para reflejar comportamiento correcto

---

## Linters

```bash
# Python — ruff (en orden)
ruff check facturacion_mexico/ruta/al/archivo.py
ruff format facturacion_mexico/ruta/al/archivo.py

# JavaScript — prettier versión exacta
npx prettier@2.7.1 --write facturacion_mexico/ruta/al/archivo.js
```

El CI usa `ruff check` + `ruff format` + `prettier@2.7.1`. Diferencias de versión de prettier generan falsos negativos locales.

---

## Exportar fixtures

```bash
bench --site facturacion-v16.dev export-fixtures --app facturacion_mexico
```

Exportar siempre desde `facturacion-v16.dev`, nunca desde el site de tests.

---

## Flujo de trabajo estándar

1. Crear rama feature desde `main` limpio
2. Implementar cambios
3. Correr linters en archivos modificados
4. Correr tests con `/test-guard`
5. Exportar fixtures si hubo cambios de schema
6. Commit → push → PR a `main`

Nunca commitear en `main` directamente. Ver reglas en `CLAUDE.md`.

---

## Documentación de referencia

Para regenerar `docs/referencia/` después de cambios en el código:

```bash
python3 scripts/generate_reference.py

# Verificar sin regenerar
python3 scripts/generate_reference.py --verify
```
