# Facturación México - Documentación Técnica

![Docstring Coverage](badges/interrogate_badge.svg)

**Sistema integral de facturación electrónica para México con soporte multi-sucursal y addendas dinámicas**

## Características Principales

- ✅ **Timbrado CFDI 4.0** - Integración completa con PACs certificados
- ✅ **Multi-sucursal** - Gestión de múltiples branches con coordinación automática  
- ✅ **Addendas Dinámicas** - Generación automática según cliente/proveedor
- ✅ **Catalogos SAT** - Sincronización completa y actualizada
- ✅ **Production Ready** - 46 tests automatizados con 100% de éxito

## Inicio Rápido

### Instalación

```bash
# 1. Instalar la app
bench get-app facturacion_mexico
bench --site tu-sitio.local install-app facturacion_mexico

# 2. Configurar certificados
bench --site tu-sitio.local execute facturacion_mexico.setup.configure_certificates

# 3. Sincronizar catalogos SAT
bench --site tu-sitio.local execute facturacion_mexico.setup.sync_sat_catalogs
```

### Configuración Básica

```python
# Site Config
{
    "pac_provider": "finkok",
    "pac_username": "tu_usuario", 
    "pac_password": "tu_password",
    "multisucursal_enabled": 1,
    "addendas_auto_generation": 1
}
```

## Guías de Documentación

- **[Guía de Usuario](user-guide/index.md)** - Aprende a usar el sistema
- **[API Reference](api/index.md)** - Documentación técnica completa
- **[Desarrollo](development/index.md)** - Setup y contribuciones

## Métricas del Proyecto

| Métrica | Valor | Estado |
|---------|-------|--------|
| Tests Automatizados | 46/46 | ✅ 100% |
| Cobertura Docstrings | 90.1% | ✅ Excelente |
| Compatibilidad SAT | CFDI 4.0 | ✅ Actualizado |
| Production Ready | Sprint 6 | ✅ Alpha |

---

**Versión:** Sprint 6 Alpha - Production Ready  
**Framework:** Frappe v15  
**Última actualización:** 2025-07-25