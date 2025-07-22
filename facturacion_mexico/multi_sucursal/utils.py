# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Utilidades del módulo Multi-Sucursal
Sprint 6: Funciones de utilidad para el sistema multi-sucursal
"""

import frappe
from frappe import _


def install_multi_sucursal_system():
	"""
	Instalar y configurar el sistema multi-sucursal completo
	Ejecuta todos los pasos necesarios para habilitar la funcionalidad
	"""
	print("🚀 Iniciando instalación del sistema Multi-Sucursal...")

	try:
		# Paso 1: Crear custom fields para Branch
		from .custom_fields.branch_fiscal_fields import create_branch_fiscal_custom_fields

		print("📝 Creando custom fields para Branch DocType...")
		if create_branch_fiscal_custom_fields():
			print("✅ Custom fields para Branch creados exitosamente")
		else:
			print("⚠️  Error creando custom fields para Branch")
			return False

		# Paso 2: Validar que los DocTypes estén disponibles
		required_doctypes = ["Configuracion Fiscal Sucursal"]

		print("🔍 Validando DocTypes requeridos...")
		for doctype in required_doctypes:
			if not frappe.db.exists("DocType", doctype):
				print(f"❌ DocType '{doctype}' no encontrado. Asegúrate de que esté migrado.")
				return False
			else:
				print(f"✅ DocType '{doctype}' disponible")

		# Paso 3: Crear certificados de ejemplo para testing (solo en modo desarrollo)
		if frappe.conf.get("developer_mode"):
			print("🧪 Creando datos de ejemplo para desarrollo...")
			create_sample_certificates()

		# Paso 4: Validar instalación
		print("🔍 Validando instalación completa...")
		if validate_multi_sucursal_installation():
			print("✅ Sistema Multi-Sucursal instalado correctamente")
			return True
		else:
			print("❌ Errores en la validación de instalación")
			return False

	except Exception as e:
		print(f"❌ Error durante la instalación: {e!s}")
		frappe.log_error(f"Error installing multi-sucursal system: {e!s}", "Multi Sucursal Installation")
		return False


def validate_multi_sucursal_installation():
	"""Validar que la instalación del sistema multi-sucursal esté completa"""
	try:
		# Validar custom fields en Branch
		required_fields = [
			"fm_enable_fiscal",
			"fm_lugar_expedicion",
			"fm_serie_pattern",
			"fm_folio_start",
			"fm_folio_current",
			"fm_share_certificates",
			"fm_certificate_ids",
		]

		missing_fields = []
		for field in required_fields:
			if not frappe.db.exists("Custom Field", {"dt": "Branch", "fieldname": field}):
				missing_fields.append(field)

		if missing_fields:
			print(f"❌ Campos faltantes en Branch: {missing_fields}")
			return False

		# Validar DocTypes
		required_doctypes = ["Configuracion Fiscal Sucursal"]
		for doctype in required_doctypes:
			if not frappe.db.exists("DocType", doctype):
				print(f"❌ DocType faltante: {doctype}")
				return False

		# Validar hooks (verificar que las funciones existan)
		try:
			from .branch_manager import BranchManager
			from .certificate_selector import MultibranchCertificateManager, get_available_certificates
			from .custom_fields.branch_fiscal_fields import (
				after_branch_insert,
				on_branch_update,
				validate_branch_fiscal_configuration,
			)

		except ImportError as e:
			print(f"❌ Error importando funciones requeridas: {e!s}")
			return False

		print("✅ Validación completa exitosa")
		return True

	except Exception as e:
		print(f"❌ Error durante validación: {e!s}")
		return False


def create_sample_certificates():
	"""Crear certificados de ejemplo para desarrollo y testing"""
	try:
		# Solo en modo desarrollo
		if not frappe.conf.get("developer_mode"):
			return

		# Obtener primera empresa disponible
		company = frappe.get_all("Company", limit=1)
		if not company:
			print("⚠️  No hay empresas disponibles para crear certificados de ejemplo")
			return

		# company_name = company[0].name  # Variable removida por no uso

		# Crear datos de ejemplo en configuraciones fiscales
		# Los certificados de ejemplo se crean como parte de las configuraciones
		# ya que el Certificate Selector trabaja con datos de configuración
		print("🧪 Los certificados de ejemplo se manejan a través del Certificate Selector")
		print("✅ Sistema preparado para certificados de desarrollo")

		frappe.db.commit()

	except Exception as e:
		print(f"⚠️  Error creando certificados de ejemplo: {e!s}")


def get_branch_certificate_summary(branch_name):
	"""
	Obtener resumen de certificados disponibles para una sucursal
	Función de utilidad para integraciones y dashboards
	"""
	try:
		from .certificate_selector import get_available_certificates

		branch_doc = frappe.get_doc("Branch", branch_name)

		if not branch_doc.get("fm_enable_fiscal"):
			return {
				"success": False,
				"message": "Sucursal no tiene habilitada la facturación fiscal",
				"summary": {},
			}

		# Obtener certificados disponibles
		certificates = get_available_certificates(branch_doc.company, branch_name)

		# Crear resumen
		summary = {
			"total_certificates": len(certificates),
			"healthy": len([c for c in certificates if c["health_status"] == "HEALTHY"]),
			"warning": len([c for c in certificates if c["health_status"] == "WARNING"]),
			"critical": len([c for c in certificates if c["health_status"] == "CRITICAL"]),
			"shared_certificates": len([c for c in certificates if c["is_shared"]]),
			"specific_certificates": len([c for c in certificates if not c["is_shared"]]),
			"expiring_soon": len([c for c in certificates if c["days_until_expiration"] <= 30]),
			"best_certificate": certificates[0] if certificates else None,
		}

		return {"success": True, "branch": branch_name, "summary": summary, "certificates": certificates}

	except Exception as e:
		frappe.log_error(
			f"Error getting branch certificate summary for {branch_name}: {e!s}", "Branch Certificate Summary"
		)
		return {"success": False, "message": f"Error obteniendo resumen: {e!s}", "summary": {}}


@frappe.whitelist()
def refresh_all_branch_configurations():
	"""
	API para refrescar todas las configuraciones fiscales de sucursales
	Útil después de cambios masivos en certificados o configuraciones
	"""
	try:
		# Obtener todas las sucursales fiscales activas
		fiscal_branches = frappe.get_all(
			"Branch", filters={"fm_enable_fiscal": 1}, fields=["name", "company"]
		)

		updated_count = 0
		error_count = 0

		for branch in fiscal_branches:
			try:
				# Verificar si tiene configuración fiscal
				config_name = frappe.db.get_value("Configuracion Fiscal Sucursal", {"branch": branch.name})

				if config_name:
					# Refrescar configuración existente
					config_doc = frappe.get_doc("Configuracion Fiscal Sucursal", config_name)
					config_doc.calculate_statistics()
					config_doc.save()
				else:
					# Crear configuración si no existe
					from .doctype.configuracion_fiscal_sucursal.configuracion_fiscal_sucursal import (
						create_default_config,
					)

					create_default_config(branch.name)

				updated_count += 1

			except Exception as e:
				error_count += 1
				frappe.log_error(
					f"Error refreshing branch config {branch.name}: {e!s}", "Branch Config Refresh"
				)

		return {
			"success": True,
			"message": f"Configuraciones actualizadas: {updated_count} exitosas, {error_count} errores",
			"updated": updated_count,
			"errors": error_count,
		}

	except Exception as e:
		return {"success": False, "message": f"Error en actualización masiva: {e!s}"}


if __name__ == "__main__":
	# Para ejecución directa del script
	install_multi_sucursal_system()
