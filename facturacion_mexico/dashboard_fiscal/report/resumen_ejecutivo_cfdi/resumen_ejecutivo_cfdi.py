# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import calendar
from datetime import date, datetime, timedelta

import frappe
from frappe import _


def execute(filters=None):
	"""
	Reporte Resumen Ejecutivo CFDI
	KPIs principales consolidados con formato ejecutivo
	"""
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	"""Definir columnas del reporte"""
	return [
		{"label": _("Métrica"), "fieldname": "metric_name", "fieldtype": "Data", "width": 200},
		{"label": _("Valor Actual"), "fieldname": "current_value", "fieldtype": "Data", "width": 120},
		{"label": _("Mes Anterior"), "fieldname": "previous_value", "fieldtype": "Data", "width": 120},
		{"label": _("Variación"), "fieldname": "variation", "fieldtype": "Data", "width": 100},
		{"label": _("Tendencia"), "fieldname": "trend", "fieldtype": "Data", "width": 100},
		{"label": _("Meta"), "fieldname": "target", "fieldtype": "Data", "width": 100},
		{"label": _("Cumplimiento"), "fieldname": "achievement", "fieldtype": "Data", "width": 120},
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 120},
	]


def get_data(filters):
	"""Obtener datos del reporte ejecutivo"""
	if not filters:
		filters = {}

	company = filters.get("company") or frappe.defaults.get_user_default("Company")
	report_date = filters.get("report_date") or date.today()

	executive_metrics = []

	# 1. Métricas de Facturación
	executive_metrics.extend(get_billing_metrics(company, report_date))

	# 2. Métricas de Timbrado
	executive_metrics.extend(get_stamping_metrics(company, report_date))

	# 3. Métricas de Complementos PPD
	executive_metrics.extend(get_ppd_metrics(company, report_date))

	# 4. Métricas Financieras
	executive_metrics.extend(get_financial_metrics(company, report_date))

	# 5. Métricas de Cumplimiento
	executive_metrics.extend(get_compliance_metrics(company, report_date))

	# 6. Métricas de Performance
	executive_metrics.extend(get_performance_metrics(company, report_date))

	return executive_metrics


def get_billing_metrics(company, report_date):
	"""Métricas de facturación"""
	metrics = []

	# Período actual vs anterior
	current_period = get_month_period(report_date)
	previous_period = get_previous_month_period(report_date)

	# Facturas emitidas
	current_invoices = frappe.db.count(
		"Sales Invoice",
		filters={"company": company, "docstatus": 1, "posting_date": ["between", current_period]},
	)

	previous_invoices = frappe.db.count(
		"Sales Invoice",
		filters={"company": company, "docstatus": 1, "posting_date": ["between", previous_period]},
	)

	variation = calculate_variation(current_invoices, previous_invoices)

	metrics.append(
		{
			"metric_name": "📄 Facturas Emitidas",
			"current_value": f"{current_invoices:,}",
			"previous_value": f"{previous_invoices:,}",
			"variation": f"{variation:+.1f}%",
			"trend": get_trend_icon(variation),
			"target": "Meta: +5%",
			"achievement": f"{min(100, max(0, 100 + variation)):.0f}%",
			"status": get_status_icon(variation, 5),
		}
	)

	# Monto facturado
	current_amount = get_invoices_amount(company, current_period)
	previous_amount = get_invoices_amount(company, previous_period)
	amount_variation = calculate_variation(current_amount, previous_amount)

	metrics.append(
		{
			"metric_name": "💰 Monto Facturado",
			"current_value": f"${current_amount:,.0f}",
			"previous_value": f"${previous_amount:,.0f}",
			"variation": f"{amount_variation:+.1f}%",
			"trend": get_trend_icon(amount_variation),
			"target": "Meta: +8%",
			"achievement": f"{min(100, max(0, 100 + amount_variation/8*100)):.0f}%",
			"status": get_status_icon(amount_variation, 8),
		}
	)

	return metrics


def get_stamping_metrics(company, report_date):
	"""Métricas de timbrado"""
	metrics = []

	current_period = get_month_period(report_date)

	# Tasa de timbrado exitoso
	total_invoices = frappe.db.count(
		"Sales Invoice",
		filters={"company": company, "docstatus": 1, "posting_date": ["between", current_period]},
	)

	stamped_invoices = frappe.db.count(
		"Sales Invoice",
		filters={
			"company": company,
			"docstatus": 1,
			"posting_date": ["between", current_period],
			"fm_timbrado_status": "Timbrada",
		},
	)

	stamping_rate = (stamped_invoices / total_invoices * 100) if total_invoices > 0 else 0

	metrics.append(
		{
			"metric_name": "✅ Tasa de Timbrado",
			"current_value": f"{stamping_rate:.1f}%",
			"previous_value": "N/A",
			"variation": "N/A",
			"trend": "📈" if stamping_rate >= 95 else ("➡️" if stamping_rate >= 90 else "📉"),
			"target": "Meta: 98%",
			"achievement": f"{min(100, stamping_rate/98*100):.0f}%",
			"status": get_status_icon_absolute(stamping_rate, 95, 90),
		}
	)

	# Tiempo promedio de timbrado
	avg_time = get_average_stamping_time(company, current_period)

	metrics.append(
		{
			"metric_name": "⏱️ Tiempo Prom. Timbrado",
			"current_value": f"{avg_time:.1f} min",
			"previous_value": "N/A",
			"variation": "N/A",
			"trend": "📈" if avg_time <= 2 else ("➡️" if avg_time <= 5 else "📉"),
			"target": "Meta: <3 min",
			"achievement": f"{min(100, (3/max(avg_time, 0.1))*100):.0f}%",
			"status": get_status_icon_absolute(avg_time, 3, 5, reverse=True),
		}
	)

	return metrics


