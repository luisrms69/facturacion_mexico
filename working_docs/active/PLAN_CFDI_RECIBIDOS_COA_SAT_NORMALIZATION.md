# Plan técnico — Normalización CoA hacia Código Agrupador SAT
## Prerequisito para asignación contable automática en CFDI Recibidos

**Fecha:** 2026-06-02
**Módulo:** CFDI Recibidos — `facturacion_mexico`
**Estado:** BORRADOR v2 — pendiente de revisión y decisiones
**Stack:** Frappe / ERPNext v16

---

## 1. Contexto y objetivo

El módulo de CFDI Recibidos genera Purchase Invoice Drafts. El flujo ya completo incluye:
carga de XML, resolución de proveedor, clasificación de conceptos, asignación de Department,
Cost Center y Project, resolución de impuestos.

La pieza pendiente es la cuenta de gasto (`expense_account`) por línea del PI Draft.

**Hoy:** llega de `item_defaults` del Item. Funcional, pero no cumple el objetivo contable.

**Objetivo:** la cuenta debe reflejar tres dimensiones combinadas:
1. La **función del gasto** dentro de la empresa → determinada por Department.
2. La **naturaleza SAT del gasto** → determinada por la categoría/concepto clasificado.
3. La **cuenta real del Chart of Accounts** → determinada por la empresa.

Esto se concreta en el modelo:

```
Department → familia SAT (601/602/603/604)
Categoría de gasto → sufijo SAT (.48, .50, .55, ...)
Combinación → código agrupador SAT completo (ej: 603.48)
Account.account_number = código agrupador SAT → expense_account
```

---

## 2. Decisiones arquitectónicas ya tomadas

| Decisión | Detalle |
|---|---|
| CoA alineado al SAT | `account_number` en formato `NNN.NN` para cuentas 601–604 |
| Sin tabla paralela SAT → Account | No ocultar CoA mal configurado con mappings libres |
| Sin campo custom en Account | `account_number` nativo es suficiente |
| Sin scripts masivos en CoA | Toda modificación: cuenta por cuenta, validada |
| Sin modificación de GL Entry | GL no se toca en este plan |
| Sin merge masivo | Merge solo como excepción extrema y documentada |
| Sin fallback silencioso | Si no existe la cuenta SAT, el sistema no asigna en silencio |
| Lógica automática bloqueada | No se implementa hasta tener CoA validado y pruebas con CFDI reales |

---

## 3. Fase cero — Validar el Código Agrupador SAT vigente

**Antes de cualquier acción en el CoA**, se debe establecer la fuente de verdad del catálogo.

### 3.1 Verificar catálogo vigente

El SAT publica el Código Agrupador de Cuentas como parte del Anexo 24 de la
Resolución Miscelánea Fiscal vigente. El catálogo puede cambiar entre ejercicios fiscales.

Verificar:
- Año fiscal objetivo (ej: 2024, 2025)
- Versión vigente del Anexo 24 / Código Agrupador

### 3.2 Construir matriz de familias y sufijos válidos

Las familias 601, 602, 603 y 604 comparten la mayoría de sufijos pero NO son idénticas.
Existen diferencias en los sufijos de cierre:

- `601.84` = Otros gastos generales
- `602.84` = Otros gastos de venta
- `603.82` = Otros gastos de administración
- `604.XX` = subcódigos propios de fabricación

**No asumir que `NNN.48` existe para todas las familias sin verificarlo.**

Entregable de esta fase: tabla `familia × sufijo → código completo` verificada contra el
catálogo SAT oficial. Solo los códigos de esta tabla pueden usarse para resolver cuentas.

### 3.3 Mapear Item Groups actuales contra sufijos SAT válidos

Los 84+ Item Groups de gastos del módulo deben mapearse contra los sufijos del catálogo.
Esta validación puede revelar:
- Item Groups sin sufijo SAT directo (requieren decisión)
- Item Groups ambiguos que mezclan varios sufijos
- Sufijos del catálogo sin Item Group correspondiente

---

## 4. Diagnóstico del CoA actual

**Herramientas preferidas:** Report nativo de Frappe, `bench execute` (solo lectura),
exportación desde ERPNext GUI.
SQL es referencia técnica interna — no el camino operativo recomendado para clientes.

