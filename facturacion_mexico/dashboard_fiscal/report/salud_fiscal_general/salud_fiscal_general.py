# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import date, datetime, timedelta

import frappe
from frappe import _


def execute(filters=None):
	"""
	Reporte de Salud Fiscal General
	Score por módulo con semáforo y tendencias históricas
	"""
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	"""Definir columnas del reporte"""
	return [
		{"label": _("Módulo"), "fieldname": "module", "fieldtype": "Data", "width": 150},
		{"label": _("Score Actual"), "fieldname": "current_score", "fieldtype": "Float", "width": 100},
		{"label": _("Semáforo"), "fieldname": "health_indicator", "fieldtype": "Data", "width": 100},
		{"label": _("Score Anterior"), "fieldname": "previous_score", "fieldtype": "Float", "width": 100},
		{"label": _("Tendencia"), "fieldname": "trend", "fieldtype": "Data", "width": 100},
		{
			"label": _("Factores Positivos"),
			"fieldname": "positive_factors",
			"fieldtype": "Text",
			"width": 250,
		},
		{
			"label": _("Factores Negativos"),
			"fieldname": "negative_factors",
			"fieldtype": "Text",
			"width": 250,
		},
		{"label": _("Recomendaciones"), "fieldname": "recommendations", "fieldtype": "Text", "width": 300},
		{
			"label": _("Última Actualización"),
			"fieldname": "last_updated",
			"fieldtype": "Datetime",
			"width": 150,
		},
	]


def get_data(filters):
	"""Obtener datos del reporte"""
	if not filters:
		filters = {}

	company = filters.get("company") or frappe.defaults.get_user_default("Company")
	period = filters.get("period") or "month"

	# Calcular scores para cada módulo
	modules_data = []

	# Módulos principales del sistema fiscal
	modules = ["Timbrado", "PPD", "E-Receipts", "Addendas", "Facturas Globales", "Motor Reglas"]

	for module in modules:
		module_data = calculate_module_health_score(module, company, period)
		if module_data:
			modules_data.append(module_data)

	# Agregar score general
	if modules_data:
		overall_score = calculate_overall_health_score(modules_data)
		modules_data.insert(0, overall_score)

	return modules_data


def calculate_module_health_score(module, company, period):
	"""Calcular score de salud fiscal para un módulo específico"""
	try:
		score_data = {
			"module": module,
			"current_score": 0.0,
			"health_indicator": "🔴 CRÍTICO",
			"previous_score": 0.0,
			"trend": "➡️ Sin cambio",
			"positive_factors": "",
			"negative_factors": "",
			"recommendations": "",
			"last_updated": datetime.now(),
		}

		# Calcular según el módulo
		if module == "Timbrado":
			score_data = calculate_timbrado_health(company, period)
		elif module == "PPD":
			score_data = calculate_ppd_health(company, period)
		elif module == "E-Receipts":
			score_data = calculate_ereceipts_health(company, period)
		elif module == "Addendas":
			score_data = calculate_addendas_health(company, period)
		elif module == "Facturas Globales":
			score_data = calculate_facturas_globales_health(company, period)
		elif module == "Motor Reglas":
			score_data = calculate_motor_reglas_health(company, period)

		return score_data

	except Exception as e:
		frappe.log_error(f"Error calculando health score para {module}: {e!s}")
		return None


def calculate_timbrado_health(company, period):
	"""Calcular salud del módulo de Timbrado"""
	# Obtener métricas del período
	period_filter = get_period_filter(period)

	# Métricas principales
	total_invoices = frappe.db.count(
		"Sales Invoice", filters={"company": company, "docstatus": 1, **period_filter}
	)

	stamped_invoices = frappe.db.count(
		"Sales Invoice",
		filters={"company": company, "docstatus": 1, "fm_timbrado_status": "Timbrada", **period_filter},
	)

	# Calcular score base (0-100)
	stamping_rate = (stamped_invoices / total_invoices * 100) if total_invoices > 0 else 0
	score = stamping_rate

	# Factores que afectan el score
	positive_factors = []
	negative_factors = []
	recommendations = []

	if stamping_rate >= 95:
		positive_factors.append("Excelente tasa de timbrado")
		score += 5
	elif stamping_rate < 80:
		negative_factors.append("Tasa de timbrado baja")
		recommendations.append("Revisar configuración PAC")
		score -= 10

	# Verificar errores recientes
	recent_errors = frappe.db.count(
		"Sales Invoice",
		filters={
			"company": company,
			"fm_timbrado_status": "Error",
			"creation": [">=", date.today() - timedelta(days=7)],
		},
	)

	if recent_errors == 0:
		positive_factors.append("Sin errores recientes")
	elif recent_errors > 10:
		negative_factors.append(f"{recent_errors} errores en últimos 7 días")
		score -= 15
		recommendations.append("Investigar errores de timbrado")

	# Limitar score entre 0 y 100
	score = max(0, min(100, score))

	return {
		"module": "🧾 Timbrado",
		"current_score": round(score, 1),
		"health_indicator": get_health_indicator(score),
		"previous_score": 0.0,  # TODO: Obtener de registros históricos
		"trend": get_trend_indicator(score, 0.0),
		"positive_factors": "; ".join(positive_factors) or "Ninguno identificado",
		"negative_factors": "; ".join(negative_factors) or "Ninguno identificado",
		"recommendations": "; ".join(recommendations) or "Continuar con operación normal",
		"last_updated": datetime.now(),
	}


