"""
Sales Invoice Submit Handler - Sistema de Addendas
Sprint 3 - Facturación México
"""

from typing import Optional

import frappe
from frappe import _


def sales_invoice_on_submit(doc, method):
	"""
	Hook handler para submit de Sales Invoice.
	Se ejecuta después de que la factura es enviada exitosamente.
	"""
	try:
		# Solo procesar si requiere addenda
		if not should_process_addenda_on_submit(doc):
			return

		# Procesar addenda después del submit
		process_addenda_after_submit(doc)

	except Exception as e:
		# Log del error sin interrumpir el flujo
		frappe.log_error(
			f"Error procesando addenda en submit de {doc.name}: {str(e)}", "Sales Invoice Addenda Submit"
		)


def should_process_addenda_on_submit(doc) -> bool:
	"""Determinar si se debe procesar addenda en el submit."""
	# Solo si requiere addenda
	if not doc.get("fm_addenda_required"):
		return False

	# Solo si está configurado para auto-aplicar
	from facturacion_mexico.addendas.api import get_addenda_configuration

	try:
		config_result = get_addenda_configuration(doc.customer)
		if not config_result.get("success"):
			return False

		config = config_result["data"]
		return config.get("auto_apply", False)

	except Exception:
		return False


def process_addenda_after_submit(doc):
	"""Procesar addenda después del submit."""
	try:
		# Actualizar estado a generando
		update_addenda_status(doc.name, "Generando")

		# Commit para asegurar que el estado se guarde
		frappe.db.commit()

		# Generar addenda en background job para no bloquear el submit
		frappe.enqueue(
			generate_addenda_background,
			queue="default",
			timeout=300,
			sales_invoice=doc.name,
			user=frappe.session.user,
		)

		# Mostrar mensaje al usuario
		frappe.msgprint(
			_("Addenda se está generando en segundo plano. Será notificado cuando esté lista."),
			indicator="blue",
			title=_("Generando Addenda"),
		)

	except Exception as e:
		# Actualizar estado de error
		update_addenda_status(doc.name, "Error", errors=f"Error iniciando generación: {str(e)}")
		raise


def generate_addenda_background(sales_invoice: str, user: str):
	"""Generar addenda en trabajo de fondo."""
	try:
		# Establecer usuario para el contexto
		frappe.set_user(user)

		# Obtener documento actualizado
		doc = frappe.get_doc("Sales Invoice", sales_invoice)

		# Verificar estado actual
		if doc.get("fm_addenda_status") != "Generando":
			return

		# Generar addenda
		from facturacion_mexico.addendas.api import generate_addenda_xml

		result = generate_addenda_xml(sales_invoice, validate_output=True)

		if result.get("success"):
			# Addenda generada exitosamente
			process_successful_addenda(doc, result)
		else:
			# Error en generación
			process_failed_addenda(doc, result.get("message", "Error desconocido"))

	except Exception as e:
		# Error en el proceso
		error_msg = f"Error en background job: {str(e)}"
		frappe.log_error(error_msg, "Addenda Background Generation")

		try:
			update_addenda_status(sales_invoice, "Error", errors=error_msg)
		except:
			pass


def process_successful_addenda(doc, result):
	"""Procesar addenda generada exitosamente."""
	try:
		addenda_xml = result.get("xml", "")

		# Actualizar estado
		update_addenda_status(doc.name, "Completada", addenda_xml=addenda_xml)

		# Insertar en CFDI si está disponible
		if doc.get("fm_cfdi_xml") and addenda_xml:
			insert_addenda_in_cfdi(doc, addenda_xml)

		# Validar resultado si se solicita
		validation_result = result.get("validation", {})
		if not validation_result.get("valid", True):
			# Hay advertencias en la validación
			warning_msg = f"Addenda generada con advertencias: {validation_result.get('message', '')}"
			frappe.log_error(warning_msg, "Addenda Validation Warning")

		# Notificar éxito
		notify_addenda_success(doc, result)

		frappe.db.commit()

	except Exception as e:
		error_msg = f"Error procesando addenda exitosa: {str(e)}"
		frappe.log_error(error_msg)
		update_addenda_status(doc.name, "Error", errors=error_msg)


