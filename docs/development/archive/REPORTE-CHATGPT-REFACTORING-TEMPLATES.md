> **OBSOLETO**
>
> Este documento queda archivado como referencia histórica. No representa el plan vigente ni debe usarse como fuente operativa actual.

---

# 🤖 REPORTE TÉCNICO: REFACTORING SISTEMA TEMPLATES FISCALES

**Fecha:** 2025-09-22
**Audiencia:** ChatGPT / Claude Code
**Propósito:** Solicitar refactoring completo del sistema de templates fiscales
**Contexto:** Frappe Framework v15, ERPNext, Facturación México v5.0

---

## 🚨 **PROBLEMÁTICA CRÍTICA IDENTIFICADA**

### **Problema 1: Código Excesivamente Hardcodeado**
El sistema actual tiene **tasas, estructuras y configuraciones fiscales hardcodeadas** en el código fuente, violando principios de mantenibilidad y escalabilidad.

**Evidencia:**
```python
# En generador_templates_fiscal.py líneas 107-153
{
    "title": "IVA 16% - México",
    "taxes": [{
        "rate": 16.0,  # ← HARDCODED
        "description": "Impuesto al Valor Agregado 16%"  # ← HARDCODED
    }]
}
```

### **Problema 2: Implementación Incompleta**
El wizard permite configurar **IEPS y retenciones** pero el generador **NO implementa la generación** de estos templates.

**Inconsistencia crítica:**
- ✅ Usuario puede mapear "IEPS por Pagar (Alcohol)"
- ❌ Sistema NO genera template STCT/ITT para IEPS Alcohol
- ❌ 10 de 14 tipos de templates NO están implementados

---

## 🎯 **OBJETIVOS DEL REFACTORING**

### **Objetivo 1: Eliminar Hardcode Completo**
- Parametrizar todas las tasas fiscales
- Externalizar configuraciones a fixtures/JSON
- Hacer sistema completamente configurable

### **Objetivo 2: Implementación Completa**
- Generar templates IEPS (4 tipos)
- Generar templates retenciones (6 tipos)
- Cubrir 100% de roles fiscales configurables

### **Objetivo 3: Arquitectura Sostenible**
- Patrón Strategy para diferentes tipos de impuestos
- Configuración declarativa vs imperativa
- Fácil extensión para futuros impuestos

---

## 🏗️ **PROPUESTA ARQUITECTÓNICA**

### **1. Configuración Fiscal Declarativa**

**Crear archivo:** `fiscal_config_mx.json`
```json
{
  "impuestos_soportados": {
    "iva": {
      "general": {"tasa": 16.0, "descripcion": "IVA General"},
      "frontera": {"tasa": 8.0, "descripcion": "IVA Frontera"},
      "exportacion": {"tasa": 0.0, "descripcion": "IVA Exportación"},
      "exento": {"tasa": 0.0, "descripcion": "IVA Exento"}
    },
    "ieps": {
      "alcohol": {"tasa": 26.5, "tipo": "especifico", "descripcion": "IEPS Alcohol"},
      "azucar": {"tasa": 1.0, "tipo": "peso", "descripcion": "IEPS Azúcar"},
      "combustibles": {"tasa": 4.58, "tipo": "especifico", "descripcion": "IEPS Combustibles"},
      "tabaco": {"tasa": 160.0, "tipo": "porcentaje", "descripcion": "IEPS Tabaco"}
    },
    "retenciones": {
      "isr_honorarios": {"tasa": 10.0, "tipo": "retencion", "descripcion": "ISR Retenido Honorarios"},
      "iva_servicios": {"tasa": 10.67, "tipo": "retencion", "descripcion": "IVA Retenido Servicios"},
      "isr_arrendamiento": {"tasa": 10.0, "tipo": "retencion", "descripcion": "ISR Retenido Arrendamiento"},
      "iva_arrendamiento": {"tasa": 10.67, "tipo": "retencion", "descripcion": "IVA Retenido Arrendamiento"},
      "isr_autotransporte": {"tasa": 4.0, "tipo": "retencion", "descripcion": "ISR Retenido Autotransporte"},
      "iva_autotransporte": {"tasa": 4.0, "tipo": "retencion", "descripcion": "IVA Retenido Autotransporte"}
    }
  },
  "combinaciones_templates": {
    "basico": ["iva.general", "iva.exportacion", "iva.exento"],
    "frontera": ["iva.general", "iva.frontera", "iva.exportacion", "iva.exento"],
    "ieps_completo": ["iva.general", "ieps.alcohol", "ieps.azucar", "ieps.combustibles", "ieps.tabaco"],
    "retenciones_completo": ["iva.general", "retenciones.isr_honorarios", "retenciones.iva_servicios"]
  }
}
```

### **2. Patrón Strategy para Tipos de Impuestos**

**Crear clase base:** `GeneradorTemplateStrategy`
```python
class GeneradorTemplateStrategy:
    def generar_stct(self, config_impuesto: Dict, mapeo_cuentas: Dict) -> str:
        raise NotImplementedError

    def generar_itt(self, config_impuesto: Dict, mapeo_cuentas: Dict) -> str:
        raise NotImplementedError

class GeneradorIVA(GeneradorTemplateStrategy):
    # Implementación específica IVA

class GeneradorIEPS(GeneradorTemplateStrategy):
    # Implementación específica IEPS

class GeneradorRetenciones(GeneradorTemplateStrategy):
    # Implementación específica retenciones
```

### **3. Factory Pattern para Templates**

