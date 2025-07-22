"""
Dashboard Fiscal API - APIs Principales para Dashboard
Aplicando todos los patrones del Custom Fields Migration Sprint:
- Error Handling Pattern Robusto
- Response Pattern Consistente
- Backup-First Approach
- Granular Commit Strategy
- Performance Patterns
"""

import json
from datetime import datetime, timedelta
from typing import Any

import frappe
from frappe import _

from .cache_manager import DashboardCache, cached_kpi, cached_report
from .dashboard_registry import DashboardRegistry


# Aplicar patrón: Response structure consistency
def success_response(data: Any, message: str = "Success") -> dict[str, Any]:
	"""Estructura de respuesta consistente para éxito"""
	return {"success": True, "data": data, "message": message, "timestamp": datetime.now().isoformat()}


def error_response(error: str, data: Any = None, code: str = "ERROR") -> dict[str, Any]:
	"""Estructura de respuesta consistente para errores"""
	return {
		"success": False,
		"data": data,
		"error": error,
		"code": code,
		"timestamp": datetime.now().isoformat(),
	}


@frappe.whitelist()
def get_dashboard_data(period: str = "month", company: str | None = None) -> dict[str, Any]:
	"""
	Obtener todos los datos del dashboard
	Aplicar: Response pattern consistente + Error handling robusto

	Args:
		period: Período de datos (today/week/month/year)
		company: Company específica (None = company activa)

	Returns:
		Datos completos del dashboard con KPIs, widgets y alertas
	"""
	try:
		# Validar company
		if not company:
			company = frappe.defaults.get_user_default("Company")

		if not company:
			return error_response("No se pudo determinar la company", code="NO_COMPANY")

		# Verificar permisos
		if not frappe.has_permission("Company", "read", company):
			return error_response("Sin permisos para acceder a esta company", code="NO_PERMISSION")

		# Usar cache para performance
		def fetch_dashboard_data(**kwargs):
			dashboard_data = {}

			# Obtener configuración del dashboard
			config = _get_dashboard_config()
			dashboard_data["config"] = config

			# Obtener KPIs de todos los módulos registrados
			all_kpis = DashboardRegistry.get_all_kpis()
			dashboard_data["kpis"] = {}

			for module_name, module_kpis in all_kpis.items():
				dashboard_data["kpis"][module_name] = {}

				for kpi_name, _kpi_function in module_kpis.items():
					try:
						kpi_result = DashboardRegistry.evaluate_kpi(
							module_name, kpi_name, company=company, period=period
						)
						dashboard_data["kpis"][module_name][kpi_name] = kpi_result
					except Exception as e:
						frappe.logger().warning(f"Error evaluando KPI {module_name}.{kpi_name}: {e}")
						dashboard_data["kpis"][module_name][kpi_name] = None

			# Obtener widgets configurados
			dashboard_data["widgets"] = _get_active_widgets(company)

			# Obtener alertas activas
			dashboard_data["alerts"] = _get_active_alerts(company)

			# Obtener estado general del sistema
			dashboard_data["system_status"] = _get_system_health_status(company)

			return dashboard_data

		# Usar cache con TTL de configuración
		cache_ttl = _get_dashboard_config().get("cache_duration", 3600)

		result_data = DashboardCache.get_or_set(
			"dashboard_main", fetch_dashboard_data, ttl=cache_ttl, company=company, period=period
		)

		if result_data is None:
			return error_response("Error obteniendo datos del dashboard", code="FETCH_ERROR")

		return success_response(result_data, "Dashboard data obtenida exitosamente")

	except Exception as e:
		frappe.log_error(
			title="Error en get_dashboard_data", message=f"Error: {e!s}\nCompany: {company}, Period: {period}"
		)
		return error_response("Error interno obteniendo datos del dashboard", code="INTERNAL_ERROR")


