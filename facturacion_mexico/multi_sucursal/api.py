"""
Multi-Sucursal API - Sprint 3
APIs para manejo de múltiples sucursales
"""

from typing import Any

import frappe
from frappe import _

from facturacion_mexico.multi_sucursal.utils import LugarExpedicionManager


@frappe.whitelist()
def get_lugar_expedicion(
	company: str, sales_invoice: str | None = None, customer: str | None = None
) -> dict[str, Any]:
	"""
	API: Obtener lugar de expedición según reglas de negocio.

	Args:
		company: Nombre de la empresa
		sales_invoice: Nombre de Sales Invoice (opcional)
		customer: Nombre del Customer (opcional)

	Returns:
		dict: Información del lugar de expedición
	"""
	try:
		resultado = LugarExpedicionManager.get_lugar_expedicion(company, sales_invoice, customer)

		return {
			"success": True,
			"data": resultado,
			"message": _("Lugar de expedición determinado exitosamente"),
		}

	except Exception as e:
		frappe.log_error(f"Error en API get_lugar_expedicion: {e!s}")
		return {"success": False, "error": str(e), "message": _("Error determinando lugar de expedición")}


@frappe.whitelist()
def get_sucursales_disponibles(company: str) -> dict[str, Any]:
	"""
	API: Obtener lista de sucursales disponibles.

	Args:
		company: Nombre de la empresa

	Returns:
		dict: Lista de sucursales disponibles
	"""
	try:
		sucursales = LugarExpedicionManager.get_available_sucursales(company)

		return {
			"success": True,
			"data": sucursales,
			"count": len(sucursales),
			"message": _("Sucursales obtenidas exitosamente"),
		}

	except Exception as e:
		frappe.log_error(f"Error en API get_sucursales_disponibles: {e!s}")
		return {
			"success": False,
			"error": str(e),
			"data": [],
			"count": 0,
			"message": _("Error obteniendo sucursales"),
		}


@frappe.whitelist()
def establecer_lugar_expedicion(
	sales_invoice: str, codigo_postal: str, force_update: bool = False
) -> dict[str, Any]:
	"""
	API: Establecer lugar de expedición en una factura.

	Args:
		sales_invoice: Nombre de Sales Invoice
		codigo_postal: Código postal del lugar de expedición
		force_update: Forzar actualización si ya existe

	Returns:
		dict: Resultado de la operación
	"""
	try:
		# Validar código postal
		if not LugarExpedicionManager.validate_codigo_postal(codigo_postal):
			return {"success": False, "message": _("Código postal inválido: {0}").format(codigo_postal)}

		# Verificar si la factura existe
		if not frappe.db.exists("Sales Invoice", sales_invoice):
			return {"success": False, "message": _("Factura no encontrada: {0}").format(sales_invoice)}

		invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)

		# Verificar si ya tiene lugar de expedición y force_update es False
		current_cp = getattr(invoice_doc, "fm_lugar_expedicion_cp", None)
		if current_cp and not force_update:
			return {
				"success": False,
				"message": _(
					"La factura ya tiene lugar de expedición: {0}. Use force_update=True para actualizar."
				).format(current_cp),
			}

		# Establecer lugar de expedición
		source_info = {
			"codigo_postal": codigo_postal,
			"source": "manual_api",
			"updated_by": frappe.session.user,
			"updated_at": frappe.utils.now(),
		}

		LugarExpedicionManager.set_lugar_expedicion_on_invoice(sales_invoice, codigo_postal, source_info)

		return {
			"success": True,
			"data": {
				"sales_invoice": sales_invoice,
				"codigo_postal": codigo_postal,
				"previous_cp": current_cp,
			},
			"message": _("Lugar de expedición establecido exitosamente"),
		}

	except Exception as e:
		frappe.log_error(f"Error en API establecer_lugar_expedicion: {e!s}")
		return {"success": False, "error": str(e), "message": _("Error estableciendo lugar de expedición")}


@frappe.whitelist()
def validar_configuracion_sucursales(company: str) -> dict[str, Any]:
	"""
	API: Validar configuración de sucursales para una empresa.

	Args:
		company: Nombre de la empresa

	Returns:
		dict: Resultado de la validación
	"""
	try:
		summary = LugarExpedicionManager.get_lugar_expedicion_summary(company)

		# Analizar y categorizar problemas
		issues = []
		warnings = []

		if summary.get("sucursales_count", 0) == 0:
			issues.append(_("No hay sucursales configuradas"))

		if not summary.get("default_configured", False):
			issues.append(_("No hay lugar de expedición por defecto configurado"))

		if summary.get("recent_invoices_without_lugar", 0) > 0:
			warnings.append(
				_("Hay {0} facturas recientes sin lugar de expedición").format(
					summary["recent_invoices_without_lugar"]
				)
			)

		validation_errors = summary.get("validation_errors", [])
		if validation_errors:
			issues.extend(validation_errors)

		# Determinar estado general
		if issues:
			status = "error"
			message = _("Configuración de sucursales tiene problemas críticos")
		elif warnings:
			status = "warning"
			message = _("Configuración de sucursales tiene advertencias")
		else:
			status = "ok"
			message = _("Configuración de sucursales está correcta")

		return {
			"success": True,
			"status": status,
			"message": message,
			"summary": summary,
			"issues": issues,
			"warnings": warnings,
			"recommendations": _get_configuration_recommendations(summary),
		}

	except Exception as e:
		frappe.log_error(f"Error en API validar_configuracion_sucursales: {e!s}")
		return {
			"success": False,
			"error": str(e),
			"message": _("Error validando configuración de sucursales"),
		}


