"""
Multi-Sucursal Utils - Sprint 3
Utilidades para manejo de múltiples sucursales y lugar de expedición
"""

from typing import Any

import frappe
from frappe import _


class LugarExpedicionManager:
	"""Gestor de lugar de expedición para múltiples sucursales."""

	@staticmethod
	def get_lugar_expedicion(
		company: str, sales_invoice: str | None = None, customer: str | None = None
	) -> dict[str, Any]:
		"""
		Obtener lugar de expedición basado en reglas de negocio.

		Args:
			company: Company name
			sales_invoice: Sales Invoice name (opcional)
			customer: Customer name (opcional)

		Returns:
			dict: Información del lugar de expedición
		"""
		try:
			# Intentar obtener desde Sales Invoice si está disponible
			if sales_invoice:
				invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
				lugar = LugarExpedicionManager._get_from_sales_invoice(invoice_doc)
				if lugar:
					return lugar

			# Intentar obtener desde Customer si está disponible
			if customer:
				lugar = LugarExpedicionManager._get_from_customer(customer, company)
				if lugar:
					return lugar

			# Fallback: obtener lugar por defecto de la company
			return LugarExpedicionManager._get_default_lugar_expedicion(company)

		except Exception as e:
			frappe.log_error(f"Error obteniendo lugar de expedición: {e!s}")
			return LugarExpedicionManager._get_fallback_lugar_expedicion(company)

	@staticmethod
	def _get_from_sales_invoice(invoice_doc) -> dict[str, Any] | None:
		"""Obtener lugar de expedición desde Sales Invoice."""
		# Verificar si hay campo personalizado para lugar de expedición
		lugar_expedicion_field = getattr(invoice_doc, "fm_lugar_expedicion", None)
		if lugar_expedicion_field:
			return LugarExpedicionManager._build_lugar_info(lugar_expedicion_field)

		# Verificar si hay warehouse específico
		if invoice_doc.items and invoice_doc.items[0].warehouse:
			warehouse_doc = frappe.get_doc("Warehouse", invoice_doc.items[0].warehouse)
			if hasattr(warehouse_doc, "fm_codigo_postal") and warehouse_doc.fm_codigo_postal:
				return {
					"codigo_postal": warehouse_doc.fm_codigo_postal,
					"source": "warehouse",
					"warehouse": warehouse_doc.name,
					"warehouse_address": getattr(warehouse_doc, "address", ""),
				}

		# Verificar shipping address
		if hasattr(invoice_doc, "shipping_address_name") and invoice_doc.shipping_address_name:
			shipping_address = frappe.get_doc("Address", invoice_doc.shipping_address_name)
			if shipping_address.pincode:
				return {
					"codigo_postal": shipping_address.pincode,
					"source": "shipping_address",
					"address": shipping_address.name,
					"city": shipping_address.city,
					"state": shipping_address.state,
				}

		return None

	@staticmethod
	def _get_from_customer(customer: str, company: str) -> dict[str, Any] | None:
		"""Obtener lugar de expedición desde configuración del Customer."""
		try:
			customer_doc = frappe.get_doc("Customer", customer)

			# Verificar si hay configuración específica de lugar de expedición
			lugar_field = getattr(customer_doc, "fm_lugar_expedicion_preferido", None)
			if lugar_field:
				return LugarExpedicionManager._build_lugar_info(lugar_field)

			# Verificar territory del customer
			if customer_doc.territory:
				territory_config = LugarExpedicionManager._get_territory_config(
					customer_doc.territory, company
				)
				if territory_config:
					return territory_config

			# Verificar dirección principal del customer
			primary_address = LugarExpedicionManager._get_customer_primary_address(customer)
			if primary_address and primary_address.get("codigo_postal"):
				return {
					"codigo_postal": primary_address["codigo_postal"],
					"source": "customer_address",
					"customer": customer,
					"address": primary_address.get("name"),
					"city": primary_address.get("city"),
					"state": primary_address.get("state"),
				}

		except Exception as e:
			frappe.log_error(f"Error obteniendo lugar de expedición del customer {customer}: {e!s}")

		return None

	@staticmethod
	def _get_territory_config(territory: str, company: str) -> dict[str, Any] | None:
		"""Obtener configuración de lugar de expedición por territorio."""
		try:
			# Buscar configuración específica de territorio
			config = frappe.get_all(
				"Territory Lugar Expedicion",  # DocType hipotético para configuraciones
				filters={"territory": territory, "company": company, "is_active": 1},
				fields=["codigo_postal", "sucursal", "almacen"],
				limit=1,
			)

			if config:
				return {
					"codigo_postal": config[0]["codigo_postal"],
					"source": "territory_config",
					"territory": territory,
					"sucursal": config[0].get("sucursal"),
					"almacen": config[0].get("almacen"),
				}

		except Exception:
			pass  # DocType puede no existir aún

		return None

	@staticmethod
	def _get_customer_primary_address(customer: str) -> dict[str, str] | None:
		"""Obtener dirección principal del customer."""
		try:
			address_links = frappe.get_all(
				"Dynamic Link",
				filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
				fields=["parent"],
			)

			if address_links:
				# Tomar la primera dirección (o buscar la marcada como primary)
				address_name = address_links[0]["parent"]
				address_doc = frappe.get_doc("Address", address_name)

				return {
					"name": address_doc.name,
					"codigo_postal": address_doc.pincode,
					"city": address_doc.city,
					"state": address_doc.state,
					"country": address_doc.country,
				}

		except Exception as e:
			frappe.log_error(f"Error obteniendo dirección principal del customer {customer}: {e!s}")

		return None

	@staticmethod
	def _get_default_lugar_expedicion(company: str) -> dict[str, Any]:
		"""Obtener lugar de expedición por defecto de la company."""
		try:
			company_doc = frappe.get_doc("Company", company)

			# Verificar si hay configuración específica
			default_lugar = getattr(company_doc, "fm_lugar_expedicion_default", None)
			if default_lugar:
				return LugarExpedicionManager._build_lugar_info(default_lugar)

			# Obtener desde dirección de la company
			if hasattr(company_doc, "default_address") and company_doc.default_address:
				address_doc = frappe.get_doc("Address", company_doc.default_address)
				if address_doc.pincode:
					return {
						"codigo_postal": address_doc.pincode,
						"source": "company_address",
						"company": company,
						"address": address_doc.name,
						"city": address_doc.city,
						"state": address_doc.state,
					}

		except Exception as e:
			frappe.log_error(f"Error obteniendo lugar de expedición default de company {company}: {e!s}")

		return LugarExpedicionManager._get_fallback_lugar_expedicion(company)

	@staticmethod
	def _get_fallback_lugar_expedicion(company: str) -> dict[str, Any]:
		"""Lugar de expedición de emergencia cuando todo falla."""
		return {
			"codigo_postal": "00000",
			"source": "fallback",
			"company": company,
			"warning": "Lugar de expedición no configurado - usando fallback",
		}

	@staticmethod
	def _build_lugar_info(lugar_config: str) -> dict[str, Any]:
		"""Construir información de lugar desde configuración."""
		# Puede ser un JSON string o código postal simple
		try:
			import json

			lugar_data = json.loads(lugar_config)
			if isinstance(lugar_data, dict) and "codigo_postal" in lugar_data:
				lugar_data["source"] = "configured"
				return lugar_data
		except (json.JSONDecodeError, TypeError):
			pass

		# Asumir que es un código postal simple
		if lugar_config and len(lugar_config) == 5 and lugar_config.isdigit():
			return {"codigo_postal": lugar_config, "source": "configured_simple"}

		return None

	@staticmethod
	def validate_codigo_postal(codigo_postal: str) -> bool:
		"""Validar formato de código postal mexicano."""
		if not codigo_postal or len(codigo_postal) != 5:
			return False

		try:
			int(codigo_postal)
			return True
		except ValueError:
			return False

	@staticmethod
	def get_available_sucursales(company: str) -> list[dict[str, Any]]:
		"""Obtener lista de sucursales disponibles para una company."""
		try:
			# Buscar warehouses con configuración de lugar de expedición
			warehouses = frappe.get_all(
				"Warehouse",
				filters={"company": company, "disabled": 0},
				fields=["name", "warehouse_name", "fm_codigo_postal", "fm_es_sucursal"],
				order_by="warehouse_name",
			)

			sucursales = []
			for warehouse in warehouses:
				if getattr(warehouse, "fm_es_sucursal", False) and getattr(
					warehouse, "fm_codigo_postal", None
				):
					sucursales.append(
						{
							"warehouse": warehouse.name,
							"nombre": warehouse.warehouse_name,
							"codigo_postal": warehouse.fm_codigo_postal,
							"tipo": "warehouse",
						}
					)

			# Agregar sucursales desde configuración manual si existe
			custom_sucursales = frappe.get_all(
				"Sucursal Configuracion",  # DocType hipotético
				filters={"company": company, "is_active": 1},
				fields=["name", "sucursal_name", "codigo_postal", "direccion"],
				order_by="sucursal_name",
			)

			for sucursal in custom_sucursales:
				sucursales.append(
					{
						"sucursal": sucursal.name,
						"nombre": sucursal.sucursal_name,
						"codigo_postal": sucursal.codigo_postal,
						"direccion": sucursal.get("direccion"),
						"tipo": "sucursal",
					}
				)

			return sucursales

		except Exception as e:
			frappe.log_error(f"Error obteniendo sucursales para company {company}: {e!s}")
			return []

	@staticmethod
	def set_lugar_expedicion_on_invoice(
		sales_invoice: str, codigo_postal: str, source_info: dict | None = None
	):
		"""Establecer lugar de expedición en una factura."""
		try:
			if not LugarExpedicionManager.validate_codigo_postal(codigo_postal):
				raise ValueError(f"Código postal inválido: {codigo_postal}")

			invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)

			# Establecer campos de lugar de expedición
			if hasattr(invoice_doc, "fm_lugar_expedicion_cp"):
				invoice_doc.fm_lugar_expedicion_cp = codigo_postal

			if hasattr(invoice_doc, "fm_lugar_expedicion_info") and source_info:
				import json

				invoice_doc.fm_lugar_expedicion_info = json.dumps(source_info, ensure_ascii=False)

			invoice_doc.save(ignore_permissions=True)
			frappe.db.commit()

		except Exception as e:
			frappe.db.rollback()
			frappe.log_error(f"Error estableciendo lugar de expedición en factura {sales_invoice}: {e!s}")
			raise e

	@staticmethod
	def get_lugar_expedicion_summary(company: str) -> dict[str, Any]:
		"""Obtener resumen de configuración de lugares de expedición."""
		try:
			summary = {
				"company": company,
				"sucursales_count": 0,
				"default_configured": False,
				"territories_configured": 0,
				"recent_invoices_without_lugar": 0,
				"validation_errors": [],
			}

			# Contar sucursales
			sucursales = LugarExpedicionManager.get_available_sucursales(company)
			summary["sucursales_count"] = len(sucursales)

			# Verificar configuración default
			try:
				default_lugar = LugarExpedicionManager._get_default_lugar_expedicion(company)
				summary["default_configured"] = default_lugar.get("source") != "fallback"
			except Exception:
				summary["validation_errors"].append("Error verificando configuración default")

			# Contar facturas recientes sin lugar de expedición
			try:
				recent_invoices = frappe.get_all(
					"Sales Invoice",
					filters={
						"company": company,
						"docstatus": 1,
						"posting_date": [">", frappe.utils.add_days(frappe.utils.today(), -30)],
					},
					fields=["name", "fm_lugar_expedicion_cp"],
					limit=1000,
				)

				invoices_without_lugar = [
					inv for inv in recent_invoices if not getattr(inv, "fm_lugar_expedicion_cp", None)
				]
				summary["recent_invoices_without_lugar"] = len(invoices_without_lugar)

			except Exception:
				summary["validation_errors"].append("Error verificando facturas recientes")

			return summary

		except Exception as e:
			frappe.log_error(f"Error generando resumen de lugar de expedición: {e!s}")
			return {"error": str(e)}


