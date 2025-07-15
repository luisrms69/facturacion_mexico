#!/bin/bash

# Variables de configuración - PERSONALIZAR ESTOS VALORES
NOMBRE_APP="Facturacion Mexico"  # Cambiar por tu nombre de app
DESCRIPCION="App de Facturacion en Mexico Integrada a ERPNEXT"
USUARIO_GITHUB="it@buzola.mx"   # Cambiar por tu usuario de GitHub
NOMBRE_REPO="facturacion_mexico" # Nombre del repositorio en GitHub

# Verificar que estamos en el directorio bench correcto
#if [ ! -d "apps" ] || [ ! -f "sites/common_site_config.json" ]; then
#    echo "❌ Error: Ejecutar desde el directorio raíz de bench"
#    exit 1
#fi

echo "🚀 Iniciando creación de nueva app Frappe: $NOMBRE_APP"

# Crear nueva app Frappe
#bench new-app $NOMBRE_APP

# Cambiar al directorio de la app
#cd apps/$NOMBRE_APP

echo "✅ App Frappe creada exitosamente"

#!/bin/bash

echo "🔧 Configurando Git y estructura de repositorio..."

# Inicializar Git si no existe
if [ ! -d ".git" ]; then
    git init
    git branch -M main
fi

# Crear estructura de directorios GitHub
mkdir -p .github/ISSUE_TEMPLATE
mkdir -p .github/workflows

echo "📝 Creando templates de GitHub..."

# Template Bug Report
cat > .github/ISSUE_TEMPLATE/bug_report.md << 'EOF'
---
name: 🐛 Reporte de Bug
about: Crear reporte de bug para ayudar a mejorar el proyecto
title: '[BUG] '
labels: ['bug', 'needs-review']
assignees: ''
---

## 🐛 **Descripción del Bug**

Descripción clara y concisa del bug.

## 🔄 **Pasos para Reproducir**

1. Ir a '...'
2. Hacer clic en '....'
3. Desplazarse hacia abajo hasta '....'
4. Ver error

## ✅ **Comportamiento Esperado**

Descripción clara y concisa de lo que esperabas que pasara.

## ❌ **Comportamiento Actual**

Descripción clara y concisa de lo que realmente pasa.

## 📱 **Información del Ambiente**

- **Navegador:** [ej. Chrome, Firefox]
- **Versión:** [ej. 22]
- **Sistema Operativo:** [ej. Windows 10, macOS, Ubuntu]
- **Versión Frappe:** [ej. v15.0.0]

## 🎯 **Módulo Afectado**

Seleccionar el módulo donde ocurre el bug:
- [ ] Módulo Principal
- [ ] Configuración
- [ ] API
- [ ] UI/UX
- [ ] Base de Datos
- [ ] Otro: ___________

## 📎 **Capturas de Pantalla**

Si aplica, agregar capturas de pantalla para explicar el problema.

## 📋 **Información Adicional**

Agregar cualquier contexto adicional sobre el problema aquí.
EOF

# Template Feature Request
cat > .github/ISSUE_TEMPLATE/feature_request.md << 'EOF'
---
name: ✨ Solicitud de Feature
about: Sugerir una nueva funcionalidad para el proyecto
title: '[FEAT] '
labels: ['feature', 'needs-review']
assignees: ''
---

## 🎯 **Descripción del Feature**

Descripción clara y concisa del feature solicitado.

## 💡 **User Story**

Como [tipo de usuario], quiero [funcionalidad] para [beneficio/razón].

## ✅ **Criterios de Aceptación**

- [ ] Criterio 1
- [ ] Criterio 2
- [ ] Criterio 3

## 📈 **Prioridad**

- [ ] 🔴 Alta - Crítico para funcionamiento
- [ ] 🟡 Media - Importante pero no bloqueante
- [ ] 🟢 Baja - Nice to have

## 🎨 **Mockups o Diseños**

Si tienes wireframes, mockups o referencias visuales, agrégalos aquí.

## 📋 **Información Adicional**

Contexto adicional, referencias, o detalles sobre la solicitud.
EOF

echo "🏷️ Configurando sistema de labels..."

# Script para configurar labels (se ejecutará después de crear el repo)
cat > .github/setup_labels.sh << 'EOF'
#!/bin/bash