### 4.1 Exportar cuentas de gasto actuales

Desde **Contabilidad → Chart of Accounts** filtrar por `root_type = Expense` y exportar a CSV.

O via `bench execute` (solo lectura, autorizado):
```python
frappe.get_all('Account',
    filters={'company': 'MI_EMPRESA', 'root_type': 'Expense'},
    fields=['name','account_number','account_name','is_group','parent_account','disabled'],
    order_by='account_number, account_name'
)
```

### 4.2 Identificar volumen de transacciones por cuenta

Para cada cuenta de gasto hoja (is_group=0), contar asientos activos.

Clasificación sugerida:

| Rango | Clasificación |
|---|---|
| 0 | Sin transacciones |
| 1–20 | Transacciones mínimas |
| 21–200 | Transacciones moderadas |
| > 200 | Histórico significativo |

### 4.3 Detectar formato del account_number actual

| Patrón detectado | Ejemplo | Estado para SAT |
|---|---|---|
| `NNN.NN` | `603.48` | Compatible — verificar que sea el código correcto |
| `NNN-NN` | `603-48` | Normalizable por formato |
| `NNNNN` | `60348` | Normalizable si longitud = 5 |
| `NNN.N` o `NNN.NNN` | `603.480` | Requiere revisión |
| Estructura interna | `6030-048-001` | Requiere revisión contable |
| Texto libre | `GASTO-COMB` | No normalizable automáticamente |
| Vacío / NULL | — | Requiere asignación |

### 4.4 Detectar cuentas ligadas a configuraciones sensibles

Antes de cualquier cambio, identificar si la cuenta está referenciada en:
- **Company defaults** (cuentas por pagar/cobrar por defecto)
- **Warehouse** (valuation/adjustment accounts)
- **Item defaults** (expense_account por item)
- **Tax templates** (Purchase Taxes and Charges)
- **Supplier defaults**
- **Bank accounts**
- **Payroll settings**
- **Opening entry** (asientos de apertura)

Estas cuentas requieren análisis separado antes de cualquier cambio, aunque tengan pocas
transacciones.

---

## 5. Matriz situacional de decisión por cuenta

Cada cuenta de gasto se evalúa individualmente. La decisión depende de:

1. ¿Tiene transacciones? ¿Cuántas?
2. ¿Representa correctamente un código SAT específico?
3. ¿Está mezclada con conceptos de diferentes sufijos SAT?
4. ¿Está ligada a configuraciones ERPNext sensibles?
5. ¿Afecta impuestos, bancos, nómina, almacenes, cuentas críticas?
6. ¿El beneficio de normalizar el histórico justifica el riesgo?

### 5.1 Árbol de decisión

```
¿La cuenta es de gastos 601–604 y hoja (is_group=0)?
  └── No → Fuera del alcance de este plan

¿Está ligada a configuraciones sensibles (impuestos, nómina, banco, etc.)?
  └── Sí → DIFERIR a análisis separado. No tocar en este plan.

¿Tiene 0 transacciones?
  └── Sí → Opciones disponibles: conservar, cambiar número, cambiar nombre,
            cambiar nombre+número, sustituir por cuenta nueva.
            Siempre validado por contador.

¿Representa claramente un único código SAT?
  └── No (ambigua/mezclada) →
      ¿Transacciones < 21? → Crear cuentas SAT nuevas. Decidir histórico caso por caso.
      ¿Transacciones > 20? → Dejar cuenta actual en histórico. Crear cuenta SAT nueva
                              hacia futuro. Definir fecha de corte.

¿Tiene entre 1 y 20 transacciones?
  └── Evaluar piloto controlado. Ver sección 5.2.

¿Tiene entre 21 y 200 transacciones?
  └── Cambios muy selectivos. Ver sección 5.2.

¿Tiene más de 200 transacciones?
  └── No migrar en flujo normal. Ver sección 6.3.
```

### 5.2 Acciones posibles y criterios

#### Conservar (ningún cambio)

- Cuándo: `account_number` ya es `NNN.NN` correcto y el nombre es razonable.
- Resultado: la cuenta ya es compatible con la resolución automática.
- Riesgo: bajo — debe validarse que el código SAT realmente corresponda al uso
  contable actual de la cuenta, no solo que el formato sea correcto.

