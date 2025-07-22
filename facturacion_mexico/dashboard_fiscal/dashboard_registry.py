"""
Dashboard Registry - Sistema Central de Integración
Patrón Registry para extensibilidad sin modificación
Aplicando lecciones del Custom Fields Migration Sprint
"""

import threading
from collections.abc import Callable
from typing import Any, ClassVar

import frappe


class DashboardRegistry:
	"""Registry central para integración de módulos del dashboard fiscal"""

	_lock = threading.Lock()
	_kpis: ClassVar[dict[str, dict[str, Callable]]] = {}
	_widgets: ClassVar[dict[str, dict[str, Any]]] = {}
	_alerts: ClassVar[dict[str, dict[str, Callable]]] = {}
	_initialized = False

	@classmethod
	def initialize(cls):
		"""Inicializar registry con módulos disponibles"""
		with cls._lock:
			if cls._initialized:
				return

			try:
				# Registrar módulos automáticamente
				cls._register_available_modules()
				cls._initialized = True
				frappe.logger().info("Dashboard Registry inicializado exitosamente")
			except Exception as e:
				frappe.log_error(title="Error inicializando Dashboard Registry", message=f"Error: {e!s}")

	@classmethod
	def _register_available_modules(cls):
		"""Registrar módulos disponibles automáticamente"""
		# Aplicar patrón de auto-discovery para módulos
		available_modules = ["timbrado", "ppd", "ereceipts", "addendas", "facturas_globales", "motor_reglas"]

		for module in available_modules:
			try:
				cls._register_module_if_exists(module)
			except Exception as e:
				frappe.logger().warning(f"Módulo {module} no disponible para dashboard: {e}")

	@classmethod
	def _register_module_if_exists(cls, module_name: str):
		"""Registrar módulo si existe su integración"""
		try:
			# Intentar importar integración del módulo
			integration_path = f"facturacion_mexico.dashboard_fiscal.integrations.{module_name}_integration"
			integration_module = frappe.get_module(integration_path)

			# Ejecutar función de registro si existe
			if hasattr(integration_module, f"register_{module_name}_dashboard"):
				register_func = getattr(integration_module, f"register_{module_name}_dashboard")
				register_func()
				frappe.logger().info(f"Módulo {module_name} registrado en dashboard")
		except (ImportError, AttributeError):
			# Módulo no tiene integración de dashboard
			pass

	@classmethod
	def register_kpi(cls, module_name: str, kpi_config: dict[str, Callable]):
		"""
		Registrar KPIs de un módulo

		Args:
			module_name: Nombre del módulo
			kpi_config: Diccionario {kpi_name: kpi_function}
		"""
		with cls._lock:
			if not isinstance(kpi_config, dict):
				raise ValueError("kpi_config debe ser un diccionario")

			cls._kpis[module_name] = kpi_config
			frappe.logger().info(f"KPIs registrados para módulo: {module_name}")

	@classmethod
	def register_widget(cls, widget_config: dict[str, Any]):
		"""
		Registrar widget personalizado

		Args:
			widget_config: Configuración del widget
		"""
		with cls._lock:
			required_fields = ["code", "name", "type", "module"]
			for field in required_fields:
				if field not in widget_config:
					raise ValueError(f"Campo requerido faltante en widget: {field}")

			cls._widgets[widget_config["code"]] = widget_config
			frappe.logger().info(f"Widget registrado: {widget_config['code']}")

	@classmethod
	def register_alert_evaluator(cls, module_name: str, alert_evaluators: dict[str, Callable]):
		"""
		Registrar evaluadores de alertas

		Args:
			module_name: Nombre del módulo
			alert_evaluators: Diccionario {alert_name: evaluator_function}
		"""
		with cls._lock:
			if not isinstance(alert_evaluators, dict):
				raise ValueError("alert_evaluators debe ser un diccionario")

			cls._alerts[module_name] = alert_evaluators
			frappe.logger().info(f"Alertas registradas para módulo: {module_name}")

	@classmethod
	def get_all_kpis(cls) -> dict[str, dict[str, Callable]]:
		"""Obtener todos los KPIs registrados"""
		cls.initialize()
		return cls._kpis.copy()

	@classmethod
	def get_module_kpis(cls, module_name: str) -> dict[str, Callable]:
		"""Obtener KPIs de un módulo específico"""
		cls.initialize()
		return cls._kpis.get(module_name, {})

	@classmethod
	def get_all_widgets(cls) -> dict[str, dict[str, Any]]:
		"""Obtener todos los widgets registrados"""
		cls.initialize()
		return cls._widgets.copy()

	@classmethod
	def get_module_widgets(cls, module_name: str) -> dict[str, dict[str, Any]]:
		"""Obtener widgets de un módulo específico"""
		cls.initialize()
		return {k: v for k, v in cls._widgets.items() if v.get("module") == module_name}

	@classmethod
	def get_all_alert_evaluators(cls) -> dict[str, dict[str, Callable]]:
		"""Obtener todos los evaluadores de alertas"""
		cls.initialize()
		return cls._alerts.copy()

	@classmethod
	def get_module_alerts(cls, module_name: str) -> dict[str, Callable]:
		"""Obtener evaluadores de alertas de un módulo"""
		cls.initialize()
		return cls._alerts.get(module_name, {})

	@classmethod
	def evaluate_kpi(cls, module_name: str, kpi_name: str, **kwargs) -> Any:
		"""
		Evaluar un KPI específico de forma segura

		Args:
			module_name: Nombre del módulo
			kpi_name: Nombre del KPI
			**kwargs: Argumentos para la función KPI

		Returns:
			Resultado del KPI o None si hay error
		"""
		try:
			module_kpis = cls.get_module_kpis(module_name)
			if kpi_name not in module_kpis:
				return None

			kpi_function = module_kpis[kpi_name]
			return kpi_function(**kwargs)

		except Exception as e:
			frappe.log_error(
				title=f"Error evaluando KPI {module_name}.{kpi_name}",
				message=f"Error: {e!s}\nKwargs: {kwargs}",
			)
			return None

	@classmethod
	def evaluate_alert(cls, module_name: str, alert_name: str, **kwargs) -> dict | None:
		"""
		Evaluar una alerta específica de forma segura

		Args:
			module_name: Nombre del módulo
			alert_name: Nombre de la alerta
			**kwargs: Argumentos para la función de evaluación

		Returns:
			Resultado de la alerta o None si no se debe activar
		"""
		try:
			module_alerts = cls.get_module_alerts(module_name)
			if alert_name not in module_alerts:
				return None

			alert_function = module_alerts[alert_name]
			result = alert_function(**kwargs)

			# La función debe retornar dict con alerta o None
			if isinstance(result, dict):
				result["module"] = module_name
				result["alert_name"] = alert_name

			return result

		except Exception as e:
			frappe.log_error(
				title=f"Error evaluando alerta {module_name}.{alert_name}",
				message=f"Error: {e!s}\nKwargs: {kwargs}",
			)
			return None

	@classmethod
	def get_registry_stats(cls) -> dict[str, int]:
		"""Obtener estadísticas del registry para debugging"""
		cls.initialize()

		total_kpis = sum(len(kpis) for kpis in cls._kpis.values())
		total_alerts = sum(len(alerts) for alerts in cls._alerts.values())

		return {
			"modules_with_kpis": len(cls._kpis),
			"total_kpis": total_kpis,
			"total_widgets": len(cls._widgets),
			"modules_with_alerts": len(cls._alerts),
			"total_alerts": total_alerts,
			"initialized": cls._initialized,
		}

	@classmethod
	def reset_registry(cls):
		"""Reset registry (solo para testing)"""
		with cls._lock:
			cls._kpis.clear()
			cls._widgets.clear()
			cls._alerts.clear()
			cls._initialized = False