```python
class TemplateFactory:
    strategies = {
        "iva": GeneradorIVA(),
        "ieps": GeneradorIEPS(),
        "retenciones": GeneradorRetenciones()
    }

    @classmethod
    def generar_template(cls, tipo_impuesto: str, config: Dict, mapeo: Dict):
        strategy = cls.strategies.get(tipo_impuesto)
        return strategy.generar_template(config, mapeo)
```

### **4. Configuración por Alcance Empresarial**

```python
class ConfiguradorAlcanceFiscal:
    def obtener_templates_requeridos(self, config_fiscal) -> List[str]:
        """Retorna lista de templates necesarios según alcance empresarial."""
        templates = ["iva.general", "iva.exportacion", "iva.exento"]

        if config_fiscal.enable_frontera:
            templates.append("iva.frontera")

        if config_fiscal.enable_ieps_alcohol:
            templates.append("ieps.alcohol")

        # ... lógica condicional basada en configuración
        return templates
```

---

## 📋 **PLAN DE IMPLEMENTACIÓN**

### **Fase 1: Preparación (1-2 horas)**
1. **Crear configuración fiscal JSON** con todas las tasas actualizadas SAT 2025
2. **Implementar loader de configuración** fiscal desde JSON
3. **Crear fixtures** para configuración por defecto

### **Fase 2: Refactoring Core (3-4 horas)**
1. **Implementar patrón Strategy** para diferentes tipos impuestos
2. **Refactorizar GeneradorTemplatesFiscales** para usar strategies
3. **Eliminar hardcode** completo del código actual

### **Fase 3: Implementación Faltante (4-5 horas)**
1. **Implementar GeneradorIEPS** completo (4 tipos)
2. **Implementar GeneradorRetenciones** completo (6 tipos)
3. **Testing exhaustivo** de nuevas implementaciones

### **Fase 4: Validación (1-2 horas)**
1. **Migración automática** configuraciones existentes
2. **Testing compatibilidad** hacia atrás
3. **Documentación actualizada**

---

## 🧪 **CASOS DE TESTING CRÍTICOS**

### **Testing Configuración Parametrizada:**
```python
def test_configuracion_desde_json():
    config = CargarConfiguracionFiscal()
    assert config.get_tasa("iva", "general") == 16.0
    assert config.get_tasa("ieps", "alcohol") == 26.5

def test_cambio_tasa_dinamico():
    # Simular cambio fiscal SAT
    config.update_tasa("iva", "general", 17.0)
    templates = generar_templates(company="Test", config=config)
    assert templates[0].tasa == 17.0
```

### **Testing Implementación IEPS:**
```python
def test_generacion_templates_ieps():
    config_fiscal = create_test_config(enable_ieps_alcohol=True)
    mapeo = {"IEPS por Pagar (Alcohol)": "IEPS Alcohol - Test"}

    resultado = GeneradorTemplatesFiscales(company="Test").generar_templates_completos()

    assert "IEPS Alcohol - México - Test" in resultado["stct_generados"]
    assert "ITT IEPS Alcohol - Test" in resultado["itt_generados"]
```

---

## 🎯 **BENEFICIOS ESPERADOS**

### **Operativos:**
- ✅ **100% templates implementados** (14/14 en lugar de 4/14)
- ✅ **Configuración completa** IEPS y retenciones
- ✅ **Mantenimiento simplificado** para cambios fiscales SAT

### **Técnicos:**
- ✅ **Zero hardcode** - Todas las tasas configurables
- ✅ **Arquitectura extensible** - Nuevos impuestos fácil agregado
- ✅ **Testing robusto** - Configuración parametrizada testeable

### **Negocio:**
- ✅ **Cumplimiento fiscal completo** para todo tipo de empresas
- ✅ **Adaptabilidad** a cambios normativos SAT
- ✅ **Escalabilidad** para futuros requerimientos

---

## 🚀 **ENTREGABLES SOLICITADOS**

### **Código:**
1. **fiscal_config_mx.json** - Configuración fiscal completa
2. **GeneradorTemplateStrategy** - Clase base y implementaciones
3. **TemplateFactory** - Factory pattern para templates
4. **Refactoring completo** de `generador_templates_fiscal.py`

### **Testing:**
1. **Suite testing** configuración parametrizada
2. **Tests unitarios** para cada strategy
3. **Tests integración** generación completa

### **Documentación:**
1. **Manual desarrollador** actualizado
2. **Guía migración** para configuraciones existentes
3. **Documentación API** para nuevas funcionalidades

---

## ⚠️ **RESTRICCIONES TÉCNICAS**

### **Compatibilidad:**
- ✅ **Backward compatible** - Configuraciones existentes deben seguir funcionando
- ✅ **Frappe Framework v15** - Usar APIs nativas
- ✅ **Zero breaking changes** - No romper funcionalidad actual

### **Rendimiento:**
- ✅ **Lazy loading** configuración fiscal
- ✅ **Caching inteligente** para templates generados
- ✅ **Bulk operations** para múltiples empresas

### **Seguridad:**
- ✅ **Validación estricta** configuración JSON
- ✅ **Permisos granulares** para modificar configuración fiscal
- ✅ **Auditoría completa** cambios de configuración

---

**🎯 RESULTADO ESPERADO:** Sistema de templates fiscales completamente funcional (100% implementado), parametrizado y extensible, que soporte todos los tipos de impuestos mexicanos sin código hardcodeado.

---

*📖 Reporte técnico para refactoring ERPNext v15 + Facturación México v5.0*
*🤖 Generated with [Claude Code](https://claude.ai/code)*