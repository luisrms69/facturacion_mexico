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