@frappe.whitelist()
def get_module_kpis(module_name: str, filters: dict | None = None) -> dict[str, Any]:
	"""
	Obtener KPIs específicos de un módulo
	Aplicar: Error handling robusto + Granular operations

	Args:
		module_name: Nombre del módulo
		filters: Filtros adicionales

	Returns:
		KPIs detallados del módulo con drill-down
	"""
	try:
		if not module_name:
			return error_response("module_name es requerido", code="MISSING_PARAM")

		# Sanitizar filtros
		if filters is None:
			filters = {}

		if isinstance(filters, str):
			try:
				filters = json.loads(filters)
			except json.JSONDecodeError:
				filters = {}

		# Obtener KPIs del módulo con cache
		@cached_kpi(f"{module_name}_detailed", ttl=900)  # 15 min cache
		def fetch_module_kpis(**kwargs):
			module_kpis = DashboardRegistry.get_module_kpis(module_name)

			if not module_kpis:
				return None

			detailed_results = {}

			for kpi_name, _kpi_function in module_kpis.items():
				try:
					result = DashboardRegistry.evaluate_kpi(module_name, kpi_name, **filters)

					# Agregar metadatos para drill-down
					detailed_results[kpi_name] = {
						"value": result,
						"module": module_name,
						"last_calculated": datetime.now().isoformat(),
						"filters_applied": filters,
					}

				except Exception as e:
					frappe.logger().warning(f"Error en KPI {module_name}.{kpi_name}: {e}")
					detailed_results[kpi_name] = {"value": None, "error": str(e), "module": module_name}

			return detailed_results

		result_data = fetch_module_kpis(module_name=module_name, filters=filters)

		if result_data is None:
			return error_response(f"Módulo '{module_name}' no encontrado o sin KPIs", code="MODULE_NOT_FOUND")

		return success_response(result_data, f"KPIs de {module_name} obtenidos exitosamente")

	except Exception as e:
		frappe.log_error(
			title=f"Error en get_module_kpis - {module_name}", message=f"Error: {e!s}\nFilters: {filters}"
		)
		return error_response("Error obteniendo KPIs del módulo", code="INTERNAL_ERROR")


@frappe.whitelist()
def get_active_alerts(severity: str | None = None, module: str | None = None) -> dict[str, Any]:
	"""
	Obtener alertas activas del sistema
	Aplicar: Performance patterns + Error handling

	Args:
		severity: Filtrar por severidad (error/warning/info/success)
		module: Filtrar por módulo específico

	Returns:
		Lista de alertas activas priorizadas
	"""
	try:
		# Usar cache para alertas (menor TTL por ser críticas)
		@cached_kpi("active_alerts", ttl=300)  # 5 min cache
		def fetch_active_alerts(**kwargs):
			return _get_active_alerts()

		all_alerts = fetch_active_alerts(severity=severity, module=module)

		# Aplicar filtros
		filtered_alerts = all_alerts

		if severity:
			filtered_alerts = [a for a in filtered_alerts if a.get("severity") == severity]

		if module:
			filtered_alerts = [a for a in filtered_alerts if a.get("module") == module]

		# Ordenar por prioridad
		filtered_alerts.sort(key=lambda x: x.get("priority", 0), reverse=True)

		return success_response(
			{
				"alerts": filtered_alerts,
				"total_count": len(filtered_alerts),
				"by_severity": _group_alerts_by_severity(filtered_alerts),
				"by_module": _group_alerts_by_module(filtered_alerts),
			},
			"Alertas obtenidas exitosamente",
		)

	except Exception as e:
		# En testing, evitar log_error que puede causar DocType None errors
		if not frappe.flags.in_test:
			frappe.log_error(
				title="Error en get_active_alerts",
				message=f"Error: {e!s}\nSeverity: {severity}, Module: {module}",
			)
		return error_response("Error obteniendo alertas activas", code="INTERNAL_ERROR")


