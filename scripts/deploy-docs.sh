#!/bin/bash

# Deploy script para documentación con Mike
# Uso: ./scripts/deploy-docs.sh [version] [alias]

VERSION=${1:-dev}
ALIAS=${2:-}

echo "📚 Generando documentación para versión $VERSION..."

# Verificar que estamos en el directorio correcto
if [ ! -f "mkdocs.yml" ]; then
    echo "❌ Error: mkdocs.yml no encontrado. Ejecutar desde la raíz del proyecto."
    exit 1
fi

# Instalar dependencias si es necesario
if [ ! -d "venv" ]; then
    echo "📦 Instalando dependencias de documentación..."
    pip install -r requirements-docs.txt
fi

# Generar documentación de API automáticamente
if [ -f "scripts/generate_docs.py" ]; then
    echo "🔄 Generando documentación de API..."
    python scripts/generate_docs.py
fi

# Construir documentación para verificar errores
echo "🔨 Construyendo documentación..."
mkdocs build --strict

if [ $? -ne 0 ]; then
    echo "❌ Error en la construcción de la documentación"
    exit 1
fi

# Configurar Git para Mike si no está configurado
if [ -z "$(git config user.name)" ]; then
    git config user.name "Documentation Deploy"
    git config user.email "docs@$(basename $(pwd)).local"
fi

# Desplegar con Mike
echo "🚀 Desplegando con Mike..."
if [ -z "$ALIAS" ]; then
    mike deploy --push $VERSION
else
    mike deploy --push --update-aliases $VERSION $ALIAS
fi

if [ $? -eq 0 ]; then
    echo "✅ Documentación desplegada exitosamente"
    echo "🔗 URL: https://$(git config remote.origin.url | sed 's/.*github.com[:/]\([^/]*\)\/\([^.]*\).*/\1.github.io\/\2/')/"
else
    echo "❌ Error en el despliegue"
    exit 1
fi

# Listar versiones disponibles
echo "📋 Versiones disponibles:"
mike list