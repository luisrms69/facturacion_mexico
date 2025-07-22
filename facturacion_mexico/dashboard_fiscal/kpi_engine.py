"""
KPI Engine - Dashboard Fiscal
Motor de cálculo de KPIs para el sistema de facturación
"""

import json
import time
from datetime import date, datetime, timedelta

import frappe
from frappe import _

from .cache_manager import DashboardCache
from .dashboard_registry import DashboardRegistry


class KPIEngine:
	"""Motor de cálculo de KPIs del dashboard fiscal"""

	def __init__(self, company=None, period="month"):
		self.company = company or frappe.defaults.get_user_default("Company")
		self.period = period
		self.cache_ttl = 1800  # 30 minutos por defecto

	def get_all_kpis(self, use_cache=True):
		"""Obtener todos los KPIs de todos los módulos registrados"""
		try:
			cache_key = f"all_kpis_{self.company}_{self.period}"

			if use_cache:
				cached_result = DashboardCache.get(cache_key)
				if cached_result:
					return cached_result

			# Obtener KPIs de todos los módulos registrados
			all_kpis = {}
			registered_kpis = DashboardRegistry.get_all_kpis()

			for module_name, kpi_functions in registered_kpis.items():
				module_kpis = {}

				for kpi_name, kpi_function in kpi_functions.items():
					try:
						kpi_result = self.calculate_kpi(kpi_function, module_name, kpi_name)
						module_kpis[kpi_name] = kpi_result
					except Exception as e:
						frappe.log_error(
							f"Error calculando KPI {kpi_name} de {module_name}: {e!s}", "KPI Engine Error"
						)
						module_kpis[kpi_name] = self.get_error_kpi(str(e))

				all_kpis[module_name] = module_kpis

			# Calcular KPIs generales del sistema
			all_kpis["Sistema"] = self.calculate_system_kpis()

			result = {
				"success": True,
				"data": all_kpis,
				"company": self.company,
				"period": self.period,
				"calculated_at": datetime.now().isoformat(),
			}

			# Guardar en cache
			if use_cache:
				DashboardCache.set(cache_key, result, ttl=self.cache_ttl)

			return result

		except Exception as e:
			frappe.log_error(f"Error obteniendo todos los KPIs: {e!s}", "KPI Engine")
			return {"success": False, "error": str(e), "data": {}}

	def get_module_kpis(self, module_name, use_cache=True):
		"""Obtener KPIs de un módulo específico"""
		try:
			cache_key = f"module_kpis_{module_name}_{self.company}_{self.period}"

			if use_cache:
				cached_result = DashboardCache.get(cache_key)
				if cached_result:
					return cached_result

			# Obtener funciones KPI del módulo
			registered_kpis = DashboardRegistry.get_all_kpis()

			if module_name not in registered_kpis:
				return {"success": False, "error": f"Módulo {module_name} no encontrado", "data": {}}

			module_kpis = {}
			kpi_functions = registered_kpis[module_name]

			for kpi_name, kpi_function in kpi_functions.items():
				try:
					kpi_result = self.calculate_kpi(kpi_function, module_name, kpi_name)
					module_kpis[kpi_name] = kpi_result
				except Exception as e:
					frappe.log_error(f"Error calculando KPI {kpi_name}: {e!s}", f"KPI Engine - {module_name}")
					module_kpis[kpi_name] = self.get_error_kpi(str(e))

			result = {
				"success": True,
				"module": module_name,
				"data": module_kpis,
				"company": self.company,
				"calculated_at": datetime.now().isoformat(),
			}

			# Guardar en cache
			if use_cache:
				DashboardCache.set(cache_key, result, ttl=self.cache_ttl)

			return result

		except Exception as e:
			frappe.log_error(f"Error obteniendo KPIs del módulo {module_name}: {e!s}", "KPI Engine")
			return {"success": False, "error": str(e), "data": {}}

	def calculate_kpi(self, kpi_function, module_name, kpi_name):
		"""Calcular un KPI individual con manejo de errores"""
		start_time = time.time()

		try:
			# Preparar argumentos para la función KPI
			kpi_args = {
				"company": self.company,
				"period": self.period,
				"date_range": self.get_date_range(),
				"engine": self,
			}

			# Ejecutar función KPI
			result = kpi_function(**kpi_args)

			# Validar resultado
			if not isinstance(result, dict):
				result = {"value": result, "format": "number"}

			# Agregar metadatos
			result.update(
				{
					"module": module_name,
					"kpi_name": kpi_name,
					"company": self.company,
					"calculation_time_ms": int((time.time() - start_time) * 1000),
					"calculated_at": datetime.now().isoformat(),
				}
			)

			return result

		except Exception as e:
			# KPI falló - devolver resultado de error
			return self.get_error_kpi(
				str(e),
				{
					"module": module_name,
					"kpi_name": kpi_name,
					"calculation_time_ms": int((time.time() - start_time) * 1000),
				},
			)

	def calculate_system_kpis(self):
		"""Calcular KPIs generales del sistema"""
		system_kpis = {}

		try:
			# KPI: Salud general del sistema
			system_kpis["salud_general_sistema"] = self.calculate_overall_health()

			# KPI: Total de facturas del período
			system_kpis["total_facturas_periodo"] = self.calculate_total_invoices()

			# KPI: Monto total facturado
			system_kpis["monto_total_facturado"] = self.calculate_total_invoiced_amount()

			# KPI: Tasa de éxito global
			system_kpis["tasa_exito_global"] = self.calculate_global_success_rate()

			# KPI: Alertas activas
			system_kpis["alertas_activas"] = self.calculate_active_alerts()

			# KPI: Performance del sistema
			system_kpis["performance_promedio"] = self.calculate_system_performance()

		except Exception as e:
			frappe.log_error(f"Error calculando KPIs del sistema: {e!s}", "KPI Engine")

		return system_kpis

	def calculate_overall_health(self):
		"""Calcular salud general del sistema"""
		try:
			# Obtener el score más reciente de salud fiscal
			health_score = frappe.db.get_value(
				"Fiscal Health Score",
				filters={"company": self.company, "score_date": ["<=", date.today()]},
				fieldname="overall_score",
				order_by="score_date desc",
			)

			if health_score:
				color = "success" if health_score >= 85 else ("warning" if health_score >= 70 else "danger")
				return {
					"value": round(health_score, 1),
					"format": "float",
					"subtitle": "Score de salud fiscal",
					"color": color,
					"trend": self.calculate_health_trend(),
				}
			else:
				# Calcular health score básico si no existe
				return {"value": 0, "format": "float", "subtitle": "Score no calculado", "color": "secondary"}

		except Exception as e:
			return self.get_error_kpi(str(e))

	def calculate_total_invoices(self):
		"""Calcular total de facturas del período"""
		try:
			date_range = self.get_date_range()

			count = frappe.db.count(
				"Sales Invoice",
				filters={
					"company": self.company,
					"docstatus": 1,
					"posting_date": ["between", [date_range["start"], date_range["end"]]],
				},
			)

			return {
				"value": count,
				"format": "number",
				"subtitle": f"Facturas {self.get_period_label()}",
				"color": "primary",
			}

		except Exception as e:
			return self.get_error_kpi(str(e))

	def calculate_total_invoiced_amount(self):
		"""Calcular monto total facturado"""
		try:
			date_range = self.get_date_range()

			result = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(grand_total), 0) as total
				FROM `tabSales Invoice`
				WHERE company = %s
				AND docstatus = 1
				AND posting_date BETWEEN %s AND %s
			""",
				(self.company, date_range["start"], date_range["end"]),
				as_dict=True,
			)

			total = float(result[0].total or 0)

			return {
				"value": total,
				"format": "currency",
				"subtitle": f"Monto facturado {self.get_period_label()}",
				"color": "success" if total > 0 else "secondary",
			}

		except Exception as e:
			return self.get_error_kpi(str(e))

	def calculate_global_success_rate(self):
		"""Calcular tasa de éxito global del sistema"""
		try:
			date_range = self.get_date_range()

			# Total de facturas
			total_invoices = frappe.db.count(
				"Sales Invoice",
				filters={
					"company": self.company,
					"docstatus": 1,
					"posting_date": ["between", [date_range["start"], date_range["end"]]],
				},
			)

			if total_invoices == 0:
				return {
					"value": 100,
					"format": "percentage",
					"subtitle": "Sin facturas para evaluar",
					"color": "secondary",
				}

			# Facturas sin errores críticos
			successful_invoices = frappe.db.count(
				"Sales Invoice",
				filters={
					"company": self.company,
					"docstatus": 1,
					"posting_date": ["between", [date_range["start"], date_range["end"]]],
					"fm_timbrado_status": ["not in", ["Error", "Failed"]],
				},
			)

			rate = (successful_invoices / total_invoices) * 100
			color = "success" if rate >= 95 else ("warning" if rate >= 85 else "danger")

			return {
				"value": round(rate, 1),
				"format": "percentage",
				"subtitle": "Tasa éxito global",
				"color": color,
			}

		except Exception as e:
			return self.get_error_kpi(str(e))

	def calculate_active_alerts(self):
		"""Calcular número de alertas activas"""
		try:
			# Esto se implementará cuando tengamos el alert engine
			# Por ahora, simular con datos básicos
			count = 0

			return {
				"value": count,
				"format": "number",
				"subtitle": "Alertas activas",
				"color": "danger" if count > 0 else "success",
			}

		except Exception as e:
			return self.get_error_kpi(str(e))

	def calculate_system_performance(self):
		"""Calcular performance promedio del sistema"""
		try:
			# Obtener tiempo promedio de cache hits
			cache_stats = DashboardCache.get_cache_stats()

			if cache_stats.get("hit_ratio", 0) >= 0.8:
				performance_score = "Excelente"
				color = "success"
			elif cache_stats.get("hit_ratio", 0) >= 0.6:
				performance_score = "Bueno"
				color = "warning"
			else:
				performance_score = "Regular"
				color = "danger"

			return {
				"value": performance_score,
				"format": "text",
				"subtitle": f"Cache hit: {cache_stats.get('hit_ratio', 0)*100:.1f}%",
				"color": color,
			}

		except Exception as e:
			return self.get_error_kpi(str(e))

	def get_date_range(self):
		"""Obtener rango de fechas basado en el período"""
		today = date.today()

		if self.period == "today":
			return {"start": today, "end": today}
		elif self.period == "week":
			start = today - timedelta(days=today.weekday())
			end = start + timedelta(days=6)
			return {"start": start, "end": end}
		elif self.period == "month":
			start = date(today.year, today.month, 1)
			if today.month == 12:
				end = date(today.year + 1, 1, 1) - timedelta(days=1)
			else:
				end = date(today.year, today.month + 1, 1) - timedelta(days=1)
			return {"start": start, "end": end}
		elif self.period == "quarter":
			quarter = (today.month - 1) // 3 + 1
			start = date(today.year, (quarter - 1) * 3 + 1, 1)
			if quarter == 4:
				end = date(today.year + 1, 1, 1) - timedelta(days=1)
			else:
				end = date(today.year, quarter * 3 + 1, 1) - timedelta(days=1)
			return {"start": start, "end": end}
		elif self.period == "year":
			return {"start": date(today.year, 1, 1), "end": date(today.year, 12, 31)}
		else:
			# Por defecto, mes actual
			start = date(today.year, today.month, 1)
			if today.month == 12:
				end = date(today.year + 1, 1, 1) - timedelta(days=1)
			else:
				end = date(today.year, today.month + 1, 1) - timedelta(days=1)
			return {"start": start, "end": end}

	def get_period_label(self):
		"""Obtener etiqueta del período"""
		labels = {
			"today": "hoy",
			"week": "esta semana",
			"month": "este mes",
			"quarter": "este trimestre",
			"year": "este año",
		}
		return labels.get(self.period, "período actual")

	def calculate_health_trend(self):
		"""Calcular tendencia de salud fiscal"""
		try:
			# Obtener últimos 2 scores para comparar
			scores = frappe.db.get_all(
				"Fiscal Health Score",
				filters={"company": self.company, "score_date": ["<=", date.today()]},
				fields=["overall_score", "score_date"],
				order_by="score_date desc",
				limit=2,
			)

			if len(scores) >= 2:
				current_score = scores[0].overall_score
				previous_score = scores[1].overall_score

				if current_score > previous_score:
					return {
						"direction": "up",
						"percentage": round(((current_score - previous_score) / previous_score) * 100, 1),
					}
				elif current_score < previous_score:
					return {
						"direction": "down",
						"percentage": round(((previous_score - current_score) / previous_score) * 100, 1),
					}
				else:
					return {"direction": "stable", "percentage": 0}

			return None

		except Exception:
			return None

	def get_error_kpi(self, error_message, metadata=None):
		"""Generar KPI de error estándar"""
		result = {
			"value": 0,
			"format": "number",
			"subtitle": "Error en cálculo",
			"color": "danger",
			"error": error_message,
			"calculated_at": datetime.now().isoformat(),
		}

		if metadata:
			result.update(metadata)

		return result

	@staticmethod
	def invalidate_cache(company=None, module=None):
		"""Invalidar cache de KPIs"""
		if company and module:
			pattern = f"*kpis_{module}_{company}_*"
		elif company:
			pattern = f"*kpis_*_{company}_*"
		elif module:
			pattern = f"*kpis_{module}_*"
		else:
			pattern = "*kpis_*"

		DashboardCache.invalidate_pattern(pattern)

	@staticmethod
	def warmup_kpis(company=None):
		"""Pre-cargar KPIs en cache"""
		try:
			periods = ["today", "week", "month"]
			companies = [company] if company else frappe.get_all("Company", pluck="name")

			for comp in companies:
				for period in periods:
					engine = KPIEngine(company=comp, period=period)
					engine.get_all_kpis(use_cache=False)  # Forzar cálculo fresco

			frappe.logger().info("KPI warmup completado")

		except Exception as e:
			frappe.log_error(f"Error en KPI warmup: {e!s}", "KPI Engine Warmup")


# Funciones de utilidad para APIs
def get_kpi_engine(company=None, period="month"):
	"""Factory function para crear instancia del KPI Engine"""
	return KPIEngine(company=company, period=period)


def calculate_all_kpis(company=None, period="month", use_cache=True):
	"""Función de conveniencia para calcular todos los KPIs"""
	engine = KPIEngine(company=company, period=period)
	return engine.get_all_kpis(use_cache=use_cache)


def calculate_module_kpis(module_name, company=None, period="month", use_cache=True):
	"""Función de conveniencia para calcular KPIs de un módulo"""
	engine = KPIEngine(company=company, period=period)
	return engine.get_module_kpis(module_name, use_cache=use_cache)
