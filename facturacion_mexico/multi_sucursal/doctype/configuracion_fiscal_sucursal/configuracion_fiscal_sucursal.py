# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now


class ConfiguracionFiscalSucursal(Document):
	"""
	DocType: Configuracion Fiscal Sucursal
	Gestiona la configuración fiscal específica de cada sucursal
	Parte del Sprint 6 - Multi-Sucursal + Addendas Genéricas
	"""

	def validate(self):
		"""Validaciones del documento"""
		self.validate_branch_configuration()
		self.validate_folio_thresholds()
		self.sync_with_branch()
		self.calculate_statistics()

	def before_save(self):
		"""Acciones antes de guardar"""
		# Actualizar timestamp de sincronización
		self.last_sync_date = now()

		# Evaluar si necesita atención
		self.evaluate_attention_needed()

	def validate_branch_configuration(self):
		"""Validar que la sucursal esté habilitada para facturación fiscal"""
		if not self.branch:
			frappe.throw(_("Sucursal es obligatoria"))

		# REGLA #35: Defensive DocType access
		try:
			branch_doc = frappe.get_doc("Branch", self.branch)
		except frappe.DoesNotExistError:
			frappe.throw(_("La sucursal '{0}' no existe").format(self.branch))

		# Verificar que branch_doc se obtuvo correctamente
		if not branch_doc:
			frappe.throw(_("Error al obtener datos de la sucursal '{0}'").format(self.branch))

		if not branch_doc.get("fm_enable_fiscal"):
			frappe.throw(
				_("La sucursal '{0}' no está habilitada para facturación fiscal").format(self.branch)
			)

		# Sincronizar company desde branch
		if branch_doc.company != self.company:
			self.company = branch_doc.company

	def validate_folio_thresholds(self):
		"""Validar umbrales de folios"""
		if self.folio_critical_threshold and self.folio_warning_threshold:
			if self.folio_critical_threshold >= self.folio_warning_threshold:
				frappe.throw(_("El umbral crítico debe ser menor al umbral de advertencia"))

		# Establecer valores por defecto
		if not self.folio_warning_threshold:
			self.folio_warning_threshold = 100

		if not self.folio_critical_threshold:
			self.folio_critical_threshold = 50

	def sync_with_branch(self):
		"""Sincronizar datos críticos con Branch"""
		# REGLA #35: Defensive DocType access
		try:
			branch_doc = frappe.get_doc("Branch", self.branch)
		except frappe.DoesNotExistError:
			frappe.log_error(f"Branch {self.branch} not found during sync", "Branch Sync Error")
			return

		# Sincronizar desde Branch hacia Configuracion Fiscal
		self.serie_fiscal = branch_doc.get("fm_serie_pattern", "")
		self.folio_current = branch_doc.get("fm_folio_current", 0)

		# Si se especifica threshold en configuración fiscal, sincronizar hacia Branch
		if (
			self.folio_warning_threshold
			and branch_doc.get("fm_folio_warning_threshold") != self.folio_warning_threshold
		):
			branch_doc.fm_folio_warning_threshold = self.folio_warning_threshold
			branch_doc.save()

	def calculate_statistics(self):
		"""Calcular estadísticas de la sucursal"""
		try:
			# Obtener estadísticas de facturas de esta sucursal
			stats = self.get_branch_invoice_statistics()

			self.total_invoices_generated = stats.get("total_invoices", 0)
			self.monthly_average = stats.get("monthly_average", 0.0)
			self.last_invoice_date = stats.get("last_invoice_date")

			# Calcular días hasta agotamiento
			self.calculate_days_until_exhaustion()

		except Exception as e:
			frappe.log_error(
				f"Error calculating statistics for {self.name}: {e!s}", "Fiscal Branch Config Stats"
			)

	def get_branch_invoice_statistics(self):
		"""Obtener estadísticas de facturas de la sucursal"""
		try:
			# Query para obtener facturas de esta sucursal
			# Nota: Asumiendo que existe custom field fm_branch en Sales Invoice
			invoice_data = frappe.db.sql(
				"""
				SELECT
					COUNT(*) as total_invoices,
					MAX(posting_date) as last_invoice_date,
					AVG(CASE
						WHEN DATEDIFF(NOW(), posting_date) <= 30 THEN 1
						ELSE 0
					END) * 30 as monthly_average
				FROM `tabSales Invoice`
				WHERE docstatus = 1
				AND fm_branch = %s
				AND company = %s
			""",
				(self.branch, self.company),
				as_dict=True,
			)

			if invoice_data and invoice_data[0]:
				data = invoice_data[0]
				return {
					"total_invoices": data.get("total_invoices", 0),
					"monthly_average": round(data.get("monthly_average", 0.0), 2),
					"last_invoice_date": data.get("last_invoice_date"),
				}

		except Exception as e:
			frappe.logger().warning(f"Error getting invoice statistics for branch {self.branch}: {e!s}")

		return {"total_invoices": 0, "monthly_average": 0.0, "last_invoice_date": None}

	def calculate_days_until_exhaustion(self):
		"""Calcular días estimados hasta agotar folios"""
		try:
			branch_doc = frappe.get_doc("Branch", self.branch)

			folio_current = self.folio_current or 0
			folio_end = branch_doc.get("fm_folio_end", 0)
			monthly_avg = self.monthly_average or 0

			if folio_end > folio_current and monthly_avg > 0:
				remaining_folios = folio_end - folio_current
				daily_average = monthly_avg / 30

				self.days_until_exhaustion = (
					int(remaining_folios / daily_average) if daily_average > 0 else 999999
				)
			else:
				self.days_until_exhaustion = 999999  # Sin límite o sin datos

		except Exception as e:
			self.days_until_exhaustion = 0
			frappe.logger().warning(f"Error calculating exhaustion days: {e!s}")

	def evaluate_attention_needed(self):
		"""Evaluar si la configuración necesita atención"""
		needs_attention = False

		# Evaluar folios bajos
		if self.days_until_exhaustion and self.days_until_exhaustion <= 30:
			needs_attention = True

		# Evaluar umbrales
		branch_doc = frappe.get_doc("Branch", self.branch)
		folio_end = branch_doc.get("fm_folio_end", 0)
		folio_current = self.folio_current or 0

		if folio_end > 0:
			remaining = folio_end - folio_current
			if remaining <= self.folio_critical_threshold:
				needs_attention = True

		# Evaluar última sincronización
		if self.last_sync_date:
			days_since_sync = (get_datetime() - get_datetime(self.last_sync_date)).days
			if days_since_sync > 7:  # Una semana sin sincronización
				needs_attention = True

		self.needs_attention = needs_attention

	def get_folio_status(self):
		"""Obtener estado actual de folios con semáforo"""
		try:
			branch_doc = frappe.get_doc("Branch", self.branch)

			folio_current = self.folio_current or 0
			folio_end = branch_doc.get("fm_folio_end", 0)

			if folio_end == 0:
				return {
					"status": "unknown",
					"color": "gray",
					"message": "Sin límite de folios configurado",
					"remaining": 0,
					"percentage": 0,
				}

			remaining = folio_end - folio_current
			percentage = (remaining / (folio_end - branch_doc.get("fm_folio_start", 1))) * 100

			if remaining <= self.folio_critical_threshold:
				status = "critical"
				color = "red"
				message = f"Crítico: {remaining} folios restantes"
			elif remaining <= self.folio_warning_threshold:
				status = "warning"
				color = "yellow"
				message = f"Advertencia: {remaining} folios restantes"
			else:
				status = "good"
				color = "green"
				message = f"Normal: {remaining} folios disponibles"

			return {
				"status": status,
				"color": color,
				"message": message,
				"remaining": remaining,
				"percentage": round(percentage, 1),
				"days_until_exhaustion": self.days_until_exhaustion,
			}

		except Exception as e:
			frappe.log_error(f"Error getting folio status: {e!s}", "Folio Status")
			return {
				"status": "error",
				"color": "red",
				"message": f"Error calculando estado: {e!s}",
				"remaining": 0,
				"percentage": 0,
			}

	def get_certificate_configuration(self):
		"""Obtener configuración de certificados"""
		try:
			branch_doc = frappe.get_doc("Branch", self.branch)

			config = {
				"share_certificates": branch_doc.get("fm_share_certificates", True),
				"specific_certificates": [],
				"available_certificates": [],
			}

			# Si tiene certificados específicos
			if self.certificate_ids and isinstance(self.certificate_ids, str):
				try:
					config["specific_certificates"] = json.loads(self.certificate_ids)
				except json.JSONDecodeError:
					config["specific_certificates"] = []

			# Obtener certificados disponibles usando el Certificate Selector
			try:
				from facturacion_mexico.multi_sucursal.certificate_selector import get_available_certificates

				config["available_certificates"] = get_available_certificates(self.company, self.branch)
			except ImportError:
				# Fallback si el Certificate Selector no está disponible
				config["available_certificates"] = []

			return config

		except Exception as e:
			frappe.log_error(f"Error getting certificate config: {e!s}", "Certificate Config")
			return {"share_certificates": True, "specific_certificates": [], "available_certificates": []}