#### Cambiar solo `account_number`

- Cuándo: la cuenta representa correctamente el concepto SAT pero el número tiene
  formato diferente (`603-48`, `60348`, etc.) o está vacío.
- Nota: `account_number` es metadata — NO debería afectar GL ni saldos.
  Sin embargo, PUEDE afectar: reportes configurados por número, exportaciones contables,
  conciliaciones externas, integraciones con sistemas fiscales.
  Por eso debe validarse con contador antes.
- Requiere: que el número SAT objetivo no exista ya en otra cuenta de la misma empresa.
- Riesgo: bajo, pero no nulo. Validar Trial Balance antes/después.
- Para cuentas con muchas transacciones (> 20): aplicar SOLO si se cumplen todas las
  condiciones siguientes:
  - El concepto contable de la cuenta es claro y no ambiguo.
  - No existen integraciones o reportes externos dependientes del número actual.
  - El contador valida explícitamente el cambio.
  - Se compara Trial Balance antes/después para confirmar que nada contable cambió.

#### Cambiar solo nombre

- Cuándo: `account_number` ya es correcto pero el nombre no coincide con descripción SAT.
- Ejemplo: `603.48 Gasolina` → `603.48 Combustibles y lubricantes`.
- Riesgo: bajo. Validar que no rompa criterios operativos o reportes por nombre.
- Aplica a: cualquier volumen de transacciones.

#### Cambiar nombre + número

- Cuándo: principalmente en cuentas sin transacciones o con 1–20 transacciones.
- Si hay más de 20 transacciones, evaluar si basta cambiar solo número.

#### Crear cuenta nueva

- Cuándo: la cuenta actual es ambigua, mezcla conceptos o no puede normalizarse.
- Ejemplo: `Gastos varios 603` con gasolina, papelería, internet y honorarios mezclados.
  No conviene asignar esa cuenta a `603.48`.
  Mejor crear cuentas SAT limpias para operación futura.
- El histórico queda en la cuenta vieja.
- La nueva cuenta se usa para CFDI Recibidos desde la fecha de activación.
- Riesgo: bajo si no se toca la cuenta vieja.

#### Dejar histórico y usar cuenta nueva hacia futuro

- Cuándo: cuenta con muchas transacciones (> 20) donde el concepto es correcto pero
  la normalización del histórico tiene riesgo alto o no justifica el costo.
- Proceso:
  1. Crear cuenta nueva con `account_number = código SAT`.
  2. Definir fecha de corte.
  3. A partir de esa fecha, todos los CFDI Recibidos usan la cuenta nueva.
  4. El histórico permanece en la cuenta vieja intacto.
- La cuenta vieja puede cerrarse gradualmente en el siguiente período fiscal.
- Riesgo: bajo para la operación nueva. El histórico no se toca.

#### Merge de cuentas (excepción extrema)

- Cuándo: SOLO si la cuenta vieja y la nueva representan exactamente el mismo concepto
  y hay un motivo contable claro para unificar el histórico.
- Proceso: ver sección 7.
- Nunca como flujo normal. Nunca masivo. Nunca para limpiar ambigüedades.
- Riesgo: ALTO — modifica GL Entry. Requiere proceso formal.

#### Diferir a proyecto formal de migración

- Cuándo: cuenta crítica, con más de 200 transacciones, o con complejidad que supera
  el alcance de esta normalización.
- La cuenta se documenta como pendiente en la matriz de equivalencias.
- CFDI Recibidos usará cuenta manual o fallback explícito para ese código SAT.

---

## 6. Estrategia por tipo de cliente

### 6.1 Cliente nuevo (sin histórico contable)

- Riesgo: bajo — siempre que el CoA sea validado por contador antes de operar.
  Cliente nuevo no significa sin riesgo: un CoA mal construido desde el inicio genera
  problemas que se arrastran por años.
- Acción: implementar CoA desde cero con estructura SAT 601–604.
- Proceso:
  1. Validar catálogo SAT vigente (Fase 0).
  2. Diseñar árbol de cuentas 601–604 completo o parcial según giro.
  3. Revisión y aprobación por contador antes de cargar.
  4. Cargar CoA via CoA importer o creación manual.
  5. Activar CFDI Recibidos con resolución automática desde el inicio.
