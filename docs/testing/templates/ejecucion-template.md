# 📊 Reporte Ejecución - [NOMBRE_PLAN]

**Fecha ejecución:** [YYYY-MM-DD]
**Ejecutor:** [Nombre]
**Duración total:** [HH:MM]
**Plan base:** [Link al plan principal]

---

## 📈 **Resumen Ejecutivo**

| Métrica | Valor | Target | Estado |
|---------|-------|--------|--------|
| Casos ejecutados | X/XX | XX | ✅/❌ |
| Success rate | XX% | XX% | ✅/❌ |
| Tiempo promedio/caso | X min | X min | ✅/❌ |
| Issues críticos | X | 0 | ✅/❌ |

---

## 🎯 **Resultados por Nivel**

### **[NIVEL 1] ([RANGO]): XX% success**
- Ejecutados: X/X
- Fallidos: X
- Tiempo promedio: X min

#### **Issues Identificados:**
- [Issue 1 - Severidad]
- [Issue 2 - Severidad]

### **[NIVEL 2] ([RANGO]): XX% success**
[Repetir estructura]

---

## 🐛 **Issues Detallados**

### **🔴 Críticos**
| ID | Descripción | Caso Afectado | Evidencia |
|----|-------------|---------------|-----------|
| ISS-001 | [Descripción] | TC-X-XXX | [screenshot] |

### **🟡 Menores**
[Misma estructura]

---

## 📸 **Evidencias por Caso**

### **TC-[NIVEL]-[NUM]: [Nombre]**
- ✅ G01: [evidencias/TC-X-XXX/G01.png]
- ✅ G02: [evidencias/TC-X-XXX/G02.png]
- ❌ G03: [FALLO - descripción]
- ⏹️ G04: [No ejecutado por fallo G03]

---

## 📋 **Acciones Correctivas**

### **Inmediatas (< 24h)**
1. [Acción prioritaria 1]
2. [Acción prioritaria 2]

### **Corto plazo (< 1 semana)**
1. [Mejora 1]
2. [Mejora 2]

### **Seguimiento requerido**
- [ ] Re-ejecutar casos fallidos
- [ ] Validar fixes implementados
- [ ] Actualizar plan si es necesario

---

## 📊 **Datos Exportables**

```json
{
  "plan": "[NOMBRE_PLAN]",
  "fecha": "[YYYY-MM-DD]",
  "total_casos": XX,
  "casos_exitosos": XX,
  "success_rate": XX.X,
  "tiempo_total_min": XXX,
  "issues_criticos": X,
  "issues_menores": X
}
```

---

**✅ Estado Final:** [EXITOSO/FALLIDO/PARCIAL]
**🔄 Próxima ejecución:** [Fecha programada o "No requerida"]