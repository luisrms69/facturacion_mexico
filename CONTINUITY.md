# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-31
**Rama activa:** `feature/addenda-la-comer`
**Tarea actual:** Addenda La Comer — soporte genérico committed, esperando spec del cliente

---

## Recuperación rápida

Estoy trabajando en:
Implementación de Addenda La Comer. El soporte genérico (`product_mapping` en contexto
Jinja) está committed. Falta spec del cliente para el template.

Plan que estoy siguiendo:
No hay working doc activo — trabajo directo en rama.

Objetivo inmediato:
Recibir XML de ejemplo + spec La Comer para implementar el template Jinja2.

Criterio de avance:
Template Jinja2 en Addenda Type "La Comer" renderiza XML válido con datos del cliente.

---

## Estado actual

### Ya cerrado
- PR #170: reestructuración documental (Fases 5–7)
- PR #172: Facturacion Mexico Company Settings — configuración multi-company

### En esta rama
- `product_mapping` en contexto Jinja de addendas — committed (`dc055cf`)

### Pendiente inmediato
1. Recibir del cliente: XML ejemplo, namespace, número de proveedor, spec Provecomer
2. Implementar template Jinja2 en Addenda Type "La Comer"
3. issue #165: is_submittable CFDI Recibido (fuera de alcance aquí)

### No repetir
- No hardcodear La Comer en código Python
- No crear campos custom para La Comer
- El template vive en Addenda Type DocType, no en código

---

## Información faltante (bloqueante para template)
- XML ejemplo aceptado por La Comer / Provecomer
- Namespace URI exacto
- Número de proveedor asignado por La Comer
- Si usan código interno, EAN/GTIN o código del proveedor por línea

---

## Archivos relevantes ahora
- `facturacion_mexico/addendas/generic_addenda_generator.py` — _prepare_template_context
- `facturacion_mexico/addendas/tests/test_addenda_generator_product_mapping.py`

---

## Riesgos / cuidados
- issue #165 (is_submittable) antes de poner CFDI Recibidos en producción
- Instalaciones existentes deben crear Company Settings y correr bench migrate
