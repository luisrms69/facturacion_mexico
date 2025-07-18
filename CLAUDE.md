# ⚠️ AVISO IMPORTANTE: ESTE NO ES EL ARCHIVO DE SEGUIMIENTO ACTIVO

**🔄 SISTEMA BUZOLA ACTIVO** - El contexto de desarrollo de este proyecto se maneja a través del sistema Buzola centralizado ubicado en:

- **Directorio:** `/home/erpnext/frappe-bench/apps/buzola-internal/projects/facturacion_mexico/`
- **Comandos:** `buzola-status`, `buzola-update "mensaje"`, `buzola-switch`
- **Contexto actual:** Se actualiza automáticamente via scripts de Buzola

**Este archivo permanece como referencia local únicamente.**

---

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

cat > tests/**init**.py << 'EOF'

# Tests base del proyecto
