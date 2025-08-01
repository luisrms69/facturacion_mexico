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

	# Auto-asignar uso CFDI default si es necesario
	_auto_assign_cfdi_use_default(doc)

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
	return bool(customer.tax_id)


def _validate_customer_rfc(doc):
	"""Validar RFC del cliente."""
	if not doc.customer:
		return

	customer = frappe.get_doc("Customer", doc.customer)

	if not customer.tax_id:
		frappe.throw(_("El cliente debe tener RFC configurado en Tax ID para facturación fiscal"))

	# Validar formato básico de RFC
	rfc = customer.tax_id.strip().upper()
	if len(rfc) < 12 or len(rfc) > 13:
		frappe.throw(_("El RFC del cliente tiene formato inválido"))

	# Validar que no sea RFC genérico
	if rfc in ["XAXX010101000", "XEXX010101000"]:
		frappe.throw(_("No se puede usar RFC genérico para facturación fiscal"))


def _auto_assign_cfdi_use_default(doc):
	"""Auto-asignar uso CFDI default desde Customer si no está definido."""
	# Solo asignar si el campo está vacío y hay cliente
	if not doc.fm_cfdi_use and doc.customer:
		try:
			customer = frappe.get_doc("Customer", doc.customer)
			if customer.fm_uso_cfdi_default:
				doc.fm_cfdi_use = customer.fm_uso_cfdi_default
				frappe.logger().info(
					f"Auto-asignado uso CFDI '{customer.fm_uso_cfdi_default}' para factura {doc.name}"
				)
		except Exception as e:
			frappe.logger().error(f"Error auto-asignando uso CFDI default: {e}")


def _validate_cfdi_use(doc):
	"""Validar uso de CFDI - OBLIGATORIO para todas las facturas."""

	# 1. VALIDACIÓN BLOQUEANTE: Uso CFDI es OBLIGATORIO
	if not doc.fm_cfdi_use:
		frappe.throw(
			_(
				"Uso de CFDI es obligatorio para facturación fiscal mexicana. "
				"Configure un default en el Cliente o seleccione manualmente."
			)
		)

	# 2. Validar que el uso de CFDI existe en catálogo SAT
	if not frappe.db.exists("Uso CFDI SAT", doc.fm_cfdi_use):
		frappe.throw(_("El Uso de CFDI '{0}' no existe en el catálogo SAT").format(doc.fm_cfdi_use))

	# 3. Validar que el uso de CFDI está activo
	uso_cfdi = frappe.get_doc("Uso CFDI SAT", doc.fm_cfdi_use)
	if not uso_cfdi.is_active():
		frappe.throw(_("El Uso de CFDI '{0}' no está activo en el catálogo SAT").format(doc.fm_cfdi_use))


def _validate_items_sat_codes(doc):
	"""Validar códigos SAT en items."""
	for item in doc.items:
		item_doc = frappe.get_doc("Item", item.item_code)

		# Validar código de producto/servicio SAT
		if not item_doc.fm_producto_servicio_sat:
			frappe.throw(_(f"El item {item.item_name} no tiene código de producto/servicio SAT configurado"))

		# Validar UOM con formato SAT (NUEVA VALIDACIÓN)
		_validate_uom_sat_format(item)


def _validate_uom_sat_format(item):
	"""
	Validar que UOM tenga formato SAT válido: 'CODIGO - Descripción'
	Reemplaza la validación anterior de fm_unidad_sat por formato UOM nativo.
	"""
	if not item.uom:
		frappe.throw(_(f"Item {item.item_code}: UOM es obligatoria"))

	# Verificar formato SAT: "CODIGO - Descripción"
	uom_parts = item.uom.split(" - ")
	if len(uom_parts) < 2:
		frappe.throw(
			_(
				f"Item {item.item_code}: UOM '{item.uom}' debe tener formato SAT 'CODIGO - Descripción'. "
				f"Ejemplo: 'H87 - Pieza', 'KGM - Kilogramo'"
			)
		)

	sat_code = uom_parts[0].strip()
	if len(sat_code) < 2:
		frappe.throw(
			_(
				f"Item {item.item_code}: Código SAT '{sat_code}' inválido en UOM '{item.uom}'. "
				f"El código debe tener al menos 2 caracteres"
			)
		)

	# Verificar que la UOM existe y está activa
	if not frappe.db.exists("UOM", item.uom):
		frappe.throw(_(f"Item {item.item_code}: UOM '{item.uom}' no existe"))

	uom_enabled = frappe.db.get_value("UOM", item.uom, "enabled")
	if not uom_enabled:
		frappe.throw(
			_(
				f"Item {item.item_code}: UOM '{item.uom}' está desactivada. "
				f"Active la UOM o seleccione una UOM SAT válida"
			)
		)


def _validate_payment_method(doc):
	"""Validar método de pago SAT."""
	if not doc.fm_payment_method_sat:
		# Asignar método por defecto
		doc.fm_payment_method_sat = "PUE"  # Pago en una sola exhibición

	# Validar que el método existe
	valid_methods = ["PUE", "PPD"]
	if doc.fm_payment_method_sat not in valid_methods:
		frappe.throw(_("Método de pago SAT inválido. Use PUE o PPD"))

	# Validar coherencia con forma de pago
	if doc.fm_payment_method_sat == "PPD" and doc.is_return:
		frappe.throw(_("Las notas de crédito no pueden usar método PPD"))