- Esfuerzo: medio (diseño del CoA).
- Prerequisito de activación: CoA aprobado por contador, pruebas con CFDI sintéticos.

### 6.2 Cliente con poco movimiento (< 6 meses operando, < 200 asientos totales)

- Riesgo: bajo-medio.
- Acción: normalizar `account_number` y crear cuentas faltantes. Histórico manejable.
- Proceso:
  1. Diagnóstico completo del CoA.
  2. Trial Balance exportado como punto de control.
  3. Clasificar cada cuenta según matriz situacional.
  4. Ejecutar cambios cuenta por cuenta, priorizando sin transacciones.
  5. Para cuentas con 1–20 transacciones: cambiar `account_number` si el concepto es claro.
  6. Trial Balance después: debe ser idéntico.
  7. Prueba con CFDI Recibidos reales o sintéticos.
  8. Activar resolución automática una vez validado.
- Esfuerzo: medio.
- Prerequisito: aprobación contable de cada cambio.

### 6.3 Cliente con histórico grande (> 6 meses, muchos asientos)

- Riesgo: medio-alto. Gestión por lotes pequeños.
- Acción: normalización gradual. Fecha de corte para operación nueva.
- Proceso:
  1. Diagnóstico completo del CoA.
  2. Congelar análisis del período anterior (no tocar).
  3. Operar CFDI Recibidos en modo manual/asistido mientras se normaliza: si falta
     cuenta SAT, mostrar advertencia visible y requerir asignación manual o configuración
     previa. Nunca asignar silenciosamente item_defaults ni otra cuenta alternativa.
  4. Priorizar cuentas sin transacciones y cuentas con pocas transacciones.
  5. Para cuentas con > 200 transacciones: crear cuenta nueva SAT, definir fecha de corte.
     El histórico permanece. Solo la operación futura usa la cuenta nueva.
  6. Avanzar por lotes de 5–10 cuentas máximo.
  7. Validar Trial Balance por lote.
  8. Activar resolución automática por código SAT a medida que las cuentas estén listas,
     no esperar a tener el 100%.
- Esfuerzo: alto.
- Prerequisito: plan aprobado por contador antes de iniciar.

---

## 7. Proceso de merge excepcional

Solo si hay motivo contable documentado y el contador lo autoriza.

### 7.1 Prerrequisitos obligatorios

- [ ] Backup completo verificado (restauración probada)
- [ ] GL Entry de ambas cuentas exportado y guardado
- [ ] Trial Balance antes exportado y guardado
- [ ] Estado de Resultados antes exportado y guardado
- [ ] Balance General antes exportado y guardado
- [ ] Autorización escrita del contador
- [ ] Prueba piloto exitosa con una cuenta de volumen mínimo

### 7.2 Criterios para NO usar merge

- La cuenta vieja mezcla conceptos distintos
- La cuenta nueva es distinta conceptualmente
- El merge se propone para "limpiar" la estructura (eso no justifica merge)
- Hay integración externa que referencia la cuenta vieja por nombre
- La cuenta afecta bancos, nómina, inventario, impuestos o defaults ERPNext
- No existe autorización formal del contador

### 7.3 Proceso (si se aprueba)

1. Crear cuenta nueva con estructura correcta (parent, root_type, is_group=0)
2. Verificar que la nueva cuenta no tiene transacciones
3. En ERPNext: Account → "Merge with" → cuenta destino
4. Verificar Trial Balance después: debe ser igual al anterior en totales
5. Verificar que reportes clave no muestran diferencias inesperadas
6. Documentar en bitácora del proyecto

---

## 8. Validaciones obligatorias

Para cualquier cambio en el CoA, independientemente de su magnitud:

| Validación | Cuándo | Responsable |
|---|---|---|
| Backup completo | Antes de cualquier cambio | Administrador técnico / implementador |
| GL Entry exportado de cuentas afectadas | Antes de cambios | Administrador técnico / implementador |
| Trial Balance antes | Antes de cada lote | Contador |
| Trial Balance después | Después de cada lote | Contador |
| Estado de Resultados antes/después | Para lotes con cuentas con movimiento | Contador |
| Balance General antes/después | Para cambios de estructura (parent, grupos) | Contador |
| Revisión de reportes clave | Después de normalización por lote | Usuario/Contador |
| Prueba con CFDI Recibidos | Antes de activar resolución automática | Equipo técnico |
| Aprobación final del contador | Antes de activar en producción | Contador |