@frappe.whitelist()
def get_fiscal_health_score(company: str | None = None, date: str | None = None) -> dict[str, Any]:
	"""
	Calcular score de salud fiscal
	Aplicar: Dual-layer update (score + metadata)

	Args:
		company: Company a evaluar
		date: Fecha específica (None = hoy)

	Returns:
		Score de salud fiscal con factores y recomendaciones
	"""
	try:
		# Validar parámetros
		if not company:
			company = frappe.defaults.get_user_default("Company")

		if not date:
			date = datetime.now().date().isoformat()

		# Usar cache con TTL más largo para scores históricos
		cache_ttl = (
			1800 if date == datetime.now().date().isoformat() else 86400
		)  # 30min actual, 24h histórico

		@cached_kpi("fiscal_health_score", ttl=cache_ttl)
		def calculate_fiscal_health(**kwargs):
			# Algoritmo de scoring basado en todos los módulos
			scores = {}
			overall_factors = {"positive": [], "negative": [], "recommendations": []}

			# Evaluar cada módulo registrado
			all_kpis = DashboardRegistry.get_all_kpis()

			for module_name in all_kpis.keys():
				module_score = _calculate_module_health_score(module_name, company, date)
				scores[f"{module_name}_score"] = module_score["score"]

				# Agregar factores
				overall_factors["positive"].extend(module_score.get("positive_factors", []))
				overall_factors["negative"].extend(module_score.get("negative_factors", []))
				overall_factors["recommendations"].extend(module_score.get("recommendations", []))

			# Calcular score general (promedio ponderado)
			if scores:
				overall_score = sum(scores.values()) / len(scores)
			else:
				overall_score = 0

			# Aplicar patrón: Dual-layer update
			health_record = {
				"score_date": date,
				"company": company,
				"overall_score": round(overall_score, 2),
				"factors_positive": overall_factors["positive"][:10],  # Top 10
				"factors_negative": overall_factors["negative"][:10],  # Top 10
				"recommendations": overall_factors["recommendations"][:5],  # Top 5
			}

			# Persistir score en DocType (si existe)
			try:
				_save_fiscal_health_record(health_record)
			except Exception as e:
				frappe.logger().warning(f"No se pudo persistir health score: {e}")

			return {**health_record, **scores, "calculation_timestamp": datetime.now().isoformat()}

		result_data = calculate_fiscal_health(company=company, date=date)

		return success_response(result_data, "Score de salud fiscal calculado exitosamente")

	except Exception as e:
		frappe.log_error(
			title="Error en get_fiscal_health_score",
			message=f"Error: {e!s}\nCompany: {company}, Date: {date}",
		)
		return error_response("Error calculando score de salud fiscal", code="INTERNAL_ERROR")


@frappe.whitelist()
def save_dashboard_layout(layout_config: str | dict) -> dict[str, Any]:
	"""
	Guardar configuración de dashboard del usuario
	Aplicar: Backup-first approach + Granular commit

	Args:
		layout_config: Configuración del layout

	Returns:
		Confirmación de guardado
	"""
	try:
		# Validar parámetros
		if isinstance(layout_config, str):
			try:
				layout_config = json.loads(layout_config)
			except json.JSONDecodeError:
				return error_response("layout_config debe ser JSON válido", code="INVALID_JSON")

		if not isinstance(layout_config, dict):
			return error_response("layout_config debe ser un diccionario", code="INVALID_FORMAT")

		user = frappe.session.user

		# Aplicar patrón: Backup-first approach
		existing_preferences = None
		try:
			existing_preferences = frappe.get_doc("Dashboard User Preference", {"user": user})
		except frappe.DoesNotExistError:
			pass

		# Backup de configuración anterior
		backup_data = None
		if existing_preferences:
			backup_data = {
				"previous_layout": existing_preferences.dashboard_layout,
				"backup_timestamp": datetime.now().isoformat(),
			}

		try:
			# Crear o actualizar preferencias
			if existing_preferences:
				existing_preferences.dashboard_layout = json.dumps(layout_config)
				existing_preferences.save()
			else:
				new_preference = frappe.get_doc(
					{
						"doctype": "Dashboard User Preference",
						"user": user,
						"dashboard_layout": json.dumps(layout_config),
						"last_viewed": datetime.now(),
					}
				)
				new_preference.insert()

			# Aplicar patrón: Granular commit
			frappe.db.commit()

			# Invalidar cache del usuario
			DashboardCache.invalidate_pattern(f"user_preferences_{user}")

			return success_response(
				{
					"layout_saved": True,
					"user": user,
					"backup_available": backup_data is not None,
					"timestamp": datetime.now().isoformat(),
				},
				"Layout guardado exitosamente",
			)

		except Exception as e:
			# Rollback en caso de error
			frappe.db.rollback()

			# Si hay backup, se podría restaurar aquí
			if backup_data:
				frappe.logger().error(f"Layout save failed, backup available: {backup_data}")

			raise e

	except Exception as e:
		frappe.log_error(
			title="Error en save_dashboard_layout",
			message=f"Error: {e!s}\nUser: {frappe.session.user}\nLayout: {layout_config}",
		)
		return error_response("Error guardando layout del dashboard", code="SAVE_ERROR")


