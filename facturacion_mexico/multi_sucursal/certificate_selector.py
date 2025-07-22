# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Multibranch Certificate Selector
Sprint 6 Phase 1 Step 3: Selector inteligente de certificados para sistema multi-sucursal
Extiende el sistema de certificados existente para soporte multi-branch
"""

import json
from datetime import date, datetime
from typing import Optional

import frappe
from frappe import _


class MultibranchCertificateManager:
	"""
	Gestor de certificados multi-sucursal que extiende la funcionalidad existente
	Maneja la lógica de selección entre certificados globales y específicos de sucursal
	"""

	def __init__(self, company: str, branch: str | None = None):
		self.company = company
		self.branch = branch

	def get_available_certificates(self, certificate_type: str | None = None) -> list[dict]:
		"""
		Obtener certificados disponibles para una sucursal específica o company
		Implementa la lógica de certificados compartidos vs específicos
		"""
		try:
			certificates = []

			# 1. Obtener configuración de la sucursal si se especifica
			if self.branch:
				branch_config = self._get_branch_certificate_config()
				if branch_config:
					# Si la sucursal comparte certificados, incluir pool global
					if branch_config.get("share_certificates", True):
						certificates.extend(self._get_global_certificates(certificate_type))

					# Agregar certificados específicos de la sucursal
					certificates.extend(self._get_branch_specific_certificates(certificate_type))
			else:
				# Si no se especifica sucursal, obtener todos los certificados globales
				certificates = self._get_global_certificates(certificate_type)

			# 2. Filtrar certificados activos y válidos
			valid_certificates = self._filter_valid_certificates(certificates)

			# 3. Ordenar por prioridad (certificados más saludables primero)
			valid_certificates.sort(key=self._calculate_certificate_priority, reverse=True)

			return valid_certificates

		except Exception as e:
			frappe.log_error(f"Error getting available certificates: {e!s}", "Certificate Selector")
			return []

	def select_best_certificate(self, certificate_type: str | None = None) -> dict | None:
		"""
		Seleccionar el mejor certificado disponible para una operación
		"""
		available = self.get_available_certificates(certificate_type)

		if not available:
			return None

		# El primer certificado es el mejor (ya está ordenado por prioridad)
		return available[0]

	def validate_certificate_availability(self, certificate_id: str) -> tuple[bool, str]:
		"""
		Validar si un certificado específico está disponible para esta sucursal
		"""
		try:
			# Buscar en certificados globales
			global_cert = self._find_certificate_in_global_settings(certificate_id)
			if global_cert:
				if self.branch:
					# Verificar si la sucursal puede usar certificados globales
					branch_config = self._get_branch_certificate_config()
					if branch_config and branch_config.get("share_certificates", True):
						return True, "Certificado global disponible"
				else:
					return True, "Certificado global disponible"

			# Buscar en certificados específicos de sucursal
			if self.branch:
				branch_cert = self._find_certificate_in_branch_config(certificate_id)
				if branch_cert:
					return True, "Certificado específico de sucursal disponible"

			return False, "Certificado no encontrado o no disponible para esta sucursal"

		except Exception as e:
			frappe.log_error(
				f"Error validating certificate {certificate_id}: {e!s}", "Certificate Validation"
			)
			return False, f"Error de validación: {e!s}"

	def get_certificate_health_summary(self) -> dict:
		"""
		Obtener resumen de salud de certificados disponibles
		Compatible con el sistema de health monitoring del Dashboard Fiscal
		"""
		certificates = self.get_available_certificates()

		summary = {
			"total_certificates": len(certificates),
			"healthy": 0,
			"warning": 0,
			"critical": 0,
			"expired": 0,
			"shared_certificates": 0,
			"specific_certificates": 0,
			"expiring_soon": 0,
			"recommended_certificate": None,
			"integration_notes": {
				"facturapi_compatibility": "FacturAPI usa API keys globales, certificados son para validación local",
				"dashboard_integration": "Compatible con health monitoring del Dashboard Fiscal",
				"certificate_purpose": "Certificados para timbrado y validación CFDI, no para FacturAPI",
			},
		}

		today = date.today()

		for cert in certificates:
			# Analizar salud del certificado
			health_status = self._get_certificate_health_status(cert)

			if health_status == "healthy":
				summary["healthy"] += 1
			elif health_status == "warning":
				summary["warning"] += 1
			elif health_status == "critical":
				summary["critical"] += 1
			elif health_status == "expired":
				summary["expired"] += 1

			# Contar tipos
			if cert.get("is_shared", True):
				summary["shared_certificates"] += 1
			else:
				summary["specific_certificates"] += 1

			# Verificar vencimiento próximo (30 días)
			if cert.get("valid_to") and isinstance(cert["valid_to"], date):
				days_to_expiry = (cert["valid_to"] - today).days
				if 0 < days_to_expiry <= 30:
					summary["expiring_soon"] += 1

		# Certificado recomendado (el de mayor prioridad)
		if certificates:
			summary["recommended_certificate"] = certificates[0]

		return summary

	def _get_branch_certificate_config(self) -> dict | None:
		"""
		Obtener configuración de certificados de la sucursal
		"""
		try:
			if not self.branch:
				return None

			# Obtener Branch doc
			branch_doc = frappe.get_cached_doc("Branch", self.branch)

			# Obtener configuración fiscal de la sucursal
			fiscal_config = frappe.db.get_value(
				"Configuracion Fiscal Sucursal",
				{"branch": self.branch},
				["name", "certificate_ids"],
				as_dict=True,
			)

			config = {
				"share_certificates": branch_doc.get("fm_share_certificates", True),
				"specific_certificate_ids": [],
			}

			# Parsear certificate_ids si existe
			if fiscal_config and fiscal_config.certificate_ids:
				try:
					config["specific_certificate_ids"] = json.loads(fiscal_config.certificate_ids)
				except json.JSONDecodeError:
					config["specific_certificate_ids"] = []

			return config

		except Exception as e:
			frappe.log_error(f"Error getting branch certificate config: {e!s}", "Branch Config")
			return None

	def _get_global_certificates(self, certificate_type: str | None = None) -> list[dict]:
		"""
		Obtener certificados del pool global (Facturacion Mexico Settings)
		"""
		# Por ahora retornar lista vacía ya que el DocType principal no tiene certificados
		# En el futuro aquí se conectaría con Facturacion Mexico Settings

		# TODO: Implementar cuando se agreguen campos de certificado a Settings
		global_certificates = []

		# Simular estructura para desarrollo
		if frappe.conf.get("developer_mode"):
			global_certificates = [
				{
					"id": "global_cert_1",
					"name": "Certificado Global CSD",
					"type": "CSD",
					"source": "global",
					"company": self.company,
					"valid_from": date.today(),
					"valid_to": date(2025, 12, 31),
					"is_shared": True,
					"is_active": True,
					"file_path": "/path/to/cert.cer",
					"key_path": "/path/to/key.key",
					"password": "encrypted_password",
				}
			]

		# Filtrar por tipo si se especifica
		if certificate_type and global_certificates:
			global_certificates = [
				cert for cert in global_certificates if cert.get("type") == certificate_type
			]

		return global_certificates

	def _get_branch_specific_certificates(self, certificate_type: str | None = None) -> list[dict]:
		"""
		Obtener certificados específicos de la sucursal
		"""
		certificates = []

		try:
			# Obtener configuración fiscal de la sucursal
			fiscal_config = frappe.db.get_value(
				"Configuracion Fiscal Sucursal", {"branch": self.branch}, ["certificate_ids"], as_dict=True
			)

			if fiscal_config and fiscal_config.certificate_ids:
				# Parsear certificate_ids JSON
				try:
					cert_ids = json.loads(fiscal_config.certificate_ids)

					# Por cada ID, crear estructura de certificado
					for cert_id in cert_ids:
						cert = {
							"id": cert_id,
							"name": f"Certificado Sucursal {cert_id}",
							"type": certificate_type or "CSD",
							"source": "branch",
							"branch": self.branch,
							"company": self.company,
							"valid_from": date.today(),
							"valid_to": date(2025, 12, 31),  # Placeholder
							"is_shared": False,
							"is_active": True,
						}

						# Filtrar por tipo si se especifica
						if not certificate_type or cert["type"] == certificate_type:
							certificates.append(cert)

				except json.JSONDecodeError:
					frappe.logger().warning(f"Invalid certificate_ids JSON for branch {self.branch}")

		except Exception as e:
			frappe.log_error(f"Error getting branch specific certificates: {e!s}", "Branch Certificates")

		return certificates

	def _filter_valid_certificates(self, certificates: list[dict]) -> list[dict]:
		"""
		Filtrar certificados válidos (activos y no vencidos)
		"""
		valid_certificates = []
		today = date.today()

		for cert in certificates:
			# Verificar que esté activo
			if not cert.get("is_active", True):
				continue

			# Verificar que no esté vencido
			valid_to = cert.get("valid_to")
			if valid_to and isinstance(valid_to, date) and valid_to < today:
				continue

			valid_certificates.append(cert)

		return valid_certificates

	def _calculate_certificate_priority(self, certificate: dict) -> int:
		"""
		Calcular prioridad de un certificado para ordenamiento
		"""
		priority = 100  # Prioridad base

		# Bonificar certificados compartidos (mejor distribución de carga)
		if certificate.get("is_shared", True):
			priority += 20

		# Penalizar por vencimiento cercano
		valid_to = certificate.get("valid_to")
		if valid_to and isinstance(valid_to, date):
			days_to_expiry = (valid_to - date.today()).days
			if days_to_expiry < 30:
				priority -= 50
			elif days_to_expiry < 90:
				priority -= 20

		# Bonificar certificados específicos de sucursal si la sucursal los tiene
		if not certificate.get("is_shared", True) and certificate.get("branch") == self.branch:
			priority += 10

		return priority

	def _get_certificate_health_status(self, certificate: dict) -> str:
		"""
		Obtener estado de salud de un certificado
		"""
		if not certificate.get("is_active", True):
			return "inactive"

		valid_to = certificate.get("valid_to")
		if valid_to and isinstance(valid_to, date):
			days_to_expiry = (valid_to - date.today()).days

			if days_to_expiry <= 0:
				return "expired"
			elif days_to_expiry <= 15:
				return "critical"
			elif days_to_expiry <= 30:
				return "warning"

		return "healthy"

	def _find_certificate_in_global_settings(self, certificate_id: str) -> dict | None:
		"""
		Buscar certificado en configuración global
		"""
		# TODO: Implementar búsqueda en Facturacion Mexico Settings
		# cuando se agreguen los campos de certificado
		return None

	def _find_certificate_in_branch_config(self, certificate_id: str) -> dict | None:
		"""
		Buscar certificado en configuración de sucursal
		"""
		try:
			fiscal_config = frappe.db.get_value(
				"Configuracion Fiscal Sucursal", {"branch": self.branch}, ["certificate_ids"], as_dict=True
			)

			if fiscal_config and fiscal_config.certificate_ids:
				cert_ids = json.loads(fiscal_config.certificate_ids)
				if certificate_id in cert_ids:
					return {"id": certificate_id, "branch": self.branch}

		except Exception as e:
			frappe.logger().warning(f"Error searching certificate in branch config: {e!s}")

		return None


def get_available_certificates(
	company: str, branch: str | None = None, certificate_type: str | None = None
) -> list[dict]:
	"""
	Función wrapper para obtener certificados disponibles
	Implementa la función referenciada en configuracion_fiscal_sucursal.py
	"""
	manager = MultibranchCertificateManager(company, branch)
	return manager.get_available_certificates(certificate_type)


@frappe.whitelist()
def get_branch_certificate_status(branch: str) -> dict:
	"""
	API para obtener estado de certificados de una sucursal
	"""
	try:
		branch_doc = frappe.get_cached_doc("Branch", branch)

		if not branch_doc.get("fm_enable_fiscal"):
			return {
				"success": False,
				"message": "Sucursal no tiene habilitada la facturación fiscal",
				"data": {},
			}

		manager = MultibranchCertificateManager(branch_doc.company, branch)

		# Obtener certificados disponibles
		certificates = manager.get_available_certificates()

		# Obtener resumen de salud
		health_summary = manager.get_certificate_health_summary()

		# Obtener certificado recomendado
		best_cert = manager.select_best_certificate()

		return {
			"success": True,
			"data": {
				"branch": branch,
				"certificates": certificates,
				"health_summary": health_summary,
				"recommended_certificate": best_cert,
				"total_available": len(certificates),
			},
		}

	except Exception as e:
		frappe.log_error(f"Error getting branch certificate status: {e!s}", "Branch Certificate Status")
		return {"success": False, "message": f"Error obteniendo estado: {e!s}", "data": {}}


@frappe.whitelist()
def select_certificate_for_invoice(branch: str, certificate_type: str = "CSD") -> dict:
	"""
	API para seleccionar certificado óptimo para facturación
	"""
	try:
		branch_doc = frappe.get_cached_doc("Branch", branch)
		manager = MultibranchCertificateManager(branch_doc.company, branch)

		# Seleccionar mejor certificado para el tipo solicitado
		certificate = manager.select_best_certificate(certificate_type)

		if not certificate:
			return {
				"success": False,
				"message": f"No hay certificados {certificate_type} disponibles para la sucursal",
				"certificate": None,
			}

		return {
			"success": True,
			"message": "Certificado seleccionado exitosamente",
			"certificate": certificate,
		}

	except Exception as e:
		frappe.log_error(f"Error selecting certificate for invoice: {e!s}", "Certificate Selection")
		return {"success": False, "message": f"Error seleccionando certificado: {e!s}", "certificate": None}
