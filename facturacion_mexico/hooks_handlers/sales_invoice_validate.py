"""
Sales Invoice Validate Handler - Sistema de Addendas
Sprint 3 - Facturación México
"""

from typing import Optional

import frappe
from frappe import _


def sales_invoice_validate(doc, method):
	"""
	Hook handler para validación de Sales Invoice.
	Se ejecuta antes de guardar el documento.
	"""
	try:
		# Solo procesar facturas que van a ser enviadas (docstatus = 1)
		if doc.docstatus != 1:
			return

		# Verificar requerimientos de addenda
		check_addenda_requirements(doc)

		# Validar configuración de addenda si es requerida
		if doc.get("fm_addenda_required"):
			validate_addenda_configuration(doc)

			# Validar mapeo de productos si es necesario
			validate_product_mappings(doc)

	except Exception as e:
		# Log del error sin interrumpir el flujo principal
		frappe.log_error(
			f"Error en validación de addenda para {doc.name}: {str(e)}", "Sales Invoice Addenda Validation"
		)


def check_addenda_requirements(doc):
	"""Verificar si la factura requiere addenda."""
	try:
		from facturacion_mexico.addendas.api import get_addenda_requirements

		requirements = get_addenda_requirements(doc.customer)

		if requirements.get("requires_addenda"):
			config = requirements.get("configuration")

			# Marcar como requerida
			doc.fm_addenda_required = 1
			doc.fm_addenda_type = config.get("addenda_type")

			# Establecer estado inicial
			if config.get("auto_apply"):
				doc.fm_addenda_status = "Pendiente"
			else:
				doc.fm_addenda_status = ""
		else:
			# Limpiar campos si no requiere
			doc.fm_addenda_required = 0
			doc.fm_addenda_type = ""
			doc.fm_addenda_status = ""

	except Exception as e:
		frappe.log_error(f"Error verificando requerimientos de addenda: {str(e)}")


def validate_addenda_configuration(doc):
	"""Validar que existe configuración válida para la addenda."""
	try:
		from facturacion_mexico.addendas.api import get_addenda_configuration

		config_result = get_addenda_configuration(doc.customer)

		if not config_result.get("success") or not config_result.get("data"):
			frappe.msgprint(
				_("Cliente {0} requiere addenda pero no tiene configuración válida").format(doc.customer),
				indicator="orange",
				title=_("Configuración de Addenda Faltante"),
			)
			return

		config = config_result["data"]

		# Verificar vigencia
		if config.get("effective_date") and doc.posting_date < config["effective_date"]:
			frappe.msgprint(
				_("Configuración de addenda no está vigente para la fecha de la factura"), indicator="orange"
			)

		if config.get("expiry_date") and doc.posting_date > config["expiry_date"]:
			frappe.msgprint(
				_("Configuración de addenda ha expirado para la fecha de la factura"), indicator="orange"
			)

		# Verificar nivel de validación
		validation_level = config.get("validation_level", "Warning")

		if validation_level == "Strict":
			validate_addenda_fields_strict(doc, config)
		elif validation_level == "Error":
			validate_addenda_fields_error(doc, config)
		else:  # Warning
			validate_addenda_fields_warning(doc, config)

	except Exception as e:
		frappe.log_error(f"Error validando configuración de addenda: {str(e)}")


def validate_addenda_fields_strict(doc, config):
	"""Validación estricta - interrumpe el proceso si hay errores."""
	errors = validate_field_values(config.get("field_values", {}), doc)

	if errors:
		error_msg = _("Errores en configuración de addenda:\n• {0}").format("\n• ".join(errors))
		frappe.throw(error_msg, title=_("Validación de Addenda Fallida"))


def validate_addenda_fields_error(doc, config):
	"""Validación con errores - muestra errores pero no interrumpe."""
	errors = validate_field_values(config.get("field_values", {}), doc)

	if errors:
		error_msg = _("Errores en configuración de addenda:\n• {0}").format("\n• ".join(errors))
		frappe.msgprint(error_msg, indicator="red", title=_("Errores en Addenda"))


def validate_addenda_fields_warning(doc, config):
	"""Validación con advertencias - solo muestra advertencias."""
	errors = validate_field_values(config.get("field_values", {}), doc)

	if errors:
		error_msg = _("Advertencias en configuración de addenda:\n• {0}").format("\n• ".join(errors))
		frappe.msgprint(error_msg, indicator="orange", title=_("Advertencias en Addenda"))


def validate_field_values(field_values: dict, doc) -> list:
	"""Validar valores de campos de addenda."""
	errors = []

	try:
		# Resolver valores dinámicos para validación
		context_data = {
			"sales_invoice": doc,
			"customer": frappe.get_doc("Customer", doc.customer),
			"cfdi_data": {},
			"custom_data": {},
		}

		for field_name, field_config in field_values.items():
			try:
				# Validar campo individual
				field_errors = validate_individual_field(field_name, field_config, context_data)
				errors.extend(field_errors)

			except Exception as e:
				errors.append(f"Error validando campo {field_name}: {str(e)}")

	except Exception as e:
		errors.append(f"Error general en validación de campos: {str(e)}")

	return errors


def validate_individual_field(field_name: str, field_config: dict, context_data: dict) -> list:
	"""Validar un campo individual."""
	errors = []

	try:
		# Si es dinámico, verificar que la fuente existe
		if field_config.get("is_dynamic"):
			source = field_config.get("dynamic_source")
			field = field_config.get("dynamic_field")

			if source == "Sales Invoice":
				if not hasattr(context_data["sales_invoice"], field):
					errors.append(f"Campo dinámico {field} no existe en Sales Invoice")
			elif source == "Customer":
				if not hasattr(context_data["customer"], field):
					errors.append(f"Campo dinámico {field} no existe en Customer")

		# Verificar valor requerido
		if field_config.get("is_required"):
			value = field_config.get("value", "")
			if not value and not field_config.get("is_dynamic"):
				errors.append(f"Campo requerido {field_name} está vacío")

	except Exception as e:
		errors.append(f"Error en validación individual de {field_name}: {str(e)}")

	return errors