**Regla:** ningún cambio se considera "completado" hasta que el contador valide los
reportes clave. El equipo técnico no es el responsable de validación contable.

---

## 9. Impacto futuro en CFDI Recibidos

### 9.1 Fuentes de datos para resolver `expense_account`

**Fuente 1 — familia SAT del Department:**
```
CFDI Recibido.department
  → Mapeo Departamento CFDI Recibido.familia_sat
  → extraer número: "603 Gastos de administración" → "603"
```
Esta fuente ya existe en `Configuracion CFDI Recibidos`.

**Fuente 2 — sufijo SAT de la categoría del gasto:**
```
Concepto.item_code
  → Item.item_group
  → Item Group.codigo_sufijo_sat  ← campo pendiente de implementar (MVP)
  → ej: ".48"
```

**Diseño del MVP:** `Item Group.codigo_sufijo_sat` es la fuente principal del sufijo.
Es suficiente para el caso general donde la categoría de gasto determina unívocamente
el tipo de gasto SAT.

**Extensión futura reservada:** el diseño debe anticipar que en casos de mayor
precisión contable, el sufijo puede necesitar un override por proveedor específico,
por concepto de CFDI, o por combinación proveedor+categoría. Esa capa de override
no se implementa en esta fase, pero la arquitectura no debe cerrar esa posibilidad.
Por ejemplo: un proveedor puede emitir en la misma categoría conceptos que corresponden
a sufijos distintos (ej: servicio de mantenimiento que puede ser `.56` o `.64` según
el tipo específico).

**Las cuatro identidades que el sistema debe mantener separadas:**

```
1. Código Agrupador SAT   →  603.48
   (clasificación fiscal oficial — catálogo SAT Anexo 24)

2. Código normalizado      →  familia=603, sufijo=48
   (descomposición interna para lógica del builder)

3. Número operativo ERPNext → 603-48-000 / 603.48 / 60348000 / 6000-300-048
   (account_number de la empresa — depende de su CoA)

4. Account real ERPNext    →  Account.name
   (cuenta hoja activa usada en GL)
```

**Regla clave:** `account_number` es el número operativo de la empresa.
No debe ser forzado al formato SAT (`603.48`). El punto de `603.48` pertenece al
catálogo del SAT, no a la numeración interna de ninguna empresa.

**Sí exigir:** que toda cuenta resuelta automáticamente por CFDI Recibidos pueda
demostrar compatibilidad con un Código Agrupador SAT válido.

---

### Estrategias de resolución de cuenta (`modo_resolucion_cuenta_gasto`)

No todas las empresas pueden resolverse con el mismo mecanismo. La estrategia se
configura por empresa en `Configuracion CFDI Recibidos`.

#### Estrategia 1: `patron`

Para clientes nuevos o con CoA diseñado de forma derivable desde el catálogo SAT.

El builder construye el `account_number` usando una plantilla:

```
formato_cuenta_gasto: "{f}-{s}-000"  →  603-48-000
                      "{f}.{s}"      →  603.48   (si la empresa eligió SAT literal)
                      "{f}{s}000"    →  60348000
                      "6-{f}-{s}-0"  →  6-603-48-0
```

Proceso:
1. Calcular código SAT: `familia=603`, `sufijo=48`
2. Construir `account_number` con patrón: `603-48-000`
3. Buscar cuenta hoja activa en ERPNext
4. Si no existe → error auditable:
   ```
   No se encontró cuenta hoja para SAT 603.48.
   Formato configurado: {f}-{s}-000
   Cuenta esperada: 603-48-000
   ```

Recomendación para clientes nuevos: `{f}-{s}-000` — compatible con CONTPAQi,
preserva espacio de subcuentas, no confunde identidades.

#### Estrategia 2: `matriz_equivalencias`

Para clientes con CoA histórico cuya numeración interna no puede derivarse por patrón
simple, pero existe una correspondencia auditable con el catálogo SAT.

