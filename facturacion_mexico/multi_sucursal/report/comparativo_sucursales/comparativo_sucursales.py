# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Comparativo de Sucursales - Sprint 6 Phase 5
Reporte comparativo de performance entre sucursales
"""

from datetime import datetime, timedelta

import frappe
from frappe import _


def execute(filters=None):
	"""Ejecutar reporte comparativo de sucursales"""
	columns = get_columns(filters)
	data = get_data(filters)
	summary = get_summary(data, filters)
	chart = get_chart_data(data, filters)

	return columns, data, None, chart, summary


def get_columns(filters):
	"""Definir columnas del reporte"""
	comparison_type = filters.get("comparison_type", "Completo")

	base_columns = [
		{
			"fieldname": "branch",
			"label": _("Sucursal"),
			"fieldtype": "Link",
			"options": "Branch",
			"width": 150,
		},
		{
			"fieldname": "branch_name",
			"label": _("Nombre"),
			"fieldtype": "Data",
			"width": 180,
		},
	]

	# Columnas de facturación
	if comparison_type in ["Facturación", "Completo"]:
		base_columns.extend(
			[
				{
					"fieldname": "total_invoices",
					"label": _("Total Facturas"),
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"fieldname": "total_amount",
					"label": _("Monto Total"),
					"fieldtype": "Currency",
					"width": 140,
				},
				{
					"fieldname": "average_invoice_amount",
					"label": _("Promedio por Factura"),
					"fieldtype": "Currency",
					"width": 150,
				},
			]
		)

	# Columnas de volumen
	if comparison_type in ["Volumen", "Completo"]:
		base_columns.extend(
			[
				{
					"fieldname": "daily_average",
					"label": _("Promedio Diario"),
					"fieldtype": "Float",
					"width": 120,
					"precision": 1,
				},
				{
					"fieldname": "growth_rate",
					"label": _("Crecimiento %"),
					"fieldtype": "Percent",
					"width": 120,
				},
				{
					"fieldname": "market_share",
					"label": _("Participación %"),
					"fieldtype": "Percent",
					"width": 120,
				},
			]
		)

	# Columnas de cumplimiento
	if comparison_type in ["Cumplimiento", "Completo"]:
		base_columns.extend(
			[
				{
					"fieldname": "stamped_invoices",
					"label": _("Facturas Timbradas"),
					"fieldtype": "Int",
					"width": 140,
				},
				{
					"fieldname": "stamping_success_rate",
					"label": _("% Éxito Timbrado"),
					"fieldtype": "Percent",
					"width": 130,
				},
				{
					"fieldname": "addendas_compliance",
					"label": _("% Cumpl. Addendas"),
					"fieldtype": "Percent",
					"width": 140,
				},
			]
		)

	# Columnas de eficiencia
	if comparison_type in ["Eficiencia", "Completo"]:
		base_columns.extend(
			[
				{
					"fieldname": "avg_stamping_time",
					"label": _("Tiempo Timbrado (s)"),
					"fieldtype": "Float",
					"width": 140,
					"precision": 2,
				},
				{
					"fieldname": "error_rate",
					"label": _("Tasa de Error %"),
					"fieldtype": "Percent",
					"width": 120,
				},
				{
					"fieldname": "efficiency_score",
					"label": _("Score Eficiencia"),
					"fieldtype": "Float",
					"width": 130,
					"precision": 1,
				},
			]
		)

	# Columnas de ranking y comparación
	if comparison_type == "Completo":
		base_columns.extend(
			[
				{
					"fieldname": "overall_ranking",
					"label": _("Ranking General"),
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"fieldname": "performance_vs_benchmark",
					"label": _("vs Benchmark %"),
					"fieldtype": "Percent",
					"width": 140,
				},
				{
					"fieldname": "status",
					"label": _("Estado"),
					"fieldtype": "Data",
					"width": 120,
				},
			]
		)

	return base_columns


def get_data(filters):
	"""Obtener datos del reporte"""
	conditions = get_conditions(filters)
	comparison_type = filters.get("comparison_type", "Completo")

	# Query principal para obtener datos de sucursales
	query = f"""
		SELECT
			b.name as branch,
			b.branch_name,
			COUNT(si.name) as total_invoices,
			SUM(si.grand_total) as total_amount,
			COUNT(CASE WHEN si.fm_cfdi_xml IS NOT NULL THEN 1 END) as stamped_invoices
		FROM `tabBranch` b
		LEFT JOIN `tabSales Invoice` si ON si.fm_branch = b.name
			AND si.docstatus = 1 {conditions}
		WHERE 1=1 {get_branch_conditions(filters)}
		GROUP BY b.name, b.branch_name
		ORDER BY total_amount DESC
	"""

	# REGLA #35: Defensive SQL execution with error handling
	try:
		branch_data = frappe.db.sql(query, filters, as_dict=True)
	except Exception as e:
		frappe.log_error(f"Error executing branch comparison query: {e}", "Branch Comparison Report")
		branch_data = []

	# Enriquecer con métricas calculadas
	total_period_amount = sum(row["total_amount"] or 0 for row in branch_data)
	benchmark_branch = filters.get("benchmark_branch")
	benchmark_data = None

	if benchmark_branch:
		benchmark_data = next((row for row in branch_data if row["branch"] == benchmark_branch), None)

	for row in branch_data:
		# Calcular métricas básicas
		row["total_invoices"] = row["total_invoices"] or 0
		row["total_amount"] = row["total_amount"] or 0
		row["stamped_invoices"] = row["stamped_invoices"] or 0

		# Métricas de facturación
		if comparison_type in ["Facturación", "Completo"]:
			row["average_invoice_amount"] = (
				row["total_amount"] / row["total_invoices"] if row["total_invoices"] > 0 else 0
			)

		# Métricas de volumen
		if comparison_type in ["Volumen", "Completo"]:
			row["daily_average"] = calculate_daily_average(row["branch"], filters)
			row["growth_rate"] = calculate_growth_rate(row["branch"], filters)
			row["market_share"] = (
				(row["total_amount"] / total_period_amount * 100) if total_period_amount > 0 else 0
			)

		# Métricas de cumplimiento
		if comparison_type in ["Cumplimiento", "Completo"]:
			row["stamping_success_rate"] = (
				(row["stamped_invoices"] / row["total_invoices"] * 100) if row["total_invoices"] > 0 else 0
			)
			row["addendas_compliance"] = calculate_addendas_compliance(row["branch"], filters)

		# Métricas de eficiencia
		if comparison_type in ["Eficiencia", "Completo"]:
			row["avg_stamping_time"] = calculate_avg_stamping_time(row["branch"], filters)
			row["error_rate"] = calculate_error_rate(row["branch"], filters)
			row["efficiency_score"] = calculate_efficiency_score(row)

		# Ranking y comparación vs benchmark
		if comparison_type == "Completo":
			if benchmark_data and benchmark_data["total_amount"] > 0:
				row["performance_vs_benchmark"] = (
					row["total_amount"] / benchmark_data["total_amount"] * 100
				) - 100
			else:
				row["performance_vs_benchmark"] = 0

			row["status"] = determine_branch_status(row)

	# Calcular rankings
	if comparison_type == "Completo":
		sorted_data = sorted(branch_data, key=lambda x: x.get("efficiency_score", 0), reverse=True)
		for i, row in enumerate(sorted_data):
			row["overall_ranking"] = i + 1

		# Reordenar por ranking
		branch_data = sorted_data

	return branch_data


def get_conditions(filters):
	"""Construir condiciones para facturas"""
	conditions = []

	if filters.get("from_date"):
		conditions.append("AND si.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("AND si.posting_date <= %(to_date)s")

	return " ".join(conditions)


def get_branch_conditions(filters):
	"""Construir condiciones para sucursales"""
	conditions = []

	if filters.get("branches"):
		branch_list = "', '".join(filters["branches"])
		conditions.append(f"AND b.name IN ('{branch_list}')")

	if not filters.get("include_inactive"):
		conditions.append("AND b.disabled = 0")

	return " ".join(conditions)


def calculate_daily_average(branch, filters):
	"""Calcular promedio diario de facturas"""
	try:
		from_date = filters.get("from_date")
		to_date = filters.get("to_date")

		if not from_date or not to_date:
			return 0

		date_diff = (to_date - from_date).days + 1

		invoice_count = frappe.db.count(
			"Sales Invoice",
			{"fm_branch": branch, "docstatus": 1, "posting_date": ["between", [from_date, to_date]]},
		)

		return round(invoice_count / date_diff, 1) if date_diff > 0 else 0

	except Exception:
		return 0


def calculate_growth_rate(branch, filters):
	"""Calcular tasa de crecimiento vs período anterior"""
	try:
		from_date = filters.get("from_date")
		to_date = filters.get("to_date")

		if not from_date or not to_date:
			return 0

		# Período actual con manejo defensivo
		try:
			current_amount = (
				frappe.db.sql(
					"""
				SELECT SUM(grand_total)
				FROM `tabSales Invoice`
				WHERE fm_branch = %s
				AND docstatus = 1
				AND posting_date BETWEEN %s AND %s
			""",
					(branch, from_date, to_date),
				)[0][0]
				or 0
			)
		except Exception as e:
			frappe.log_error(
				f"Error calculating current amount for branch {branch}: {e}", "Growth Calculation"
			)
			current_amount = 0

		# Período anterior (mismo rango de días)
		date_diff = (to_date - from_date).days
		prev_from = from_date - timedelta(days=date_diff + 1)
		prev_to = from_date - timedelta(days=1)

		try:
			previous_amount = (
				frappe.db.sql(
					"""
				SELECT SUM(grand_total)
				FROM `tabSales Invoice`
				WHERE fm_branch = %s
				AND docstatus = 1
				AND posting_date BETWEEN %s AND %s
			""",
					(branch, prev_from, prev_to),
				)[0][0]
				or 0
			)
		except Exception as e:
			frappe.log_error(
				f"Error calculating previous amount for branch {branch}: {e}", "Growth Calculation"
			)
			previous_amount = 0

		if previous_amount == 0:
			return 0

		growth = ((current_amount - previous_amount) / previous_amount) * 100
		return round(growth, 2)

	except Exception:
		return 0


def calculate_addendas_compliance(branch, filters):
	"""Calcular cumplimiento de addendas"""
	try:
		# Facturas que requieren addenda
		required_addendas = (
			frappe.db.sql(
				"""
			SELECT COUNT(*)
			FROM `tabSales Invoice` si
			INNER JOIN `tabCustomer` c ON c.name = si.customer
			WHERE si.fm_branch = %s
			AND si.docstatus = 1
			AND si.posting_date BETWEEN %s AND %s
			AND c.fm_requires_addenda = 1
		""",
				(branch, filters.get("from_date"), filters.get("to_date")),
			)[0][0]
			or 0
		)

		# Facturas con addenda generada
		with_addendas = (
			frappe.db.sql(
				"""
			SELECT COUNT(*)
			FROM `tabSales Invoice` si
			INNER JOIN `tabCustomer` c ON c.name = si.customer
			WHERE si.fm_branch = %s
			AND si.docstatus = 1
			AND si.posting_date BETWEEN %s AND %s
			AND c.fm_requires_addenda = 1
			AND si.fm_addenda_xml IS NOT NULL
		""",
				(branch, filters.get("from_date"), filters.get("to_date")),
			)[0][0]
			or 0
		)

		if required_addendas == 0:
			return 100  # Sin requerimientos = 100% cumplimiento

		return round((with_addendas / required_addendas) * 100, 2)

	except Exception:
		return 0


def calculate_avg_stamping_time(branch, filters):
	"""Calcular tiempo promedio de timbrado"""
	try:
		# Simulado - en implementación real vendría de logs
		result = frappe.db.sql(
			"""
			SELECT AVG(TIMESTAMPDIFF(SECOND, creation, modified)) as avg_time
			FROM `tabSales Invoice`
			WHERE fm_branch = %s
			AND docstatus = 1
			AND fm_cfdi_xml IS NOT NULL
			AND posting_date BETWEEN %s AND %s
		""",
			(branch, filters.get("from_date"), filters.get("to_date")),
		)

		return round(result[0][0] or 30, 2)  # Default 30 segundos

	except Exception:
		return 30


def calculate_error_rate(branch, filters):
	"""Calcular tasa de errores"""
	try:
		total_attempts = frappe.db.count(
			"Sales Invoice",
			{
				"fm_branch": branch,
				"docstatus": 1,
				"posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
			},
		)

		# Simular errores basado en facturas sin timbrar
		errors = frappe.db.count(
			"Sales Invoice",
			{
				"fm_branch": branch,
				"docstatus": 1,
				"fm_cfdi_xml": ["is", "not set"],
				"posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
			},
		)

		if total_attempts == 0:
			return 0

		return round((errors / total_attempts) * 100, 2)

	except Exception:
		return 0


def calculate_efficiency_score(row):
	"""Calcular score de eficiencia (0-100)"""
	try:
		# Ponderación de métricas
		weights = {
			"stamping_success_rate": 0.3,
			"addendas_compliance": 0.2,
			"avg_stamping_time": 0.2,  # Invertido: menor tiempo = mejor
			"error_rate": 0.2,  # Invertido: menor error = mejor
			"growth_rate": 0.1,
		}

		score = 0

		# Success rate (directo)
		score += (row.get("stamping_success_rate", 0) * weights["stamping_success_rate"]) / 100

		# Addendas compliance (directo)
		score += (row.get("addendas_compliance", 0) * weights["addendas_compliance"]) / 100

		# Tiempo timbrado (invertido - 30s = bueno, >60s = malo)
		stamping_time = row.get("avg_stamping_time", 30)
		time_score = max(0, 100 - ((stamping_time - 10) * 2))  # 10s = 100, 60s = 0
		score += (time_score * weights["avg_stamping_time"]) / 100

		# Error rate (invertido)
		error_rate = row.get("error_rate", 0)
		error_score = max(0, 100 - (error_rate * 10))  # 0% = 100, 10% = 0
		score += (error_score * weights["error_rate"]) / 100

		# Growth rate (normalizado)
		growth_rate = row.get("growth_rate", 0)
		growth_score = min(100, max(0, 50 + growth_rate))  # -50% = 0, 50% = 100
		score += (growth_score * weights["growth_rate"]) / 100

		return round(score * 100, 1)

	except Exception:
		return 50  # Score neutro


def determine_branch_status(row):
	"""Determinar estado de la sucursal"""
	efficiency_score = row.get("efficiency_score", 50)
	error_rate = row.get("error_rate", 0)
	stamping_success = row.get("stamping_success_rate", 0)

	if efficiency_score >= 85 and error_rate <= 2:
		return "🟢 Excelente"
	elif efficiency_score >= 70 and error_rate <= 5:
		return "🟡 Bueno"
	elif efficiency_score >= 50 and stamping_success >= 80:
		return "🟠 Regular"
	else:
		return "🔴 Requiere Atención"


def get_summary(data, filters):
	"""Generar resumen del reporte"""
	if not data:
		return []

	# Estadísticas generales
	total_branches = len(data)
	total_invoices = sum(row["total_invoices"] for row in data)
	total_amount = sum(row["total_amount"] for row in data)

	# Performance por estado
	excellent = len([row for row in data if "Excelente" in row.get("status", "")])
	len([row for row in data if "Bueno" in row.get("status", "")])
	len([row for row in data if "Regular" in row.get("status", "")])
	attention = len([row for row in data if "Atención" in row.get("status", "")])

	# Métricas promedio
	avg_efficiency = (
		sum(row.get("efficiency_score", 0) for row in data) / total_branches if total_branches > 0 else 0
	)
	avg_stamping_success = (
		sum(row.get("stamping_success_rate", 0) for row in data) / total_branches if total_branches > 0 else 0
	)
	avg_error_rate = (
		sum(row.get("error_rate", 0) for row in data) / total_branches if total_branches > 0 else 0
	)

	# Top performer
	top_branch = max(data, key=lambda x: x.get("efficiency_score", 0)) if data else None

	summary = [
		{"label": _("Total Sucursales"), "value": total_branches, "indicator": "blue"},
		{"label": _("Total Facturas"), "value": f"{total_invoices:,}", "indicator": "blue"},
		{
			"label": _("Monto Total"),
			"value": frappe.format_value(total_amount, "Currency"),
			"indicator": "blue",
		},
		{"label": _("Performance Excelente"), "value": f"{excellent} sucursales", "indicator": "green"},
		{
			"label": _("Requieren Atención"),
			"value": f"{attention} sucursales",
			"indicator": "red" if attention > 0 else "green",
		},
		{
			"label": _("Eficiencia Promedio"),
			"value": f"{avg_efficiency:.1f}/100",
			"indicator": "green" if avg_efficiency >= 70 else "orange" if avg_efficiency >= 50 else "red",
		},
		{
			"label": _("% Éxito Timbrado Promedio"),
			"value": f"{avg_stamping_success:.1f}%",
			"indicator": "green" if avg_stamping_success >= 95 else "orange",
		},
		{
			"label": _("Tasa Error Promedio"),
			"value": f"{avg_error_rate:.1f}%",
			"indicator": "green" if avg_error_rate <= 2 else "red",
		},
	]

	if top_branch:
		summary.append(
			{
				"label": _("Top Performer"),
				"value": f"{top_branch['branch_name']} ({top_branch.get('efficiency_score', 0):.1f})",
				"indicator": "green",
			}
		)

	return summary


def get_chart_data(data, filters):
	"""Generar datos para gráfico"""
	if not data:
		return None

	comparison_type = filters.get("comparison_type", "Completo")

	if comparison_type in ["Facturación", "Completo"]:
		# Gráfico de barras para comparar facturación
		return {
			"data": {
				"labels": [row["branch_name"][:15] for row in data[:10]],  # Top 10
				"datasets": [{"name": "Monto Total", "values": [row["total_amount"] for row in data[:10]]}],
			},
			"type": "bar",
			"height": 400,
			"colors": ["#007bff"],
		}

	elif comparison_type == "Eficiencia":
		# Gráfico de scatter para eficiencia vs error rate
		return {
			"data": {
				"labels": [row["branch_name"][:10] for row in data],
				"datasets": [
					{"name": "Score Eficiencia", "values": [row.get("efficiency_score", 0) for row in data]}
				],
			},
			"type": "line",
			"height": 300,
			"colors": ["#28a745"],
		}

	else:
		# Gráfico de distribución por estado
		status_counts = {}
		for row in data:
			status = row.get("status", "Sin Estado")
			clean_status = status.replace("🟢 ", "").replace("🟡 ", "").replace("🟠 ", "").replace("🔴 ", "")
			status_counts[clean_status] = status_counts.get(clean_status, 0) + 1

		return {
			"data": {
				"labels": list(status_counts.keys()),
				"datasets": [{"name": "Sucursales por Estado", "values": list(status_counts.values())}],
			},
			"type": "pie",
			"height": 300,
			"colors": ["#28a745", "#ffc107", "#fd7e14", "#dc3545"],
		}