@frappe.whitelist()
def export_dashboard_report(
	report_type: str, filters: dict | None = None, format_type: str = "pdf"
) -> dict[str, Any]:
	"""
	Exportar reportes del dashboard
	Aplicar: Performance patterns para datasets grandes

	Args:
		report_type: Tipo de reporte a exportar
		filters: Filtros para el reporte
		format_type: Formato de exportación (pdf/excel)

	Returns:
		URL o datos del reporte exportado
	"""
	try:
		# Validar parámetros
		valid_report_types = [
			"salud_fiscal_general",
			"auditoria_fiscal",
			"resumen_ejecutivo_cfdi",
			"facturas_sin_timbrar",
			"complementos_pendientes",
		]

		if report_type not in valid_report_types:
			return error_response(
				f"Tipo de reporte inválido. Válidos: {valid_report_types}", code="INVALID_REPORT"
			)

		valid_formats = ["pdf", "excel"]
		if format_type not in valid_formats:
			return error_response(f"Formato inválido. Válidos: {valid_formats}", code="INVALID_FORMAT")

		# Sanitizar filtros
		if filters is None:
			filters = {}

		if isinstance(filters, str):
			try:
				filters = json.loads(filters)
			except json.JSONDecodeError:
				filters = {}

		# Aplicar patrón: Performance patterns para datasets grandes
		@cached_report(f"{report_type}_{format_type}", ttl=1800)  # 30 min cache
		def generate_report():
			return _generate_dashboard_report(report_type, filters, format_type)

		report_result = generate_report(report_type=report_type, filters=filters, format_type=format_type)

		if not report_result:
			return error_response("No se pudo generar el reporte", code="GENERATION_ERROR")

		return success_response(report_result, f"Reporte {report_type} generado exitosamente")

	except Exception as e:
		frappe.log_error(
			title=f"Error en export_dashboard_report - {report_type}",
			message=f"Error: {e!s}\nFilters: {filters}, Format: {format_type}",
		)
		return error_response("Error exportando reporte", code="EXPORT_ERROR")


@frappe.whitelist()
def get_trend_analysis(metric: str, period: str = "month") -> dict[str, Any]:
	"""
	Análisis de tendencias para métrica
	Aplicar: Intelligent caching con invalidación

	Args:
		metric: Nombre de la métrica
		period: Período de análisis

	Returns:
		Análisis de tendencias con cálculos históricos y proyecciones
	"""
	try:
		# Validar parámetros
		valid_periods = ["week", "month", "quarter", "year"]
		if period not in valid_periods:
			return error_response(f"Período inválido. Válidos: {valid_periods}", code="INVALID_PERIOD")

		# Cache con TTL basado en período
		cache_ttl_map = {"week": 3600, "month": 7200, "quarter": 14400, "year": 28800}
		cache_ttl = cache_ttl_map.get(period, 3600)

		@cached_kpi(f"trend_{metric}_{period}", ttl=cache_ttl)
		def calculate_trend():
			return _calculate_metric_trend(metric, period)

		trend_data = calculate_trend(metric=metric, period=period)

		if not trend_data:
			return error_response(f"No se encontraron datos para métrica '{metric}'", code="NO_DATA")

		return success_response(trend_data, f"Análisis de tendencias para {metric} completado")

	except Exception as e:
		frappe.log_error(
			title=f"Error en get_trend_analysis - {metric}", message=f"Error: {e!s}\nPeriod: {period}"
		)
		return error_response("Error calculando tendencias", code="TREND_ERROR")


# Funciones auxiliares privadas


def _get_dashboard_config() -> dict[str, Any]:
	"""Obtener configuración del dashboard"""
	try:
		config = frappe.get_single("Fiscal Dashboard Config")
		return {
			"refresh_interval": config.refresh_interval,
			"cache_duration": config.cache_duration,
			"enable_auto_refresh": config.enable_auto_refresh,
			"dashboard_theme": config.dashboard_theme,
			"performance_mode": config.performance_mode,
		}
	except Exception:
		# Valores por defecto
		return {
			"refresh_interval": 300,
			"cache_duration": 3600,
			"enable_auto_refresh": True,
			"dashboard_theme": "light",
			"performance_mode": False,
		}


def _get_active_widgets(company: str) -> list[dict[str, Any]]:
	"""Obtener widgets activos para una company"""
	try:
		# Obtener widgets configurados
		widgets = frappe.get_all("Dashboard Widget Config", filters={"is_active": 1}, fields=["*"])

		# Enriquecer con datos del registry
		enriched_widgets = []
		for widget in widgets:
			registry_widget = DashboardRegistry.get_all_widgets().get(widget.widget_code, {})
			widget_data = {**widget, "registry_config": registry_widget}
			enriched_widgets.append(widget_data)

		return enriched_widgets
	except Exception:
		return []


