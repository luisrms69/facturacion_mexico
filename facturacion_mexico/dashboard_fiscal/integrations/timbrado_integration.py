# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Integración del módulo Timbrado con el Dashboard Fiscal
Proporciona KPIs y alertas específicas para el proceso de timbrado CFDI
"""

from datetime import datetime, timedelta

import frappe


def register_timbrado_kpis():
	"""Registrar KPIs del módulo de Timbrado"""
	from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry

	kpis = {
		"facturas_timbradas_hoy": get_facturas_timbradas_hoy,
		"facturas_pendientes_timbrado": get_facturas_pendientes_timbrado,
		"tasa_exito_timbrado": get_tasa_exito_timbrado,
		"tiempo_promedio_timbrado": get_tiempo_promedio_timbrado,
		"errores_timbrado_recientes": get_errores_timbrado_recientes,
		"creditos_pac_restantes": get_creditos_pac_restantes,
	}

	DashboardRegistry.register_kpi("Timbrado", kpis)


def register_timbrado_alerts():
	"""Registrar evaluadores de alertas del módulo Timbrado"""
	from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry

	alerts = {
		"creditos_pac_bajos": evaluar_creditos_pac_bajos,
		"tasa_error_alta": evaluar_tasa_error_alta,
		"tiempo_timbrado_lento": evaluar_tiempo_timbrado_lento,
		"facturas_pendientes_criticas": evaluar_facturas_pendientes_criticas,
	}

	DashboardRegistry.register_alert_evaluator("Timbrado", alerts)


def get_facturas_timbradas_hoy(**kwargs):
	"""Obtener número de facturas timbradas hoy"""
	try:
		company = kwargs.get("company")
		today = datetime.now().date()

		filters = {
			"docstatus": 1,
			"creation": ["between", [today, today + timedelta(days=1)]],
			"fm_uuid": ["!=", ""],
		}

		if company:
			filters["company"] = company

		count = frappe.db.count("Sales Invoice", filters)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Facturas timbradas hoy",
			"timestamp": datetime.now().isoformat(),
			"drill_down": {"doctype": "Sales Invoice", "filters": filters},
		}

	except Exception as e:
		frappe.log_error(f"Error en get_facturas_timbradas_hoy: {e}")
		return None


def get_facturas_pendientes_timbrado(**kwargs):
	"""Obtener facturas pendientes de timbrar"""
	try:
		company = kwargs.get("company")

		filters = {
			"docstatus": 1,
			"fm_uuid": ["in", ["", None]],
			"custom_timbrado_status": ["in", ["Pendiente", "Error"]],
		}

		if company:
			filters["company"] = company

		count = frappe.db.count("Sales Invoice", filters)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Facturas pendientes de timbrar",
			"timestamp": datetime.now().isoformat(),
			"trend": "warning" if count > 10 else "normal",
			"drill_down": {"doctype": "Sales Invoice", "filters": filters},
		}

	except Exception as e:
		frappe.log_error(f"Error en get_facturas_pendientes_timbrado: {e}")
		return None


def get_tasa_exito_timbrado(**kwargs):
	"""Calcular tasa de éxito del timbrado en los últimos 7 días"""
	try:
		company = kwargs.get("company")
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=7)

		base_filters = {"docstatus": 1, "creation": ["between", [start_date, end_date + timedelta(days=1)]]}

		if company:
			base_filters["company"] = company

		# Total de facturas
		total_facturas = frappe.db.count("Sales Invoice", base_filters)

		if total_facturas == 0:
			return {
				"value": 0,
				"format": "percentage",
				"subtitle": "Tasa de éxito (7 días)",
				"timestamp": datetime.now().isoformat(),
			}

		# Facturas timbradas exitosamente
		filters_exitosas = {**base_filters, "fm_uuid": ["!=", ""]}
		facturas_exitosas = frappe.db.count("Sales Invoice", filters_exitosas)

		tasa_exito = (facturas_exitosas / total_facturas) * 100

		return {
			"value": round(tasa_exito, 1),
			"format": "percentage",
			"subtitle": f"Tasa de éxito ({facturas_exitosas}/{total_facturas})",
			"timestamp": datetime.now().isoformat(),
			"trend": "good" if tasa_exito >= 95 else "warning" if tasa_exito >= 85 else "critical",
		}

	except Exception as e:
		frappe.log_error(f"Error en get_tasa_exito_timbrado: {e}")
		return None


def get_tiempo_promedio_timbrado(**kwargs):
	"""Calcular tiempo promedio de timbrado"""
	try:
		company = kwargs.get("company")
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=1)  # Últimas 24 horas

		filters = {
			"docstatus": 1,
			"creation": ["between", [start_date, end_date + timedelta(days=1)]],
			"fm_uuid": ["!=", ""],
			"custom_timbrado_time": ["!=", None],
		}

		if company:
			filters["company"] = company

		# Obtener tiempos de timbrado
		tiempos = frappe.db.get_all(
			"Sales Invoice", filters=filters, fields=["custom_timbrado_time"], limit=100
		)

		if not tiempos:
			return {
				"value": 0,
				"format": "number",
				"subtitle": "Tiempo promedio (seg)",
				"timestamp": datetime.now().isoformat(),
			}

		tiempo_promedio = sum(t.custom_timbrado_time or 0 for t in tiempos) / len(tiempos)

		return {
			"value": round(tiempo_promedio, 1),
			"format": "number",
			"subtitle": "Tiempo promedio timbrado (seg)",
			"timestamp": datetime.now().isoformat(),
			"trend": "good" if tiempo_promedio <= 10 else "warning" if tiempo_promedio <= 30 else "critical",
		}

	except Exception as e:
		frappe.log_error(f"Error en get_tiempo_promedio_timbrado: {e}")
		return None


def get_errores_timbrado_recientes(**kwargs):
	"""Obtener errores de timbrado en las últimas 24 horas"""
	try:
		company = kwargs.get("company")
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=1)

		filters = {
			"docstatus": 1,
			"creation": ["between", [start_date, end_date + timedelta(days=1)]],
			"custom_timbrado_status": "Error",
		}

		if company:
			filters["company"] = company

		count = frappe.db.count("Sales Invoice", filters)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Errores últimas 24h",
			"timestamp": datetime.now().isoformat(),
			"trend": "critical" if count > 5 else "warning" if count > 0 else "good",
		}

	except Exception as e:
		frappe.log_error(f"Error en get_errores_timbrado_recientes: {e}")
		return None


def get_creditos_pac_restantes(**kwargs):
	"""Obtener créditos PAC restantes (mock - implementar según PAC)"""
	try:
		# Esto sería una llamada real al PAC para obtener saldo
		# Por ahora retornamos un valor simulado

		return {
			"value": 1500,  # Valor simulado
			"format": "number",
			"subtitle": "Créditos PAC restantes",
			"timestamp": datetime.now().isoformat(),
			"trend": "critical" if 1500 < 100 else "warning" if 1500 < 500 else "good",
		}

	except Exception as e:
		frappe.log_error(f"Error en get_creditos_pac_restantes: {e}")
		return None


# Evaluadores de Alertas


def evaluar_creditos_pac_bajos(context_data=None):
	"""Evaluar si los créditos PAC están bajos"""
	try:
		kpi_data = get_creditos_pac_restantes()
		if kpi_data and kpi_data["value"] < 100:
			return {
				"triggered": True,
				"message": f"Créditos PAC críticos: {kpi_data['value']} restantes",
				"priority": 9,
				"data": kpi_data,
			}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_creditos_pac_bajos: {e}")
		return {"triggered": False}


def evaluar_tasa_error_alta(context_data=None):
	"""Evaluar si la tasa de error es alta"""
	try:
		tasa_data = get_tasa_exito_timbrado()
		if tasa_data and tasa_data["value"] < 85:
			return {
				"triggered": True,
				"message": f"Tasa de éxito de timbrado baja: {tasa_data['value']}%",
				"priority": 7,
				"data": tasa_data,
			}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_tasa_error_alta: {e}")
		return {"triggered": False}


def evaluar_tiempo_timbrado_lento(context_data=None):
	"""Evaluar si el tiempo de timbrado es lento"""
	try:
		tiempo_data = get_tiempo_promedio_timbrado()
		if tiempo_data and tiempo_data["value"] > 30:
			return {
				"triggered": True,
				"message": f"Tiempo de timbrado lento: {tiempo_data['value']} segundos",
				"priority": 5,
				"data": tiempo_data,
			}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_tiempo_timbrado_lento: {e}")
		return {"triggered": False}


def evaluar_facturas_pendientes_criticas(context_data=None):
	"""Evaluar si hay muchas facturas pendientes"""
	try:
		pendientes_data = get_facturas_pendientes_timbrado()
		if pendientes_data and pendientes_data["value"] > 20:
			return {
				"triggered": True,
				"message": f"Facturas pendientes críticas: {pendientes_data['value']}",
				"priority": 8,
				"data": pendientes_data,
			}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_facturas_pendientes_criticas: {e}")
		return {"triggered": False}


# Función de inicialización para auto-registro
def initialize_timbrado_integration():
	"""Inicializar integración de Timbrado con el Dashboard"""
	try:
		register_timbrado_kpis()
		register_timbrado_alerts()
		frappe.logger().info("Integración de Timbrado inicializada correctamente")
	except Exception as e:
		frappe.log_error(f"Error inicializando integración de Timbrado: {e}")
