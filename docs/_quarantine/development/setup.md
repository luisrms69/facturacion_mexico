# Setup de Desarrollo - Facturación México

Guía completa para configurar el entorno de desarrollo del proyecto.

## 🛠️ Entorno de Desarrollo

### Requisitos del Sistema

#### Software Base
- **Python 3.8+** (recomendado 3.10+)
- **Node.js 16+** con npm
- **MariaDB 10.6+** o **MySQL 8.0+**
- **Redis** (para cache y queue)
- **Git** para control de versiones

#### Herramientas de Desarrollo
- **VS Code** con extensiones Python y JavaScript
- **Postman** o **Thunder Client** para API testing
- **Docker** (opcional, para testing isolado)

### Instalación Paso a Paso

#### 1. Clonar Repositorio

```bash
# Clonar el repositorio principal
git clone https://github.com/tu-org/facturacion_mexico.git
cd facturacion_mexico

# Revisar branches disponibles
git branch -a

# Cambiar a branch de desarrollo
git checkout develop
```

#### 2. Setup Frappe Bench

```bash
# Crear nuevo bench para desarrollo
bench init --frappe-branch version-15 frappe-dev
cd frappe-dev

# Obtener la app desde repo local
bench get-app facturacion_mexico /path/to/facturacion_mexico

# Crear site de desarrollo
bench new-site dev.facturacion.local --db-root-password your_password

# Instalar app
bench --site dev.facturacion.local install-app facturacion_mexico
```

#### 3. Configuración de Desarrollo

```bash
# Habilitar modo desarrollador
bench --site dev.facturacion.local set-config developer_mode 1

# Configurar debug mode
bench --site dev.facturacion.local set-config debug 1

# Configurar reload automático
bench --site dev.facturacion.local set-config auto_reload 1
```

### Configuración site_config.json

```json
{
  "developer_mode": 1,
  "debug": 1,
  "auto_reload": 1,
  "pac_provider": "finkok",
  "pac_test_mode": 1,
  "pac_username": "test_user",
  "pac_password": "test_password",
  "multisucursal_enabled": 1,
  "addendas_auto_generation": 1,
  "cfdi_version": "4.0",
  "logging": {
    "facturacion_mexico": "DEBUG"
  }
}
```

## 🧪 Setup de Testing

### Estructura de Tests

```
facturacion_mexico/tests/
├── __init__.py
├── test_layer1_basic_cfdi_functionality.py          # 15 tests
├── test_layer2_advanced_multisucursal_operations.py # 15 tests  
├── test_layer3_*.py                                 # 12 tests (5 archivos)
└── test_layer4_*.py                                 # 4 tests (4 archivos)
```

### Configuración de Test Environment

```bash
# Crear site específico para tests
bench new-site test.facturacion.local --db-root-password your_password

# Instalar app en site de tests
bench --site test.facturacion.local install-app facturacion_mexico

# Configurar datos de prueba
bench --site test.facturacion.local execute facturacion_mexico.install.before_tests
```

### Ejecutar Tests

#### Tests Completos

```bash
# Todos los tests (46 tests)
bench --site test.facturacion.local run-tests --app facturacion_mexico

# Con coverage
bench --site test.facturacion.local run-tests --app facturacion_mexico --coverage

# Verbose mode
bench --site test.facturacion.local run-tests --app facturacion_mexico -v
```

#### Tests por Layer

```bash
# Layer 1: Funcionalidad básica CFDI
bench --site test.facturacion.local run-tests --app facturacion_mexico --module facturacion_mexico.tests.test_layer1_basic_cfdi_functionality

# Layer 2: Operaciones multi-sucursal avanzadas  
bench --site test.facturacion.local run-tests --app facturacion_mexico --module facturacion_mexico.tests.test_layer2_advanced_multisucursal_operations

# Layer 3: Integración completa del sistema
bench --site test.facturacion.local run-tests --app facturacion_mexico --module facturacion_mexico.tests.test_layer3_complete_system_integration_sprint6

# Layer 4: Tests de producción
bench --site test.facturacion.local run-tests --app facturacion_mexico --module facturacion_mexico.tests.test_layer4_sprint6_multisucursal_production
```

#### Tests Específicos

```bash
# Test específico por nombre
bench --site test.facturacion.local run-tests --app facturacion_mexico --module facturacion_mexico.tests.test_layer1_basic_cfdi_functionality --test test_basic_cfdi_creation

# Tests que coincidan con patrón
bench --site test.facturacion.local run-tests --app facturacion_mexico --module facturacion_mexico.tests.test_layer3_addenda_multisucursal_workflows --test "*addenda*"
```

### Debugging Tests

#### Con pdb

```python
# En el código de test
import pdb; pdb.set_trace()

# O usando frappe debugger
import frappe
frappe.log_error("Debug point reached", "Test Debug")
```

#### Con logs detallados

