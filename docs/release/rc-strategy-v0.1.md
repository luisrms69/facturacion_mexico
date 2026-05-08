# Estrategia Release Candidates v0.1

## Objetivo

Cerrar el MVP de facturacion_mexico v0.1 con tres etapas controladas para reducir riesgo antes del primer sitio nuevo.

## RC0 — Estado funcional actual

Propósito:
Congelar el estado actual del MVP antes de cualquier limpieza.

Características:
- Incluye todo el trabajo funcional ya mergeado:
  - Complemento Pago MX MVP
  - PDF/XML de Complemento
  - FFM status migrado a status
  - Settings mínimos v0.1
- Mantiene patches canónicos actuales.
- No intenta limpiar fixtures/filter/schema.
- No intenta eliminar patches.
- Sirve como baseline funcional.

Uso:
- Validación funcional.
- Punto de comparación.
- Punto de retorno si la limpieza posterior introduce errores.

## RC1 — Limpieza controlada con patches

Propósito:
Corregir inconsistencias detectadas por auditoría sin retirar todavía los patches.

Alcance esperado:
- Corregir fixtures/filter/schema necesarios para instalación limpia futura.
- Agregar Branch-fm_certificate_ids si se confirma necesario.
- Alinear hooks.py fixture filter con custom_field.json.
- Revisar naming_series/property setters de DocTypes propios.
- Mantener patches canónicos.
- No eliminar patches todavía.

Criterio:
El sistema debe seguir funcionando igual que RC0.

## RC2 — Versión limpia sin patches

Propósito:
Eliminar dependencia de patches para instalaciones nuevas.

Alcance esperado:
- Remover patches innecesarios de patches.txt.
- Confirmar que nuevos sites nacen correctamente desde:
  - DocType JSON
  - fixtures
  - setup/after_install si aplica
- Probar instalación limpia desde cero.
- No depender de migraciones históricas.

Criterio:
Un site nuevo debe instalar facturacion_mexico sin requerir patches históricos.

## Reglas de trabajo

- No copiar todo lo que existe en BD al repo.
- Cada diferencia BD vs schema debe clasificarse:
  - necesario para MVP
  - legacy/migración histórica
  - basura de desarrollo
  - setup local
  - duda pendiente
- No modificar patches sin prueba limpia.
- No correr export-fixtures sin revisar diff.
- No usar git add .
- Tests con /test-guard.
- Commit/push/PR con /ship.

## Pendientes conocidos

- Issue #95 timezone usuario / System Settings.
- Limpieza futura de columna física fm_fiscal_status en FFM.
- Revisión completa de Settings después del MVP.
- Motivo 01/sustitución de Complemento Pago fuera de MVP.
- Addendas para v0.2.