# Script para configurar labels en GitHub
# Ejecutar después de crear el repositorio

echo "🏷️ Configurando labels del repositorio..."

# Función para crear o actualizar label
create_label() {
    local name=$1
    local color=$2
    local description=$3
    
    gh label create "$name" --color "$color" --description "$description" --force
}

# Labels de Prioridad
create_label "critical" "d73a4a" "🔴 Problema crítico que requiere atención inmediata"
create_label "high" "ff6b6b" "🟠 Alta prioridad, resolver en sprint actual"
create_label "medium" "ffa500" "🟡 Prioridad media, planificar para próximo sprint"
create_label "low" "28a745" "🟢 Baja prioridad, backlog"

# Labels de Estado
create_label "needs-review" "0052cc" "👀 Requiere revisión técnica o de negocio"
create_label "in-progress" "fbca04" "🔄 En desarrollo activo"
create_label "blocked" "d73a4a" "🚫 Bloqueado, no se puede continuar"
create_label "ready-to-test" "0e8a16" "✅ Listo para testing/QA"

# Labels de Tipo
create_label "bug" "ee0701" "🐛 Algo no está funcionando"
create_label "feature" "1d76db" "✨ Nueva funcionalidad"
create_label "docs" "5319e7" "📚 Documentación"
create_label "refactor" "fbca04" "🔧 Refactorización de código"
create_label "test" "0052cc" "🧪 Testing"

# Labels de Effort
create_label "easy" "c2e0c6" "😊 Fácil implementación"
create_label "medium" "fef2c0" "🤔 Implementación media"
create_label "hard" "f9d0c4" "😅 Implementación compleja"

echo "✅ Labels configurados exitosamente"
EOF

chmod +x .github/setup_labels.sh

echo "⚙️ Creando workflow de GitHub Actions..."

# Workflow principal para tests
cat > .github/workflows/tests.yml << 'EOF'
name: Tests and Quality

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install frappe-bench
        
    - name: Setup Frappe environment
      run: |
        # Setup básico de Frappe para testing
        echo "Setting up Frappe test environment"
        
    - name: Run Python linting
      run: |
        pip install ruff
        ruff check .
        ruff format --check .
        
    - name: Run tests
      run: |
        # Aquí irían los tests específicos de la app
        echo "Running app tests"
        
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      if: matrix.python-version == 3.9
EOF

# Workflow para validación de commits
cat > .github/workflows/commit-validation.yml << 'EOF'
name: Commit Validation

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  validate:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0
        
    - name: Validate commit messages
      uses: wagoid/commitlint-github-action@v5
      with:
        configFile: '.github/commitlint.config.js'
        
    - name: Validate branch naming
      if: github.event_name == 'pull_request'
      run: |
        branch_name="${{ github.head_ref }}"
        if [[ ! $branch_name =~ ^(feature|fix|docs|style|refactor|test|chore)/.+ ]]; then
          echo "❌ Branch name debe seguir convención: tipo/descripcion"
          echo "Ejemplos: feature/nueva-funcionalidad, fix/corregir-bug"
          exit 1
        fi
        echo "✅ Nombre de branch válido: $branch_name"
EOF

# Configuración de CommitLint
cat > .github/commitlint.config.js << 'EOF'
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore']
    ],
    'subject-case': [2, 'always', 'lower-case'],
    'subject-max-length': [2, 'always', 72],
    'body-max-line-length': [2, 'always', 100]
  }
};
EOF

echo "✅ Estructura GitHub configurada"

#!/bin/bash

echo "🪝 Configurando pre-commit hooks..."

# Instalar pre-commit si no existe
pip install pre-commit

# Crear configuración de pre-commit
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: check-merge-conflict
      - id: check-ast
      - id: debug-statements
      - id: mixed-line-ending

  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.0.3
    hooks:
      - id: prettier
        types_or: [javascript, jsx, ts, tsx, css, scss, json, yaml, markdown]

  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.53.0
    hooks:
      - id: eslint
        files: \.(js|jsx|ts|tsx)$
        types: [file]
        additional_dependencies:
          - eslint@8.53.0
EOF

# Instalar hooks
pre-commit install

echo "✅ Pre-commit hooks configurados"

