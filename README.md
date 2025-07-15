### Facturacion Mexico

App de Facturacion en Mexico Integrada a ERPNEXT

App de Facturación Legal México para ERPNext
Solución integral de facturación electrónica mexicana que extiende ERPNext con cumplimiento total SAT
🎯 Descripción General
Sistema completo de facturación fiscal mexicana desarrollado como aplicación Frappe Framework que se integra transparentemente con ERPNext. Utiliza un servicio de timbrado fiscal y proporciona cumplimiento total con la regulación del SAT mexicano, incluyendo validaciones proactivas, motor de reglas declarativas y trazabilidad completa de operaciones fiscales.
✨ Características Principales
🏢 Integración Nativa con ERPNext

Extiende Sales Invoices existentes sin duplicar funcionalidad
Reutiliza datos maestros (Customers, Items, Companies)
Custom fields fiscales en DocTypes nativos
Flujo de trabajo transparente para usuarios

📋 Cumplimiento Fiscal Completo SAT

Facturación CFDI 4.0 con soporte legacy 3.3
Complementos de pago PPD automáticos y manuales
E-Receipts con autofacturación para clientes
Facturas globales para períodos específicos
Cancelaciones fiscales con 4 motivos SAT
Retenciones para proveedores
Nómina fiscal complementaria

🔍 Validaciones Proactivas SAT

Verificación automática de RFCs contra constancia SAT
Detección de contribuyentes en lista 69-B
Validación de catálogos SAT actualizados
Coherencia de datos fiscales en tiempo real
Motor de reglas declarativas actualizable

🎛️ Motor de Reglas Declarativas

Validaciones SAT configurables sin código
Actualización de reglas fiscales sin deployments
Priorización y versionado de reglas
Templates personalizables por caso de uso

📊 Trazabilidad y Auditoría

Event sourcing nativo para trazabilidad completa
Timeline de eventos fiscales correlacionados
Logs exhaustivos de operaciones
Exportación para auditorías externas
Dashboard de salud fiscal

🚀 Experiencia de Usuario Optimizada

Panel de facturación rápida con vista Kanban
Wizards intuitivos para configuración
Validaciones en tiempo real con feedback visual
Operaciones masivas (batch processing)
Templates inteligentes para casos comunes

⚡ Performance y Escalabilidad

Procesamiento asíncrono con colas
Cache estratégico de catálogos SAT
Sincronización inteligente diferencial
Manejo selectivo de catálogo productos (~100k registros)
Rate limiting y retry automático

🔧 Características Técnicas
Arquitectura

Framework: Frappe Framework (ERPNext compatible)
Lenguaje: Python 3.8+
Base de datos: MariaDB/PostgreSQL
API Externa: FacturAPI.io SDK Python
Cache: Redis (opcional)

Módulos del Sistema

Facturación Fiscal: Timbrado y gestión CFDI
Documentos Especiales: E-Receipts, globales, retenciones
Validación y Cumplimiento: Motor de reglas SAT
Catálogos SAT: Sincronización automática
Trazabilidad: Event sourcing y auditoría

DocTypes Principales

Factura Fiscal Mexico: Registro de timbrado fiscal
Complemento Pago MX: Complementos PPD automáticos
EReceipt MX: Recibos digitales autofacturables
Fiscal Validation Rule: Motor de reglas declarativas
Fiscal Event MX: Event sourcing para auditoría

Sistema de Permisos

Facturación Mexico User: Operaciones básicas
Facturación Mexico Supervisor: Cancelaciones y reportes
Facturación Mexico Administrator: Configuración completa

🎯 Casos de Uso
Para Empresas

Facturación automática desde Sales Invoices
Complementos de pago sin intervención manual
Dashboard ejecutivo de cumplimiento fiscal
Reportes de inconsistencias administrativas
Validación proactiva de clientes contra SAT

Para Contadores/Administradores

Panel de salud fiscal con scoring
Herramientas de corrección masiva
Timeline completo de eventos fiscales
Exportación de reportes para auditorías
Gestión de reglas de validación

Para Desarrolladores

APIs RESTful para integraciones
Hooks configurables para customizaciones
Motor de reglas extensible
Event sourcing para trazabilidad
Arquitectura modular y escalable

📈 Ventajas Competitivas
vs. Sistema Anterior (facturacion_mx)

✅ Integración no invasiva con ERPNext
✅ Motor de reglas declarativas vs. hardcoded
✅ Event sourcing vs. logs básicos
✅ Validaciones proactivas SAT
✅ UX moderna con wizards y dashboards
✅ Arquitectura escalable y mantenible

vs. Soluciones Comerciales

✅ Integración nativa (no conectores externos)
✅ Sin costos adicionales por usuario
✅ Código abierto y personalizable
✅ Performance optimizado para ERPNext
✅ Actualizaciones incluidas
✅ Comunidad y soporte activo

🛠️ Instalación y Configuración
Requisitos

ERPNext v14+ (recomendado v15)
Python 3.8+ con dependencias

Instalación Rápida
bash# Obtener la app
bench get-app facturacion_mexico

# Instalar en sitio
bench --site [sitename] install-app facturacion_mexico

# Ejecutar wizard de configuración
# Configurar certificados y API keys
# Sincronizar catálogos SAT iniciales
Configuración Inicial

Wizard de configuración guiado
Importación de datos existentes
Mapeo de productos a claves SAT
Configuración de reglas de validación
Pruebas en ambiente sandbox

📊 Métricas y Monitoreo

Dashboard en tiempo real con KPIs fiscales
Alertas proactivas de vencimientos y errores
Reportes de cumplimiento automatizados
Analytics de performance y uso
Health checks de conectividad y certificados

🔮 Roadmap
v1.1 (Q4 2025)

App móvil para consultas
Editor visual de reglas
API pública para integraciones
Reportes personalizables

v1.2 (Q1 2026)

IA para detección de anomalías
Integración con bancos
Marketplace de templates
Soporte multi-idioma

v2.0 (Q2 2026)

Multi-PAC support
Facturación internacional
Blockchain para trazabilidad
Asistente virtual con IA

📞 Soporte y Comunidad

Documentación completa en /docs
Issues y Feature Requests en GitHub
Comunidad ERPNext para soporte
Actualizaciones regulares de cumplimiento SAT


Desarrollado específicamente para el ecosistema ERPNext mexicano, proporcionando la solución más completa y moderna para facturación electrónica en México.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app facturacion_mexico
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/facturacion_mexico
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

### License

gpl-3.0
