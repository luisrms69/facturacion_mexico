# ADR 0040 — Aprendizaje por historial en la clasificación de conceptos CFDI Recibido

**Estado:** Aceptado
**Fecha:** 2026-09-07

## Contexto

Al clasificar conceptos de un CFDI Recibido, el motor de resolución
(`item_resolution_engine.get_resolution_options`) proponía un `item_code` combinando reglas
configuradas (`Regla Item CFDI Recibido`), coincidencia por `no_identificacion`, match textual y
un genérico `GASTO-*`. La única memoria del trabajo humano previo era la **materialización de
reglas**: al asignar un Item manualmente, `assign_item_to_concepto` creaba una `Regla Item CFDI
Recibido` con `match_reason = "Auto: …"`.

Una auditoría retrospectiva sobre datos reales mostró que ese mecanismo cubría poco: dependía de
que existiera `no_identificacion` y generaba reglas frágiles. La mayor parte del trabajo humano
—cientos de conceptos ya clasificados por proveedor + clave SAT— **no se reutilizaba**. El
resultado: un concepto que un humano ya había resuelto muchas veces volvía a aparecer como
pendiente para el mismo proveedor.

El principio que guió el rediseño: *el sistema debe aprender del trabajo humano realizado
anteriormente, pero no debe autoasignar un Item con evidencia débil.*

## Decisión

Se agrega una fuente de resolución **por historial** (`_resolve_by_history`) y se reordena la
precedencia del motor:

1. Regla **manual** (`Regla Item CFDI Recibido` cuyo `match_reason` **no** empieza con `Auto:`).
2. Determinista: `Item.item_code == no_identificacion`.
3. **Historial** — clave `(company, supplier_rfc, sat_product_key)`.
4. Regla **`Auto:`** legacy (degradada por debajo del historial).
5. Match textual.
6. Genérico `GASTO-*`.

La memoria del sistema pasa a ser el **propio historial de conceptos ya clasificados**, no reglas
materializadas. En consecuencia:

- `assign_item_to_concepto` **deja de crear** reglas `Auto:` (el helper `_auto_create_regla` se
  conserva sin llamador, como referencia legacy).
- Confirmar una sugerencia histórica es una **decisión humana**: se persiste como `item_resolution
  = "Manual"` (no `"Historial"`), de modo que alimente el aprendizaje y no cuente como
  autoasignación.

### Gate de autoasignación

`_resolve_by_history` cuenta, por clave, cuántas veces cada Item **válido** (filtrado con
`validate_expense_item` **antes** de contar) fue asignado por humanos. Ranking determinista
(`count` desc, `item_code` asc). Solo el Item **top** puede autoasignarse, y solo si:

- `count ≥ 2` (`HIST_MIN_PREV`), y
- `share ≥ 0.80` (`HIST_MIN_SHARE`).

Umbrales calibrados con la auditoría real: con este gate la precisión de autoasignación fue
≈ 0.94 y la cobertura automática ≈ 0.56. Si no se alcanza el gate, el historial se ofrece como
**sugerencia** (alternativa), nunca se autoasigna: el concepto queda pendiente de decisión humana.

`classify_all_concepts` solo autoasigna en batch cuando el `primary` es `Código proveedor` o un
historial `auto_assignable`; el resto queda pendiente sin escribir sugerencias.

### Anti-refuerzo (evitar bucle de realimentación)

La consulta de historial **excluye** los conceptos cuyo `item_resolution = "Historial"` (las
propias autoasignaciones) y los CFDIs con `no_procesar = 1`. Así el algoritmo solo aprende de
clasificaciones **humanas** (`Manual`, `Mapeado`, `Código proveedor`, …) y no se auto-confirma.
Se excluye también el propio concepto en evaluación (anti-autocontaminación). No hay corte por
fecha en producción: se usa todo el trabajo humano disponible.

### Scope y trazabilidad

- La clave incluye `company` → un sitio multi-empresa no cruza aprendizaje entre empresas.
- Se agrega el valor `Historial` a las opciones de `item_resolution` (DocType `CFDI Recibido
  Concepto`) para trazar el origen de una autoasignación; el detalle (frecuencia/share) queda en
  `item_match_reason`.
- `auto_assignable` describe la capacidad operativa en el resultado **final**: si una fuente de
  mayor precedencia ocupó el `primary`, el historial queda como alternativa **sin**
  `auto_assignable`, aunque hubiera pasado el gate.

## Consecuencias

- Conceptos repetidos por proveedor + clave SAT dejan de reaparecer como pendientes una vez que
  hay ≥ 2 clasificaciones humanas concordantes.
- El aprendizaje es transparente y auditable (valor `Historial` + `item_match_reason`), sin poblar
  la tabla de reglas con entradas `Auto:` frágiles.
- Riesgo controlado: el gate exige evidencia (≥ 2 previos, ≥ 80 % de acuerdo) y la exclusión
  anti-refuerzo impide que una autoasignación errónea se consolide sola.

## Alternativa descartada

**Seguir materializando reglas `Auto:`** al asignar manualmente. Se descartó porque dependía de
`no_identificacion`, cubría una fracción menor de los casos y producía reglas difíciles de auditar.
Las reglas `Auto:` existentes se conservan como fuente degradada (paso 4), pero ya no se crean
nuevas. La limpieza de las reglas `Auto:` legacy, de `CFDI Concepto Mapping` y de `item_resolver`
queda fuera de alcance de esta decisión (issue de cleanup separado).
