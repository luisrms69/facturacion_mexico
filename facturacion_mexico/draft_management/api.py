"""
API para manejo de borradores de facturas
Sistema Draft/Preview - Issue #27
"""

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import now


@frappe.whitelist()
def create_draft_invoice(sales_invoice_name: str) -> dict[str, Any]:
	"""
	Crear factura borrador en FacturAPI

	Args:
		sales_invoice_name: Nombre del documento Sales Invoice

	Returns:
		Dict con resultado de la operación
	"""
	try:
		# Obtener documento Sales Invoice
		sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

		# Verificar que está marcado como borrador
		if not sales_invoice.get("fm_create_as_draft"):
			return {"success": False, "message": "La factura no está marcada para crear como borrador"}

		# Verificar que no sea ya un borrador existente
		if sales_invoice.get("fm_draft_status") == "Borrador":
			return {
				"success": False,
				"message": "La factura ya existe como borrador",
				"draft_id": sales_invoice.get("fm_factorapi_draft_id"),
			}

		# Construir payload para FacturAPI
		payload = build_cfdi_payload(sales_invoice)
		payload["draft"] = True  # Modo borrador

		# Enviar a FacturAPI (simulado por ahora)
		response = send_to_factorapi(payload, draft_mode=True)

		if response.get("success"):
			# Actualizar campos de borrador
			frappe.db.set_value(
				"Sales Invoice",
				sales_invoice_name,
				{
					"fm_draft_status": "Borrador",
					"fm_factorapi_draft_id": response.get("draft_id"),
					"fm_draft_created_date": now(),
				},
			)
			frappe.db.commit()

			return {
				"success": True,
				"message": "Borrador creado exitosamente",
				"draft_id": response.get("draft_id"),
				"preview_url": response.get("preview_url"),
			}
		else:
			return {"success": False, "message": f"Error creando borrador: {response.get('message')}"}

	except Exception as e:
		frappe.log_error(f"Error creating draft invoice: {e!s}")
		return {"success": False, "message": f"Error interno: {e!s}"}


@frappe.whitelist()
def approve_and_invoice_draft(sales_invoice_name: str, approved_by: str | None = None) -> dict[str, Any]:
	"""
	Aprobar borrador y convertir a factura timbrada

	Args:
		sales_invoice_name: Nombre del documento Sales Invoice
		approved_by: Usuario que aprueba (opcional, usa el actual por defecto)

	Returns:
		Dict con resultado de la operación
	"""
	try:
		# Obtener documento Sales Invoice
		sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

		# Verificar que está en estado borrador
		if sales_invoice.get("fm_draft_status") != "Borrador":
			return {"success": False, "message": "La factura no está en estado borrador"}

		draft_id = sales_invoice.get("fm_factorapi_draft_id")
		if not draft_id:
			return {"success": False, "message": "No se encontró ID de borrador en FacturAPI"}

		# Actualizar estado a "En Revisión"
		frappe.db.set_value("Sales Invoice", sales_invoice_name, {"fm_draft_status": "En Revisión"})
		frappe.db.commit()

		# Convertir borrador a factura final en FacturAPI
		response = convert_draft_to_invoice(draft_id)

		if response.get("success"):
			# Actualizar a estado final
			update_data = {
				"fm_draft_status": "Timbrado",
				"fm_draft_approved_by": approved_by or frappe.session.user,
			}

			# Si hay datos CFDI, guardarlos
			if response.get("cfdi_xml"):
				update_data["fm_cfdi_xml"] = response["cfdi_xml"]
			if response.get("cfdi_uuid"):
				update_data["fm_cfdi_uuid"] = response["cfdi_uuid"]

			frappe.db.set_value("Sales Invoice", sales_invoice_name, update_data)
			frappe.db.commit()

			return {
				"success": True,
				"message": "Borrador aprobado y timbrado exitosamente",
				"cfdi_uuid": response.get("cfdi_uuid"),
				"pdf_url": response.get("pdf_url"),
			}
		else:
			# Revertir a borrador en caso de error
			frappe.db.set_value("Sales Invoice", sales_invoice_name, {"fm_draft_status": "Borrador"})
			frappe.db.commit()

			return {"success": False, "message": f"Error aprobando borrador: {response.get('message')}"}

	except Exception as e:
		frappe.log_error(f"Error approving draft invoice: {e!s}")
		return {"success": False, "message": f"Error interno: {e!s}"}


@frappe.whitelist()
def cancel_draft(sales_invoice_name: str) -> dict[str, Any]:
	"""
	Cancelar borrador sin timbrar

	Args:
		sales_invoice_name: Nombre del documento Sales Invoice

	Returns:
		Dict con resultado de la operación
	"""
	try:
		# Obtener documento Sales Invoice
		sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

		# Verificar que está en estado borrador
		if sales_invoice.get("fm_draft_status") not in ["Borrador", "En Revisión"]:
			return {"success": False, "message": "Solo se pueden cancelar borradores pendientes"}

		draft_id = sales_invoice.get("fm_factorapi_draft_id")

		# Cancelar en FacturAPI si existe
		if draft_id:
			cancel_response = cancel_draft_in_factorapi(draft_id)
			# Log pero no falla si hay error cancelando en FacturAPI
			if not cancel_response.get("success"):
				frappe.log_error(f"Error cancelando borrador en FacturAPI: {cancel_response.get('message')}")

		# Limpiar campos de borrador
		frappe.db.set_value(
			"Sales Invoice",
			sales_invoice_name,
			{
				"fm_draft_status": "",
				"fm_factorapi_draft_id": "",
				"fm_draft_created_date": "",
				"fm_draft_approved_by": "",
				"fm_create_as_draft": 0,
			},
		)
		frappe.db.commit()

		return {"success": True, "message": "Borrador cancelado exitosamente"}

	except Exception as e:
		frappe.log_error(f"Error canceling draft: {e!s}")
		return {"success": False, "message": f"Error interno: {e!s}"}