Importante — distinción necesaria:

| Tipo | Descripción | ¿Aceptable? |
|---|---|---|
| Tabla libre `SAT → Account` | Para esconder un CoA mal configurado | ❌ Rechazado |
| Matriz auditada validada | Cada equivalencia aprobada por contador, ligada a código SAT válido | ✅ Aceptable |

La matriz auditada es una child table en `Configuracion CFDI Recibidos`:

```
codigo_agrupador_sat  |  account
603.48                |  6000-300-048 - Combustibles - ACE
603.50                |  6000-300-050 - Teléfono - ACE
```

Condiciones para usar esta estrategia:
- Cada fila requiere validación y firma del contador
- Solo se aceptan códigos SAT que existen en el catálogo vigente
- No es una "tabla de escape" — la cuenta listada debe representar correctamente el concepto SAT

#### Estrategia 3: `manual_asistido`

Para empresas cuyo CoA aún no está normalizado o en proceso de migración.

- El builder NO resuelve `expense_account` automáticamente.
- Si falta cuenta compatible, muestra advertencia visible y requiere asignación manual.
- Nunca asigna silenciosamente `item_defaults` ni otra cuenta alternativa.
- Útil como estado temporal mientras se normaliza el CoA.

---

**Campos nuevos en `Configuracion CFDI Recibidos`:**

```
modo_resolucion_cuenta_gasto
  fieldtype: Select
  options:   patron | matriz_equivalencias | manual_asistido
  default:   manual_asistido
  label:     Modo de resolución de cuenta de gasto

formato_cuenta_gasto
  fieldtype: Data
  default:   {f}-{s}-000
  label:     Formato de cuenta (aplica solo en modo patrón)
  description: {f}=familia(ej:603), {s}=sufijo sin punto(ej:48)
  depends_on: modo_resolucion_cuenta_gasto = patron

[child table nueva: Matriz de Equivalencias SAT]
  aplica solo en modo: matriz_equivalencias
  campos: codigo_agrupador_sat (Data, reqd), account (Link→Account, reqd)
  requiere: validado_por_contador (Check)
```

### 9.2 Comportamiento cuando no existe la cuenta SAT

**No usar fallback silencioso.** El fallback silencioso a `item_defaults` reproduce
exactamente el problema que este plan busca resolver.

**Comportamiento a definir (decisión técnica pendiente de validación):**

Si no existe `Account.account_number = "603.48"` para la empresa, hay dos opciones:

**Opción preferida** (si ERPNext permite PI Draft sin `expense_account` por línea):
- El PI Draft se genera sin `expense_account` en esa línea.
- Se registra una advertencia visible en el CFDI Recibido indicando exactamente
  qué código SAT no se encontró: `"No se encontró cuenta para 603.48"`
- El usuario completa manualmente o configura la cuenta antes del submit del PI.
- Requiere validar que ERPNext permite guardar PI Draft con líneas sin `expense_account`.

**Opción alternativa** (si ERPNext no lo permite, o por decisión de control):
- Se bloquea la generación automática del PI.
- El CFDI Recibido queda en estado "Pendiente de cuenta contable".
- El usuario debe configurar la cuenta o asignarla manualmente antes de reintentarlo.

En ambos casos: nunca asignar silenciosamente una cuenta incorrecta.
La opción aplicable depende de la validación técnica con ERPNext y de la decisión del
equipo sobre el nivel de control deseado.

### 9.3 Prerequisitos para activar la resolución automática

La lógica de `expense_account` automática NO debe activarse hasta que se cumplan TODOS:

- [ ] Catálogo SAT vigente validado (Fase 0 completa)
- [ ] Diagnóstico del CoA completado para la empresa
- [ ] Estrategia de resolución elegida y configurada (`modo_resolucion_cuenta_gasto`)
- [ ] Las cuentas asociadas a los códigos SAT `.48`, `.50`, `.55` están resueltas
      mediante la estrategia configurada: patrón construye cuenta existente, o
      están listadas en la matriz de equivalencias validada por contador
- [ ] `Mapeo Departamento CFDI Recibido` tiene `familia_sat` configurado para
      todos los departamentos activos
