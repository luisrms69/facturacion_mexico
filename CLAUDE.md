# 🤖 CLAUDE.md - FACTURACIÓN MÉXICO v5.0

**Proyecto:** Facturación México
**Framework:** Frappe v15
**Fecha:** 2025-09-16
**Sistema Control:** Claude Code + Sistema Buzola Integrado

**Última actualización:** 2025-09-17
**Versión compatible:** Frappe v15, Claude Code

---

## 🚨 **DOCUMENTACIÓN TÉCNICA PRIVADA**

### **¿Qué es buzola-internal?**
- **Repositorio privado:** https://github.com/luisrms69/buzola-development-internal
- **Ubicación local:** `/home/erpnext/frappe-bench/apps/buzola-internal`
- **Propósito:** Solo documentación técnica privada empresarial
- **Alcance:** Arquitectura, testing detallado, reportes técnicos

### **Separación Completa v5.1**
- ✅ **Control principal:** Este archivo CLAUDE.md (autocontained)
- ✅ **Documentación técnica:** `/buzola-internal/projects/facturacion_mexico/`
- ✅ **No scripts:** Sistema migrado a Claude Code nativo
- ✅ **No referencias cruzadas:** Proyectos completamente independientes
- ✅ **Navegación:** `buzola-internal/INDEX.md` para entrada principal

### **Principio Fundamental**
- **Autocontained:** Todo lo crítico en este CLAUDE.md
- **Buzola solo docs:** Documentación técnica privada únicamente
- **Zero dependencies:** No dependencias entre este proyecto y otros

---

## 🌍 **REGLAS GENERALES FRAPPE**

### **RG-001: IDIOMA ESPAÑOL OBLIGATORIO**
- ✅ **Labels DocTypes/campos** en español sin excepciones
- ✅ **Opciones Select/MultiSelect** en español
- ✅ **Mensajes validación/error** en español
- ✅ **Documentación usuario** en español
- ✅ **Docstrings/comentarios** en español
- ❌ **Variables código** en inglés (convención técnica)

### **RG-002: GIT WORKFLOW COMPLETO**
- ✅ **Formato commits:** `tipo(alcance): descripción en español`
- ✅ **Tipos:** feat, fix, docs, style, refactor, test, chore
- ✅ **Alcances específicos:** companies, tests, docs, config, api, ui, database, sync, validation
- ✅ **Footer obligatorio:**
  ```
  🤖 Generated with [Claude Code](https://claude.ai/code)

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```
- ❌ **PROHIBIDO:** `git commit --no-verify` bajo cualquier circunstancia
- ❌ **PROHIBIDO:** Trabajar directamente en main o develop
- ✅ **BRANCH STRATEGY:** Siempre feature/ branches
- ✅ **Convención:** `feature/[modulo]-[descripcion]`
- ✅ **WORKFLOW:**
  ```bash
  git checkout main && git pull origin main
  git checkout -b feature/[modulo]-[descripcion]
  bench --site facturacion.dev backup --with-files  # Backup al crear rama nueva
  # Desarrollo...
  git log --oneline main..HEAD  # Verificar commits únicos
  gh pr list --state open --head feature/[branch-name]  # Verificar PR no existe
  gh pr create --base main --head feature/[branch-name]  # Target MAIN siempre
  ```
- ⚠️ **AUTORIZACIÓN:** Todo commit debe ser aprobado por el usuario
- ❌ **TESTS OBLIGATORIOS:** NO se permite commit si algún test falla. Todos los tests deben pasar al 100% antes de cualquier commit
- ✅ **ISSUES TEMPORALES:** Crear GitHub issue cuando problema no puede resolverse
- ✅ **DOCUMENTACIÓN ISSUE:**
  ```markdown
  # Título: [FRAMEWORK] Descripción específica del problema

  ## Contexto del problema
  - ¿Qué se intentaba hacer?
  - ¿Qué limitación específica lo impide?
  - ¿En qué archivo/línea ocurre?

  ## Reproducción del problema
  - Pasos exactos para reproducir
  - Código mínimo que demuestra el issue
  - Error específico que aparece

  ## Workaround actual
  - Solución temporal implementada
  - Limitaciones del workaround
  - Código del workaround con comentarios

  ## Resolución futura esperada
  - ¿Qué cambio en framework lo resolvería?
  - ¿En qué versión podría estar disponible?
  - Links a documentación/issues upstream
  ```