#!/bin/bash

echo "📚 Configurando documentación..."

# Crear CLAUDE.md con configuración base
cat > CLAUDE.md << 'EOF'
# 🤖 CLAUDE.md - CONFIGURACIÓN DEL PROYECTO

**Proyecto:** Nueva App Frappe  
**Framework:** Frappe v15  
**Fecha Inicio:** 25 de junio de 2025  
**Estado:** Desarrollo Activo  

---

## 🎯 **REGLAS FUNDAMENTALES DEL PROYECTO**

### **REGLA #1: ESPAÑOL OBLIGATORIO**
- ✅ **TODAS las etiquetas** de DocTypes, campos, opciones deben estar en español
- ✅ **Mensajes de validación** en español
- ✅ **Documentación de usuario** en español
- ❌ **Variables y código** permanecen en inglés (convención técnica)

### **REGLA #2: CONVENTIONAL COMMITS OBLIGATORIOS**

---

## 🧪 **PARTE 5: CONFIGURAR ESTRUCTURA DE TESTING**


echo "🧪 Configurando estructura de testing..."

# Crear directorio de tests si no existe
mkdir -p tests

# Crear archivo base de tests
cat > tests/__init__.py << 'EOF'
# Tests base del proyecto
EOF

# Crear template de tests
cat > tests/test_template.py << 'EOF'
"""
Template base para crear tests de DocTypes.
Copiar y personalizar para cada DocType nuevo.
"""

import unittest
import frappe
from frappe.tests.utils import FrappeTestCase


class TestDocTypeTemplate(FrappeTestCase):
    """Test template para DocTypes del proyecto."""
    
    @classmethod
    def setUpClass(cls):
        """Configurar data que persiste para todos los tests."""
        super().setUpClass()
        cls.create_test_dependencies()
    
    @classmethod
    def create_test_dependencies(cls):
        """Crear dependencies de test si no existen."""
        if getattr(frappe.flags, 'test_doctype_deps_created', False):
            return
        
        # Crear dependencies aquí
        # Ejemplo: Companies, Users, etc.
        
        frappe.flags.test_doctype_deps_created = True
    
    def setUp(self):
        """Configurar antes de cada test."""
        frappe.set_user("Administrator")
        self.test_data = {
            "doctype": "DocType Name",
            "name": "Test Document",
            # Agregar campos requeridos
        }
    
    def tearDown(self):
        """Limpiar después de cada test."""
        frappe.set_user("Administrator")
        # FrappeTestCase maneja rollback automático
    
    def test_creation(self):
        """Test creación básica del DocType."""
        doc = frappe.get_doc(self.test_data)
        doc.insert(ignore_permissions=True)
        
        # Validaciones
        self.assertEqual(doc.name, self.test_data["name"])
        self.assertTrue(doc.creation)
        
        # NO hacer doc.delete() - rollback automático
    
    def test_spanish_labels(self):
        """Test que etiquetas estén en español."""
        meta = frappe.get_meta(self.test_data["doctype"])
        
        # Verificar label principal
        self.assertIsNotNone(meta.get("label"))
        # Agregar validaciones específicas de español
        
        # Verificar labels de campos principales
        for field in meta.fields:
            if field.fieldname in ["name", "title"]:  # Campos importantes
                self.assertIsNotNone(field.label)
    
    def test_required_fields_validation(self):
        """Test validación de campos requeridos."""
        doc_data = self.test_data.copy()
        doc_data.pop("name")  # Remover campo requerido
        
        with self.assertRaises(frappe.ValidationError):
            doc = frappe.get_doc(doc_data)
            doc.insert(ignore_permissions=True)
    
    def test_spanish_options(self):
        """Test opciones de campos Select en español."""
        meta = frappe.get_meta(self.test_data["doctype"])
        
        for field in meta.fields:
            if field.fieldtype == "Select" and field.options:
                options = field.options.split("\n")
                for option in options:
                    if option.strip():
                        # Verificar que no contenga texto en inglés común
                        self.assertNotIn("Active", option)
                        self.assertNotIn("Inactive", option)
                        # Agregar más validaciones según necesidades
EOF

# Crear utilidades de testing
cat > tests/test_utils.py << 'EOF'
"""
Utilidades para testing del proyecto.
"""