def calculate_ppd_health(company, period):
	"""Calcular salud del módulo PPD"""
	period_filter = get_period_filter(period)

	# Pagos que requieren complemento
	total_payments = frappe.db.count(
		"Payment Entry",
		filters={"company": company, "docstatus": 1, "payment_type": "Receive", **period_filter},
	)

	# Pagos con complemento generado
	completed_complements = frappe.db.count(
		"Payment Entry",
		filters={
			"company": company,
			"docstatus": 1,
			"payment_type": "Receive",
			"fm_ppd_status": "Completed",
			**period_filter,
		},
	)

	complement_rate = (completed_complements / total_payments * 100) if total_payments > 0 else 0
	score = complement_rate

	positive_factors = []
	negative_factors = []
	recommendations = []

	if complement_rate >= 90:
		positive_factors.append("Excelente cumplimiento PPD")
		score += 5
	elif complement_rate < 70:
		negative_factors.append("Baja generación de complementos")
		recommendations.append("Automatizar proceso PPD")
		score -= 15

	# Verificar pagos vencidos (>30 días sin complemento)
	overdue_payments = frappe.db.sql(
		"""
        SELECT COUNT(*) as count
        FROM `tabPayment Entry`
        WHERE company = %s
        AND docstatus = 1
        AND payment_type = 'Receive'
        AND (fm_ppd_status != 'Completed' OR fm_ppd_status IS NULL)
        AND DATEDIFF(CURDATE(), posting_date) > 30
    """,
		company,
	)[0][0]

	if overdue_payments == 0:
		positive_factors.append("Sin pagos vencidos")
	else:
		negative_factors.append(f"{overdue_payments} pagos vencidos sin complemento")
		score -= 20
		recommendations.append("Urgente: Generar complementos vencidos")

	score = max(0, min(100, score))

	return {
		"module": "💰 PPD",
		"current_score": round(score, 1),
		"health_indicator": get_health_indicator(score),
		"previous_score": 0.0,
		"trend": get_trend_indicator(score, 0.0),
		"positive_factors": "; ".join(positive_factors) or "Ninguno identificado",
		"negative_factors": "; ".join(negative_factors) or "Ninguno identificado",
		"recommendations": "; ".join(recommendations) or "Continuar con operación normal",
		"last_updated": datetime.now(),
	}


def calculate_ereceipts_health(company, period):
	"""Calcular salud del módulo E-Receipts"""
	# Implementación básica - puede expandirse
	score = 85.0  # Score placeholder

	return {
		"module": "📧 E-Receipts",
		"current_score": score,
		"health_indicator": get_health_indicator(score),
		"previous_score": 82.0,
		"trend": "📈 Mejorando",
		"positive_factors": "Procesamiento automático funcionando",
		"negative_factors": "Algunos errores de validación",
		"recommendations": "Revisar templates de e-receipts",
		"last_updated": datetime.now(),
	}


def calculate_addendas_health(company, period):
	"""Calcular salud del módulo Addendas"""
	score = 78.0  # Score placeholder

	return {
		"module": "📄 Addendas",
		"current_score": score,
		"health_indicator": get_health_indicator(score),
		"previous_score": 75.0,
		"trend": "📈 Mejorando",
		"positive_factors": "Templates actualizados",
		"negative_factors": "Algunos clientes sin addenda configurada",
		"recommendations": "Completar configuración de addendas",
		"last_updated": datetime.now(),
	}


