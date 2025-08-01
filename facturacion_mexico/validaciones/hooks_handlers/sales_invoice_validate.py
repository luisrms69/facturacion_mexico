"""
Sales Invoice Validate Hook Handler - Sprint 2
Sistema de Validaciones SAT México
"""

import frappe
from frappe import _


def validate_sat_requirements(doc, method):
	"""
	Hook handler para validar requerimientos SAT en Sales Invoice.

	Valida datos fiscales, RFC, uso CFDI y otros campos requeridos
	para el timbrado CFDI 4.0.

	Args:
		doc: Sales Invoice document
		method: Hook method name ('validate')
	"""
	try:
		# Solo validar si es factura con timbrado fiscal
		if not _requires_sat_validation(doc):
			return

		# Ejecutar validaciones SAT
		_validate_customer_rfc(doc)
		_validate_uso_cfdi(doc)
		_validate_regimen_fiscal(doc)
		_validate_forma_pago(doc)
		_validate_metodo_pago(doc)
		_validate_currency_and_exchange_rate(doc)
		_validate_items_sat_codes(doc)
		_validate_uom_sat_codes(doc)  # Sprint 6 Phase 2: UOM-SAT validation

	except Exception as e:
		frappe.log_error(
			message=f"Error en validate_sat_requirements: {e!s}", title="Sales Invoice Validate Hook Error"
		)
		# Re-lanzar para bloquear validación si es crítico
		raise


def _requires_sat_validation(sales_invoice):
	"""
	Determinar si la factura requiere validación SAT.

	Args:
		sales_invoice: Sales Invoice document

	Returns:
		bool: True si requiere validación SAT
	"""
	try:
		# REGLA #35: Defensive access para fm_requires_stamp
		requires_stamp = getattr(sales_invoice, "fm_requires_stamp", None)
		if not requires_stamp:
			return False

		# REGLA #35: Defensive access para customer field
		customer_name = getattr(sales_invoice, "customer", None)
		if not customer_name:
			return False

		# Verificar que sea a un cliente nacional (México)
		customer_country = frappe.get_value("Customer", customer_name, "country")
		if customer_country and customer_country != "Mexico":
			return False

		return True

	except Exception as e:
		frappe.log_error(f"Error checking SAT validation requirements: {e}", "SAT Validation Check")
		return False


def _validate_customer_rfc(sales_invoice):
	"""
	Validar RFC del cliente usando cache SAT.

	Args:
		sales_invoice: Sales Invoice document
	"""
	try:
		# REGLA #35: Defensive access para customer field
		customer_name = getattr(sales_invoice, "customer", None)
		if not customer_name:
			frappe.throw(_("Sales Invoice debe tener cliente configurado"))

		customer_rfc = frappe.get_value("Customer", customer_name, "tax_id")

		if not customer_rfc:
			frappe.throw(
				_("El cliente {0} debe tener RFC configurado para facturación fiscal").format(customer_name)
			)

		# Validar formato básico de RFC
		if not _is_valid_rfc_format(customer_rfc):
			frappe.throw(_("RFC del cliente '{0}' tiene formato inválido").format(customer_rfc))

		# Validar contra SAT usando cache
		_validate_rfc_with_sat_cache(customer_rfc, customer_name)

	except frappe.ValidationError:
		raise
	except Exception as e:
		frappe.log_error(
			message=f"Error validando RFC cliente: {e!s}", title="Sales Invoice - RFC Validation Error"
		)
		frappe.throw(_("Error validando RFC del cliente"))


def _validate_rfc_with_sat_cache(rfc, customer_name):
	"""
	Validar RFC usando el sistema de cache SAT.

	Args:
		rfc: RFC a validar
		customer_name: Nombre del cliente
	"""
	try:
		from facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache import (
			SATValidationCache,
		)

		# Buscar en cache primero
		cache_key = f"RFC_{rfc.upper()}"
		cached_result = SATValidationCache.get_valid_cache(cache_key, "rfc_validation")

		if cached_result:
			# Usar resultado del cache
			result_data = frappe.parse_json(cached_result.get("result_data", "{}"))
			if not result_data.get("valid", False):
				frappe.throw(
					_("RFC '{0}' no es válido según SAT (cache): {1}").format(
						rfc, result_data.get("message", "RFC inválido")
					)
				)
		else:
			# Validar con SAT y guardar en cache
			_validate_and_cache_rfc(rfc, cache_key)

	except frappe.ValidationError:
		raise
	except Exception:
		# Si falla la validación SAT, permitir continuar con advertencia
		frappe.msgprint(
			_("Advertencia: No se pudo validar RFC '{0}' con SAT. Procediendo sin validación.").format(rfc),
			alert=True,
			indicator="orange",
		)