- ✅ **TODO MARKERS:**
  ```python
  # TODO: ISSUE #123 - Frappe mandatory field validation
  # CONTEXT: Framework limitation prevents custom validation
  # WORKAROUND: Manual validation in validate() method
  # RESOLUTION: Track upstream fix in v16+
  ```
- ✅ **Linting:** `ruff --fix .` para auto-corrección común
- ✅ **Pre-commit:** Hooks automáticos en `.pre-commit-config.yaml`
- ✅ **Commits:** `feat(scope): descripción en español`

### **RG-003: TESTING FRAMEWORK**
**Meta:** Suite rápida, determinista y útil (≤ 5 min), sin dependencias externas.

#### **RG-003.1: Principios**
- ✅ **Simplicidad:** Prueba reglas de negocio, no UI
- ✅ **Determinismo:** Sin red, sin reloj real, sin commits manuales
- ✅ **Aislamiento:** Cada test crea sus datos y no comparte estado

#### **RG-003.2: Pirámide Testing**
- ✅ **Unit** (prioridad) → **Service/DB** (mínimos) → **Smoke integración** (con mock del gateway)

#### **RG-003.3: Estructura Mínima**
```python
# tests/__init__.py - Setup global una vez
import frappe
frappe.flags.skip_test_records = True  # Evita framework issues
```

```python
# tests/test_modulo_basico.py
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch
import frappe

class TestReglaNegocio(FrappeTestCase):
    def setUp(self):
        # IDs únicos, no hardcode
        self.test_id = "TEST-" + frappe.generate_hash()[:6]

    def test_creation(self):
        """Test básico - crear documento."""
        doc = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": self.test_id
        })
        doc.insert()
        self.assertTrue(frappe.db.exists("Sales Invoice", doc.name))

    def test_spanish_labels(self):
        """Test obligatorio - labels específicos en español."""
        meta = frappe.get_meta("Sales Invoice")
        self.assertEqual(meta.get_label("customer"), "Cliente")

    def test_integration_with_mock(self):
        """Test integración con mock del gateway externo."""
        doc = frappe.get_doc({"doctype": "Sales Invoice", "customer": self.test_id})
        doc.insert()

        with patch("facturacion_mexico.integrations.facturapi.Client.emitir") as mock_emit:
            mock_emit.return_value = {"uuid": "TEST-UUID", "status": "success"}
            # Llamar función que integra
            result = doc.emitir_cfdi()
            self.assertEqual(result["status"], "success")

    # NO definir tearDown() - framework maneja rollback automático
```

#### **RG-003.4: Ejecución**
```bash
# Variables comando
: "${SITE:=facturacion.dev}"  # Sitio recomendado proyecto
: "${APP:=facturacion_mexico}"

# Tests completos
bench --site "$SITE" run-tests --app "$APP"

# Tests específicos
bench --site "$SITE" run-tests --app "$APP" --module tests.test_modulo_basico
```

#### **RG-003.5: Factories (ligeras)**
```python
# tests/factories.py - Helpers para crear test docs
import frappe

def create_test_doc(doctype, **kwargs):
    """Helper para crear docs test rápido."""
    defaults = {"name": f"TEST-{frappe.generate_hash()[:6]}"}
    defaults.update(kwargs)
    return frappe.get_doc({"doctype": doctype, **defaults})
```