# Funciones de conveniencia para APIs
@frappe.whitelist()
def get_lugar_expedicion_for_invoice(sales_invoice: str) -> dict[str, Any]:
	"""API: Obtener lugar de expedición para una factura."""
	try:
		invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
		return LugarExpedicionManager.get_lugar_expedicion(
			company=invoice_doc.company, sales_invoice=sales_invoice, customer=invoice_doc.customer
		)
	except Exception as e:
		frappe.log_error(f"Error en API get_lugar_expedicion_for_invoice: {e!s}")
		return {"error": str(e)}


@frappe.whitelist()
def get_available_sucursales_for_company(company: str) -> list[dict[str, Any]]:
	"""API: Obtener sucursales disponibles para una company."""
	try:
		return LugarExpedicionManager.get_available_sucursales(company)
	except Exception as e:
		frappe.log_error(f"Error en API get_available_sucursales_for_company: {e!s}")
		return []


@frappe.whitelist()
def validate_and_set_lugar_expedicion(sales_invoice: str, codigo_postal: str) -> dict[str, Any]:
	"""API: Validar y establecer lugar de expedición en factura."""
	try:
		if not LugarExpedicionManager.validate_codigo_postal(codigo_postal):
			return {"success": False, "message": _("Código postal inválido")}

		LugarExpedicionManager.set_lugar_expedicion_on_invoice(sales_invoice, codigo_postal)

		return {
			"success": True,
			"message": _("Lugar de expedición establecido correctamente"),
			"codigo_postal": codigo_postal,
		}
	except Exception as e:
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_lugar_expedicion_summary_api(company: str) -> dict[str, Any]:
	"""API: Obtener resumen de configuración de lugar de expedición."""
	try:
		return LugarExpedicionManager.get_lugar_expedicion_summary(company)
	except Exception as e:
		return {"error": str(e)}