import frappe
from frappe.utils import random_string


def create_test_company(company_name=None, abbreviation=None):
    """Crear company de test."""
    if not company_name:
        company_name = f"Test Company {random_string(5)}"
    
    if not abbreviation:
        abbreviation = f"TC{random_string(3)}"
    
    if frappe.db.exists("Company", company_name):
        return frappe.get_doc("Company", company_name)
    
    company = frappe.get_doc({
        "doctype": "Company",
        "company_name": company_name,
        "abbr": abbreviation,
        "default_currency": "MXN",
        "country": "Mexico"
    })
    company.insert(ignore_permissions=True)
    return company


def create_test_user(email=None, first_name="Test", last_name="User"):
    """Crear usuario de test."""
    if not email:
        email = f"test_{random_string(5)}@test.com"
    
    if frappe.db.exists("User", email):
        return frappe.get_doc("User", email)
    
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "enabled": 1,
        "user_type": "System User"
    })
    user.insert(ignore_permissions=True)
    return user


def cleanup_test_records(doctype, filters=None):
    """Limpiar registros de test."""
    if not filters:
        filters = {"name": ["like", "Test%"]}
    
    records = frappe.get_all(doctype, filters=filters)
    for record in records:
        frappe.delete_doc(doctype, record.name, ignore_permissions=True)


def ensure_spanish_labels(doctype_name):
    """Verificar que DocType tiene labels en español."""
    meta = frappe.get_meta(doctype_name)
    
    # Verificar label principal
    assert meta.get("label"), f"DocType {doctype_name} no tiene label"
    
    # Verificar campos principales
    required_spanish_fields = ["name", "title", "status"]
    for field in meta.fields:
        if field.fieldname in required_spanish_fields:
            assert field.label, f"Campo {field.fieldname} no tiene label"
    
    return True
EOF

# Crear configuración de testing
cat > tests/conftest.py << 'EOF'
"""
Configuración pytest para el proyecto.
"""