def process_failed_addenda(doc, error_message: str):
	"""Procesar fallo en generación de addenda."""
	try:
		# Actualizar estado de error
		update_addenda_status(doc.name, "Error", errors=error_message)

		# Notificar error
		notify_addenda_error(doc, [error_message])

		frappe.db.commit()

	except Exception as e:
		frappe.log_error(f"Error procesando fallo de addenda: {str(e)}")


def insert_addenda_in_cfdi(doc, addenda_xml: str):
	"""Insertar addenda en el CFDI."""
	try:
		from facturacion_mexico.addendas.parsers.cfdi_parser import CFDIParser

		parser = CFDIParser(doc.fm_cfdi_xml)

		# Validar que el CFDI puede recibir la addenda
		is_valid, message = parser.validate_cfdi_structure()

		if not is_valid:
			frappe.log_error(f"CFDI no válido para addenda: {message}")
			return

		# Insertar addenda
		modified_cfdi = parser.insert_addenda(addenda_xml)

		# Actualizar CFDI en la factura
		frappe.db.set_value("Sales Invoice", doc.name, {"fm_cfdi_xml": modified_cfdi})

		# Log del éxito
		frappe.logger().info(f"Addenda insertada exitosamente en CFDI de factura {doc.name}")

	except Exception as e:
		error_msg = f"Error insertando addenda en CFDI: {str(e)}"
		frappe.log_error(error_msg)

		# No fallar todo el proceso por esto, solo logear
		# El XML de addenda independiente sigue siendo válido


def update_addenda_status(sales_invoice: str, status: str, addenda_xml: str = "", errors: str = ""):
	"""Actualizar estado de addenda en Sales Invoice."""
	try:
		update_data = {
			"fm_addenda_status": status,
			"modified": frappe.utils.now(),
			"modified_by": frappe.session.user,
		}

		if status == "Completada" and addenda_xml:
			update_data.update(
				{
					"fm_addenda_xml": addenda_xml,
					"fm_addenda_generated_date": frappe.utils.now(),
					"fm_addenda_errors": "",
				}
			)
		elif status == "Error" and errors:
			update_data.update(
				{"fm_addenda_errors": errors, "fm_addenda_xml": "", "fm_addenda_generated_date": ""}
			)

		frappe.db.set_value("Sales Invoice", sales_invoice, update_data)

	except Exception as e:
		frappe.log_error(f"Error actualizando estado de addenda: {str(e)}")


def notify_addenda_success(doc, result):
	"""Notificar éxito en generación de addenda."""
	try:
		# Obtener configuración para ver si hay notificaciones configuradas
		from facturacion_mexico.addendas.api import get_addenda_configuration

		config_result = get_addenda_configuration(doc.customer)

		if not config_result.get("success"):
			return

		config = config_result["data"]

		# Solo enviar si hay destinatarios configurados
		if not config.get("error_recipients"):
			return

		recipients = [email.strip() for email in config["error_recipients"].split(",")]

		subject = f"Addenda Generada - Factura {doc.name}"
		message = f"""
		<h3>Addenda Generada Exitosamente</h3>
		<p><strong>Factura:</strong> {doc.name}</p>
		<p><strong>Cliente:</strong> {doc.customer}</p>
		<p><strong>Fecha:</strong> {doc.posting_date}</p>
		<p><strong>Tipo de Addenda:</strong> {doc.get('fm_addenda_type', 'N/A')}</p>
		<p><strong>Fecha de Generación:</strong> {frappe.utils.now()}</p>

		<h4>Información Adicional:</h4>
		<ul>
		<li>Validación: {'Exitosa' if result.get('validation', {}).get('valid', True) else 'Con advertencias'}</li>
		<li>CFDI Actualizado: {'Sí' if doc.get('fm_cfdi_xml') else 'No'}</li>
		</ul>
		"""

		frappe.sendmail(recipients=recipients, subject=subject, message=message)

	except Exception as e:
		frappe.log_error(f"Error enviando notificación de éxito: {str(e)}")


