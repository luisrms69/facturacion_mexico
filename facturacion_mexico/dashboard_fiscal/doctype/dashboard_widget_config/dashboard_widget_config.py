# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json
import re
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document

from facturacion_mexico.dashboard_fiscal.cache_manager import DashboardCache
from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry


class DashboardWidgetConfig(Document):
	"""Configuración de widgets del dashboard fiscal"""

	def validate(self):
		"""Validar configuración del widget"""
		self.validate_widget_code()
		self.validate_grid_position()
		self.validate_data_configuration()
		self.validate_json_configs()
		self.validate_intervals()
		self.validate_permissions()

	def validate_widget_code(self):
		"""Validar que el código del widget sea único y válido"""
		if not self.widget_code:
			frappe.throw(_("Código del widget es requerido"))

		# Validar formato del código (solo alfanumérico y guiones bajos)
		if not re.match(r"^[a-zA-Z0-9_]+$", self.widget_code):
			frappe.throw(_("El código del widget solo puede contener letras, números y guiones bajos"))

		# Verificar unicidad
		existing = frappe.get_all(
			"Dashboard Widget Config",
			filters={"widget_code": self.widget_code, "name": ["!=", self.name]},
			limit=1,
		)

		if existing:
			frappe.throw(_("Ya existe un widget con el código: {0}").format(self.widget_code))

	def validate_grid_position(self):
		"""Validar posición en el grid del dashboard"""
		# Validar rangos del grid (1-4 para cada dimensión)
		grid_fields = {
			"grid_row": "fila",
			"grid_col": "columna",
			"grid_width": "ancho",
			"grid_height": "alto",
		}

		for field, label in grid_fields.items():
			value = getattr(self, field, 0)
			if not (1 <= value <= 4):
				frappe.throw(_("El valor de {0} del grid debe estar entre 1 y 4").format(label))

		# Validar que no se sobrepase el grid
		if (self.grid_col + self.grid_width - 1) > 4:
			frappe.throw(_("El widget se extiende más allá del ancho del grid"))

		if (self.grid_row + self.grid_height - 1) > 4:
			frappe.throw(_("El widget se extiende más allá del alto del grid"))

		# Verificar colisiones con otros widgets activos
		self._check_grid_collisions()

	def _check_grid_collisions(self):
		"""Verificar colisiones con otros widgets en el grid"""
		existing_widgets = frappe.get_all(
			"Dashboard Widget Config",
			filters={"is_active": 1, "name": ["!=", self.name]},
			fields=["widget_code", "grid_row", "grid_col", "grid_width", "grid_height"],
		)

		for widget in existing_widgets:
			if self._widgets_overlap(widget):
				frappe.throw(_("El widget colisiona con el widget existente: {0}").format(widget.widget_code))

	def _widgets_overlap(self, other_widget):
		"""Verificar si dos widgets se superponen en el grid"""
		# Calcular coordenadas de este widget
		self_x1, self_y1 = self.grid_col, self.grid_row
		self_x2 = self_x1 + self.grid_width - 1
		self_y2 = self_y1 + self.grid_height - 1

		# Calcular coordenadas del otro widget
		other_x1, other_y1 = other_widget.grid_col, other_widget.grid_row
		other_x2 = other_x1 + other_widget.grid_width - 1
		other_y2 = other_y1 + other_widget.grid_height - 1

		# Verificar superposición
		return not (self_x2 < other_x1 or self_x1 > other_x2 or self_y2 < other_y1 or self_y1 > other_y2)

	def validate_data_configuration(self):
		"""Validar configuración de fuente de datos"""
		if not self.data_source:
			return

		if self.data_source == "Registry KPI":
			if not self.kpi_function:
				frappe.throw(_("Se requiere función KPI cuando la fuente de datos es 'Registry KPI'"))

		elif self.data_source == "Custom Query":
			if not self.custom_query:
				frappe.throw(_("Se requiere query personalizada cuando la fuente de datos es 'Custom Query'"))

			# Validación básica de SQL para prevenir inyecciones
			dangerous_keywords = ["DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER", "TRUNCATE"]
			query_upper = self.custom_query.upper()

			for keyword in dangerous_keywords:
				if keyword in query_upper:
					frappe.throw(_("Query contiene palabra clave no permitida: {0}").format(keyword))

	def validate_json_configs(self):
		"""Validar configuraciones JSON"""
		json_fields = {
			"custom_styles": "Estilos personalizados",
			"chart_config": "Configuración del chart",
			"color_config": "Configuración de colores",
			"icon_config": "Configuración del icono",
		}

		for field, label in json_fields.items():
			value = getattr(self, field, None)
			if value:
				try:
					json.loads(value)
				except (json.JSONDecodeError, TypeError) as e:
					frappe.throw(_("Error en {0}: {1}").format(label, str(e)))

	def validate_intervals(self):
		"""Validar intervalos de actualización y cache"""
		if self.refresh_interval and self.refresh_interval < 60:
			frappe.throw(_("El intervalo de actualización no puede ser menor a 60 segundos"))

		if self.cache_enabled and self.cache_ttl:
			if self.cache_ttl < (self.refresh_interval * 2):
				frappe.throw(_("El TTL del cache debe ser al menos el doble del intervalo de actualización"))

	def validate_permissions(self):
		"""Validar configuración de permisos"""
		if self.required_permissions:
			# Validar formato de permisos (separados por comas)
			permissions = [p.strip() for p in self.required_permissions.split(",")]
			for perm in permissions:
				if not re.match(r"^[a-zA-Z0-9_\s]+$", perm):
					frappe.throw(_("Formato de permiso inválido: {0}").format(perm))

	def get_widget_data(self, context_data=None):
		"""
		Obtener datos del widget según su configuración

		Args:
			context_data: Datos del contexto adicionales

		Returns:
			dict: Datos del widget formateados
		"""
		try:
			if not self.is_active:
				return None

			# Actualizar estadísticas de acceso
			self._update_access_stats()

			# Obtener datos según fuente configurada
			raw_data = self._fetch_widget_data(context_data)

			if raw_data is None:
				return None

			# Formatear datos para display
			formatted_data = self._format_widget_data(raw_data, context_data)

			return formatted_data

		except Exception as e:
			frappe.log_error(
				title=f"Error obteniendo datos del widget {self.widget_code}",
				message=f"Error: {e!s}\\nContext: {context_data}",
			)
			return None

	def _fetch_widget_data(self, context_data):
		"""Obtener datos crudos según la fuente configurada"""
		cache_key = f"widget_data_{self.widget_code}"

		if self.cache_enabled:
			# Intentar obtener de cache primero
			cached_data = DashboardCache.get_or_set(
				cache_key, lambda: self._execute_data_fetch(context_data), ttl=self.cache_ttl or 3600
			)
			return cached_data
		else:
			return self._execute_data_fetch(context_data)

	def _execute_data_fetch(self, context_data):
		"""Ejecutar la obtención de datos según el tipo de fuente"""
		if self.data_source == "Registry KPI":
			return self._fetch_from_registry(context_data)

		elif self.data_source == "Custom Query":
			return self._fetch_from_query(context_data)

		elif self.data_source == "API Endpoint":
			return self._fetch_from_api(context_data)

		elif self.data_source == "Static Data":
			return self._fetch_static_data()

		return None

	def _fetch_from_registry(self, context_data):
		"""Obtener datos desde el Registry de KPIs"""
		try:
			result = DashboardRegistry.evaluate_kpi(self.module, self.kpi_function, context_data)
			return result
		except Exception as e:
			frappe.log_error(
				title=f"Error evaluando KPI {self.kpi_function}",
				message=f"Module: {self.module}\\nError: {e!s}",
			)
			return None

	def _fetch_from_query(self, context_data):
		"""Obtener datos desde query personalizada"""
		try:
			# Ejecutar query con parámetros seguros
			query = self.custom_query

			# Solo permitir SELECT queries
			if not query.strip().upper().startswith("SELECT"):
				frappe.log_error(title=f"Query no válida para widget {self.widget_code}")
				return None

			result = frappe.db.sql(query, as_dict=True)
			return result

		except Exception as e:
			frappe.log_error(
				title=f"Error ejecutando query del widget {self.widget_code}",
				message=f"Query: {self.custom_query}\\nError: {e!s}",
			)
			return None

	def _fetch_from_api(self, context_data):
		"""Obtener datos desde API endpoint"""
		# Implementación placeholder para endpoints API
		frappe.logger().info(f"API fetch no implementado para widget {self.widget_code}")
		return {"message": "API fetch not implemented"}

	def _fetch_static_data(self):
		"""Obtener datos estáticos"""
		return {"value": "Static Data", "timestamp": datetime.now().isoformat()}

	def _format_widget_data(self, raw_data, context_data):
		"""Formatear datos para display en el widget"""
		try:
			formatted = {
				"widget_code": self.widget_code,
				"widget_name": self.widget_name,
				"widget_type": self.widget_type,
				"module": self.module,
				"last_updated": datetime.now().isoformat(),
				"position": {
					"row": self.grid_row,
					"col": self.grid_col,
					"width": self.grid_width,
					"height": self.grid_height,
				},
				"display_config": self._get_display_config(),
				"raw_data": raw_data,
			}

			# Aplicar formateo de valor
			if self.value_format and isinstance(raw_data, dict) and "value" in raw_data:
				formatted["formatted_value"] = self._format_value(raw_data["value"])

			# Aplicar template de título
			if self.title_template:
				formatted["title"] = self._apply_title_template(context_data or {})
			else:
				formatted["title"] = self.widget_name

			return formatted

		except Exception as e:
			frappe.log_error(
				title=f"Error formateando datos del widget {self.widget_code}",
				message=f"Raw data: {raw_data}\\nError: {e!s}",
			)
			return None

	def _get_display_config(self):
		"""Obtener configuración de display del widget"""
		config = {
			"css_classes": self.css_classes or "",
			"show_trend": self.show_trend,
			"show_comparison": self.show_comparison,
		}

		# Agregar configuraciones JSON si están definidas
		json_configs = ["custom_styles", "color_config", "icon_config", "chart_config"]

		for json_field in json_configs:
			value = getattr(self, json_field, None)
			if value:
				try:
					config[json_field.replace("_config", "")] = json.loads(value)
				except (json.JSONDecodeError, TypeError):
					config[json_field.replace("_config", "")] = {}

		return config

	def _format_value(self, value):
		"""Formatear valor según el tipo configurado"""
		try:
			if self.value_format == "currency":
				return f"${float(value):,.2f}"
			elif self.value_format == "percentage":
				return f"{float(value):.1f}%"
			elif self.value_format == "number":
				return f"{float(value):,.0f}"
			else:
				return str(value)
		except (ValueError, TypeError):
			return str(value)

	def _apply_title_template(self, context_data):
		"""Aplicar template de título con variables del contexto"""
		try:
			title = self.title_template

			# Reemplazar variables {variable_name}
			variables = re.findall(r"\\{([^}]+)\\}", title)

			for var in variables:
				value = context_data.get(var, f"[{var}]")
				title = title.replace(f"{{{var}}}", str(value))

			return title

		except Exception:
			return self.widget_name

	def _update_access_stats(self):
		"""Actualizar estadísticas de acceso del widget"""
		try:
			self.view_count = (self.view_count or 0) + 1
			self.last_accessed = datetime.now()
			self.last_updated = datetime.now()
			self.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(
				title=f"Error actualizando stats del widget {self.widget_code}", message=f"Error: {e!s}"
			)

	@staticmethod
	def get_active_widgets(module=None):
		"""Obtener widgets activos, opcionalmente filtrados por módulo"""
		filters = {"is_active": 1}
		if module:
			filters["module"] = module

		return frappe.get_all(
			"Dashboard Widget Config",
			filters=filters,
			fields=["*"],
			order_by="display_order ASC, widget_name",
		)

	@staticmethod
	def get_dashboard_layout():
		"""Obtener layout completo del dashboard"""
		try:
			widgets = DashboardWidgetConfig.get_active_widgets()

			# Organizar widgets por posición en el grid
			layout = {}

			for widget_data in widgets:
				widget = frappe.get_doc("Dashboard Widget Config", widget_data.name)
				position_key = f"{widget.grid_row}_{widget.grid_col}"

				layout[position_key] = {
					"widget_code": widget.widget_code,
					"widget_name": widget.widget_name,
					"widget_type": widget.widget_type,
					"module": widget.module,
					"position": {
						"row": widget.grid_row,
						"col": widget.grid_col,
						"width": widget.grid_width,
						"height": widget.grid_height,
					},
					"config": widget._get_display_config(),
				}

			return layout

		except Exception as e:
			frappe.log_error(title="Error obteniendo layout del dashboard", message=f"Error: {e!s}")
			return {}

	@staticmethod
	def register_widget_in_registry(widget_code):
		"""Registrar widget en el Registry del dashboard"""
		try:
			widget = frappe.get_doc("Dashboard Widget Config", widget_code)

			if not widget.is_active:
				return False

			widget_config = {
				"code": widget.widget_code,
				"name": widget.widget_name,
				"type": widget.widget_type,
				"module": widget.module,
				"position": {
					"row": widget.grid_row,
					"col": widget.grid_col,
					"width": widget.grid_width,
					"height": widget.grid_height,
				},
				"data_source": widget.data_source,
				"kpi_function": widget.kpi_function,
				"refresh_interval": widget.refresh_interval,
			}

			DashboardRegistry.register_widget(widget_config)
			return True

		except Exception as e:
			frappe.log_error(
				title=f"Error registrando widget {widget_code} en Registry", message=f"Error: {e!s}"
			)
			return False


# Child Table para roles permitidos


class DashboardWidgetAllowedRole(Document):
	"""Tabla hijo para roles permitidos en widgets"""

	pass
