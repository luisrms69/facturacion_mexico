# INVENTARIO PRE-LIMPIEZA TAX CATEGORIES SAT
**Fecha:** 2025-10-01 18:56
**Backup:** 20251001_185615-facturacion_dev-database.sql.gz
**Propósito:** Implementación propuesta ChatGPT limpieza régimen fiscal

## 📊 RESUMEN INVENTARIO

### Customers con fm_tax_regime: **3**
- A&B Tecnología Sustentable S.A. de C.V.: `601 - General de Ley Personas Morales`
- Concesionaria de Vias Troncales: `601 - General de Ley Personas Morales`
- CONCESIONARIA VUELA COMPAÑIA DE AVIACION: `601 - General de Ley Personas Morales`

### Tax Categories SAT a eliminar: **20**
```
626 - Régimen Simplificado de Confianza
625 - Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas
624 - Coordinados
623 - Opcional para Grupos de Sociedades
622 - Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras
621 - Incorporación Fiscal
620 - Sociedades Cooperativas de Producción que optan por diferir sus ingresos
616 - Sin obligaciones fiscales
615 - Régimen de los ingresos por obtención de premios
614 - Ingresos por intereses
612 - Personas Físicas con Actividades Empresariales y Profesionales
611 - Ingresos por Dividendos (socios y accionistas)
610 - Residentes en el Extranjero sin Establecimiento Permanente en México
609 - Consolidación
608 - Demás ingresos
607 - Régimen de Enajenación o Adquisición de Bienes
606 - Arrendamiento
605 - Sueldos y Salarios e Ingresos Asimilados a Salarios
603 - Personas Morales con Fines no Lucrativos
601 - General de Ley Personas Morales
```

### Tax Categories normales a conservar: **6**
```
Retenciones Honorarios
Exempt
Zero 0
General 16
_Test Tax Category 2
_Test Tax Category 1
```

### DocType Regimen Fiscal SAT: **20 registros**
- Disponible con fixture completo
- Ejemplos: 601, 612, 626

## 🎯 CRITERIOS ELIMINACIÓN

**Patrón Tax Categories SAT:** `^\d{3}\s-\s` (3 dígitos + espacio + guión + espacio)
**Estado:** Todas habilitadas actualmente
**Estrategia:** Desactivar primero → comprobar funcionalidad → eliminar definitivamente

## ✅ VERIFICACIÓN ESTADO

- ✅ Backup completado: `20251001_185615-facturacion_dev-database.sql.gz`
- ✅ Customers fm_tax_regime funcionando (3 registros)
- ✅ DocType Regimen Fiscal SAT disponible (20 registros)
- ✅ Tax Categories normales identificadas (6 conservar)
- ✅ Tax Categories SAT identificadas (20 eliminar)

**STATUS:** LISTO PARA FASE 1