@frappe.whitelist()
def get_draft_preview(sales_invoice_name: str) -> dict[str, Any]:
	"""
	Obtener preview/vista previa del borrador

	Args:
		sales_invoice_name: Nombre del documento Sales Invoice

	Returns:
		Dict con datos del preview
	"""
	try:
		# Obtener documento Sales Invoice
		sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

		draft_id = sales_invoice.get("fm_factorapi_draft_id")
		if not draft_id:
			return {"success": False, "message": "No hay borrador disponible para preview"}

		# Obtener preview de FacturAPI
		preview_data = get_draft_preview_from_factorapi(draft_id)

		if preview_data.get("success"):
			return {
				"success": True,
				"preview_xml": preview_data.get("xml"),
				"preview_pdf_url": preview_data.get("pdf_url"),
				"draft_data": {
					"created_date": sales_invoice.get("fm_draft_created_date"),
					"status": sales_invoice.get("fm_draft_status"),
					"draft_id": draft_id,
				},
			}
		else:
			return {"success": False, "message": f"Error obteniendo preview: {preview_data.get('message')}"}

	except Exception as e:
		frappe.log_error(f"Error getting draft preview: {e!s}")
		return {"success": False, "message": f"Error interno: {e!s}"}


# Funciones auxiliares para integración FacturAPI


def build_cfdi_payload(sales_invoice) -> dict[str, Any]:
	"""Construir payload CFDI para FacturAPI"""
	# Implementación simplificada - en realidad usaría el sistema existente
	return {
		"invoice_data": {
			"customer": sales_invoice.customer,
			"total": sales_invoice.grand_total,
			"currency": sales_invoice.currency,
			"items": [
				{
					"description": item.description,
					"quantity": item.qty,
					"unit_price": item.rate,
					"amount": item.amount,
				}
				for item in sales_invoice.items
			],
		}
	}


def send_to_factorapi(payload: dict[str, Any], draft_mode: bool = False) -> dict[str, Any]:
	"""Enviar payload a FacturAPI (simulado)"""
	# Simulación de respuesta exitosa
	import uuid

	return {
		"success": True,
		"draft_id": f"draft_{uuid.uuid4().hex[:8]}",
		"preview_url": "https://factorapi.io/preview/draft_12345",
		"message": "Borrador creado exitosamente",
	}


def convert_draft_to_invoice(draft_id: str) -> dict[str, Any]:
	"""Convertir borrador a factura final en FacturAPI (simulado)"""
	import uuid

	return {
		"success": True,
		"cfdi_uuid": str(uuid.uuid4()),
		"cfdi_xml": "<cfdi:Comprobante>...</cfdi:Comprobante>",
		"pdf_url": f"https://factorapi.io/pdf/{draft_id}",
		"message": "Factura timbrada exitosamente",
	}


def cancel_draft_in_factorapi(draft_id: str) -> dict[str, Any]:
	"""Cancelar borrador en FacturAPI (simulado)"""
	return {"success": True, "message": "Borrador cancelado en FacturAPI"}


def get_draft_preview_from_factorapi(draft_id: str) -> dict[str, Any]:
	"""Obtener preview de borrador desde FacturAPI (simulado)"""
	return {
		"success": True,
		"xml": "<cfdi:Comprobante>...preview XML...</cfdi:Comprobante>",
		"pdf_url": f"https://factorapi.io/preview/{draft_id}.pdf",
	}


# Hooks handlers para integración automática


def on_sales_invoice_submit(doc, method):
	"""Hook ejecutado al submit de Sales Invoice"""
	try:
		# Si está marcado para crear como borrador, crear automáticamente
		if doc.get("fm_create_as_draft") and not doc.get("fm_draft_status"):
			result = create_draft_invoice(doc.name)
			if not result.get("success"):
				frappe.log_error(f"Error auto-creando borrador: {result.get('message')}")

	except Exception as e:
		frappe.log_error(f"Error en hook sales invoice submit: {e!s}")


def validate_draft_workflow(doc, method):
	"""Validar flujo de trabajo de borradores"""
	try:
		# Si está marcado como borrador pero ya está timbrado, prevenir
		if doc.get("fm_create_as_draft") and doc.get("fm_cfdi_uuid"):
			frappe.throw(_("No se puede marcar como borrador una factura ya timbrada"))

		# Si no está marcado como borrador, limpiar campos relacionados
		if not doc.get("fm_create_as_draft"):
			doc.fm_draft_status = ""
			doc.fm_factorapi_draft_id = ""
			doc.fm_draft_created_date = ""
			doc.fm_draft_approved_by = ""

	except Exception as e:
		frappe.log_error(f"Error validando draft workflow: {e!s}")