- [ ] `Item Group.codigo_sufijo_sat` configurado para las categorías de CFDI Recibidos
- [ ] Al menos 5 CFDI Recibidos de prueba (reales o sintéticos) generaron PI con
      `expense_account` correcto y auditable contra el catálogo SAT
- [ ] Trial Balance no muestra diferencias después de cualquier normalización de CoA
- [ ] Aprobación explícita del contador

---

## 9.4 Compatibilidad futura con contabilidad electrónica

**Este plan NO implementa contabilidad electrónica.**

Sin embargo, las decisiones de normalización deben dejar la arquitectura preparada
para generarla en el futuro, si el cliente o la regulación lo requieren.

Para eso, las identidades que este plan mantiene separadas son exactamente las que
la contabilidad electrónica necesita:

```
Account ERPNext (account_number operativo)
  └── asociable en el futuro a Código Agrupador SAT
  └── asociable en el futuro a naturaleza/descripción SAT
  └── asociable en el futuro a integrador/formato de exportación XML
```

**Regla de diseño:** ninguna decisión de este plan debe cerrar la posibilidad de
generar en el futuro un mapeo formal:

```
Account → Código Agrupador SAT → XML contabilidad electrónica
```

Lo que NO se implementa ahora:
- Campo `codigo_agrupador_sat` en Account
- Exportación XML de contabilidad electrónica
- Catálogo de naturalezas SAT vinculado a cuentas

Lo que SÍ queda compatible:
- Toda cuenta resuelta automáticamente tiene un Código Agrupador SAT trazable
- La estrategia `matriz_equivalencias` documenta explícitamente esa relación
- La estrategia `patron` la hace derivable de forma consistente

---

## 10. Entregables del plan

### 10.1 Reporte de diagnóstico del CoA (por empresa)

Columnas mínimas:
- `account_name`
- `account_number_actual`
- `formato_detectado` (SAT exacto / normalizable / requiere revisión / vacío)
- `transacciones_count`
- `ligada_a_configuracion` (sí/no + detalle)
- `codigo_sat_objetivo` (propuesto)
- `clasificacion` (conservar / cambiar número / crear nueva / diferir / etc.)
- `accion_propuesta`
- `validado_por_contador` (pendiente / aprobado / rechazado)

### 10.2 Matriz de equivalencias

Tabla por empresa: cuenta_actual → código_SAT_objetivo → clasificación → acción → estado.

### 10.3 Matriz de sufijos SAT por Item Group

Tabla: Item Group → sufijo SAT → código agrupador para cada familia (601/602/603/604).
Debe incluir cuáles combinaciones son inválidas en el catálogo SAT.

### 10.4 Checklist de activación por empresa

```
Fase 0:
  [ ] Catálogo SAT vigente verificado
  [ ] Matriz de familias × sufijos construida

Diagnóstico:
  [ ] Reporte de CoA generado
  [ ] Cuentas con transacciones identificadas
  [ ] Cuentas ligadas a configuraciones detectadas

Normalización:
  [ ] Cuentas sin transacciones normalizadas
  [ ] Cuentas con 1-20 transacciones evaluadas
  [ ] Cuentas > 20 transacciones: plan de corte definido
  [ ] Trial Balance validado por lote

Configuración del módulo:
  [ ] familia_sat configurado en Mapeo Departamento
  [ ] codigo_sufijo_sat configurado en Item Groups relevantes
  [ ] modo_resolucion_cuenta_gasto seleccionado para la empresa
  [ ] Si modo=patron: formato_cuenta_gasto configurado y verificado
  [ ] Si modo=matriz_equivalencias: matriz validada y firmada por contador
  [ ] Si modo=manual_asistido: flujo de advertencia visible configurado

Pruebas:
  [ ] 5+ CFDI Recibidos de prueba generados
  [ ] expense_account correcta en cada línea del PI
  [ ] Advertencias funcionan cuando falta cuenta SAT
  [ ] Sin asignación silenciosa a cuenta incorrecta

Aprobación:
  [ ] Contador aprueba CoA normalizado
  [ ] Contador aprueba resultados de prueba
  [ ] Activación autorizada para producción
```

### 10.5 Plan de piloto