def create_default_config(branch_name):
	"""
	Crear configuración fiscal por defecto para una sucursal
	Se llama automáticamente cuando se habilita fm_enable_fiscal en Branch
	"""
	try:
		# Verificar si ya existe
		existing = frappe.db.exists("Configuracion Fiscal Sucursal", {"branch": branch_name})
		if existing:
			return existing

		branch_doc = frappe.get_doc("Branch", branch_name)

		# Crear nueva configuración
		config = frappe.new_doc("Configuracion Fiscal Sucursal")
		config.branch = branch_name
		config.company = branch_doc.company
		config.is_active = 1
		config.created_automatically = 1
		config.folio_warning_threshold = 100
		config.folio_critical_threshold = 50

		config.insert()
		frappe.db.commit()

		frappe.msgprint(
			_("Configuración fiscal creada automáticamente para la sucursal {0}").format(branch_name)
		)

		return config.name

	except Exception as e:
		frappe.log_error(
			f"Error creating default fiscal config for {branch_name}: {e!s}", "Auto Config Creation"
		)
		return None


@frappe.whitelist()
def get_branch_fiscal_status(branch):
	"""
	API para obtener estado fiscal de una sucursal
	"""
	try:
		# REGLA #35: Validate required parameters
		if not branch:
			return {"success": False, "message": "branch parameter is required", "data": None}

		config_name = frappe.db.get_value("Configuracion Fiscal Sucursal", {"branch": branch})

		if not config_name:
			return {
				"success": False,
				"message": "Configuración fiscal no encontrada para la sucursal",
				"data": None,
			}

		# REGLA #35: Defensive DocType access
		try:
			config_doc = frappe.get_doc("Configuracion Fiscal Sucursal", config_name)
		except frappe.DoesNotExistError:
			return {
				"success": False,
				"message": f"Configuracion Fiscal Sucursal {config_name} not found",
				"data": None,
			}

		return {
			"success": True,
			"data": {
				"branch": branch,
				"folio_status": config_doc.get_folio_status(),
				"certificate_config": config_doc.get_certificate_configuration(),
				"statistics": {
					"total_invoices": config_doc.total_invoices_generated,
					"monthly_average": config_doc.monthly_average,
					"last_invoice_date": config_doc.last_invoice_date,
					"needs_attention": config_doc.needs_attention,
				},
				"last_sync": config_doc.last_sync_date,
			},
		}

	except Exception as e:
		frappe.log_error(f"Error getting branch fiscal status: {e!s}", "Branch Status API")
		return {"success": False, "message": f"Error obteniendo estado: {e!s}", "data": None}


@frappe.whitelist()
def sync_all_branch_configurations():
	"""
	Sincronizar todas las configuraciones fiscales con sus respectivas sucursales
	"""
	try:
		configs = frappe.get_all("Configuracion Fiscal Sucursal", filters={"is_active": 1})

		updated_count = 0
		error_count = 0

		for config in configs:
			try:
				config_doc = frappe.get_doc("Configuracion Fiscal Sucursal", config.name)
				config_doc.calculate_statistics()
				config_doc.save()
				updated_count += 1
			except Exception as e:
				error_count += 1
				frappe.log_error(f"Error syncing config {config.name}: {e!s}", "Config Sync")

		return {
			"success": True,
			"message": f"Sincronización completada: {updated_count} actualizadas, {error_count} errores",
		}

	except Exception as e:
		return {"success": False, "message": f"Error en sincronización masiva: {e!s}"}