# Hook handlers para integración automática
def on_sales_invoice_validate(doc, method):
	"""Hook: Validar y establecer lugar de expedición en Sales Invoice."""
	try:
		# Solo procesar si no tiene lugar de expedición ya establecido
		if hasattr(doc, "fm_lugar_expedicion_cp") and doc.fm_lugar_expedicion_cp:
			return

		# Obtener lugar de expedición automáticamente
		lugar_info = LugarExpedicionManager.get_lugar_expedicion(
			company=doc.company, sales_invoice=doc.name if not doc.is_new() else None, customer=doc.customer
		)

		if lugar_info and lugar_info.get("codigo_postal"):
			# Establecer en el documento
			if hasattr(doc, "fm_lugar_expedicion_cp"):
				doc.fm_lugar_expedicion_cp = lugar_info["codigo_postal"]

			if hasattr(doc, "fm_lugar_expedicion_info"):
				import json

				doc.fm_lugar_expedicion_info = json.dumps(lugar_info, ensure_ascii=False)

			# Log para auditoría
			frappe.logger().info(
				f"Lugar de expedición establecido automáticamente en {doc.name}: "
				f"{lugar_info['codigo_postal']} (source: {lugar_info.get('source', 'unknown')})"
			)

	except Exception as e:
		# No fallar la validación por problemas de lugar de expedición
		frappe.log_error(f"Error estableciendo lugar de expedición automático en {doc.name}: {e!s}")


def on_sales_invoice_submit(doc, method):
	"""Hook: Verificar lugar de expedición al hacer submit."""
	try:
		lugar_cp = getattr(doc, "fm_lugar_expedicion_cp", None)

		if not lugar_cp:
			# Intentar obtener y establecer automáticamente
			lugar_info = LugarExpedicionManager.get_lugar_expedicion(
				company=doc.company, sales_invoice=doc.name, customer=doc.customer
			)

			if lugar_info and lugar_info.get("codigo_postal"):
				LugarExpedicionManager.set_lugar_expedicion_on_invoice(
					doc.name, lugar_info["codigo_postal"], lugar_info
				)
			else:
				frappe.msgprint(
					_(
						"Advertencia: No se pudo determinar el lugar de expedición para esta factura. "
						"Esto puede afectar la validez fiscal del CFDI."
					),
					indicator="orange",
				)

		elif not LugarExpedicionManager.validate_codigo_postal(lugar_cp):
			frappe.throw(_("Código postal del lugar de expedición es inválido: {0}").format(lugar_cp))

	except Exception as e:
		frappe.log_error(f"Error validando lugar de expedición en submit de {doc.name}: {e!s}")