def _validate_and_cache_rfc(rfc, cache_key):
	"""
	Validar RFC con SAT API y guardar resultado en cache.

	Args:
		rfc: RFC a validar
		cache_key: Key para el cache
	"""
	try:
		# TODO: Implementar llamada real a API SAT
		# Por ahora simular validación básica
		result_data = {
			"valid": True,
			"status": "Activo",
			"message": "RFC válido (validación simulada)",
			"validation_date": frappe.utils.now(),
		}

		# Guardar en cache
		from facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache import (
			SATValidationCache,
		)

		SATValidationCache.create_cache_record(
			validation_key=cache_key,
			validation_type="rfc_validation",
			result_data=result_data,
			source_system="SAT_API_SIMULATION",
		)

	except Exception as e:
		frappe.log_error(
			message=f"Error validando RFC con SAT API: {e!s}", title="RFC SAT API Validation Error"
		)


def _is_valid_rfc_format(rfc):
	"""
	Validar formato básico de RFC.

	Args:
		rfc: RFC a validar

	Returns:
		bool: True si el formato es válido
	"""
	import re

	if not rfc:
		return False

	# RFC persona física: 4 letras + 6 dígitos + 3 caracteres
	# RFC persona moral: 3 letras + 6 dígitos + 3 caracteres
	rfc_pattern = r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$"

	return bool(re.match(rfc_pattern, rfc.upper()))


def _validate_uso_cfdi(sales_invoice):
	"""
	Validar Uso CFDI configurado.

	Args:
		sales_invoice: Sales Invoice document
	"""
	uso_cfdi = sales_invoice.get("fm_uso_cfdi")

	if not uso_cfdi:
		frappe.throw(_("Uso CFDI es requerido para facturación fiscal"))

	# Validar que el código sea válido según catálogo SAT
	valid_usos = _get_valid_uso_cfdi_codes()
	if uso_cfdi not in valid_usos:
		frappe.throw(_("Uso CFDI '{0}' no es válido según catálogo SAT").format(uso_cfdi))


def _get_valid_uso_cfdi_codes():
	"""
	Obtener códigos válidos de Uso CFDI desde configuración.

	Returns:
		list: Lista de códigos válidos
	"""
	# En una implementación real, esto vendría de una tabla o configuración
	return [
		"G01",
		"G02",
		"G03",
		"I01",
		"I02",
		"I03",
		"I04",
		"I05",
		"I06",
		"I07",
		"I08",
		"D01",
		"D02",
		"D03",
		"D04",
		"D05",
		"D06",
		"D07",
		"D08",
		"D09",
		"D10",
		"P01",
		"CP01",
		"CN01",
		"S01",
	]


def _validate_regimen_fiscal(sales_invoice):
	"""
	Validar Régimen Fiscal del emisor.

	Args:
		sales_invoice: Sales Invoice document
	"""
	try:
		company_regimen = frappe.get_value("Company", sales_invoice.company, "custom_regimen_fiscal")

		if not company_regimen:
			frappe.throw(
				_("La empresa {0} debe tener configurado el Régimen Fiscal SAT").format(sales_invoice.company)
			)

	except Exception as e:
		frappe.log_error(
			message=f"Error validando régimen fiscal: {e!s}",
			title="Sales Invoice - Regimen Fiscal Validation Error",
		)
		frappe.throw(_("Error validando régimen fiscal de la empresa"))


def _validate_forma_pago(sales_invoice):
	"""
	Validar Forma de Pago SAT.

	Args:
		sales_invoice: Sales Invoice document
	"""
	forma_pago = sales_invoice.get("fm_forma_pago")

	if not forma_pago:
		frappe.throw(_("Forma de Pago SAT es requerida para facturación fiscal"))

	# Validaciones específicas por forma de pago
	if forma_pago == "99":  # Por definir (PPD)
		# Validar que método de pago sea PPD
		metodo_pago = sales_invoice.get("fm_metodo_pago")
		if metodo_pago != "PPD":
			frappe.throw(_("Forma de Pago '99 - Por definir' requiere Método de Pago 'PPD'"))


def _validate_metodo_pago(sales_invoice):
	"""
	Validar Método de Pago SAT.

	Args:
		sales_invoice: Sales Invoice document
	"""
	metodo_pago = sales_invoice.get("fm_metodo_pago")

	if not metodo_pago:
		frappe.throw(_("Método de Pago SAT es requerido para facturación fiscal"))

	# Validar códigos válidos
	valid_metodos = ["PUE", "PPD"]
	if metodo_pago not in valid_metodos:
		frappe.throw(_("Método de Pago '{0}' no es válido. Debe ser PUE o PPD").format(metodo_pago))


