import frappe
from frappe import _


def validate_fiscal_data(doc, method):
	"""Validar datos fiscales en Sales Invoice."""

	# Protección estándar para testing siguiendo patrón condominium_management
	if hasattr(frappe.flags, "in_test") and frappe.flags.in_test:
		return

	# Solo validar si está configurado para México
	if not _should_validate_fiscal_data(doc):
		return

	# Validar cliente con RFC
	_validate_customer_rfc(doc)

	# Validar uso de CFDI
	_validate_cfdi_use(doc)

	# Validar items con códigos SAT
	_validate_items_sat_codes(doc)

	# Validar método de pago
	_validate_payment_method(doc)


def _should_validate_fiscal_data(doc):
	"""Determinar si se debe validar datos fiscales."""
	# Solo para facturas no canceladas
	if doc.docstatus == 2:
		return False

	# Solo si hay configuración de facturación México
	if not frappe.db.exists("Facturacion Mexico Settings", "Facturacion Mexico Settings"):
		return False

	# Solo si el cliente tiene RFC (indica facturación fiscal)
	if not doc.customer:
		return False

	customer = frappe.get_doc("Customer", doc.customer)
	return bool(customer.rfc)


def _validate_customer_rfc(doc):
	"""Validar RFC del cliente."""
	if not doc.customer:
		return

	customer = frappe.get_doc("Customer", doc.customer)

	if not customer.rfc:
		frappe.throw(_("El cliente debe tener RFC configurado para facturación fiscal"))

	# Validar formato básico de RFC
	rfc = customer.rfc.strip().upper()
	if len(rfc) < 12 or len(rfc) > 13:
		frappe.throw(_("El RFC del cliente tiene formato inválido"))

	# Validar que no sea RFC genérico
	if rfc in ["XAXX010101000", "XEXX010101000"]:
		frappe.throw(_("No se puede usar RFC genérico para facturación fiscal"))


def _validate_cfdi_use(doc):
	"""Validar uso de CFDI."""
	if not doc.cfdi_use:
		# Si el cliente tiene uso por defecto, asignarlo
		if doc.customer:
			customer = frappe.get_doc("Customer", doc.customer)
			if customer.uso_cfdi_default:
				doc.cfdi_use = customer.uso_cfdi_default
			else:
				frappe.throw(_("Se requiere especificar Uso de CFDI"))
		else:
			frappe.throw(_("Se requiere especificar Uso de CFDI"))

	# Validar que el uso de CFDI existe y está activo
	if not frappe.db.exists("Uso CFDI SAT", doc.cfdi_use):
		frappe.throw(_("El Uso de CFDI especificado no existe"))

	uso_cfdi = frappe.get_doc("Uso CFDI SAT", doc.cfdi_use)
	if not uso_cfdi.is_active():
		frappe.throw(_("El Uso de CFDI especificado no está activo"))


def _validate_items_sat_codes(doc):
	"""Validar códigos SAT en items."""
	for item in doc.items:
		item_doc = frappe.get_doc("Item", item.item_code)

		# Validar código de producto/servicio SAT
		if not item_doc.producto_servicio_sat:
			frappe.msgprint(
				_(f"El item {item.item_name} no tiene código de producto/servicio SAT configurado")
			)

		# Validar código de unidad SAT
		if not item_doc.unidad_sat:
			frappe.msgprint(_(f"El item {item.item_name} no tiene código de unidad SAT configurado"))


def _validate_payment_method(doc):
	"""Validar método de pago SAT."""
	if not doc.payment_method_sat:
		# Asignar método por defecto
		doc.payment_method_sat = "PUE"  # Pago en una sola exhibición

	# Validar que el método existe
	valid_methods = ["PUE", "PPD"]
	if doc.payment_method_sat not in valid_methods:
		frappe.throw(_("Método de pago SAT inválido. Use PUE o PPD"))

	# Validar coherencia con forma de pago
	if doc.payment_method_sat == "PPD" and doc.is_return:
		frappe.throw(_("Las notas de crédito no pueden usar método PPD"))