```python
# Setup logging en tests
import logging
logging.basicConfig(level=logging.DEBUG)

# O usando frappe logger
import frappe
frappe.logger("test_debug").debug("Test checkpoint reached")
```

## 🔧 Herramientas de Desarrollo

### Pre-commit Hooks

```bash
# Instalar pre-commit
pip install pre-commit

# Setup hooks
pre-commit install

# Ejecutar manualmente
pre-commit run --all-files
```

#### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
        language_version: python3
        
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=100]
        
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: [--profile=black]
```

### Code Quality Tools

#### Linting

```bash
# flake8 para style checking
flake8 facturacion_mexico/ --max-line-length=100

# black para formatting
black facturacion_mexico/

# isort para import sorting  
isort facturacion_mexico/ --profile=black
```

#### Documentation Quality

```bash
# pydocstyle para docstring checking
pydocstyle facturacion_mexico/ --convention=google

# interrogate para docstring coverage
interrogate facturacion_mexico/ --verbose
```

## 📊 Monitoreo de Desarrollo

### Performance Profiling

```python
# Profiling de funciones críticas
import cProfile
import pstats
from functools import wraps

def profile_function(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        
        stats = pstats.Stats(pr)
        stats.sort_stats('cumulative')
        stats.print_stats(10)  # Top 10 functions
        
        return result
    return wrapper

# Uso en código
@profile_function
def generate_cfdi_xml(invoice_doc):
    # Implementación...
    pass
```

### Memory Profiling

```python
# Con memory_profiler
from memory_profiler import profile

@profile
def memory_intensive_function():
    # Código que consume memoria
    pass

# Ejecutar con:
# python -m memory_profiler script.py
```

### Database Query Monitoring

```python
# Monitoring de queries
import frappe

# Habilitar query logging
frappe.db.debug = True

# Ver queries ejecutadas
print(frappe.db.get_query_log())

# Resetear log  
frappe.db.reset_query_log()
```

## 🚀 Deployment Testing

### Docker Environment

#### Dockerfile.dev

```dockerfile
FROM frappe/erpnext:v15

# Copy app
COPY . /home/frappe/frappe-bench/apps/facturacion_mexico

# Install app
RUN cd /home/frappe/frappe-bench && \
    bench get-app facturacion_mexico --resolve-deps && \
    bench build

# Development specific configurations
ENV DEVELOPER_MODE=1
ENV DEBUG_MODE=1
```

#### docker-compose.dev.yml

```yaml
version: '3.8'

services:
  erpnext:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    environment:
      - SITE_NAME=dev.facturacion.local
      - DB_ROOT_PASSWORD=admin
    volumes:
      - ./facturacion_mexico:/home/frappe/frappe-bench/apps/facturacion_mexico
    depends_on:
      - db
      - redis
      
  db:
    image: mariadb:10.6
    environment:
      - MYSQL_ROOT_PASSWORD=admin
      
  redis:
    image: redis:alpine
```

### CI/CD Pipeline Testing

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      mariadb:
        image: mariadb:10.6
        env:
          MYSQL_ROOT_PASSWORD: root
        options: --health-cmd="mysqladmin ping" --health-interval=10s
          
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install Frappe
        run: |
          pip install frappe-bench
          bench init --skip-redis-config-generation frappe-bench
          
      - name: Setup App
        run: |
          cd frappe-bench
          bench get-app facturacion_mexico $GITHUB_WORKSPACE
          bench new-site test.local --db-root-password root
          bench install-app facturacion_mexico --site test.local
          
      - name: Run Tests
        run: |
          cd frappe-bench
          bench --site test.local run-tests --app facturacion_mexico --coverage
```

## 🔄 Workflow de Desarrollo

### Branch Strategy

```bash
# Feature branch
git checkout -b feature/nueva-funcionalidad

# Desarrollo...
git add .
git commit -m "feat: agregar nueva funcionalidad"

# Push y crear PR  
git push origin feature/nueva-funcionalidad
```

### Conventional Commits

```bash
# Ejemplos de commits válidos
git commit -m "feat: agregar soporte para addendas Liverpool"
git commit -m "fix: corregir validación RFC en CFDI generation"
git commit -m "test: agregar tests para multi-sucursal failover"
git commit -m "docs: actualizar documentación API"
git commit -m "refactor: optimizar algoritmo de selección de branch"
```

### Pull Request Checklist

- [ ] Tests pasan (46/46) ✅
- [ ] Code coverage > 90% ✅  
- [ ] Linting sin errores ✅
- [ ] Documentación actualizada ✅
- [ ] CHANGELOG.md actualizado ✅
- [ ] Conventional commits ✅

---

!!! tip "Performance"
    Usa `bench --site site.local clear-cache` frecuentemente durante desarrollo para evitar cache issues.

!!! warning "Database"
    Nunca hagas cambios directos a la DB en development. Usa migrations para cambios de schema.

!!! info "Hot Reload"
    Con `auto_reload: 1`, Frappe recargará automáticamente cuando detecte cambios en Python files.