#### **RG-003.6: Constantes Testing**
```python
# Constantes inline en tests (no archivo separado)
TIMEZONE = "America/Mexico_City"
BASE_DATETIME = "2024-01-15 10:00:00-06:00"  # Usar mock/monkeypatch
CURRENCY = "MXN"  # 2 decimales
FX = {"USD": 20.00, "EUR": 24.00}
```

#### **RG-003.7: Mocks**
- ✅ **Mock solo gateway/adaptador externo** - NO `frappe.get_doc`
- ✅ **Respuestas mínimas** "contrato", no JSONs enciclopédicos
```python
# ✅ CORRECTO - Mock boundary externo
with patch("facturacion_mexico.integrations.sat_client.validate") as mock_sat:
    mock_sat.return_value = {"valid": True, "uuid": "test-uuid"}

# ❌ PROBLEMÁTICO - Mock framework core
with patch("frappe.get_doc") as mock_get:
    mock_get.return_value = MagicMock()  # Efectos colaterales
```

#### **RG-003.8: DoD (Definition of Done)**
- ✅ **≥1 test por regla nueva**; si integra servicio externo → 1 smoke con mock
- ✅ **Suite ≤ 5 min; 0 flaky; 0 redes; 0 SQL a metadatos**
- ❌ **Prohibido:** Tests sin valor negocio, over-engineering

### **RG-004: ARCHITECTURE FIRST**
- ✅ **Documentación técnica** antes de código
- ✅ **Fixtures first** para configuraciones
- ✅ **Override class > hooks** para enlaces bidireccionales
- ✅ **Zero-config deployment** obligatorio

### **RG-009: FIXTURES OBLIGATORIOS (ZERO-CONFIG)**
- ✅ **OBLIGATORIO:** Todo campo/DocType/configuración DEBE tener fixture
- ❌ **PROHIBIDO:** Crear datos únicamente local que no migren
- ❌ **PROHIBIDO:** Modificar BD directa como reemplazo de fixture
- ✅ **REGLA ABSOLUTA:** Si cambio va en fixture → arreglar fixture, nunca BD
- ✅ **PROCESO CORRECTO:**
  ```bash
  # ✅ Fixture roto → Arreglar fixture JSON → migrate
  # ❌ NUNCA: frappe.db.sql("UPDATE tabla") como "atajo"
  ```
- ⚠️ **CRÍTICO:** Fixtures garantizan consistencia entre sitios/deployments
- ✅ **ZERO-CONFIG:** Nuevas instalaciones deben funcionar sin configuración manual

### **RG-010: ONE-OFF SCRIPTS STORAGE**
- ✅ **UBICACIÓN OBLIGATORIA:** `{app_name}/{app_name}/one_offs/` dentro del paquete Python
- ✅ **EJEMPLO:** `/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/one_offs/`
- ✅ **PROPÓSITO:** Scripts para `bench execute` que NO se commitean al repositorio
- ✅ **SETUP INICIAL OBLIGATORIO:**
  ```bash
  # Crear directorio dentro del paquete Python
  mkdir -p {app_name}/{app_name}/one_offs/
  echo "# one_offs module" > {app_name}/{app_name}/one_offs/__init__.py
  ```
- ✅ **NAMING CONVENTION:** Nombres Python válidos (sin números al inicio)
  - ❌ INCORRECTO: `20250916_script.py` (números al inicio - Python no permite)
  - ✅ CORRECTO: `script_20250916.py`, `migrar_customers.py`, `compare_ffm_docs.py`
  - ✅ REGLA: Usar formato `{accion}_{fecha}.py` o `{descripcion_funcional}.py`