def _get_active_alerts(company: str | None = None) -> list[dict[str, Any]]:
	"""Obtener alertas activas evaluando todas las reglas"""
	try:
		active_alerts = []

		# Obtener reglas de alerta activas
		alert_rules = frappe.get_all("Fiscal Alert Rule", filters={"is_active": 1}, fields=["*"])

		for rule in alert_rules:
			# Evaluar regla usando registry
			alert_result = DashboardRegistry.evaluate_alert(rule.module, rule.alert_code, company=company)

			if alert_result:
				alert_result.update(
					{
						"rule_name": rule.alert_name,
						"severity": rule.alert_type,
						"priority": rule.priority,
						"message": rule.message_template,
					}
				)
				active_alerts.append(alert_result)

		return active_alerts
	except Exception as e:
		frappe.logger().warning(f"Error obteniendo alertas activas: {e}")
		return []


def _group_alerts_by_severity(alerts: list[dict]) -> dict[str, int]:
	"""Agrupar alertas por severidad"""
	groups = {"error": 0, "warning": 0, "info": 0, "success": 0}
	for alert in alerts:
		severity = alert.get("severity", "info")
		if severity in groups:
			groups[severity] += 1
	return groups


def _group_alerts_by_module(alerts: list[dict]) -> dict[str, int]:
	"""Agrupar alertas por módulo"""
	groups = {}
	for alert in alerts:
		module = alert.get("module", "unknown")
		groups[module] = groups.get(module, 0) + 1
	return groups


def _get_system_health_status(company: str) -> dict[str, Any]:
	"""Obtener estado general de salud del sistema"""
	try:
		# Estadísticas básicas del sistema
		return {
			"total_modules_active": len(DashboardRegistry.get_all_kpis()),
			"cache_stats": DashboardCache.get_cache_stats(),
			"registry_stats": DashboardRegistry.get_registry_stats(),
			"last_updated": datetime.now().isoformat(),
		}
	except Exception:
		return {"status": "unknown"}


def _calculate_module_health_score(module_name: str, company: str, date: str) -> dict[str, Any]:
	"""Calcular score de salud para un módulo específico"""
	try:
		# Implementar algoritmo específico por módulo
		# Por ahora, placeholder
		return {
			"score": 85.0,  # Score base
			"positive_factors": [f"{module_name} funcionando correctamente"],
			"negative_factors": [],
			"recommendations": [],
		}
	except Exception:
		return {
			"score": 0.0,
			"positive_factors": [],
			"negative_factors": [f"Error evaluando {module_name}"],
			"recommendations": [f"Revisar configuración de {module_name}"],
		}


def _save_fiscal_health_record(health_data: dict[str, Any]):
	"""Guardar registro de salud fiscal en DocType"""
	try:
		# Verificar si ya existe un registro para esta fecha
		existing = frappe.get_all(
			"Fiscal Health Score",
			filters={"score_date": health_data["score_date"], "company": health_data["company"]},
		)

		if existing:
			# Actualizar existente
			doc = frappe.get_doc("Fiscal Health Score", existing[0].name)
			doc.update(health_data)
			doc.save()
		else:
			# Crear nuevo
			doc = frappe.get_doc({"doctype": "Fiscal Health Score", **health_data})
			doc.insert()

		frappe.db.commit()
	except Exception as e:
		frappe.logger().warning(f"No se pudo guardar health score: {e}")


def _generate_dashboard_report(report_type: str, filters: dict, format_type: str) -> dict[str, Any] | None:
	"""Generar reporte específico del dashboard"""
	try:
		# Placeholder para generación de reportes
		# Implementar según el tipo de reporte
		return {
			"file_url": f"/files/dashboard_report_{report_type}.{format_type}",
			"file_name": f"dashboard_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}",
			"generated_at": datetime.now().isoformat(),
			"report_type": report_type,
			"format": format_type,
		}
	except Exception:
		return None


def _calculate_metric_trend(metric: str, period: str) -> dict[str, Any] | None:
	"""Calcular tendencia para una métrica"""
	try:
		# Placeholder para cálculo de tendencias
		return {
			"metric": metric,
			"period": period,
			"trend_direction": "up",  # up/down/stable
			"trend_percentage": 15.5,
			"historical_data": [],
			"projection": None,
			"calculated_at": datetime.now().isoformat(),
		}
	except Exception:
		return None
