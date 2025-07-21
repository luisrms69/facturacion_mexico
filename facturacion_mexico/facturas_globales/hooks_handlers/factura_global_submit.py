"""
Factura Global Submit Handler - Sprint 4 Semana 1
Hooks para manejo de eventos de Factura Global MX
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime


def on_factura_global_submit(doc, method):
	"""Hook ejecutado al enviar Factura Global MX."""
	try:
		# Ya se ejecuta generate_global_cfdi en before_submit
		# Aquí agregamos validaciones adicionales post-submit
		validate_post_submit(doc)

		# Actualizar estadísticas de la empresa
		update_company_stats(doc)

		# Notificar si está configurado
		send_notifications(doc)

	except Exception as e:
		frappe.log_error(f"Error en hook submit de Factura Global {doc.name}: {e}")


def on_factura_global_cancel(doc, method):
	"""Hook ejecutado al cancelar Factura Global MX."""
	try:
		# Registrar evento de cancelación
		create_cancellation_log(doc)

		# Actualizar estadísticas
		update_company_stats_on_cancel(doc)

	except Exception as e:
		frappe.log_error(f"Error en hook cancel de Factura Global {doc.name}: {e}")


def validate_post_submit(doc):
	"""Validaciones adicionales post-submit."""
	# Verificar que se generó el UUID
	if not doc.uuid:
		frappe.throw(_("Error: No se generó UUID fiscal"))

	# Verificar que todos los receipts están marcados
	for detail in doc.receipts_detail:
		if detail.included_in_cfdi:
			receipt_doc = frappe.get_doc("EReceipt MX", detail.ereceipt)
			if not receipt_doc.global_invoice:
				frappe.db.set_value(
					"EReceipt MX", detail.ereceipt, "global_invoice", doc.name, update_modified=False
				)


def update_company_stats(doc):
	"""Actualizar estadísticas de facturas globales de la empresa."""
	try:
		# Verificar si existe el DocType de estadísticas
		if not frappe.db.exists("DocType", "Company Global Invoice Stats"):
			return

		stats_name = f"{doc.company}-Global-Stats"

		if frappe.db.exists("Company Global Invoice Stats", stats_name):
			stats_doc = frappe.get_doc("Company Global Invoice Stats", stats_name)
		else:
			stats_doc = frappe.get_doc(
				{
					"doctype": "Company Global Invoice Stats",
					"name": stats_name,
					"company": doc.company,
					"total_global_invoices": 0,
					"total_amount": 0,
					"total_receipts": 0,
				}
			)

		# Actualizar contadores
		stats_doc.total_global_invoices += 1
		stats_doc.total_amount += flt(doc.total_periodo)
		stats_doc.total_receipts += doc.cantidad_receipts
		stats_doc.last_global_invoice = doc.name
		stats_doc.last_updated = now_datetime()

		if stats_doc.is_new():
			stats_doc.insert(ignore_permissions=True)
		else:
			stats_doc.save(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(f"Error actualizando estadísticas de empresa: {e}")


def update_company_stats_on_cancel(doc):
	"""Actualizar estadísticas al cancelar."""
	try:
		stats_name = f"{doc.company}-Global-Stats"

		if frappe.db.exists("Company Global Invoice Stats", stats_name):
			stats_doc = frappe.get_doc("Company Global Invoice Stats", stats_name)

			# Restar contadores
			stats_doc.total_global_invoices = max(0, stats_doc.total_global_invoices - 1)
			stats_doc.total_amount = max(0, stats_doc.total_amount - flt(doc.total_periodo))
			stats_doc.total_receipts = max(0, stats_doc.total_receipts - doc.cantidad_receipts)
			stats_doc.last_updated = now_datetime()

			stats_doc.save(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(f"Error actualizando estadísticas en cancelación: {e}")


def send_notifications(doc):
	"""Enviar notificaciones de factura global creada."""
	try:
		settings = frappe.get_single("Facturacion Mexico Settings")

		if not settings.notify_global_generation:
			return

		recipients = []
		if settings.global_notification_emails:
			recipients.extend(settings.global_notification_emails.split(","))

		# Agregar usuario creador
		if doc.created_by:
			recipients.append(doc.created_by)

		if not recipients:
			return

		# Preparar datos del email
		subject = f"Factura Global {doc.name} - Timbrada Exitosamente"

		template_data = {
			"factura_name": doc.name,
			"company": doc.company,
			"periodo_inicio": doc.periodo_inicio,
			"periodo_fin": doc.periodo_fin,
			"total_periodo": doc.total_periodo,
			"cantidad_receipts": doc.cantidad_receipts,
			"uuid": doc.uuid,
			"folio": doc.folio,
			"processing_time": doc.processing_time,
		}

		message = get_notification_template(template_data)

		# Enviar email
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			header=["Factura Global Timbrada", "green"],
		)

	except Exception as e:
		frappe.log_error(f"Error enviando notificaciones: {e}")


def get_notification_template(data):
	"""Obtener template de notificación."""
	return f"""
	<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
		<h2 style="color: #2ecc71;">✅ Factura Global Timbrada</h2>

		<div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
			<h3>Información de la Factura</h3>
			<p><strong>Factura:</strong> {data['factura_name']}</p>
			<p><strong>Empresa:</strong> {data['company']}</p>
			<p><strong>Período:</strong> {data['periodo_inicio']} al {data['periodo_fin']}</p>
			<p><strong>Total:</strong> ${data['total_periodo']:,.2f} MXN</p>
			<p><strong>Receipts Incluidos:</strong> {data['cantidad_receipts']}</p>
		</div>

		<div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
			<h3>Información Fiscal</h3>
			<p><strong>UUID:</strong> {data['uuid']}</p>
			<p><strong>Folio:</strong> {data['folio']}</p>
			<p><strong>Tiempo de Procesamiento:</strong> {data['processing_time']:.2f} segundos</p>
		</div>

		<div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
			<p>Este email fue generado automáticamente por el sistema de Facturación México.</p>
			<p>Para ver más detalles, acceda al sistema ERP.</p>
		</div>
	</div>
	"""


def create_cancellation_log(doc):
	"""Crear log de cancelación."""
	try:
		log_doc = frappe.get_doc(
			{
				"doctype": "Global Invoice Cancellation Log",
				"factura_global": doc.name,
				"company": doc.company,
				"cancelled_by": frappe.session.user,
				"cancellation_date": now_datetime(),
				"original_amount": doc.total_periodo,
				"receipts_count": doc.cantidad_receipts,
				"uuid": doc.uuid,
				"reason": "Cancelación manual",
				"status": "Cancelled",
			}
		)
		log_doc.insert(ignore_permissions=True)

	except Exception as e:
		# Si no existe el DocType, solo logear
		frappe.log_error(f"Error creando log de cancelación: {e}")


def on_ereceipt_update(doc, method):
	"""Hook para actualizar disponibilidad de E-Receipt."""
	try:
		# Solo para E-Receipt MX
		if doc.doctype != "EReceipt MX":
			return

		# Actualizar disponibilidad para facturas globales
		if doc.docstatus == 1 and not doc.get("included_in_global"):
			# Marcar como disponible para factura global
			if not hasattr(doc, "available_for_global") or doc.available_for_global is None:
				frappe.db.set_value("EReceipt MX", doc.name, "available_for_global", 1, update_modified=False)

		elif doc.docstatus == 2:  # Cancelado
			# Quitar de factura global si estaba incluido
			if doc.get("global_invoice"):
				remove_from_global_invoice(doc)

	except Exception as e:
		frappe.log_error(f"Error en hook de E-Receipt {doc.name}: {e}")


def remove_from_global_invoice(ereceipt_doc):
	"""Remover E-Receipt de factura global al cancelar."""
	try:
		if not ereceipt_doc.global_invoice:
			return

		global_invoice = frappe.get_doc("Factura Global MX", ereceipt_doc.global_invoice)

		# Solo si la factura global está en draft
		if global_invoice.docstatus == 0:
			# Remover del detalle - iterar en reversa para evitar problemas de modificación
			for i in range(len(global_invoice.receipts_detail) - 1, -1, -1):
				detail = global_invoice.receipts_detail[i]
				if detail.ereceipt == ereceipt_doc.name:
					global_invoice.receipts_detail.pop(i)
					break

			# Recalcular totales
			global_invoice.calculate_totals()
			global_invoice.save()

			# Limpiar referencias en el receipt
			frappe.db.set_value(
				"EReceipt MX",
				ereceipt_doc.name,
				{
					"global_invoice": None,
					"included_in_global": 0,
					"available_for_global": 0,  # Ya no disponible porque está cancelado
				},
				update_modified=False,
			)

	except Exception as e:
		frappe.log_error(f"Error removiendo E-Receipt de factura global: {e}")