- ❌ **PROHIBIDO ABSOLUTO:** Comandos python directos (`python3 script.py`)
- ✅ **OBLIGATORIO:** Solo usar `bench execute` para todos los scripts
- ✅ **EJECUCIÓN SCRIPTS - INSTRUCCIONES EXACTAS:**
  ```bash
  # 1. OBLIGATORIO: one_offs/ debe estar dentro del paquete Python
  # UBICACIÓN CORRECTA: apps/{app}/facturacion_mexico/one_offs/
  # NO: apps/{app}/one_offs/ (no funciona con bench execute)

  # 2. ESTRUCTURA OBLIGATORIA del script:
  # #!/usr/bin/env python3
  # import frappe
  # def run():  # ← NOMBRE FUNCIÓN ESTÁNDAR
  #     # código aquí
  #     return True
  # if __name__ == "__main__":
  #     run()

  # 3. EJECUCIÓN (funciona con paquete Python):
  bench --site facturacion.dev execute "{app_name}.one_offs.script_name.run"

  # EJEMPLO WORKING:
  bench --site facturacion.dev execute "facturacion_mexico.one_offs.fix_customers_currency.run"
  ```
- ❌ **ERRORES COMUNES QUE NO FUNCIONAN:**
  - Poner one_offs/ fuera del paquete Python principal
  - Scripts sin `__init__.py` en one_offs/
  - Nombres archivo con números al inicio
  - Usar python3 -c o ejecución directa (PROHIBIDO)
  - Funciones con nombres distintos a `run()`
- ✅ **CONTENIDO TÍPICO:** Migraciones datos, correcciones one-time, scripts diagnóstico
- ❌ **PROHIBIDO:** Commitear scripts one-off al repositorio del proyecto
- ⚠️ **IMPORTANTE:** Scripts deben ser idempotentes y con validaciones previas

### **RG-011: PLANES IMPLEMENTACIÓN AUTOCONTENIDOS**
- ✅ **Estructura obligatoria:** `docs/testing/planes/plan-[categoria]-[objetivo]/`
- ✅ **Nombre descriptivo:** Archivo principal con nombre específico (no genérico)
- ✅ **Subdirectorios estándar:** evidencias/ + resultados/ + config/
- ✅ **Índice central:** docs/testing/PLAN-INDEX.md lista todos los planes
- ✅ **Templates:** Usar docs/testing/templates/ para nuevos planes
- ✅ **Aislamiento:** Cada plan completamente autocontenido
- ❌ **Prohibido:** Carpetas compartidas entre múltiples planes
- ❌ **Prohibido:** Nombres genéricos (plan.md, README.md)
- ✅ **Categorías:** testing, performance, migracion, integracion, security, compliance
- ✅ **Estados:** ⏳ Pendiente, 🔄 En ejecución, ✅ Completado, ❌ Fallido, 🕐 Programado, 🚫 Cancelado

### **RG-005: MULTI-LAYER SECURITY**
- ✅ **3 capas:** Permisos DocType + Backend Guards + UI Removal
- ✅ **Defense in depth** operaciones críticas
- ✅ **Validaciones server-side** siempre
- ✅ **Roles específicos** con permisos granulares

### **RG-007: HOOKS ESPECÍFICOS OBLIGATORIO**
- ❌ **PROHIBIDO:** Hooks universales (`"*"`) - causan conflictos setup wizard
- ✅ **REQUERIDO:** Hooks específicos por DocType solamente
- ✅ **EJEMPLO CORRECTO:**
  ```python
  doc_events = {
      "Sales Invoice": {
          "after_insert": "facturacion_mexico.hooks.sales_invoice_insert"
      }
  }
  ```
- ❌ **EJEMPLO PROHIBIDO:**
  ```python
  doc_events = {
      "*": {  # ← ESTO BLOQUEA SETUP WIZARD
          "after_insert": "app.hooks.universal_handler"
      }
  }
  ```
- ✅ **VERIFICACIÓN:** Tests obligatorios después de modificar hooks.py
- ⚠️ **CRÍTICO:** Hooks afectan múltiples módulos, pueden bloquear desarrollo completo

