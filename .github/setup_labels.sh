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