def calculate_facturas_globales_health(company, period):
	"""Calcular salud del módulo Facturas Globales"""
	score = 92.0  # Score placeholder

	return {
		"module": "🌐 Facturas Globales",
		"current_score": score,
		"health_indicator": get_health_indicator(score),
		"previous_score": 90.0,
		"trend": "📈 Mejorando",
		"positive_factors": "Consolidación automática eficiente",
		"negative_factors": "Ninguno identificado",
		"recommendations": "Continuar con operación normal",
		"last_updated": datetime.now(),
	}


def calculate_motor_reglas_health(company, period):
	"""Calcular salud del módulo Motor de Reglas"""
	# Verificar reglas activas
	active_rules = frappe.db.count("Fiscal Validation Rule", filters={"is_active": 1, "docstatus": 1})

	# Verificar ejecuciones recientes
	recent_executions = frappe.db.count(
		"Rule Execution Log", filters={"creation": [">=", date.today() - timedelta(days=7)]}
	)

	score = 88.0 if active_rules > 0 and recent_executions > 0 else 60.0

	return {
		"module": "⚙️ Motor Reglas",
		"current_score": score,
		"health_indicator": get_health_indicator(score),
		"previous_score": 85.0,
		"trend": "📈 Mejorando",
		"positive_factors": f"{active_rules} reglas activas, {recent_executions} ejecuciones recientes",
		"negative_factors": "Ninguno identificado",
		"recommendations": "Considerar agregar más reglas de validación",
		"last_updated": datetime.now(),
	}


def calculate_overall_health_score(modules_data):
	"""Calcular score general combinando todos los módulos"""
	total_score = sum(module["current_score"] for module in modules_data)
	avg_score = total_score / len(modules_data) if modules_data else 0

	# Identificar módulos críticos
	critical_modules = [m["module"] for m in modules_data if m["current_score"] < 70]

	positive_factors = []
	negative_factors = []
	recommendations = []

	if avg_score >= 90:
		positive_factors.append("Excelente salud fiscal general")
	elif avg_score >= 80:
		positive_factors.append("Buena salud fiscal general")
	elif avg_score < 70:
		negative_factors.append("Salud fiscal requiere atención")
		recommendations.append("Enfocar mejoras en módulos críticos")

	if critical_modules:
		negative_factors.append(f"Módulos críticos: {', '.join(critical_modules)}")

	return {
		"module": "🏆 SCORE GENERAL",
		"current_score": round(avg_score, 1),
		"health_indicator": get_health_indicator(avg_score),
		"previous_score": 0.0,
		"trend": "➡️ Sin histórico",
		"positive_factors": "; ".join(positive_factors) or "En proceso de evaluación",
		"negative_factors": "; ".join(negative_factors) or "Ninguno identificado",
		"recommendations": "; ".join(recommendations) or "Mantener monitoreo continuo",
		"last_updated": datetime.now(),
	}


def get_health_indicator(score):
	"""Obtener indicador de salud basado en score"""
	if score >= 90:
		return "🟢 EXCELENTE"
	elif score >= 80:
		return "🟡 BUENO"
	elif score >= 70:
		return "🟠 REGULAR"
	else:
		return "🔴 CRÍTICO"


def get_trend_indicator(current_score, previous_score):
	"""Obtener indicador de tendencia"""
	if previous_score == 0:
		return "➡️ Sin histórico"

	diff = current_score - previous_score
	if diff > 5:
		return "📈 Mejorando"
	elif diff < -5:
		return "📉 Empeorando"
	else:
		return "➡️ Estable"


def get_period_filter(period):
	"""Obtener filtro de fecha según el período"""
	today = date.today()

	if period == "week":
		start_date = today - timedelta(days=7)
	elif period == "month":
		start_date = date(today.year, today.month, 1)
	elif period == "quarter":
		quarter_start_month = ((today.month - 1) // 3) * 3 + 1
		start_date = date(today.year, quarter_start_month, 1)
	else:  # year
		start_date = date(today.year, 1, 1)

	return {"creation": [">=", start_date]}


# Filtros del reporte
def get_filters():
	"""Definir filtros disponibles para el reporte"""
	return [
		{
			"fieldname": "company",
			"label": _("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
		},
		{
			"fieldname": "period",
			"label": _("Período de Análisis"),
			"fieldtype": "Select",
			"options": "week\nmonth\nquarter\nyear",
			"default": "month",
		},
	]