### **RG-008: REUTILIZACIÓN CÓDIGO EXISTENTE**
- ✅ **PRIORIDAD 1:** Código nativo Frappe Framework SIEMPRE primero
- ✅ **PRIORIDAD 2:** Código ERPNext/otros apps antes que crear nuevo
- ✅ **OBLIGATORIO:** Comentarios explicativos para código externo
- ✅ **OBLIGATORIO:** Unit test para detectar cambios en código externo
- ✅ **CRITERIOS:**
  - Frappe nativo disponible → USAR FRAPPE (sin tests externos)
  - ERPNext/apps disponible → USAR + comentario + test unitario
  - No existe → CREAR NUEVO código propio
- ✅ **EJEMPLOS:**
  ```python
  # ✅ PRIORIDAD 1 - Frappe nativo
  from frappe.utils import now_datetime, get_date_str

  # ✅ PRIORIDAD 2 - ERPNext con documentación
  from erpnext.accounts.utils import get_balance_on
  # EXTERNAL: ERPNext function for account balance calculation
  # Used instead of recreating balance logic

  def test_external_balance_function(self):
      """Test ERPNext balance function behavior hasn't changed."""
      # Ensure external function still returns expected format
      balance = get_balance_on("Test Account", "2025-01-01")
      self.assertIsInstance(balance, (int, float))
  ```
- ❌ **EVITAR:** Recrear funcionalidad ya existente en framework/apps

### **RG-006: DOCSTRINGS ESTÁNDAR OBLIGATORIO**
- ✅ **Formato requerido:** Descripción breve + Funcionalidades + Parámetros + Errores + Ejemplo
- ✅ **Estructura clase:**
  ```python
  class NombreClase(Document):
      """
      Descripción breve en español de la funcionalidad principal.

      Funcionalidades principales:
      - Lista de funcionalidades específicas
      - Una por línea, en español

      Parámetros importantes:
          campo_1 (Tipo): Descripción del campo en español

      Errores comunes:
          ValidationError: Descripción del error específico

      Ejemplo de uso:
          doc = frappe.new_doc("DocType Name")
          doc.campo_1 = "valor"
          doc.save()
      """
  ```
- ✅ **Métodos:** Args, Returns, Raises obligatorios en español
- ✅ **MkDocs compatible:** Formato mkdocstrings para autogeneración
- ✅ **Navegación explícita:** Páginas deben agregarse a mkdocs.yml nav
- ✅ **Validación:** `mkdocs build --strict` debe pasar sin errores

---

## 🚨 **REGLAS CRÍTICAS**
*(No negociables, bloquean desarrollo)*

### **RC-001: SIN COMMITS MANUALES**
- ❌ **NUNCA** `frappe.db.commit()` manual
- ✅ **Confiar** atomicidad Frappe
- ⚠️ **Anti-pattern** detectado por linters

### **RC-002: SIN HARDCODE CONFIGURACIONES**
- ✅ **TODO configurable** = fixture
- ✅ **Zero-config deployment** obligatorio
- ✅ **Version controlled** roles/permisos

### **RC-003: SPANISH COMPLIANCE**
- ❌ **DocType con labels inglés** = RECHAZADO
- ❌ **Mensajes error inglés** = RECHAZADO
- ❌ **Documentación inglés** = RECHAZADO

### **RC-004: TESTING COVERAGE**
- ❌ **Funcionalidad sin tests** = RECHAZADO
- ❌ **Workflows críticos sin testing granular** = RECHAZADO
- ❌ **Pre-commit hooks fallando** = RECHAZADO

### **RC-005: AUTORIZACIÓN EXPLÍCITA OBLIGATORIA**
- ⚠️ **REGLA ABSOLUTA:** Todo cambio técnico requiere autorización explícita usuario
- ❌ **PROHIBIDO:** Modificar código sin autorización explícita
- ❌ **PROHIBIDO:** Asumir que "arreglar" significa "hacer lo que sea"
- ✅ **PROCESO OBLIGATORIO:**
  ```
  1. Describir específicamente qué hará
  2. Preguntar: "¿Proceder? (si/no)"
  3. ESPERAR respuesta del usuario
  4. Solo proceder con "si"
  ```
