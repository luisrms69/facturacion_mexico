# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Proyección de Folios por Sucursal - Sprint 6 Phase 5
Reporte para proyectar agotamiento de folios por sucursal
"""

import math
from datetime import datetime, timedelta

import frappe
from frappe import _


def execute(filters=None):
	"""Ejecutar reporte de proyección de folios"""
	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data, filters)
	chart = get_chart_data(data, filters)

	return columns, data, None, chart, summary


def get_columns():
	"""Definir columnas del reporte"""
	return [
		{
			"fieldname": "branch",
			"label": _("Sucursal"),
			"fieldtype": "Link",
			"options": "Branch",
			"width": 150,
		},
		{
			"fieldname": "branch_name",
			"label": _("Nombre Sucursal"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "serie",
			"label": _("Serie"),
			"fieldtype": "Data",
			"width": 80,
		},
		{
			"fieldname": "folio_start",
			"label": _("Folio Inicial"),
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"fieldname": "folio_end",
			"label": _("Folio Final"),
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"fieldname": "folio_current",
			"label": _("Folio Actual"),
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"fieldname": "folios_used",
			"label": _("Folios Usados"),
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"fieldname": "folios_remaining",
			"label": _("Folios Restantes"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "usage_percentage",
			"label": _("% Utilizado"),
			"fieldtype": "Percent",
			"width": 100,
		},
		{
			"fieldname": "daily_average",
			"label": _("Promedio Diario"),
			"fieldtype": "Float",
			"width": 120,
			"precision": 2,
		},
		{
			"fieldname": "monthly_trend",
			"label": _("Tendencia Mensual"),
			"fieldtype": "Float",
			"width": 130,
			"precision": 2,
		},
		{
			"fieldname": "projected_depletion_date",
			"label": _("Fecha Agotamiento"),
			"fieldtype": "Date",
			"width": 140,
		},
		{
			"fieldname": "days_remaining",
			"label": _("Días Restantes"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "risk_level",
			"label": _("Nivel de Riesgo"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "recommended_action",
			"label": _("Acción Recomendada"),
			"fieldtype": "Data",
			"width": 200,
		},
	]


def get_data(filters):
	"""Obtener datos del reporte"""
	conditions = get_conditions(filters)
	months_ahead = filters.get("months_ahead", 6)
	alert_threshold = filters.get("alert_threshold", 80)

	# Obtener configuraciones fiscales activas
	query = f"""
		SELECT
			b.name as branch,
			b.branch_name,
			cfs.fm_serie_cfdi as serie,
			cfs.fm_folio_start as folio_start,
			cfs.fm_folio_end as folio_end,
			cfs.fm_folio_current as folio_current,
			cfs.fm_is_active as is_active,
			cfs.fm_date_activated as date_activated
		FROM `tabBranch` b
		INNER JOIN `tabConfiguración Fiscal Sucursal` cfs ON cfs.parent = b.name
		WHERE cfs.fm_is_active = 1 {conditions}
		ORDER BY b.name, cfs.fm_serie_cfdi
	"""

	fiscal_configs = frappe.db.sql(query, filters, as_dict=True)

	data = []
	today = datetime.now().date()

	for config in fiscal_configs:
		# Calcular estadísticas básicas
		folios_used = config.get("folio_current", 1) - config.get("folio_start", 1)
		total_folios = config.get("folio_end", 1) - config.get("folio_start", 1) + 1
		folios_remaining = total_folios - folios_used
		usage_percentage = (folios_used / total_folios * 100) if total_folios > 0 else 0

		# Calcular tendencias de uso
		daily_average = calculate_daily_average(config["branch"], config["serie"])
		monthly_trend = calculate_monthly_trend(config["branch"], config["serie"])

		# Proyectar fecha de agotamiento
		projected_date, days_remaining = calculate_depletion_projection(
			folios_remaining, daily_average, today
		)

		# Determinar nivel de riesgo
		risk_level = determine_risk_level(
			usage_percentage, days_remaining, alert_threshold, months_ahead * 30
		)

		# Recomendaciones
		recommended_action = get_recommended_action(
			risk_level, days_remaining, folios_remaining, monthly_trend
		)

		row = {
			"branch": config["branch"],
			"branch_name": config["branch_name"],
			"serie": config["serie"] or "DEFAULT",
			"folio_start": config["folio_start"],
			"folio_end": config["folio_end"],
			"folio_current": config["folio_current"],
			"folios_used": folios_used,
			"folios_remaining": folios_remaining,
			"usage_percentage": usage_percentage,
			"daily_average": daily_average,
			"monthly_trend": monthly_trend,
			"projected_depletion_date": projected_date,
			"days_remaining": days_remaining,
			"risk_level": risk_level,
			"recommended_action": recommended_action,
		}

		data.append(row)

	return data


def get_conditions(filters):
	"""Construir condiciones WHERE del query"""
	conditions = []

	if filters.get("branch"):
		conditions.append("b.name = %(branch)s")

	if filters.get("serie_filter"):
		conditions.append("cfs.fm_serie_cfdi = %(serie_filter)s")

	if not filters.get("include_inactive"):
		conditions.append("b.disabled = 0")

	return " AND " + " AND ".join(conditions) if conditions else ""


def calculate_daily_average(branch, serie):
	"""Calcular promedio diario de uso de folios"""
	try:
		# Obtener facturas de los últimos 30 días
		result = frappe.db.sql(
			"""
			SELECT COUNT(*) as invoice_count
			FROM `tabSales Invoice`
			WHERE fm_branch = %s
			AND fm_serie_cfdi = %s
			AND docstatus = 1
			AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
		""",
			(branch, serie or "DEFAULT"),
		)

		invoice_count = result[0][0] if result else 0
		return round(invoice_count / 30.0, 2)

	except Exception:
		return 0.0


def calculate_monthly_trend(branch, serie):
	"""Calcular tendencia mensual de uso"""
	try:
		# Comparar últimos 30 días vs 30 días anteriores
		current_month = frappe.db.sql(
			"""
			SELECT COUNT(*) as count
			FROM `tabSales Invoice`
			WHERE fm_branch = %s
			AND fm_serie_cfdi = %s
			AND docstatus = 1
			AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
		""",
			(branch, serie or "DEFAULT"),
		)

		previous_month = frappe.db.sql(
			"""
			SELECT COUNT(*) as count
			FROM `tabSales Invoice`
			WHERE fm_branch = %s
			AND fm_serie_cfdi = %s
			AND docstatus = 1
			AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
			AND posting_date < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
		""",
			(branch, serie or "DEFAULT"),
		)

		current = current_month[0][0] if current_month else 0
		previous = previous_month[0][0] if previous_month else 1

		if previous == 0:
			return 0.0

		trend = ((current - previous) / previous) * 100
		return round(trend, 2)

	except Exception:
		return 0.0


def calculate_depletion_projection(folios_remaining, daily_average, today):
	"""Calcular proyección de agotamiento"""
	if daily_average <= 0 or folios_remaining <= 0:
		return None, 999999  # Sin proyección válida

	days_to_depletion = math.ceil(folios_remaining / daily_average)
	projected_date = today + timedelta(days=days_to_depletion)

	return projected_date, days_to_depletion


def determine_risk_level(usage_percentage, days_remaining, alert_threshold, projection_period):
	"""Determinar nivel de riesgo"""
	if usage_percentage >= 95:
		return "🔴 Crítico"
	elif usage_percentage >= alert_threshold:
		return "🟠 Alto"
	elif days_remaining <= 30:
		return "🟡 Medio"
	elif days_remaining <= projection_period:
		return "🟢 Bajo"
	else:
		return "⚪ Normal"


def get_recommended_action(risk_level, days_remaining, folios_remaining, monthly_trend):
	"""Obtener recomendación de acción"""
	if "Crítico" in risk_level:
		return "⚡ URGENTE: Renovar folios inmediatamente"
	elif "Alto" in risk_level:
		return "📞 Contactar SAT para renovación"
	elif "Medio" in risk_level:
		return "📅 Programar renovación en 2 semanas"
	elif days_remaining <= 60:
		return "📋 Preparar documentación para renovación"
	elif monthly_trend > 50:
		return "📈 Monitorear incremento en uso"
	elif folios_remaining < 1000:
		return "📊 Revisar asignación de folios"
	else:
		return "✅ Sin acción requerida"


def get_summary(data, filters):
	"""Generar resumen del reporte"""
	if not data:
		return []

	# Estadísticas generales
	total_branches = len(set(row["branch"] for row in data))
	total_series = len(data)

	# Análisis de riesgo
	critical_risk = len([row for row in data if "Crítico" in row["risk_level"]])
	high_risk = len([row for row in data if "Alto" in row["risk_level"]])
	medium_risk = len([row for row in data if "Medio" in row["risk_level"]])

	# Folios totales
	total_folios_remaining = sum(row["folios_remaining"] for row in data)
	total_usage_percentage = sum(row["usage_percentage"] for row in data) / len(data)

	# Próximos vencimientos
	near_depletion = len([row for row in data if row["days_remaining"] <= 30])

	# Tendencias
	positive_trend = len([row for row in data if row["monthly_trend"] > 10])
	negative_trend = len([row for row in data if row["monthly_trend"] < -10])

	summary = [
		{"label": _("Total Sucursales"), "value": total_branches, "indicator": "blue"},
		{"label": _("Series Configuradas"), "value": total_series, "indicator": "blue"},
		{
			"label": _("Riesgo Crítico"),
			"value": critical_risk,
			"indicator": "red" if critical_risk > 0 else "green",
		},
		{"label": _("Riesgo Alto"), "value": high_risk, "indicator": "orange" if high_risk > 0 else "green"},
		{
			"label": _("Riesgo Medio"),
			"value": medium_risk,
			"indicator": "yellow" if medium_risk > 0 else "green",
		},
		{"label": _("Folios Restantes"), "value": f"{total_folios_remaining:,}", "indicator": "blue"},
		{
			"label": _("% Uso Promedio"),
			"value": f"{total_usage_percentage:.1f}%",
			"indicator": "orange" if total_usage_percentage > 80 else "green",
		},
		{
			"label": _("Próximos a Agotar (30 días)"),
			"value": near_depletion,
			"indicator": "red" if near_depletion > 0 else "green",
		},
		{
			"label": _("Tendencia al Alza"),
			"value": f"{positive_trend} series",
			"indicator": "yellow" if positive_trend > 0 else "blue",
		},
		{
			"label": _("Tendencia a la Baja"),
			"value": f"{negative_trend} series",
			"indicator": "green" if negative_trend > 0 else "blue",
		},
	]

	return summary


def get_chart_data(data, filters):
	"""Generar datos para gráfico"""
	if not data:
		return None

	# Gráfico de distribución por nivel de riesgo
	risk_counts = {}
	for row in data:
		risk = (
			row["risk_level"]
			.replace("🔴 ", "")
			.replace("🟠 ", "")
			.replace("🟡 ", "")
			.replace("🟢 ", "")
			.replace("⚪ ", "")
		)
		risk_counts[risk] = risk_counts.get(risk, 0) + 1

	return {
		"data": {
			"labels": list(risk_counts.keys()),
			"datasets": [{"name": "Series por Nivel de Riesgo", "values": list(risk_counts.values())}],
		},
		"type": "pie",
		"height": 300,
		"colors": ["#dc3545", "#fd7e14", "#ffc107", "#28a745", "#6c757d"],
	}
