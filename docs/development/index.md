# Guía de Desarrollo - Facturación México

Documentación técnica para desarrolladores que contribuyen al proyecto.

## Setup del Entorno

### Requisitos
- Frappe Framework v15
- Python 3.8+
- Node.js 16+
- MariaDB 10.6+

### Instalación para Desarrollo

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-org/facturacion_mexico.git

# 2. Setup bench
bench get-app facturacion_mexico /path/to/repo

# 3. Instalar dependencias
bench --site development.local install-app facturacion_mexico

# 4. Ejecutar tests
bench --site development.local run-tests --app facturacion_mexico
```

## Estructura del Proyecto

### Módulos Core
- `cfdi/` - Timbrado y validación
- `multisucursal/` - Gestión branches
- `addendas/` - Generación dinámica
- `catalogos_sat/` - Sincronización SAT

### Testing Framework
- Layer 1: Unit tests
- Layer 2: Integration tests  
- Layer 3: Workflow tests
- Layer 4: Production tests

## Contribuciones

### Standards
- Google-style docstrings
- Conventional commits
- 90%+ test coverage
- Spanish labels, English code

---

!!! warning "Testing"
    Todos los PRs deben tener 100% de tests exitosos antes del merge.