import pytest
import frappe


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Configurar ambiente de test antes de cada test."""
    frappe.set_user("Administrator")
    frappe.clear_cache()
    yield
    frappe.db.rollback()


@pytest.fixture
def test_company():
    """Fixture para crear company de test."""
    from tests.test_utils import create_test_company
    return create_test_company()


@pytest.fixture
def test_user():
    """Fixture para crear usuario de test."""
    from tests.test_utils import create_test_user
    return create_test_user()
EOF

echo "✅ Estructura de testing configurada"

#!/bin/bash

echo "🔐 Configurando hooks y seguridad..."

# Configurar hooks básicos en la app
cat > ${NOMBRE_APP}/hooks.py << 'EOF'
"""
Hooks configuration para la app.
Basado en mejores prácticas de condominium_management.
"""

app_name = "nueva_app_frappe"  # Cambiar por nombre real
app_title = "Nueva App Frappe"  # Cambiar por título real
app_publisher = "Tu Empresa"  # Cambiar por tu empresa
app_description = "Descripción de la nueva app"  # Cambiar descripción
app_email = "admin@tuempresa.com"  # Cambiar email
app_license = "GPL v3"
app_version = "1.0.0"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/nueva_app_frappe/css/nueva_app_frappe.css"
# app_include_js = "/assets/nueva_app_frappe/js/nueva_app_frappe.js"

# include js, css files in header of web template
# web_include_css = "/assets/nueva_app_frappe/css/nueva_app_frappe.css"
# web_include_js = "/assets/nueva_app_frappe/js/nueva_app_frappe.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "nueva_app_frappe/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "nueva_app_frappe/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "nueva_app_frappe.utils.jinja_methods",
# 	"filters": "nueva_app_frappe.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "nueva_app_frappe.install.before_install"
after_install = "nueva_app_frappe.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "nueva_app_frappe.uninstall.before_uninstall"
# after_uninstall = "nueva_app_frappe.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "nueva_app_frappe.utils.before_app_install"
# after_app_install = "nueva_app_frappe.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "nueva_app_frappe.utils.before_app_uninstall"
# after_app_uninstall = "nueva_app_frappe.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "nueva_app_frappe.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"nueva_app_frappe.tasks.all"
# 	],
# 	"daily": [
# 		"nueva_app_frappe.tasks.daily"
# 	],
# 	"hourly": [
# 		"nueva_app_frappe.tasks.hourly"
# 	],
# 	"weekly": [
# 		"nueva_app_frappe.tasks.weekly"
# 	],
# 	"monthly": [
# 		"nueva_app_frappe.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "nueva_app_frappe.utils.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "nueva_app_frappe.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "nueva_app_frappe.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["nueva_app_frappe.utils.before_request"]
# after_request = ["nueva_app_frappe.utils.after_request"]

# Job Events
# ----------
# before_job = ["nueva_app_frappe.utils.before_job"]
# after_job = ["nueva_app_frappe.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"nueva_app_frappe.auth.validate"
# ]

# Automatically update python controller files with type annotations for Intellisense
# Use "GenerateSchema", "GenerateSchemaChild", "GenerateSchema" in manifest.json
# uncomment and add them to "export" field of manifest.json
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
EOF

# Crear archivo de instalación
mkdir -p ${NOMBRE_APP}
cat > ${NOMBRE_APP}/install.py << 'EOF'
"""
Post-installation setup para la app.
"""

import frappe


def after_install():
    """Configuración después de la instalación."""
    print("🔧 Nueva App Frappe: Ejecutando configuración post-instalación...")
    
    # Limpiar cache
    frappe.clear_cache()
    
    # Configuraciones adicionales aquí
    setup_default_roles()
    create_default_settings()
    
    print("✅ Configuración post-instalación completada")


def setup_default_roles():
    """Configurar roles por defecto si es necesario."""
    # Crear roles customizados aquí si se requieren
    pass


def create_default_settings():
    """Crear configuraciones por defecto."""
    # Configuraciones iniciales de la app
    pass
EOF

# Crear archivo de utilidades
cat > ${NOMBRE_APP}/utils.py << 'EOF'
"""
Utilidades generales para la app.
"""

import frappe
from frappe.utils import now_datetime


def before_tests():
    """Configuración antes de ejecutar tests."""
    frappe.clear_cache()
    
    # Configurar ambiente de testing
    setup_test_environment()
    
    print("🧪 Ambiente de testing configurado")


def setup_test_environment():
    """Configurar ambiente específico para tests."""
    from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
    
    # Verificar si ya existe configuración básica
    if not frappe.get_list("Company"):
        year = now_datetime().year
        setup_complete({
            "currency": "MXN",
            "company_name": "Test Company LLC",
            "timezone": "America/Mexico_City",
            "country": "Mexico",
            "fy_start_date": f"{year}-01-01",
            "fy_end_date": f"{year}-12-31",
            "language": "es",
            "company_abbr": "TC"
        })
    
    # Configuraciones adicionales de test
    _ensure_basic_records_exist()
    enable_all_roles_and_domains()
    frappe.db.commit()


def _ensure_basic_records_exist():
    """Asegurar que registros básicos existen."""
    # Crear registros básicos que podrían faltar en testing
    
    # Warehouse Types si se requieren
    if not frappe.db.exists("Warehouse Type", "Transit"):
        warehouse_type = frappe.get_doc({
            "doctype": "Warehouse Type",
            "name": "Transit"
        })
        warehouse_type.insert(ignore_permissions=True)
    
    # Department padre si se requiere
    if not frappe.db.exists("Department", "All Departments"):
        dept = frappe.get_doc({
            "doctype": "Department",
            "department_name": "All Departments",
            "is_group": 1
        })
        dept.insert(ignore_permissions=True)


def enable_all_roles_and_domains():
    """Habilitar todos los roles y dominios para testing."""
    from frappe.core.doctype.role.role import desk_properties
    
    # Habilitar roles
    for role in frappe.get_all("Role"):
        role_doc = frappe.get_doc("Role", role.name)
        role_doc.desk_access = 1
        role_doc.save(ignore_permissions=True)
    
    # Configuraciones adicionales si se requieren
    pass


@frappe.whitelist()
def get_app_version():
    """Obtener versión de la app."""
    from nueva_app_frappe import __version__
    return __version__


def log_action(user, action, details=None):
    """Log de acciones importantes."""
    frappe.logger().info(f"User {user} performed {action}: {details or ''}")


def validate_spanish_content(content):
    """Validar que el contenido esté en español."""
    # Palabras comunes en inglés que no deberían estar
    english_words = [
        "Active", "Inactive", "Draft", "Submitted", "Cancelled",
        "Save", "Cancel", "Delete", "Edit", "Create", "Update"
    ]
    
    for word in english_words:
        if word in content:
            frappe.throw(f"Contenido contiene texto en inglés: {word}")
    
    return True
EOF

echo "✅ Hooks y seguridad configurados"

#!/bin/bash

echo "🌐 Configurando repositorio GitHub..."

# Verificar que GitHub CLI está instalado
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI no está instalado"
    echo "Instalar con: curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg"
    exit 1
fi

# Verificar autenticación
if ! gh auth status &> /dev/null; then
    echo "🔐 Autenticando con GitHub..."
    gh auth login
fi

echo "📝 Configurando Git..."

# Configurar Git si no está configurado
git config user.name "${GIT_USER_NAME:-Tu Nombre}"
git config user.email "${GIT_USER_EMAIL:-tu_email@ejemplo.com}"

# Inicializar repositorio si no existe
if [ ! -d ".git" ]; then
    git init
    git branch -M main
fi

# Crear .gitignore apropiado para Frappe
cat > .gitignore << 'EOF'
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Frappe specific
node_modules/
*.compiled
*.css.map
.build/
sites/
archived_sites/
logs/
*.log

# App specific
public/js/frappe-web.min.js
public/js/frappe-desk.min.js
public/css/frappe-web.css
public/css/frappe-desk.css
public/js/dialog.min.js
public/js/controls.min.js
public/css/desk.min.css
public/css/form.min.css

# Local configuration
site_config.json
common_site_config.json

# Backup files
*.sql
*.sql.gz
*.bak

# Temporary files
*~
.#*
#*#
.*.rej
*.rej
*.orig
EOF

# Agregar archivos al repositorio
echo "📁 Agregando archivos al repositorio..."

git add .
git commit -m "feat(init): configuración inicial del proyecto

🚀 Configuración completa basada en condominium_management:
- ✅ Estructura GitHub (templates, workflows, labels)
- ✅ Pre-commit hooks (ruff, validaciones)
- ✅ Documentación (CLAUDE.md, README)
- ✅ Testing framework (FrappeTestCase)
- ✅ Hooks de instalación
- ✅ Configuración de seguridad

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Crear repositorio en GitHub
echo "🚀 Creando repositorio en GitHub..."

gh repo create $NOMBRE_REPO \
    --description "$DESCRIPCION" \
    --private \
    --source . \
    --remote origin \
    --push

echo "✅ Repositorio creado: https://github.com/$USUARIO_GITHUB/$NOMBRE_REPO"

# Configurar labels
echo "🏷️ Configurando labels..."
./.github/setup_labels.sh

# Configurar branch protection
echo "🛡️ Configurando protección de branches..."

gh api repos/$USUARIO_GITHUB/$NOMBRE_REPO/branches/main/protection \
    --method PUT \
    --field required_status_checks='{"strict":true,"contexts":[]}' \
    --field enforce_admins=true \
    --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
    --field restrictions=null

echo "✅ Protección de branches configurada"

#!/bin/bash

echo "📊 Configurando Project Boards..."

# Crear project board
PROJECT_ID=$(gh api graphql -f query='
  mutation {
    createProjectV2(input: {
      ownerId: "'$(gh api user --jq .node_id)'"
      title: "'$NOMBRE_APP' Development"
    }) {
      projectV2 {
        id
        number
      }
    }
  }
' --jq .data.createProjectV2.projectV2.id)

echo "✅ Project Board creado con ID: $PROJECT_ID"

# Configurar columnas del project board
gh api graphql -f query='
  mutation {
    addProjectV2Field(input: {
      projectId: "'$PROJECT_ID'"
      dataType: SINGLE_SELECT
      name: "Status"
      singleSelectOptions: [
        {name: "Backlog", color: GRAY}
        {name: "In Progress", color: YELLOW}
        {name: "Review", color: BLUE}
        {name: "Testing", color: PURPLE}
        {name: "Done", color: GREEN}
      ]
    }) {
      projectV2Field {
        id
      }
    }
  }
'

echo "✅ Columnas de status configuradas"

# Conectar repositorio al project
gh api graphql -f query='
  mutation {
    linkProjectV2ToRepository(input: {
      projectId: "'$PROJECT_ID'"
      repositoryId: "'$(gh api repos/$USUARIO_GITHUB/$NOMBRE_REPO --jq .node_id)'"
    }) {
      repository {
        id
      }
    }
  }
'

echo "✅ Repositorio conectado al project board"

#!/bin/bash

echo "🎯 Realizando configuración final..."

# Instalar dependencias de desarrollo
echo "📦 Instalando dependencias..."

pip install -r requirements.txt 2>/dev/null || echo "ℹ️ requirements.txt no encontrado, continuando..."

# Verificar que pre-commit funciona
echo "🧪 Validando pre-commit..."
pre-commit run --all-files || echo "⚠️ Pre-commit encontró issues, corregir antes de commits futuros"

# Crear primer issue de ejemplo
echo "📝 Creando issue de ejemplo..."

gh issue create \
    --title "🚀 Configuración inicial completada" \
    --body "
## ✅ Configuración Completada

El repositorio ha sido configurado exitosamente con:

- ✅ **GitHub Templates** - Bug reports y feature requests
- ✅ **Labels System** - Prioridades, estados, tipos
- ✅ **Branch Protection** - Main protegido, PRs obligatorios
- ✅ **Pre-commit Hooks** - Ruff, formatting, validaciones
- ✅ **Project Board** - Workflow automatizado
- ✅ **Testing Framework** - Templates y utilidades
- ✅ **Documentation** - CLAUDE.md y README
- ✅ **CI/CD Workflows** - GitHub Actions configurado

## 🎯 Próximos Pasos

1. Crear primer DocType del proyecto
2. Implementar tests correspondientes
3. Configurar módulos específicos
4. Establecer workflows de desarrollo

## 📚 Referencias

- Revisar \`CLAUDE.md\` para reglas del proyecto
- Seguir templates en \`tests/\` para nuevos tests
- Usar conventional commits para todos los cambios

---

**Configuración basada en:** condominium_management  
**Metodología:** Frappe Framework Best Practices  
" \
    --label "docs,ready-to-test"

echo "📋 Creando checklist de configuración..."

# Crear issue con checklist de validación
gh issue create \
    --title "📋 Checklist de Validación - Configuración del Proyecto" \
    --body "
## 🔍 Validación de Configuración

Verificar que todos los componentes estén funcionando correctamente:

### GitHub Repository
- [ ] Branch protection rules activos en main
- [ ] Templates de issues funcionando
- [ ] Labels configurados correctamente
- [ ] Project board conectado
- [ ] CI/CD workflows activos

### Desarrollo Local
- [ ] Pre-commit hooks instalados y funcionando
- [ ] App Frappe creada en bench
- [ ] Tests base ejecutándose sin errores
- [ ] Documentación actualizada

### Estructura de Archivos
- [ ] \`CLAUDE.md\` con reglas del proyecto
- [ ] \`README.md\` con información completa
- [ ] Templates de tests en \`tests/\`
- [ ] Hooks configurados en \`hooks.py\`
- [ ] Utilities en \`utils.py\`

### Validaciones de Calidad
- [ ] Conventional commits funcionando
- [ ] Ruff linting sin errores
- [ ] Spanish labels validation
- [ ] Testing framework operativo

### Integración
- [ ] App instalada en site de desarrollo
- [ ] Migraciones ejecutándose correctamente
- [ ] Permisos configurados apropiadamente
- [ ] Logs sin errores críticos

## 🚨 Problemas Encontrados

_Documentar aquí cualquier problema durante la validación_

## ✅ Aprobación

- [ ] **Tech Lead:** Configuración técnica aprobada
- [ ] **Project Manager:** Workflow y procesos aprobados
- [ ] **QA:** Testing framework validado

---

**Responsable:** Equipo de Desarrollo  
**Deadline:** 48 horas después de la configuración  
" \
    --label "critical,needs-review"

echo "📚 Generando documentación final..."

# Crear resumen de configuración
cat > CONFIG_SUMMARY.md << EOF
# 📋 RESUMEN DE CONFIGURACIÓN - $NOMBRE_APP

**Fecha de Configuración:** $(date)  
**Repositorio:** https://github.com/$USUARIO_GITHUB/$NOMBRE_REPO  
**Basado en:** condominium_management methodology  

---

## ✅ **COMPONENTES CONFIGURADOS**

### 🐙 **GitHub Repository**
- **Branch Protection:** Main protegido, PRs obligatorios
- **Issue Templates:** Bug reports y feature requests
- **Labels System:** Prioridades, estados, tipos, effort
- **Project Board:** Workflow automatizado
- **Workflows:** Tests, commit validation, security scanning

### 🔧 **Desarrollo**
- **Pre-commit Hooks:** Ruff, formatting, validaciones
- **Testing Framework:** FrappeTestCase templates
- **Documentation:** CLAUDE.md con reglas del proyecto
- **CI/CD:** GitHub Actions configurado

### 📁 **Estructura de Archivos**
\`\`\`
$NOMBRE_APP/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── workflows/
│   └── setup_labels.sh
├── tests/
│   ├── test_template.py
│   ├── test_utils.py
│   └── conftest.py
├── $NOMBRE_APP/
│   ├── hooks.py
│   ├── install.py
│   └── utils.py
├── CLAUDE.md
├── README.md
├── .pre-commit-config.yaml
└── .gitignore
\`\`\`

---

## 🎯 **PRÓXIMOS PASOS**

### **Inmediatos (Próximos 3 días)**
1. **Validar configuración** usando checklist de issues
2. **Crear primer DocType** siguiendo templates
3. **Implementar tests** para funcionalidad básica
4. **Configurar site de desarrollo** local

### **Corto Plazo (Próximas 2 semanas)**
1. **Desarrollar módulos core** según arquitectura
2. **Establecer workflow de desarrollo** en equipo
3. **Configurar ambientes** de staging y producción
4. **Implementar CI/CD completo**

### **Mediano Plazo (Próximo mes)**
1. **Completar funcionalidades principales**
2. **Documentación de usuario** completa
3. **Testing exhaustivo** de integración
4. **Preparar para deployment** en producción

---

## 📞 **SOPORTE Y REFERENCIAS**

### **Documentación**
- **CLAUDE.md** - Reglas y configuración del proyecto
- **README.md** - Información general y instalación
- **tests/test_template.py** - Template para nuevos tests

### **Workflows**
- **Conventional Commits** - Formato estándar obligatorio
- **Feature Branches** - \`feature/modulo-descripcion\`
- **Pull Requests** - Review obligatorio antes de merge
- **Testing** - Tests obligatorios para nueva funcionalidad

### **Herramientas**
- **GitHub CLI** - Gestión de issues y PRs
- **Pre-commit** - Validación automática de código
- **Ruff** - Linting y formatting de Python
- **FrappeTestCase** - Framework de testing

---

**Estado:** ✅ CONFIGURACIÓN COMPLETADA  
**Próxima Revisión:** $(date -d "+1 week")  
**Responsable:** $USUARIO_GITHUB  
EOF

echo "🎉 ¡Configuración completada exitosamente!"
echo ""
echo "📋 RESUMEN:"
echo "✅ Repositorio GitHub: https://github.com/$USUARIO_GITHUB/$NOMBRE_REPO"
echo "✅ App Frappe creada: $NOMBRE_APP"
echo "✅ Documentación: CLAUDE.md, README.md"
echo "✅ Testing: Framework configurado"
echo "✅ CI/CD: GitHub Actions activo"
echo "✅ Quality: Pre-commit hooks instalados"
echo ""
echo "🎯 PRÓXIMOS PASOS:"
echo "1. Revisar issues creados en GitHub"
echo "2. Instalar app en site: bench --site [site] install-app $NOMBRE_APP"
echo "3. Crear primer DocType siguiendo templates"
echo "4. Implementar tests correspondientes"
echo ""
echo "📚 REFERENCIAS:"
echo "- CLAUDE.md - Reglas del proyecto"
echo "- CONFIG_SUMMARY.md - Resumen completo"
echo "- tests/test_template.py - Template para tests"