- ✅ **FORMATO:** 🔐 CONFIRMACIÓN REQUERIDA: [acción específica] ¿Proceder? (si/no)
- ❌ **EXCEPCIÓN:** No pedir confirmación para acciones EXPLÍCITAS en instrucciones

### **RC-006: PROHIBICIÓN OPERACIONES FORZADAS**
- ❌ **PROHIBIDO:** Forzar migraciones, cache clearing, operaciones inconsistentes
- ❌ **PROHIBIDO:** Modificar BD directa cuando migrate falla
- ❌ **PROHIBIDO:** Implementar cambios manuales por fallas migración
- ✅ **PROCESO CORRECTO:** Reportar problema → Esperar autorización → Solo proceder con permiso
- ⚠️ **CRÍTICO:** Solo usar flujo normal actualizaciones del sitio

---

## 🇲🇽 **REGLAS ESPECÍFICAS FACTURACIÓN MÉXICO**

### **RE-001: NORMATIVA SAT**
- ✅ **Workflows 01/02/03/04** según normativa SAT
- ✅ **Override class** para múltiples FFMs (LinkExistsError)
- ✅ **TipoRelación 04** obligatorio sustituciones
- ✅ **Validaciones estrictas** motivos cancelación

### **RE-002: ESTRUCTURA DOCUMENTACIÓN OFICIAL**

#### **Documentación Core (claude.md)**
- ✅ **Reglas completas** - Información crítica nunca externa
- ✅ **Ejemplos esenciales** - Código samples en claude.md
- ✅ **Referencias mínimas** - Solo enlaces complementarios

#### **Documentación Complementaria (docs/)**
- ✅ **API referencias** - docs/api/ (endpoints detallados)
- ✅ **User guides** - docs/user-guide/ (tutoriales paso a paso)
- ✅ **Development** - docs/development/ (setup detallado)
- ✅ **Audit reports** - docs/audit/ (reportes automáticos)

#### **Arquitectura Técnica (buzola-internal/)**
- ✅ **PRIVADO:** buzola-internal/projects/facturacion_mexico/
- ✅ **Contenido:** ARQUITECTURA_*, TESTING_*, REPORTE_*
- ✅ **Propósito:** Documentación técnica interna, contexto crítico

