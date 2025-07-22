# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Integración del Motor de Reglas con el Dashboard Fiscal
Proporciona KPIs y alertas para el sistema de reglas globales
"""

from datetime import datetime, timedelta

import frappe


def register_motor_reglas_kpis():
	"""Registrar KPIs del Motor de Reglas"""
	from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry

	kpis = {
		"reglas_activas": get_reglas_activas,
		"ejecuciones_hoy": get_ejecuciones_hoy,
		"reglas_con_errores": get_reglas_con_errores,
		"facturas_procesadas_reglas": get_facturas_procesadas_reglas,
	}

	DashboardRegistry.register_kpi("Motor Reglas", kpis)


def register_motor_reglas_alerts():
	"""Registrar evaluadores de alertas del Motor de Reglas"""
	from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry

	alerts = {"reglas_fallando": evaluar_reglas_fallando, "motor_inactivo": evaluar_motor_inactivo}

	DashboardRegistry.register_alert_evaluator("Motor Reglas", alerts)


def get_reglas_activas(**kwargs):
	"""Obtener número de reglas activas"""
	try:
		count = frappe.db.count("Global Invoice Rule", {"is_active": 1})

		return {
			"value": count,
			"format": "number",
			"subtitle": "Reglas activas",
			"timestamp": datetime.now().isoformat(),
		}

	except Exception as e:
		frappe.log_error(f"Error en get_reglas_activas: {e}")
		return None


def get_ejecuciones_hoy(**kwargs):
	"""Obtener ejecuciones de reglas hoy"""
	try:
		today = datetime.now().date()

		count = frappe.db.count(
			"Rule Execution Log", {"creation": ["between", [today, today + timedelta(days=1)]]}
		)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Ejecuciones hoy",
			"timestamp": datetime.now().isoformat(),
		}

	except Exception as e:
		frappe.log_error(f"Error en get_ejecuciones_hoy: {e}")
		return None


def get_reglas_con_errores(**kwargs):
	"""Obtener reglas con errores recientes"""
	try:
		# Últimas 24 horas
		end_date = datetime.now()
		start_date = end_date - timedelta(hours=24)

		count = frappe.db.count(
			"Rule Execution Log",
			{"creation": ["between", [start_date, end_date]], "execution_status": "Error"},
		)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Reglas con errores (24h)",
			"timestamp": datetime.now().isoformat(),
			"trend": "critical" if count > 5 else "warning" if count > 0 else "good",
		}

	except Exception as e:
		frappe.log_error(f"Error en get_reglas_con_errores: {e}")
		return None


def get_facturas_procesadas_reglas(**kwargs):
	"""Obtener facturas procesadas por reglas hoy"""
	try:
		today = datetime.now().date()

		# Contar facturas que pasaron por el motor de reglas
		count = frappe.db.count(
			"Sales Invoice",
			{
				"docstatus": 1,
				"creation": ["between", [today, today + timedelta(days=1)]],
				"custom_rules_applied": 1,
			},
		)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Facturas procesadas por reglas",
			"timestamp": datetime.now().isoformat(),
		}

	except Exception as e:
		frappe.log_error(f"Error en get_facturas_procesadas_reglas: {e}")
		return None


# Evaluadores de Alertas


def evaluar_reglas_fallando(context_data=None):
	"""Evaluar si hay reglas fallando repetidamente"""
	try:
		errores_data = get_reglas_con_errores()
		if errores_data and errores_data["value"] > 3:
			return {
				"triggered": True,
				"message": f"Reglas con errores: {errores_data['value']}",
				"priority": 6,
				"data": errores_data,
			}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_reglas_fallando: {e}")
		return {"triggered": False}


def evaluar_motor_inactivo(context_data=None):
	"""Evaluar si el motor de reglas está inactivo"""
	try:
		ejecuciones_data = get_ejecuciones_hoy()
		if ejecuciones_data and ejecuciones_data["value"] == 0:
			# Solo alertar después del mediodía
			if datetime.now().hour > 12:
				return {
					"triggered": True,
					"message": "Motor de reglas sin actividad hoy",
					"priority": 5,
					"data": ejecuciones_data,
				}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_motor_inactivo: {e}")
		return {"triggered": False}


def initialize_motor_reglas_integration():
	"""Inicializar integración del Motor de Reglas"""
	try:
		register_motor_reglas_kpis()
		register_motor_reglas_alerts()
		frappe.logger().info("Integración de Motor Reglas inicializada correctamente")
	except Exception as e:
		frappe.log_error(f"Error inicializando integración de Motor Reglas: {e}")