def validate_product_mappings(doc):
	"""Validar mapeo de productos si es necesario."""
	try:
		# Verificar si el tipo de addenda requiere mapeo de productos
		if not doc.fm_addenda_type:
			return

		addenda_type_doc = frappe.get_doc("Addenda Type", doc.fm_addenda_type)

		if not addenda_type_doc.requires_product_mapping:
			return

		# Verificar que todos los items tienen mapeo
		missing_mappings = []

		for item in doc.items:
			from facturacion_mexico.addendas.doctype.addenda_product_mapping.addenda_product_mapping import (
				find_mapping,
			)

			mapping = find_mapping(doc.customer, item.item_code)

			if not mapping:
				missing_mappings.append(item.item_code)

		if missing_mappings:
			frappe.msgprint(
				_("Los siguientes productos no tienen mapeo para addenda: {0}").format(
					", ".join(missing_mappings)
				),
				indicator="orange",
				title=_("Mapeo de Productos Faltante"),
			)

	except Exception as e:
		frappe.log_error(f"Error validando mapeo de productos: {str(e)}")


def validate_cfdi_compatibility(doc):
	"""Validar compatibilidad con CFDI si existe."""
	try:
		if not doc.get("fm_cfdi_xml"):
			return

		# Verificar que el CFDI puede recibir addenda
		from facturacion_mexico.addendas.parsers.cfdi_parser import CFDIParser

		parser = CFDIParser(doc.fm_cfdi_xml)
		is_valid, message = parser.validate_cfdi_structure()

		if not is_valid:
			frappe.msgprint(
				_("CFDI no es compatible con addendas: {0}").format(message),
				indicator="orange",
				title=_("Incompatibilidad CFDI-Addenda"),
			)

	except Exception as e:
		frappe.log_error(f"Error validando compatibilidad CFDI: {str(e)}")


def pre_validate_addenda_requirements(doc):
	"""Pre-validación de requerimientos antes del submit."""
	try:
		# Solo para facturas que se van a timbrar
		if doc.docstatus != 1:
			return

		# Verificar que si tiene CFDI y requiere addenda, todo esté en orden
		if doc.get("fm_addenda_required") and doc.get("fm_cfdi_xml"):
			# Verificar estado de addenda
			if doc.get("fm_addenda_status") == "Error":
				frappe.throw(
					_("No se puede timbrar: La addenda tiene errores. Error: {0}").format(
						doc.get("fm_addenda_errors", "Error desconocido")
					),
					title=_("Error en Addenda"),
				)

			# Si requiere addenda pero no está generada, generar ahora
			if doc.get("fm_addenda_status") in ["", "Pendiente"]:
				frappe.msgprint(_("Generando addenda automáticamente..."), indicator="blue")

	except Exception as e:
		frappe.log_error(f"Error en pre-validación de addenda: {str(e)}")


# Funciones de utilidad
def should_process_addenda(doc) -> bool:
	"""Determinar si se debe procesar addenda para esta factura."""
	# Solo facturas timbradas
	if doc.docstatus != 1:
		return False

	# Solo si tiene configuración de addenda
	if not doc.get("fm_addenda_required"):
		return False

	# Verificar que no se esté duplicando el procesamiento
	if doc.get("fm_addenda_status") in ["Completada", "Generando"]:
		return False

	return True


def get_addenda_context_data(doc) -> dict:
	"""Obtener datos de contexto para la addenda."""
	context = {
		"sales_invoice": doc,
		"customer": frappe.get_doc("Customer", doc.customer),
		"cfdi_data": {},
		"custom_data": {},
	}

	# Agregar datos CFDI si existe
	if doc.get("fm_cfdi_xml"):
		try:
			from facturacion_mexico.addendas.parsers.cfdi_parser import CFDIParser

			parser = CFDIParser(doc.fm_cfdi_xml)
			context["cfdi_data"] = parser.get_cfdi_data()
		except Exception as e:
			frappe.log_error(f"Error obteniendo datos CFDI: {str(e)}")

	return context


def notify_addenda_errors(doc, errors: list):
	"""Notificar errores de addenda por email si está configurado."""
	try:
		from facturacion_mexico.addendas.api import get_addenda_configuration

		config_result = get_addenda_configuration(doc.customer)

		if not config_result.get("success"):
			return

		config = config_result["data"]

		if not config.get("notify_on_error") or not config.get("error_recipients"):
			return

		# Enviar notificación por email
		recipients = [email.strip() for email in config["error_recipients"].split(",")]

		subject = f"Error en Addenda - Factura {doc.name}"
		message = f"""
		<h3>Error en Generación de Addenda</h3>
		<p><strong>Factura:</strong> {doc.name}</p>
		<p><strong>Cliente:</strong> {doc.customer}</p>
		<p><strong>Fecha:</strong> {doc.posting_date}</p>
		<p><strong>Tipo de Addenda:</strong> {doc.get('fm_addenda_type', 'N/A')}</p>

		<h4>Errores:</h4>
		<ul>
		{"".join(f"<li>{error}</li>" for error in errors)}
		</ul>
		"""

		frappe.sendmail(recipients=recipients, subject=subject, message=message)

	except Exception as e:
		frappe.log_error(f"Error enviando notificación de addenda: {str(e)}")