@frappe.whitelist()
def bulk_set_lugar_expedicion(invoices: list[str], codigo_postal: str) -> dict[str, Any]:
	"""
	API: Establecer lugar de expedición en múltiples facturas.

	Args:
		invoices: Lista de nombres de Sales Invoice
		codigo_postal: Código postal del lugar de expedición

	Returns:
		dict: Resultado de la operación en lote
	"""
	try:
		if isinstance(invoices, str):
			import json

			invoices = json.loads(invoices)

		if not LugarExpedicionManager.validate_codigo_postal(codigo_postal):
			return {"success": False, "message": _("Código postal inválido: {0}").format(codigo_postal)}

		results = {
			"success": True,
			"processed": [],
			"errors": [],
			"skipped": [],
			"summary": {"total": len(invoices), "updated": 0, "errors": 0, "skipped": 0},
		}

		source_info = {
			"codigo_postal": codigo_postal,
			"source": "bulk_api",
			"updated_by": frappe.session.user,
			"updated_at": frappe.utils.now(),
		}

		for invoice in invoices:
			try:
				# Verificar si existe
				if not frappe.db.exists("Sales Invoice", invoice):
					results["errors"].append({"invoice": invoice, "error": _("Factura no encontrada")})
					results["summary"]["errors"] += 1
					continue

				# Verificar si ya tiene lugar de expedición
				invoice_doc = frappe.get_doc("Sales Invoice", invoice)
				current_cp = getattr(invoice_doc, "fm_lugar_expedicion_cp", None)

				if current_cp:
					results["skipped"].append(
						{
							"invoice": invoice,
							"reason": _("Ya tiene lugar de expedición: {0}").format(current_cp),
						}
					)
					results["summary"]["skipped"] += 1
					continue

				# Establecer lugar de expedición
				LugarExpedicionManager.set_lugar_expedicion_on_invoice(invoice, codigo_postal, source_info)

				results["processed"].append(
					{"invoice": invoice, "codigo_postal": codigo_postal, "status": "updated"}
				)
				results["summary"]["updated"] += 1

			except Exception as e:
				results["errors"].append({"invoice": invoice, "error": str(e)})
				results["summary"]["errors"] += 1

		# Actualizar mensaje final
		if results["summary"]["errors"] > 0:
			results["success"] = False
			results["message"] = _("Operación completada con {0} errores").format(
				results["summary"]["errors"]
			)
		else:
			results["message"] = _(
				"Operación completada exitosamente. {0} facturas actualizadas, {1} omitidas"
			).format(results["summary"]["updated"], results["summary"]["skipped"])

		return results

	except Exception as e:
		frappe.log_error(f"Error en API bulk_set_lugar_expedicion: {e!s}")
		return {"success": False, "error": str(e), "message": _("Error en operación en lote")}


@frappe.whitelist()
def get_facturas_sin_lugar_expedicion(company: str, days: int = 30, limit: int = 100) -> dict[str, Any]:
	"""
	API: Obtener facturas sin lugar de expedición.

	Args:
		company: Nombre de la empresa
		days: Días hacia atrás para buscar (default: 30)
		limit: Límite de resultados (default: 100)

	Returns:
		dict: Lista de facturas sin lugar de expedición
	"""
	try:
		filters = {
			"company": company,
			"docstatus": 1,
			"posting_date": [">", frappe.utils.add_days(frappe.utils.today(), -days)],
		}

		# Agregar filtro para facturas sin lugar de expedición
		# Nota: Este filtro puede variar según si el campo existe o no
		try:
			filters["fm_lugar_expedicion_cp"] = ["in", ["", None]]
		except Exception:
			# Campo puede no existir aún
			pass

		invoices = frappe.get_all(
			"Sales Invoice",
			filters=filters,
			fields=["name", "customer", "posting_date", "grand_total", "fm_lugar_expedicion_cp", "status"],
			order_by="posting_date desc",
			limit=limit,
		)

		# Filtrar manualmente si es necesario
		invoices_sin_lugar = [inv for inv in invoices if not getattr(inv, "fm_lugar_expedicion_cp", None)]

		return {
			"success": True,
			"data": invoices_sin_lugar,
			"count": len(invoices_sin_lugar),
			"total_searched": len(invoices),
			"parameters": {"company": company, "days": days, "limit": limit},
			"message": _("Búsqueda completada. {0} facturas sin lugar de expedición encontradas").format(
				len(invoices_sin_lugar)
			),
		}

	except Exception as e:
		frappe.log_error(f"Error en API get_facturas_sin_lugar_expedicion: {e!s}")
		return {
			"success": False,
			"error": str(e),
			"data": [],
			"count": 0,
			"message": _("Error buscando facturas sin lugar de expedición"),
		}


def _get_configuration_recommendations(summary: dict) -> list[str]:
	"""Generar recomendaciones basadas en el resumen de configuración."""
	recommendations = []

	if summary.get("sucursales_count", 0) == 0:
		recommendations.append(_("Configure al menos una sucursal en el sistema"))

	if not summary.get("default_configured", False):
		recommendations.append(_("Configure un lugar de expedición por defecto en la empresa"))

	if summary.get("recent_invoices_without_lugar", 0) > 0:
		recommendations.append(
			_("Revise y configure lugar de expedición para las facturas recientes que no lo tienen")
		)

	if summary.get("sucursales_count", 0) < 2:
		recommendations.append(_("Si maneja múltiples ubicaciones, configure sucursales adicionales"))

	return recommendations