#### **Archivo Obligatorio**
- ✅ **CHANGELOG.md** - Historial cambios en raíz proyecto
- ✅ **Formato:** Según [Keep a Changelog](https://keepachangelog.com/es/)
- ✅ **Mantenimiento:** Actualizar cada release/milestone

#### **RG-011: CHANGELOG.md VERSIONING OBLIGATORIO**
- ✅ **Estructura requerida:** Secciones [Unreleased] + versiones numeradas
- ✅ **Versionado semántico:** MAJOR.MINOR.PATCH según [SemVer](https://semver.org/lang/es/)
- ✅ **Fechas ISO:** YYYY-MM-DD para todas las versiones
- ✅ **Categorías obligatorias:** Added, Changed, Deprecated, Removed, Fixed, Security

#### **RG-011.1: Workflow Versioning**
```bash
# Durante desarrollo: acumular en [Unreleased]
# Al hacer release: mover [Unreleased] → [X.Y.Z] - YYYY-MM-DD

# Ejemplo release minor (nueva funcionalidad):
git tag v5.1.0
# Mover contenido [Unreleased] → [5.1.0] - 2025-09-17

# Ejemplo release patch (solo fixes):
git tag v5.0.1
# Solo fixes acumulados → [5.0.1] - 2025-09-17
```

#### **RG-011.2: Criterios Versioning (0.x.x para Alpha)**
- **MINOR (0.X.0):** Nueva funcionalidad mayor, cambios API
- **PATCH (0.X.Y):** Bug fixes, pequeñas mejoras, funcionalidad menor
- **Nota:** Versión 0.x.x indica software alpha en desarrollo activo

#### **RG-011.3: Template Obligatorio**
```markdown
# Changelog

## [Unreleased]

### Added
- Nueva funcionalidad pendiente release

### Changed
- Cambios en funcionalidad existente

### Fixed
- Bug fixes pendientes

## [0.5.1] - 2025-09-17

### Added
- Sistema unificado validación RFC/CSF Customer con banner único
- Armonización direcciones FFM-ERPNext para consistencia completa

### Fixed
- Mensajes contradictorios validación RFC/CSF
- Inconsistencia direcciones entre Customer UI y FFM

## [0.5.0] - 2025-09-16
[Versiones anteriores...]
```

#### **RG-011.4: Comandos Release**
```bash
# 1. Verificar cambios pendientes
git log --oneline v5.0.0..HEAD

# 2. Actualizar CHANGELOG.md (mover [Unreleased] → [0.5.1])
# 3. Commit de release
git add CHANGELOG.md
git commit -m "docs(release): preparar changelog v0.5.1"

# 4. Crear tag
git tag -a v0.5.1 -m "Release v0.5.1: Sistema validación RFC unificado"

# 5. Push con tags
git push origin main --tags
```

#### **Navegación Independiente**
| Propósito | Ubicación Principal | Backup/Complemento |
|-----------|-------------------|-------------------|
| Reglas desarrollo | claude.md | - |
| Comandos críticos | claude.md | docs/development/ |
| Testing framework | claude.md | docs/development/ |
| API endpoints | claude.md (básico) | docs/api/ (detallado) |
| Troubleshooting | claude.md (común) | docs/user-guide/ |

### **RE-003: FISCAL COMPLIANCE**
- ✅ **3 capas amend blocking** FFMs canceladas
- ✅ **LinkExistsError resolución** con ignore_links
- ✅ **Auditoría bidireccional** SI ↔ FFM
- ✅ **Estados fiscales sincronizados**

### **RE-004: WORKFLOW TESTING**
- ✅ **62 casos testing mínimo** sistema cancelaciones
- ✅ **48 workflow básico** + casos edge múltiples FFMs
- ✅ **Testing usuarios roles específicos** (no solo Administrator)
- ✅ **Documentación testing** en buzola-internal

### **RE-005: CUSTOM FIELDS FACTURACIÓN MÉXICO**
- ✅ **Prefijos obligatorios:** fm_* para todos los custom fields
- ✅ **Fixtures obligatorios:** Todo custom field debe tener fixture (ver RG-009)
- ✅ **Convención naming:**
  ```python
  # ✅ CORRECTO
  "fm_campo_fiscal", "fm_sat_codigo", "fm_cfdi_uuid"

  # ❌ INCORRECTO
  "campo_fiscal", "custom_field", "facturacion_campo"
  ```
- ✅ **Zero-config deployment:** Fixtures auto-instalan custom fields
- ⚠️ **CRÍTICO:** Custom fields sin fixture bloquean deployment

### **RE-006: SITIOS ESPECÍFICOS FACTURACIÓN MÉXICO**
- ✅ **SITE_PRINCIPAL:** `facturacion.dev` - Para desarrollo y testing principal
- ✅ **COMANDOS ESTÁNDAR:**
  ```bash
  # Testing completo
  bench --site facturacion.dev run-tests --app facturacion_mexico

  # Migración y cache
  bench --site facturacion.dev migrate
  bench --site facturacion.dev clear-cache
  bench --site facturacion.dev console

  # Execute scripts
  bench --site facturacion.dev execute facturacion_mexico/one_offs/script_name.py
  ```
- ❌ **PROHIBIDO:** Usar development.localhost, testing.localhost (obsoletos)
- ⚠️ **IMPORTANTE:** Siempre especificar site en comandos bench

### **RE-007: SITIOS ESPECÍFICOS CONDOMINIUM MANAGEMENT**
- ✅ **SITE_PRINCIPAL:** `admin1.dev` - Para desarrollo y testing principal
- ✅ **SITES_CONTRIBUYENTES:** `condo1.dev`, `condo2.dev` - Sites independientes
- ✅ **RECEPTOR_CENTRAL:** `domika.dev` - Matriz para community contributions
- ✅ **COMANDOS ESTÁNDAR:**
  ```bash
  # Testing completo
  bench --site admin1.dev run-tests --app condominium_management

  # Migración y cache
  bench --site admin1.dev migrate
  bench --site admin1.dev clear-cache
  bench --site admin1.dev console

  # Execute scripts
  bench --site admin1.dev execute condominium_management/one_offs/script_name.py

  # Cross-site contributions
  # Sites contribuyentes envían a domika.dev vía APIs
  ```
- ✅ **ARQUITECTURA CROSS-SITE:** Sites contribuyentes → domika.dev → propagación
- ⚠️ **IMPORTANTE:** Cada site maneja condominios independientes

---

## 🛠️ **COMANDOS DESARROLLO ESENCIALES**

**Sitio recomendado en este proyecto:** `facturacion.dev`. Por defecto, los ejemplos usan `SITE=${SITE:=facturacion.dev}`. Si tu entorno usa otro nombre, ejecuta `SITE=<tu_sitio> comando`.

### **Variables Setup**
```bash
# Variables comando
: "${SITE:=facturacion.dev}"  # Sitio recomendado proyecto
: "${APP:=facturacion_mexico}"

# Preflight crítico (solo comandos largos)
if ! bench --site "$SITE" list-apps >/dev/null 2>&1; then
  echo "⚠️ SITE='$SITE' no existe. Usa SITE=<tu_sitio>"
  exit 1
fi
```

### **Git Workflow**
```bash
git checkout -b feature/[nombre-descriptivo]
git add . && git commit -m "feat(alcance): descripción en español"
git push origin feature/[nombre-descriptivo]
```

### **Testing**
```bash
# Tests completos
bench --site "$SITE" run-tests --app "$APP"

# Tests específicos
bench --site "$SITE" run-tests --app "$APP" --module tests.test_[modulo]
```

### **GitHub**
```bash
# Ver PRs
gh pr list --state open

# Crear PR
gh pr create --title "título descriptivo" --body "descripción detallada"
```

### **Build & Deploy**
```bash
# Migración
bench --site "$SITE" migrate

# Build frontend
bench --site "$SITE" build --app "$APP"

# Clear cache
bench --site "$SITE" clear-cache

# Execute scripts
bench --site "$SITE" execute "$APP"/one_offs/script_name.py
```

---

## 📂 **REFERENCIAS RÁPIDAS**

| Área | Ubicación |
|------|-----------|
| Arquitectura técnica | `buzola-internal/projects/facturacion_mexico/ARQUITECTURA_*.md` |
| Testing detallado | `buzola-internal/projects/facturacion_mexico/TESTING_*.md` |
| **Planes implementación** | `docs/testing/PLAN-INDEX.md` |
| Docs usuario | `docs/user-guide/` |
| APIs detalladas | `docs/api/` |

---

## 🎯 **WORKFLOW & CALIDAD**

### **Desarrollo Básico:**
1. **TodoWrite** tracking → **Código + tests** → **Commit convencional** → **Docs actualizado**

### **Políticas Rechazo:**
❌ Labels inglés | ❌ Sin tests | ❌ Hardcode config | ❌ Pre-commit falla

### **Patrones Arquitectónicos:**
✅ Override class > hooks | ✅ Fixtures > BD manual | ✅ 3 capas security

---

## 🔗 **RECURSOS**

- **Frappe Framework:** https://frappeframework.com/docs
- **Conventional Commits:** https://www.conventionalcommits.org/
- **Sistema Buzola:** `buzola-internal/projects/facturacion_mexico/`

**🤖 Generated with [Claude Code](https://claude.ai/code)**