def notify_addenda_error(doc, errors: list):
	"""Notificar error en generación de addenda."""
	try:
		from facturacion_mexico.addendas.api import get_addenda_configuration

		config_result = get_addenda_configuration(doc.customer)

		if not config_result.get("success"):
			return

		config = config_result["data"]

		if not config.get("notify_on_error") or not config.get("error_recipients"):
			return

		recipients = [email.strip() for email in config["error_recipients"].split(",")]

		subject = f"Error en Addenda - Factura {doc.name}"
		message = f"""
		<h3>Error en Generación de Addenda</h3>
		<p><strong>Factura:</strong> {doc.name}</p>
		<p><strong>Cliente:</strong> {doc.customer}</p>
		<p><strong>Fecha:</strong> {doc.posting_date}</p>
		<p><strong>Tipo de Addenda:</strong> {doc.get('fm_addenda_type', 'N/A')}</p>
		<p><strong>Fecha del Error:</strong> {frappe.utils.now()}</p>

		<h4>Errores:</h4>
		<ul>
		{"".join(f"<li>{error}</li>" for error in errors)}
		</ul>

		<p><em>Por favor revise la configuración de addenda y los datos de la factura.</em></p>
		"""

		frappe.sendmail(recipients=recipients, subject=subject, message=message)

	except Exception as e:
		frappe.log_error(f"Error enviando notificación de error: {str(e)}")


def retry_failed_addenda(sales_invoice: str):
	"""Reintentar generación de addenda fallida."""
	try:
		doc = frappe.get_doc("Sales Invoice", sales_invoice)

		if doc.get("fm_addenda_status") != "Error":
			return {"success": False, "message": "La addenda no está en estado de error"}

		# Limpiar errores previos
		update_addenda_status(sales_invoice, "Pendiente")

		# Procesar nuevamente
		process_addenda_after_submit(doc)

		return {"success": True, "message": "Reintento de addenda iniciado"}

	except Exception as e:
		error_msg = f"Error reintentando addenda: {str(e)}"
		frappe.log_error(error_msg)
		return {"success": False, "message": error_msg}


def cancel_addenda_processing(sales_invoice: str):
	"""Cancelar procesamiento de addenda."""
	try:
		doc = frappe.get_doc("Sales Invoice", sales_invoice)

		if doc.get("fm_addenda_status") not in ["Pendiente", "Generando"]:
			return {"success": False, "message": "No se puede cancelar addenda en este estado"}

		# Actualizar estado
		update_addenda_status(sales_invoice, "", "", "Procesamiento cancelado por usuario")

		return {"success": True, "message": "Procesamiento de addenda cancelado"}

	except Exception as e:
		error_msg = f"Error cancelando addenda: {str(e)}"
		frappe.log_error(error_msg)
		return {"success": False, "message": error_msg}


# Funciones de utilidad para testing
def force_regenerate_addenda(sales_invoice: str):
	"""Forzar regeneración de addenda (solo para testing/admin)."""
	try:
		# Solo administradores pueden usar esta función
		if frappe.session.user != "Administrator":
			return {"success": False, "message": "Solo administradores pueden forzar regeneración"}

		doc = frappe.get_doc("Sales Invoice", sales_invoice)

		if not doc.get("fm_addenda_required"):
			return {"success": False, "message": "La factura no requiere addenda"}

		# Forzar regeneración
		update_addenda_status(sales_invoice, "Generando")

		frappe.enqueue(
			generate_addenda_background,
			queue="default",
			timeout=300,
			sales_invoice=sales_invoice,
			user=frappe.session.user,
		)

		return {"success": True, "message": "Regeneración forzada iniciada"}

	except Exception as e:
		error_msg = f"Error en regeneración forzada: {str(e)}"
		frappe.log_error(error_msg)
		return {"success": False, "message": error_msg}
