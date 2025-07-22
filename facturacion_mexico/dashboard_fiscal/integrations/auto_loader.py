# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Auto-loader para integraciones del Dashboard Fiscal
Inicializa automáticamente todas las integraciones de módulos
"""

import frappe
from frappe import _


def initialize_all_integrations():
	"""Inicializar todas las integraciones disponibles"""

	integrations = [
		{
			"module": "Timbrado",
			"loader": "facturacion_mexico.dashboard_fiscal.integrations.timbrado_integration.initialize_timbrado_integration",
		},
		{
			"module": "PPD",
			"loader": "facturacion_mexico.dashboard_fiscal.integrations.ppd_integration.initialize_ppd_integration",
		},
		{
			"module": "Motor Reglas",
			"loader": "facturacion_mexico.dashboard_fiscal.integrations.motor_reglas_integration.initialize_motor_reglas_integration",
		},
	]

	loaded_modules = []
	failed_modules = []

	for integration in integrations:
		try:
			# Intentar cargar la integración
			loader_function = frappe.get_attr(integration["loader"])
			loader_function()
			loaded_modules.append(integration["module"])

		except Exception as e:
			frappe.log_error(
				title=f"Error cargando integración {integration['module']}", message=f"Error: {e}"
			)
			failed_modules.append(integration["module"])

	# Log del resultado
	if loaded_modules:
		frappe.logger().info(f"Módulos cargados en Dashboard: {', '.join(loaded_modules)}")

	if failed_modules:
		frappe.logger().warning(f"Módulos que fallaron al cargar: {', '.join(failed_modules)}")

	return {"loaded": loaded_modules, "failed": failed_modules, "total_attempted": len(integrations)}


def get_available_integrations():
	"""Obtener lista de integraciones disponibles"""
	return [
		{
			"module": "Timbrado",
			"description": "Métricas de timbrado CFDI, PAC y errores",
			"kpis": ["facturas_timbradas_hoy", "tasa_exito_timbrado", "creditos_pac"],
			"status": "active",
		},
		{
			"module": "PPD",
			"description": "Seguimiento de Pagos en Parcialidades y Diferido",
			"kpis": ["facturas_ppd_activas", "saldo_pendiente", "cumplimiento"],
			"status": "active",
		},
		{
			"module": "Motor Reglas",
			"description": "Monitoreo del motor de reglas globales",
			"kpis": ["reglas_activas", "ejecuciones", "errores"],
			"status": "active",
		},
		{
			"module": "E-Receipts",
			"description": "Métricas de recibos electrónicos",
			"kpis": ["pendiente_implementacion"],
			"status": "planned",
		},
		{
			"module": "Addendas",
			"description": "Sistema de addendas personalizadas",
			"kpis": ["pendiente_implementacion"],
			"status": "planned",
		},
		{
			"module": "Facturas Globales",
			"description": "Facturación global y consolidación",
			"kpis": ["pendiente_implementacion"],
			"status": "planned",
		},
	]


# Hook para inicialización automática
def on_frappe_ready():
	"""Hook que se ejecuta cuando Frappe está listo"""
	try:
		# Solo inicializar en contextos apropiados
		if frappe.flags.in_install or frappe.flags.in_migrate:
			return

		# Inicializar integraciones en background
		frappe.enqueue(initialize_all_integrations, queue="default", timeout=300, is_async=True)

	except Exception as e:
		frappe.log_error(f"Error en on_frappe_ready del Dashboard: {e}")


# Utilidad para debugging
def reload_integrations():
	"""Recargar todas las integraciones (útil para desarrollo)"""
	try:
		# Limpiar registry
		from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry

		DashboardRegistry.reset_registry()

		# Reinicializar
		result = initialize_all_integrations()

		frappe.msgprint(
			_("Integraciones recargadas: {0} exitosas, {1} fallidas").format(
				len(result["loaded"]), len(result["failed"])
			),
			title=_("Dashboard Fiscal"),
			indicator="green" if not result["failed"] else "orange",
		)

		return result

	except Exception as e:
		frappe.throw(_("Error recargando integraciones: {0}").format(str(e)))
