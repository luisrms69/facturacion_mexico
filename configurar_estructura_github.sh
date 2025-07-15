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