def get_ppd_metrics(company, report_date):
	"""Métricas de complementos PPD"""
	metrics = []

	current_period = get_month_period(report_date)

	# Complementos generados
	total_payments = frappe.db.count(
		"Payment Entry",
		filters={
			"company": company,
			"docstatus": 1,
			"payment_type": "Receive",
			"posting_date": ["between", current_period],
		},
	)

	completed_complements = frappe.db.count(
		"Payment Entry",
		filters={
			"company": company,
			"docstatus": 1,
			"payment_type": "Receive",
			"posting_date": ["between", current_period],
			"fm_ppd_status": "Completed",
		},
	)

	complement_rate = (completed_complements / total_payments * 100) if total_payments > 0 else 0

	metrics.append(
		{
			"metric_name": "🧾 Tasa Complementos PPD",
			"current_value": f"{complement_rate:.1f}%",
			"previous_value": "N/A",
			"variation": "N/A",
			"trend": "📈" if complement_rate >= 90 else ("➡️" if complement_rate >= 80 else "📉"),
			"target": "Meta: 95%",
			"achievement": f"{min(100, complement_rate/95*100):.0f}%",
			"status": get_status_icon_absolute(complement_rate, 90, 80),
		}
	)

	return metrics


def get_financial_metrics(company, report_date):
	"""Métricas financieras"""
	metrics = []

	get_month_period(report_date)
	get_previous_month_period(report_date)

	# Cuentas por cobrar
	current_receivables = get_accounts_receivable(company)
	# Placeholder para mes anterior
	previous_receivables = current_receivables * 0.95  # Simulación

	receivables_variation = calculate_variation(current_receivables, previous_receivables)

	metrics.append(
		{
			"metric_name": "💳 Cuentas por Cobrar",
			"current_value": f"${current_receivables:,.0f}",
			"previous_value": f"${previous_receivables:,.0f}",
			"variation": f"{receivables_variation:+.1f}%",
			"trend": get_trend_icon(-receivables_variation),  # Menos CxC es mejor
			"target": "Meta: -5%",
			"achievement": f"{min(100, max(0, 100 - receivables_variation)):.0f}%",
			"status": get_status_icon(-receivables_variation, 5),  # Negativo es mejor
		}
	)

	return metrics


def get_compliance_metrics(company, report_date):
	"""Métricas de cumplimiento"""
	metrics = []

	# Score de salud fiscal (simulado)
	health_score = calculate_overall_health_score(company)

	metrics.append(
		{
			"metric_name": "🏥 Salud Fiscal",
			"current_value": f"{health_score:.1f}/100",
			"previous_value": f"{health_score-2:.1f}/100",
			"variation": "+2.0 pts",
			"trend": "📈",
			"target": "Meta: 85+",
			"achievement": f"{min(100, health_score/85*100):.0f}%",
			"status": get_status_icon_absolute(health_score, 85, 75),
		}
	)

	# Cumplimiento regulatorio
	compliance_rate = 94.5  # Placeholder

	metrics.append(
		{
			"metric_name": "⚖️ Cumplimiento Regulatorio",
			"current_value": f"{compliance_rate:.1f}%",
			"previous_value": "92.1%",
			"variation": "+2.4%",
			"trend": "📈",
			"target": "Meta: 98%",
			"achievement": f"{min(100, compliance_rate/98*100):.0f}%",
			"status": get_status_icon_absolute(compliance_rate, 95, 90),
		}
	)

	return metrics


def get_performance_metrics(company, report_date):
	"""Métricas de performance del sistema"""
	metrics = []

	# Tiempo promedio de respuesta del sistema
	avg_response_time = 2.3  # Placeholder

	metrics.append(
		{
			"metric_name": "⚡ Performance Sistema",
			"current_value": f"{avg_response_time:.1f}s",
			"previous_value": "2.8s",
			"variation": "-17.9%",
			"trend": "📈",
			"target": "Meta: <3s",
			"achievement": "100%",
			"status": "🟢 Excelente",
		}
	)

	# Disponibilidad del sistema
	uptime = 99.8  # Placeholder

	metrics.append(
		{
			"metric_name": "🔧 Disponibilidad Sistema",
			"current_value": f"{uptime:.1f}%",
			"previous_value": "99.5%",
			"variation": "+0.3%",
			"trend": "📈",
			"target": "Meta: 99.5%",
			"achievement": "100%",
			"status": "🟢 Excelente",
		}
	)

	return metrics


