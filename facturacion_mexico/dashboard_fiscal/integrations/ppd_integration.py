# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Integración del módulo PPD (Pagos en Parcialidades y Diferido) con el Dashboard Fiscal
Proporciona KPIs y alertas específicas para el manejo de pagos PPD
"""

from datetime import datetime, timedelta

import frappe


def register_ppd_kpis():
	"""Registrar KPIs del módulo PPD"""
	from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry

	kpis = {
		"facturas_ppd_activas": get_facturas_ppd_activas,
		"pagos_pendientes_revision": get_pagos_pendientes_revision,
		"complementos_pago_hoy": get_complementos_pago_hoy,
		"saldo_pendiente_total": get_saldo_pendiente_total,
		"facturas_vencidas_ppd": get_facturas_vencidas_ppd,
		"tasa_cumplimiento_ppd": get_tasa_cumplimiento_ppd,
	}

	DashboardRegistry.register_kpi("PPD", kpis)


def register_ppd_alerts():
	"""Registrar evaluadores de alertas del módulo PPD"""
	from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry

	alerts = {
		"facturas_vencidas_criticas": evaluar_facturas_vencidas_criticas,
		"saldo_pendiente_alto": evaluar_saldo_pendiente_alto,
		"complementos_pendientes": evaluar_complementos_pendientes,
		"validacion_sat_requerida": evaluar_validacion_sat_requerida,
	}

	DashboardRegistry.register_alert_evaluator("PPD", alerts)


def get_facturas_ppd_activas(**kwargs):
	"""Obtener número de facturas PPD activas"""
	try:
		company = kwargs.get("company")

		filters = {"docstatus": 1, "fm_metodo_pago": "PPD", "outstanding_amount": [">", 0]}

		if company:
			filters["company"] = company

		count = frappe.db.count("Sales Invoice", filters)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Facturas PPD activas",
			"timestamp": datetime.now().isoformat(),
			"drill_down": {"doctype": "Sales Invoice", "filters": filters},
		}

	except Exception as e:
		frappe.log_error(f"Error en get_facturas_ppd_activas: {e}")
		return None


def get_pagos_pendientes_revision(**kwargs):
	"""Obtener pagos pendientes de revisión SAT"""
	try:
		company = kwargs.get("company")

		filters = {"docstatus": 1, "custom_sat_validation_status": ["in", ["Pendiente", "En Proceso"]]}

		if company:
			filters["company"] = company

		count = frappe.db.count("Payment Entry", filters)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Pagos pendientes validación SAT",
			"timestamp": datetime.now().isoformat(),
			"trend": "warning" if count > 5 else "normal",
		}

	except Exception as e:
		frappe.log_error(f"Error en get_pagos_pendientes_revision: {e}")
		return None


def get_complementos_pago_hoy(**kwargs):
	"""Obtener complementos de pago generados hoy"""
	try:
		company = kwargs.get("company")
		today = datetime.now().date()

		filters = {
			"docstatus": 1,
			"creation": ["between", [today, today + timedelta(days=1)]],
			"custom_es_complemento_pago": 1,
		}

		if company:
			filters["company"] = company

		count = frappe.db.count("Payment Entry", filters)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Complementos pago hoy",
			"timestamp": datetime.now().isoformat(),
		}

	except Exception as e:
		frappe.log_error(f"Error en get_complementos_pago_hoy: {e}")
		return None


def get_saldo_pendiente_total(**kwargs):
	"""Obtener saldo total pendiente en facturas PPD"""
	try:
		company = kwargs.get("company")

		filters = {"docstatus": 1, "fm_metodo_pago": "PPD", "outstanding_amount": [">", 0]}

		if company:
			filters["company"] = company

		result = frappe.db.get_all(
			"Sales Invoice", filters=filters, fields=["sum(outstanding_amount) as total_pendiente"]
		)

		total_pendiente = result[0].total_pendiente if result and result[0].total_pendiente else 0

		return {
			"value": total_pendiente,
			"format": "currency",
			"subtitle": "Saldo pendiente total PPD",
			"timestamp": datetime.now().isoformat(),
			"trend": "warning" if total_pendiente > 1000000 else "normal",
		}

	except Exception as e:
		frappe.log_error(f"Error en get_saldo_pendiente_total: {e}")
		return None


def get_facturas_vencidas_ppd(**kwargs):
	"""Obtener facturas PPD vencidas"""
	try:
		company = kwargs.get("company")
		today = datetime.now().date()

		filters = {
			"docstatus": 1,
			"fm_metodo_pago": "PPD",
			"outstanding_amount": [">", 0],
			"due_date": ["<", today],
		}

		if company:
			filters["company"] = company

		count = frappe.db.count("Sales Invoice", filters)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Facturas PPD vencidas",
			"timestamp": datetime.now().isoformat(),
			"trend": "critical" if count > 10 else "warning" if count > 0 else "good",
		}

	except Exception as e:
		frappe.log_error(f"Error en get_facturas_vencidas_ppd: {e}")
		return None


def get_tasa_cumplimiento_ppd(**kwargs):
	"""Calcular tasa de cumplimiento de pagos PPD"""
	try:
		company = kwargs.get("company")
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=30)  # Últimos 30 días

		base_filters = {
			"docstatus": 1,
			"fm_metodo_pago": "PPD",
			"due_date": ["between", [start_date, end_date]],
		}

		if company:
			base_filters["company"] = company

		# Total de facturas que vencieron en el período
		total_vencidas = frappe.db.count("Sales Invoice", base_filters)

		if total_vencidas == 0:
			return {
				"value": 100,
				"format": "percentage",
				"subtitle": "Tasa cumplimiento PPD (30d)",
				"timestamp": datetime.now().isoformat(),
			}

		# Facturas pagadas a tiempo
		filters_cumplidas = {**base_filters, "outstanding_amount": 0}
		facturas_cumplidas = frappe.db.count("Sales Invoice", filters_cumplidas)

		tasa_cumplimiento = (facturas_cumplidas / total_vencidas) * 100

		return {
			"value": round(tasa_cumplimiento, 1),
			"format": "percentage",
			"subtitle": f"Cumplimiento PPD ({facturas_cumplidas}/{total_vencidas})",
			"timestamp": datetime.now().isoformat(),
			"trend": "good"
			if tasa_cumplimiento >= 90
			else "warning"
			if tasa_cumplimiento >= 70
			else "critical",
		}

	except Exception as e:
		frappe.log_error(f"Error en get_tasa_cumplimiento_ppd: {e}")
		return None


# Evaluadores de Alertas


def evaluar_facturas_vencidas_criticas(context_data=None):
	"""Evaluar si hay facturas vencidas críticas"""
	try:
		vencidas_data = get_facturas_vencidas_ppd()
		if vencidas_data and vencidas_data["value"] > 15:
			return {
				"triggered": True,
				"message": f"Facturas PPD vencidas críticas: {vencidas_data['value']}",
				"priority": 8,
				"data": vencidas_data,
			}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_facturas_vencidas_criticas: {e}")
		return {"triggered": False}


def evaluar_saldo_pendiente_alto(context_data=None):
	"""Evaluar si el saldo pendiente es muy alto"""
	try:
		saldo_data = get_saldo_pendiente_total()
		if saldo_data and saldo_data["value"] > 5000000:  # 5M MXN
			return {
				"triggered": True,
				"message": f"Saldo pendiente PPD alto: ${saldo_data['value']:,.2f}",
				"priority": 6,
				"data": saldo_data,
			}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_saldo_pendiente_alto: {e}")
		return {"triggered": False}


def evaluar_complementos_pendientes(context_data=None):
	"""Evaluar si hay muchos complementos pendientes de envío"""
	try:
		# Obtener complementos sin enviar al SAT
		filters = {
			"docstatus": 1,
			"custom_es_complemento_pago": 1,
			"custom_complemento_enviado_sat": 0,
			"creation": [">=", datetime.now() - timedelta(days=1)],
		}

		count = frappe.db.count("Payment Entry", filters)

		if count > 10:
			return {
				"triggered": True,
				"message": f"Complementos pendientes de envío SAT: {count}",
				"priority": 7,
				"data": {"count": count},
			}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_complementos_pendientes: {e}")
		return {"triggered": False}


def evaluar_validacion_sat_requerida(context_data=None):
	"""Evaluar si hay pagos que requieren validación SAT urgente"""
	try:
		# Pagos pendientes de validación por más de 24 horas
		cutoff_time = datetime.now() - timedelta(hours=24)

		filters = {
			"docstatus": 1,
			"custom_sat_validation_status": "Pendiente",
			"creation": ["<", cutoff_time],
		}

		count = frappe.db.count("Payment Entry", filters)

		if count > 0:
			return {
				"triggered": True,
				"message": f"Pagos requieren validación SAT urgente: {count}",
				"priority": 7,
				"data": {"count": count},
			}
		return {"triggered": False}

	except Exception as e:
		frappe.log_error(f"Error en evaluar_validacion_sat_requerida: {e}")
		return {"triggered": False}


# Función de inicialización para auto-registro
def initialize_ppd_integration():
	"""Inicializar integración de PPD con el Dashboard"""
	try:
		register_ppd_kpis()
		register_ppd_alerts()
		frappe.logger().info("Integración de PPD inicializada correctamente")
	except Exception as e:
		frappe.log_error(f"Error inicializando integración de PPD: {e}")
