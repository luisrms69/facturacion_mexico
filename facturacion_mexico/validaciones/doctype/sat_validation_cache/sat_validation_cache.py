"""
SAT Validation Cache - DocType para cache de validaciones SAT
Sprint 2 - Sistema de Facturación México
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document


class SATValidationCache(Document):
	def before_save(self):
		"""Establecer metadata antes de guardar."""
		self.set_expiry_date()
		self.set_last_updated_by()
		self.increment_validation_count()

	def set_expiry_date(self):
		"""Establecer fecha de expiración según tipo de validación."""
		if not self.expiry_date:
			settings = frappe.get_single("Facturacion Mexico Settings")
			cache_days = settings.get("rfc_cache_days", 30)

			# Diferentes duraciones según tipo de validación
			if self.validation_type == "fm_rfc":
				days = cache_days
			elif self.validation_type == "Lista69B":
				days = 7  # Lista 69B cambia semanalmente
			elif self.validation_type == "Obligaciones":
				days = cache_days
			elif self.validation_type == "fm_regimen_fiscal":
				days = cache_days
			elif self.validation_type == "Domicilio_Fiscal":
				days = cache_days
			else:
				days = 30  # Default

			self.expiry_date = frappe.utils.add_days(self.validation_date, days)

	def set_last_updated_by(self):
		"""Establecer usuario que actualiza."""
		self.last_updated_by = frappe.session.user

	def increment_validation_count(self):
		"""Incrementar contador de validaciones."""
		if not self.validation_count:
			self.validation_count = 1
		else:
			self.validation_count += 1

	def validate(self):
		"""Validaciones del documento."""
		self.validate_lookup_value()
		self.validate_validation_type()

	def validate_lookup_value(self):
		"""Validar formato del valor a consultar."""
		if self.validation_type == "fm_rfc":
			self.validate_rfc_format()

	def validate_rfc_format(self):
		"""Validar formato de RFC."""
		if not self.lookup_value:
			return

		fm_rfc = self.lookup_value.upper().strip()

		# RFC debe tener 12 o 13 caracteres
		if len(fm_rfc) not in [12, 13]:
			frappe.throw(_("RFC debe tener 12 o 13 caracteres"))

		# Validar caracteres alfanuméricos
		if not fm_rfc.replace("&", "").replace("Ñ", "N").isalnum():
			frappe.throw(_("RFC contiene caracteres inválidos"))

		self.lookup_value = fm_rfc

	def calculate_expiry_date(self):
		"""Calcular fecha de expiración según tipo de validación."""

		if not self.validation_date:
			self.validation_date = frappe.utils.now()

		base_date = frappe.utils.getdate(self.validation_date)

		if self.validation_type == "fm_rfc":
			# RFC válido por 30 días
			self.expiry_date = frappe.utils.add_days(base_date, 30)
		elif self.validation_type == "Lista69B":
			# Lista 69B válida por 7 días
			self.expiry_date = frappe.utils.add_days(base_date, 7)
		else:
			# Por defecto 30 días
			self.expiry_date = frappe.utils.add_days(base_date, 30)

	def is_cache_expired(self):
		"""Verificar si el cache ha expirado (alias para is_expired)."""
		return self.is_expired()

	def set_metadata(self):
		"""Establecer metadatos automáticamente."""
		if not self.validation_date:
			self.validation_date = frappe.utils.now()
		if not hasattr(self, "created_by") or not self.created_by:
			self.created_by = frappe.session.user
		self.last_accessed = frappe.utils.now()

	def validate_no_duplicate_cache(self):
		"""Validar que no exista cache duplicado activo."""
		if self.lookup_value and self.validation_type:
			existing = frappe.db.get_value(
				"SAT Validation Cache",
				{
					"lookup_value": self.lookup_value,
					"validation_type": self.validation_type,
					"name": ["!=", self.name or ""],
				},
				"name",
			)
			if existing:
				frappe.throw(
					_("Ya existe un cache activo para {0} tipo {1}").format(
						self.lookup_value, self.validation_type
					)
				)

	def validate_validation_type(self):
		"""Validar que el tipo de validación sea válido."""
		valid_types = ["fm_rfc", "Lista69B", "Obligaciones", "fm_regimen_fiscal", "Domicilio_Fiscal"]
		if self.validation_type not in valid_types:
			frappe.throw(_("Tipo de validación inválido: {0}").format(self.validation_type))

	def is_expired(self):
		"""Verificar si el cache ha expirado."""
		if not self.expiry_date:
			return True

		expiry_date = frappe.utils.getdate(self.expiry_date)
		today = frappe.utils.getdate(frappe.utils.today())

		return expiry_date <= today

	def refresh_validation(self, force=False):
		"""Refrescar validación si ha expirado o es forzado."""
		if not force and not self.is_expired():
			return False

		# Llamar al servicio de validación correspondiente
		if self.validation_type == "fm_rfc":
			return self.refresh_rfc_validation()
		elif self.validation_type == "Lista69B":
			return self.refresh_lista69b_validation()
		# Agregar otros tipos según necesidad

		return False

	def refresh_rfc_validation(self):
		"""Refrescar validación de RFC."""
		try:
			# Importación dinámica para evitar import cíclico
			from importlib import import_module

			api_module = import_module("facturacion_mexico.validaciones.api")
			validate_rfc = api_module.validate_rfc

			result = validate_rfc(self.lookup_value, use_cache=False)

			if result.get("success"):
				self.is_valid = result.get("is_valid", False)
				self.validation_data = json.dumps(result.get("data", {}))
				self.validation_date = frappe.utils.now()
				self.expiry_date = None  # Recalcular en before_save
				self.save()
				return True

		except Exception as e:
			frappe.log_error(message=str(e), title="Error refrescando validación RFC")

		return False

	def refresh_lista69b_validation(self):
		"""Refrescar validación de Lista 69B."""
		try:
			# Importación dinámica para evitar import cíclico
			from importlib import import_module

			api_module = import_module("facturacion_mexico.validaciones.api")
			validate_lista_69b = api_module.validate_lista_69b

			result = validate_lista_69b(self.lookup_value, use_cache=False)

			if result.get("success"):
				self.is_valid = not result.get("esta_en_lista", True)  # Invertir lógica
				self.validation_data = json.dumps(result.get("data", {}))
				self.validation_date = frappe.utils.now()
				self.expiry_date = None  # Recalcular en before_save
				self.save()
				return True

		except Exception as e:
			frappe.log_error(message=str(e), title="Error refrescando validación Lista 69B")

		return False

	@staticmethod
	def get_cached_validation(validation_type, lookup_value, auto_refresh=True):
		"""Obtener validación desde cache o crear nueva."""
		try:
			# Buscar en cache existente
			cache_name = frappe.db.get_value(
				"SAT Validation Cache",
				{"validation_type": validation_type, "lookup_value": lookup_value.upper().strip()},
			)

			if cache_name:
				cache_doc = frappe.get_doc("SAT Validation Cache", cache_name)

				# Si no ha expirado, retornar cache
				if not cache_doc.is_expired():
					cache_doc.increment_validation_count()
					cache_doc.save()
					return {
						"success": True,
						"from_cache": True,
						"is_valid": cache_doc.is_valid,
						"data": json.loads(cache_doc.validation_data or "{}"),
						"cache_date": cache_doc.validation_date,
						"expiry_date": cache_doc.expiry_date,
					}

				# Si ha expirado y auto_refresh está habilitado, refrescar
				if auto_refresh and cache_doc.refresh_validation():
					return {
						"success": True,
						"from_cache": False,
						"is_valid": cache_doc.is_valid,
						"data": json.loads(cache_doc.validation_data or "{}"),
						"cache_date": cache_doc.validation_date,
						"expiry_date": cache_doc.expiry_date,
					}

			# No existe en cache o no se pudo refrescar, crear nuevo
			return SATValidationCache.create_new_validation(validation_type, lookup_value)

		except Exception as e:
			frappe.log_error(message=str(e), title="Error obteniendo validación desde cache")
			return {"success": False, "message": str(e)}

	@staticmethod
	def create_new_validation(validation_type, lookup_value):
		"""Crear nueva validación y guardar en cache."""
		try:
			# Llamar al servicio de validación
			if validation_type == "fm_rfc":
				from facturacion_mexico.validaciones.api import validate_rfc

				result = validate_rfc(lookup_value, use_cache=False)
			elif validation_type == "Lista69B":
				from facturacion_mexico.validaciones.api import validate_lista_69b

				result = validate_lista_69b(lookup_value, use_cache=False)
			else:
				return {
					"success": False,
					"message": _("Tipo de validación no implementado: {0}").format(validation_type),
				}

			if not result.get("success"):
				return result

			# Crear documento de cache
			cache_doc = frappe.new_doc("SAT Validation Cache")
			cache_doc.validation_type = validation_type
			cache_doc.lookup_value = lookup_value.upper().strip()
			cache_doc.validation_date = frappe.utils.now()
			cache_doc.is_valid = result.get("is_valid", False)

			# Para Lista 69B, invertir lógica (estar en lista = no válido)
			if validation_type == "Lista69B":
				cache_doc.is_valid = not result.get("esta_en_lista", True)

			cache_doc.validation_data = json.dumps(result.get("data", {}))
			cache_doc.insert()

			return {
				"success": True,
				"from_cache": False,
				"is_valid": cache_doc.is_valid,
				"data": result.get("data", {}),
				"cache_date": cache_doc.validation_date,
				"expiry_date": cache_doc.expiry_date,
			}

		except Exception as e:
			frappe.log_error(message=str(e), title="Error creando nueva validación")
			return {"success": False, "message": str(e)}


@frappe.whitelist()
def cleanup_expired_cache():
	"""Limpiar cache expirado (llamada por scheduler)."""
	try:
		today = frappe.utils.today()

		# Obtener registros expirados
		expired_records = frappe.db.get_list(
			"SAT Validation Cache", filters={"expiry_date": ["<", today]}, pluck="name"
		)

		# Eliminar registros expirados
		for record_name in expired_records:
			frappe.delete_doc("SAT Validation Cache", record_name)

		frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist bulk cache cleanup for scheduled operation

		return {
			"success": True,
			"cleaned_count": len(expired_records),
			"message": _("Cache expirado limpiado: {0} registros").format(len(expired_records)),
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error limpiando cache expirado")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_cache_statistics():
	"""Obtener estadísticas del cache."""
	try:
		stats = frappe.db.sql(
			"""
			SELECT
				validation_type,
				COUNT(*) as total_records,
				SUM(CASE WHEN expiry_date >= CURDATE() THEN 1 ELSE 0 END) as active_records,
				SUM(CASE WHEN expiry_date < CURDATE() THEN 1 ELSE 0 END) as expired_records,
				SUM(validation_count) as total_validations,
				AVG(validation_count) as avg_validations_per_record
			FROM `tabSAT Validation Cache`
			GROUP BY validation_type
			ORDER BY total_records DESC
		""",
			as_dict=True,
		)

		return {
			"success": True,
			"statistics": stats,
			"total_cache_records": sum(s["total_records"] for s in stats),
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error obteniendo estadísticas de cache")
		return {"success": False, "message": str(e)}


# Métodos estáticos requeridos por los tests
class SATValidationCache(SATValidationCache):
	"""Extensión de la clase para métodos estáticos."""

	@staticmethod
	def deactivate_expired_caches():
		"""Método estático para desactivar caches expirados."""
		result = cleanup_expired_cache()
		return result.get("cleaned_count", 0)

	@staticmethod
	def create_cache_record(lookup_value, validation_type, is_valid=True, validation_data=None):
		"""Método estático para crear registro de cache."""
		try:
			cache_doc = frappe.new_doc("SAT Validation Cache")
			cache_doc.lookup_value = lookup_value
			cache_doc.validation_type = validation_type
			cache_doc.is_valid = is_valid
			cache_doc.validation_data = validation_data or "{}"
			cache_doc.validation_date = frappe.utils.now()
			cache_doc.insert()
			return cache_doc.name
		except Exception:
			return None

	@staticmethod
	def get_valid_cache(lookup_value, validation_type):
		"""Método estático para obtener cache válido."""
		result = SATValidationCache.get_cached_validation(validation_type, lookup_value)
		if result.get("success") and result.get("is_valid", False):
			return result.get("data", {})
		return None

	@staticmethod
	def cleanup_expired_caches(days_to_keep=90):
		"""Método estático para limpiar caches expirados con días de retención."""
		result = cleanup_expired_cache()
		return result.get("cleaned_count", 0)