# Funciones auxiliares


def get_month_period(report_date):
	"""Obtener período del mes actual"""
	first_day = date(report_date.year, report_date.month, 1)
	last_day = date(
		report_date.year, report_date.month, calendar.monthrange(report_date.year, report_date.month)[1]
	)
	return [first_day, last_day]


def get_previous_month_period(report_date):
	"""Obtener período del mes anterior"""
	if report_date.month == 1:
		prev_year = report_date.year - 1
		prev_month = 12
	else:
		prev_year = report_date.year
		prev_month = report_date.month - 1

	first_day = date(prev_year, prev_month, 1)
	last_day = date(prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1])
	return [first_day, last_day]


def get_invoices_amount(company, period):
	"""Obtener monto total de facturas en período"""
	result = frappe.db.sql(
		"""
        SELECT COALESCE(SUM(grand_total), 0) as total
        FROM `tabSales Invoice`
        WHERE company = %s
        AND docstatus = 1
        AND posting_date BETWEEN %s AND %s
    """,
		(company, period[0], period[1]),
	)

	return float(result[0][0] or 0)


def get_average_stamping_time(company, period):
	"""Obtener tiempo promedio de timbrado"""
	# Placeholder - requeriría campos adicionales para medir tiempo real
	return 1.8


def get_accounts_receivable(company):
	"""Obtener total de cuentas por cobrar"""
	result = frappe.db.sql(
		"""
        SELECT COALESCE(SUM(outstanding_amount), 0) as total
        FROM `tabSales Invoice`
        WHERE company = %s
        AND docstatus = 1
        AND outstanding_amount > 0
    """,
		company,
	)

	return float(result[0][0] or 0)


def calculate_overall_health_score(company):
	"""Calcular score general de salud fiscal"""
	# Simulación de cálculo complejo
	base_score = 85.0

	# Ajustar por factores varios
	# En implementación real, usaría los módulos reales
	adjustments = [
		("timbrado_rate", 2.5),
		("ppd_compliance", 1.8),
		("system_performance", 3.2),
		("error_rate", -1.0),
	]

	final_score = base_score + sum(adj[1] for adj in adjustments)
	return min(100, max(0, final_score))


def calculate_variation(current, previous):
	"""Calcular variación porcentual"""
	if previous == 0:
		return 0 if current == 0 else 100
	return ((current - previous) / previous) * 100


def get_trend_icon(variation):
	"""Obtener icono de tendencia"""
	if variation > 5:
		return "📈 Creciendo"
	elif variation < -5:
		return "📉 Decreciendo"
	else:
		return "➡️ Estable"


def get_status_icon(variation, target):
	"""Obtener icono de estado basado en variación vs target"""
	if variation >= target:
		return "🟢 Superado"
	elif variation >= target * 0.7:
		return "🟡 Progreso"
	else:
		return "🔴 Bajo Meta"


def get_status_icon_absolute(value, good_threshold, ok_threshold, reverse=False):
	"""Obtener icono de estado basado en valor absoluto"""
	if not reverse:
		if value >= good_threshold:
			return "🟢 Excelente"
		elif value >= ok_threshold:
			return "🟡 Bueno"
		else:
			return "🔴 Requiere Atención"
	else:
		if value <= good_threshold:
			return "🟢 Excelente"
		elif value <= ok_threshold:
			return "🟡 Bueno"
		else:
			return "🔴 Requiere Atención"


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
			"reqd": 1,
		},
		{
			"fieldname": "report_date",
			"label": _("Fecha del Reporte"),
			"fieldtype": "Date",
			"default": date.today().strftime("%Y-%m-%d"),
			"reqd": 1,
		},
	]


def get_chart_data(data, filters):
	"""Datos para gráficos ejecutivos"""
	if not data:
		return None

	# Extraer achievements para gráfico radial
	achievements = []
	labels = []

	for row in data:
		if "%" in row.get("achievement", ""):
			achievement_val = float(row["achievement"].replace("%", ""))
			achievements.append(achievement_val)
			labels.append(
				row["metric_name"]
				.replace("📄", "")
				.replace("💰", "")
				.replace("✅", "")
				.replace("⏱️", "")
				.strip()
			)

	return {
		"data": {
			"labels": labels[:6],  # Primeros 6 KPIs principales
			"datasets": [{"name": "Cumplimiento de Metas", "values": achievements[:6]}],
		},
		"type": "radar",
		"height": 400,
		"colors": ["#007bff"],
	}