1. Seleccionar empresa de prueba con CoA aún sin transacciones (o muy pocas).
2. Normalizar 3–5 cuentas de un sufijo (.48 o .50).
3. Configurar familia_sat en un departamento.
4. Configurar codigo_sufijo_sat en el Item Group correspondiente.
5. Cargar un CFDI Recibido real o sintético con ese concepto.
6. Verificar que el PI Draft tiene la expense_account correcta.
7. Documentar resultado antes de continuar.

### 10.6 Criterios de aceptación

- Trial Balance después de normalización = Trial Balance antes (mismos totales)
- PI Draft generado con `expense_account` correcta y trazable al Código Agrupador SAT
  en al menos 3 escenarios distintos (diferentes departamentos y categorías)
- Las cuentas asociadas a códigos SAT `.48`, `.50`, `.55` están resueltas
  mediante la estrategia configurada (patrón, matriz o manual)
- Sistema muestra advertencia clara y auditable cuando falta la cuenta
- Sin asignaciones silenciosas a cuentas incorrectas ni a `item_defaults`
- No hay duplicados de `account_number` en la misma empresa
- Toda cuenta resuelta automáticamente tiene trazabilidad hacia un Código Agrupador SAT válido
- Aprobación documentada del contador

### 10.7 Rollback y contingencia

| Operación | Rollback disponible | Proceso |
|---|---|---|
| Cambiar `account_number` | Sí | Revertir valor anterior manualmente |
| Cambiar nombre de cuenta | Sí | Revertir nombre anterior |
| Crear cuenta nueva sin asientos | Sí | Eliminar la cuenta nueva |
| Dejar histórico y usar nueva | Sí | La cuenta vieja sigue existiendo intacta |
| Merge de cuentas | ⚠️ NO automático | Restaurar backup completo |
| Cualquier error en lote | Sí si hay backup | Restaurar backup, reconstruir desde Trial Balance |

---

## 11. Decisiones pendientes antes de implementar

| Decisión | Estado | Detalle |
|---|---|---|
| **account_number ≠ Código Agrupador SAT** | ✅ Decidido | `account_number` es número operativo de la empresa. El formato SAT (`603.48`) pertenece al catálogo fiscal, no a la numeración interna. |
| **Tres estrategias de resolución** | ✅ Decidido | `patron`, `matriz_equivalencias`, `manual_asistido`. Configuradas por empresa en `Configuracion CFDI Recibidos`. Ver sección 9.1. |
| **Distinción tabla libre vs. matriz auditada** | ✅ Decidido | Tabla libre para esconder CoA mal configurado: rechazada. Matriz auditada validada por contador: aceptable como estrategia `matriz_equivalencias`. |
| **Compatibilidad con contabilidad electrónica** | ✅ Decidido (alcance) | No se implementa ahora, pero el diseño no la cierra. Ver sección 9.4. |
| **Fuente del sufijo SAT** | Pendiente | MVP = `Item Group.codigo_sufijo_sat`. Override por proveedor/concepto reservado para fase futura. |
| **Comportamiento cuando falta cuenta** | Pendiente técnico | Opción preferida: PI Draft sin expense_account + advertencia. Alternativa: bloquear PI. Requiere validar si ERPNext lo permite. |
| **Campo `codigo_sufijo_sat` en Item Group** | Pendiente | Custom Field del app (fixture) vs. campo en JSON nativo ERPNext. |
| **Cobertura mínima de sufijos para activar** | Pendiente | ¿Cuántos sufijos/equivalencias mínimas para pasar de `manual_asistido` a `patron` o `matriz`? |
| **Manejo de conceptos sin Item Group** | Pendiente | ¿Qué hace el builder si el concepto no tiene `item_code` o `item_group`? |
| **Reporte de diagnóstico** | Pendiente | ¿Script Report Frappe o herramienta externa? |

---

## Notas importantes

Este plan es un documento vivo. Las decisiones tomadas durante la ejecución deben
actualizarse aquí antes de avanzar al siguiente paso.

Ninguna acción sobre el CoA debe ejecutarse sin:
1. El reporte de diagnóstico completado para esa empresa.
2. La aprobación del contador para las cuentas afectadas.
3. Un safe point (backup verificado) previo.

La lógica automática de `expense_account` en CFDI Recibidos se implementa como
último paso, no como primer paso.