def _validate_currency_and_exchange_rate(sales_invoice):
	"""
	Validar moneda y tipo de cambio.

	Args:
		sales_invoice: Sales Invoice document
	"""
	# Validar moneda
	if not sales_invoice.currency:
		frappe.throw(_("Moneda es requerida para facturación fiscal"))

	# Si es moneda extranjera, validar tipo de cambio
	if sales_invoice.currency != "MXN":
		if not sales_invoice.conversion_rate or sales_invoice.conversion_rate <= 0:
			frappe.throw(_("Tipo de cambio es requerido para factura en {0}").format(sales_invoice.currency))

		# Validar que el tipo de cambio sea razonable
		if sales_invoice.conversion_rate > 100 or sales_invoice.conversion_rate < 0.01:
			frappe.msgprint(
				_("Advertencia: Tipo de cambio {0} parece inusual").format(sales_invoice.conversion_rate),
				alert=True,
				indicator="orange",
			)


def _validate_items_sat_codes(sales_invoice):
	"""
	Validar códigos SAT de productos/servicios.

	Args:
		sales_invoice: Sales Invoice document
	"""
	for item in sales_invoice.items:
		# Validar Clave Producto/Servicio SAT
		clave_producto = frappe.get_value("Item", item.item_code, "custom_clave_producto_sat")
		if not clave_producto:
			frappe.throw(
				_("El artículo '{0}' debe tener configurada la Clave de Producto/Servicio SAT").format(
					item.item_code
				)
			)

		# Validar Clave Unidad SAT
		clave_unidad = frappe.get_value("UOM", item.uom, "fm_clave_sat")
		if not clave_unidad:
			frappe.throw(_("La UOM '{0}' debe tener configurada la Clave de Unidad SAT").format(item.uom))


def validate_customer_fiscal_data(doc, method):
	"""
	Validar datos fiscales del cliente ANTES del submit.
	Evita que Sales Invoice se submita con datos faltantes.

	Args:
		doc: Sales Invoice document
		method: Hook method name
	"""
	try:
		# Solo validar si requiere timbrado fiscal
		if not _should_validate_fiscal_data(doc):
			return

		customer = frappe.get_doc("Customer", doc.customer)

		# VALIDACIÓN CRÍTICA: customer.address requerida por PAC
		_validate_customer_address_required(doc, customer)

		# Validar RFC usando estrategia híbrida
		_validate_customer_rfc_hybrid(doc, customer)

		# Validar otros datos fiscales
		_validate_customer_fiscal_fields(doc, customer)

	except frappe.ValidationError:
		raise
	except Exception as e:
		frappe.log_error(
			message=f"Error validando datos fiscales del cliente: {e!s}",
			title="Sales Invoice - Customer Fiscal Data Validation Error",
		)
		# Re-lanzar para bloquear submit
		raise


def _should_validate_fiscal_data(doc):
	"""Determinar si requiere validación fiscal usando misma lógica que timbrado."""
	try:
		# Usar misma lógica que _should_create_fiscal_event
		if doc.docstatus != 0:  # Solo validar en draft
			return False

		if not doc.customer:
			return False

		customer = frappe.get_doc("Customer", doc.customer)
		has_rfc = bool(customer.get("tax_id"))

		# Si tiene RFC, verificar si se va a timbrar
		if has_rfc:
			settings = frappe.get_single("Facturacion Mexico Settings")
			# Si ereceipts está deshabilitado, se va a timbrar normal
			if not settings.auto_generate_ereceipts:
				return True

		return False

	except Exception:
		return False


def _validate_customer_address_required(doc, customer):
	"""Validar que customer tenga address para PAC."""
	# Buscar primary address del customer
	primary_address = frappe.db.sql(
		"""
		SELECT addr.name, addr.address_line1, addr.city, addr.state,
		       addr.country, addr.pincode
		FROM `tabAddress` addr
		INNER JOIN `tabDynamic Link` dl ON dl.parent = addr.name
		WHERE dl.link_doctype = 'Customer'
		AND dl.link_name = %s
		AND addr.is_primary_address = 1
		LIMIT 1
	""",
		doc.customer,
		as_dict=True,
	)

	if not primary_address:
		frappe.throw(
			_(
				"VALIDACIÓN FISCAL: El cliente {0} debe tener una dirección primaria configurada para facturación"
			).format(doc.customer),
			title=_("Dirección Fiscal Requerida"),
		)

	address = primary_address[0]
	required_fields = {
		"address_line1": "Dirección",
		"city": "Ciudad",
		"state": "Estado",
		"country": "País",
		"pincode": "Código Postal",
	}

	missing_fields = []
	for field, label in required_fields.items():
		if not address.get(field):
			missing_fields.append(label)

	if missing_fields:
		frappe.throw(
			_("VALIDACIÓN FISCAL: La dirección primaria del cliente requiere: {0}").format(
				", ".join(missing_fields)
			),
			title=_("Campos de Dirección Faltantes"),
		)


