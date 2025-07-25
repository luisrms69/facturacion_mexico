# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Multibranch Addenda Manager - Sprint 6 Phase 2
Integra sistema Addendas Genéricas con infraestructura Multi-Sucursal
Gestiona addendas específicas por sucursal y configuraciones centralizadas
"""

from typing import Any

import frappe
from frappe import _

from facturacion_mexico.multi_sucursal.branch_manager import BranchManager


class MultibranchAddendaManager:
	"""
	Gestor de addendas multi-sucursal que extiende sistema Addendas Sprint 3
	Coordina configuraciones de addendas por sucursal usando infraestructura Phase 1
	"""

	def __init__(self, company: str, branch: str | None = None):
		self.company = company
		self.branch = branch
		self.branch_manager = BranchManager(company)

	def get_branch_addenda_configuration(self, customer: str | None = None) -> dict[str, Any]:
		"""
		Obtener configuración de addendas para una sucursal específica
		Integra con sistema existente de Addenda Configuration
		"""
		try:
			# 1. Obtener configuración base de addendas del sistema existente
			base_config = self._get_base_addenda_configuration(customer)

			# 2. Aplicar overrides específicos de sucursal si existen
			if self.branch:
				branch_overrides = self._get_branch_specific_overrides(customer)
				if branch_overrides:
					base_config = self._merge_configurations(base_config, branch_overrides)

			# 3. Validar configuración contra certificados disponibles
			validated_config = self._validate_config_with_certificates(base_config)

			return {
				"success": True,
				"branch": self.branch,
				"company": self.company,
				"customer": customer,
				"configuration": validated_config,
				"source": "multibranch_manager",
			}

		except Exception as e:
			frappe.log_error(
				f"Error getting branch addenda configuration: {e!s}", "Multibranch Addenda Manager"
			)
			return {
				"success": False,
				"message": f"Error obteniendo configuración: {e!s}",
				"configuration": {},
			}

	def get_available_addenda_types_for_branch(self) -> list[dict]:
		"""
		Obtener tipos de addenda disponibles para una sucursal específica
		Filtra según certificados y configuraciones fiscales de la sucursal
		"""
		try:
			# Obtener todos los tipos de addenda activos
			all_types = frappe.get_all(
				"Addenda Type",
				filters={"is_active": 1},
				fields=[
					"name",
					"description",
					"version",
					"requires_product_mapping",
					"namespace",
					"documentation_url",
					"requires_specific_certificate",
				],
			)

			if not self.branch:
				# Si no hay sucursal específica, retornar todos los tipos
				return all_types

			# Filtrar tipos según capacidades de la sucursal
			available_types = []
			branch_certificates = self._get_branch_certificate_status()

			for addenda_type in all_types:
				if self._is_addenda_type_compatible_with_branch(addenda_type, branch_certificates):
					# Agregar información específica de la sucursal
					addenda_type["branch_compatible"] = True
					addenda_type["certificate_available"] = branch_certificates.get(
						"has_valid_certificates", False
					)
					available_types.append(addenda_type)

			return available_types

		except Exception as e:
			frappe.log_error(
				f"Error getting available addenda types for branch: {e!s}", "Multibranch Addenda"
			)
			return []

	def validate_addenda_for_branch_invoice(self, sales_invoice_doc: Any) -> tuple[bool, str]:
		"""
		Validar que una addenda es compatible con la sucursal de una factura
		"""
		try:
			# Determinar sucursal de la factura
			invoice_branch = self._determine_invoice_branch(sales_invoice_doc)

			if not invoice_branch:
				return True, "No hay restricciones de sucursal para esta factura"

			# Obtener configuración de addenda para el cliente
			customer = sales_invoice_doc.customer
			addenda_config = self.get_branch_addenda_configuration(customer)

			if not addenda_config.get("success", False):
				return False, "Error obteniendo configuración de addenda para la sucursal"

			# Validar que la sucursal puede generar addendas
			branch_status = self._get_branch_certificate_status()
			if not branch_status.get("has_valid_certificates", False):
				return False, f"La sucursal {invoice_branch} no tiene certificados válidos para addendas"

			return True, "Addenda válida para la sucursal"

		except Exception as e:
			frappe.log_error(
				f"Error validating addenda for branch invoice: {e!s}", "Multibranch Addenda Validation"
			)
			return False, f"Error de validación: {e!s}"

	def generate_branch_specific_addenda(self, sales_invoice_doc: Any, addenda_type: str) -> dict[str, Any]:
		"""
		Generar addenda específica para sucursal usando sistema existente
		Integra con AddendaXMLBuilder del Sprint 3
		"""
		try:
			# Import del sistema existente
			from facturacion_mexico.addendas.parsers.xml_builder import AddendaXMLBuilder

			# Obtener datos específicos de la sucursal
			branch_data = self._get_branch_context_for_addenda(sales_invoice_doc)

			# Obtener template y configurar builder con contexto de sucursal
			template = self._get_addenda_template(addenda_type)
			field_values = self._get_branch_field_values(sales_invoice_doc, branch_data)
			builder = AddendaXMLBuilder(template, field_values)

			# Generar XML con datos de sucursal integrados
			addenda_xml = builder.build_from_sales_invoice(sales_invoice_doc, branch_context=branch_data)

			# Validar XML generado
			from facturacion_mexico.addendas.validators.xsd_validator import validate_addenda_xml

			validation_result = validate_addenda_xml(addenda_xml, addenda_type)

			return {
				"success": True,
				"addenda_xml": addenda_xml,
				"validation": validation_result,
				"branch": self.branch,
				"addenda_type": addenda_type,
			}

		except Exception as e:
			frappe.log_error(
				f"Error generating branch specific addenda: {e!s}", "Multibranch Addenda Generation"
			)
			return {"success": False, "message": f"Error generando addenda: {e!s}", "addenda_xml": None}

	def _get_base_addenda_configuration(self, customer: str | None = None) -> dict:
		"""Obtener configuración base usando sistema existente"""
		try:
			# Usar API existente del sistema Addendas
			from facturacion_mexico.addendas.api import get_addenda_configuration

			if customer:
				return get_addenda_configuration(customer)
			else:
				return {"configurations": [], "customer": None}

		except Exception as e:
			frappe.logger().warning(f"Error getting base addenda configuration: {e!s}")
			return {"configurations": []}

	def _get_branch_specific_overrides(self, customer: str | None = None) -> dict | None:
		"""Obtener overrides específicos de sucursal para addendas"""
		try:
			if not self.branch:
				return None

			# Buscar configuración fiscal de la sucursal
			fiscal_config = frappe.db.get_value(
				"Configuracion Fiscal Sucursal", {"branch": self.branch}, ["addenda_overrides"], as_dict=True
			)

			if fiscal_config and fiscal_config.get("addenda_overrides"):
				import json

				try:
					return json.loads(fiscal_config["addenda_overrides"])
				except json.JSONDecodeError:
					frappe.logger().warning(f"Invalid addenda_overrides JSON for branch {self.branch}")

			return None

		except Exception as e:
			frappe.logger().warning(f"Error getting branch specific overrides: {e!s}")
			return None

	def _merge_configurations(self, base_config: dict, overrides: dict) -> dict:
		"""Combinar configuración base con overrides de sucursal"""
		merged = base_config.copy()

		# Aplicar overrides de manera inteligente
		if "configurations" in overrides:
			# Mergear configuraciones por customer
			base_configs = merged.get("configurations", [])
			override_configs = overrides["configurations"]

			# TODO: Implementar lógica de merge inteligente
			# Por ahora, los overrides toman precedencia
			merged["configurations"] = override_configs + base_configs

		return merged

	def _validate_config_with_certificates(self, config: dict) -> dict:
		"""Validar configuración contra certificados disponibles en la sucursal"""
		if not self.branch:
			return config

		# Obtener estado de certificados de la sucursal
		branch_certificates = self._get_branch_certificate_status()

		# Marcar configuraciones como válidas/inválidas según certificados
		if "configurations" in config:
			for cfg in config["configurations"]:
				cfg["certificate_compatible"] = branch_certificates.get("has_valid_certificates", False)
				cfg["branch_validated"] = True

		return config

	def _get_branch_certificate_status(self) -> dict:
		"""Obtener estado de certificados usando BranchManager"""
		if not self.branch:
			return {"has_valid_certificates": False}

		try:
			# Usar API del BranchManager para obtener estado de certificados
			from facturacion_mexico.multi_sucursal.certificate_selector import get_branch_certificate_status

			status = get_branch_certificate_status(self.branch)
			return status.get("data", {})

		except Exception as e:
			frappe.logger().warning(f"Error getting branch certificate status: {e!s}")
			return {"has_valid_certificates": False}

	def _is_addenda_type_compatible_with_branch(self, addenda_type: dict, branch_certificates: dict) -> bool:
		"""Determinar si un tipo de addenda es compatible con la sucursal"""
		# Si el tipo de addenda requiere certificado específico
		if addenda_type.get("requires_specific_certificate"):
			return branch_certificates.get("has_valid_certificates", False)

		# Por defecto, todos los tipos son compatibles
		return True

	def _determine_invoice_branch(self, sales_invoice_doc: Any) -> str | None:
		"""Determinar la sucursal de una factura"""
		# Buscar campo de sucursal en la factura
		if hasattr(sales_invoice_doc, "fm_branch") and sales_invoice_doc.fm_branch:
			return sales_invoice_doc.fm_branch

		# Fallback: usar sucursal configurada en el manager
		return self.branch

	def _get_branch_context_for_addenda(self, sales_invoice_doc: Any) -> dict:
		"""Obtener contexto de sucursal para generación de addenda"""
		if not self.branch:
			return {}

		try:
			# Obtener datos de la sucursal
			branch_doc = frappe.get_cached_doc("Branch", self.branch)

			return {
				"branch_name": branch_doc.branch,
				"branch_code": self.branch,
				"lugar_expedicion": branch_doc.get("fm_lugar_expedicion"),
				"serie_pattern": branch_doc.get("fm_serie_pattern"),
				"company": self.company,
			}

		except Exception as e:
			frappe.logger().warning(f"Error getting branch context: {e!s}")
			return {"branch_code": self.branch, "company": self.company}

	def _get_addenda_template(self, addenda_type: str) -> str:
		"""Obtener template de addenda por tipo"""
		try:
			addenda_type_doc = frappe.get_cached_doc("Addenda Type", addenda_type)
			return addenda_type_doc.xml_template or ""
		except Exception as e:
			frappe.logger().warning(f"Error getting addenda template: {e!s}")
			return ""

	def _get_branch_field_values(self, sales_invoice_doc: Any, branch_data: dict) -> dict:
		"""Obtener valores de campos para la addenda desde la sucursal"""
		field_values = {}

		# Agregar datos de la sucursal
		field_values.update(branch_data)

		# Agregar datos de la factura
		if hasattr(sales_invoice_doc, "name"):
			field_values["invoice_name"] = sales_invoice_doc.name
		if hasattr(sales_invoice_doc, "customer"):
			field_values["customer"] = sales_invoice_doc.customer

		return field_values


# APIs públicas para integración


@frappe.whitelist()
def get_branch_addenda_configuration(
	company: str, branch: str | None = None, customer: str | None = None
) -> dict:
	"""API para obtener configuración de addendas por sucursal"""
	try:
		manager = MultibranchAddendaManager(company, branch)
		return manager.get_branch_addenda_configuration(customer)
	except Exception as e:
		frappe.log_error(f"Error in get_branch_addenda_configuration API: {e!s}", "Multibranch Addenda API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def get_available_addenda_types_for_branch(company: str, branch: str) -> dict:
	"""API para obtener tipos de addenda disponibles para una sucursal"""
	try:
		manager = MultibranchAddendaManager(company, branch)
		types = manager.get_available_addenda_types_for_branch()
		return {"success": True, "data": types, "count": len(types)}
	except Exception as e:
		frappe.log_error(
			f"Error in get_available_addenda_types_for_branch API: {e!s}", "Multibranch Addenda API"
		)
		return {"success": False, "message": f"Error: {e!s}", "data": []}


@frappe.whitelist()
def validate_addenda_for_branch_invoice(sales_invoice: str, branch: str | None = None) -> dict:
	"""API para validar addenda con sucursal específica"""
	try:
		doc = frappe.get_doc("Sales Invoice", sales_invoice)
		company = doc.company

		if not branch:
			branch = doc.get("fm_branch")

		manager = MultibranchAddendaManager(company, branch)
		is_valid, message = manager.validate_addenda_for_branch_invoice(doc)

		return {"success": True, "valid": is_valid, "message": message}
	except Exception as e:
		frappe.log_error(
			f"Error in validate_addenda_for_branch_invoice API: {e!s}", "Multibranch Addenda API"
		)
		return {"success": False, "valid": False, "message": f"Error: {e!s}"}