def _validate_customer_rfc_hybrid(doc, customer):
	"""Validar RFC usando tax_id estándar ERPNext."""
	rfc = customer.get("tax_id")

	if not rfc:
		frappe.throw(
			_("VALIDACIÓN FISCAL: El cliente {0} debe tener RFC configurado en Tax ID").format(doc.customer),
			title=_("RFC Requerido"),
		)

	# Validar formato RFC
	if not _is_valid_rfc_format(rfc):
		frappe.throw(
			_("VALIDACIÓN FISCAL: RFC '{0}' tiene formato inválido").format(rfc),
			title=_("RFC Formato Inválido"),
		)


def _validate_customer_fiscal_fields(doc, customer):
	"""Validar otros campos fiscales requeridos."""
	# Validar CFDI Use
	if not doc.get("fm_cfdi_use"):
		frappe.throw(
			_("VALIDACIÓN FISCAL: Uso CFDI es requerido para facturación"), title=_("Uso CFDI Requerido")
		)


def validate_lista_69b_customer(doc, method):
	"""
	Validar que el cliente no esté en Lista 69B del SAT.

	Args:
		doc: Sales Invoice document
		method: Hook method name
	"""
	try:
		if not _requires_sat_validation(doc):
			return

		customer_rfc = frappe.get_value("Customer", doc.customer, "tax_id")
		if not customer_rfc:
			return

		# Validar contra Lista 69B usando cache
		_validate_lista_69b_with_cache(customer_rfc, doc.customer)

	except Exception as e:
		frappe.log_error(
			message=f"Error validando Lista 69B: {e!s}", title="Sales Invoice - Lista 69B Validation Error"
		)
		# No bloquear la facturación por error en Lista 69B
		frappe.msgprint(
			_("Advertencia: No se pudo validar Lista 69B para el cliente"), alert=True, indicator="orange"
		)


def _validate_lista_69b_with_cache(rfc, customer_name):
	"""
	Validar RFC contra Lista 69B usando cache SAT.

	Args:
		rfc: RFC a validar
		customer_name: Nombre del cliente
	"""
	try:
		from facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache import (
			SATValidationCache,
		)

		# Buscar en cache
		cache_key = f"L69B_{rfc.upper()}"
		cached_result = SATValidationCache.get_valid_cache(cache_key, "lista_69b")

		if cached_result:
			result_data = frappe.parse_json(cached_result.get("result_data", "{}"))
			if result_data.get("in_lista_69b", False):
				frappe.msgprint(
					_("ADVERTENCIA: El cliente {0} (RFC: {1}) está en Lista 69B del SAT").format(
						customer_name, rfc
					),
					alert=True,
					indicator="red",
				)
		else:
			# Validar y cachear (implementación futura)
			pass

	except Exception as e:
		frappe.log_error(
			message=f"Error validando Lista 69B con cache: {e!s}", title="Lista 69B Cache Validation Error"
		)


def _validate_uom_sat_codes(sales_invoice):
	"""
	Validar códigos SAT de Unidades de Medida en items de factura.
	Sprint 6 Phase 2: Integración UOM-SAT

	Args:
		sales_invoice: Sales Invoice document
	"""
	try:
		from facturacion_mexico.uom_sat.uom_sat_catalog import validate_invoice_uom_sat_codes

		# Ejecutar validación usando el catálogo UOM-SAT
		is_valid, errors = validate_invoice_uom_sat_codes(sales_invoice)

		if not is_valid:
			# Mostrar errores de validación UOM-SAT
			error_message = "Errores de Unidades de Medida SAT:\n" + "\n".join(errors)
			frappe.throw(_(error_message))

	except ImportError:
		frappe.log_error("UOM SAT Catalog no disponible - validación omitida", "UOM SAT Validation Warning")
	except frappe.ValidationError:
		raise
	except Exception as e:
		frappe.log_error(
			message=f"Error validando códigos UOM-SAT: {e!s}",
			title="Sales Invoice - UOM SAT Validation Error",
		)
		# Por ahora no bloquear facturación por errores UOM-SAT
		frappe.msgprint(
			_(
				"Advertencia: No se pudieron validar códigos UOM-SAT. Revise configuración de Unidades de Medida."
			),
			alert=True,
			indicator="orange",
		)
