import frappe
from frappe import _


def validate_fiscal_data(doc, method):
	"""Validar datos fiscales en Sales Invoice - ARQUITECTURA MIGRADA."""

	# Protección estándar para testing siguiendo patrón condominium_management
	if hasattr(frappe.flags, "in_test") and frappe.flags.in_test:
		return

	# Solo validar si está configurado para México
	if not _should_validate_fiscal_data(doc):
		return

	# Validar cliente con RFC (básico - no requiere campos fiscales)
	_validate_customer_rfc(doc)

	# Validar items con códigos SAT (no requiere campos fiscales de factura)
	_validate_items_sat_codes(doc)

	# NOTA: Validaciones fiscales específicas (CFDI, payment method) MIGRADAS
	# Se ejecutan ahora en validate() de "Factura Fiscal Mexico" donde existen los campos fm_*


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
	"""Validación migrada a Factura Fiscal Mexico - campo ya no existe en Sales Invoice."""
	# MIGRADO: Esta validación ahora se ejecuta en validate() de "Factura Fiscal Mexico"
	# donde sí existe el campo fm_cfdi_use tras la migración arquitectural
	return


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
	"""Validación migrada a Factura Fiscal Mexico - campo ya no existe en Sales Invoice."""
	# MIGRADO: Esta validación ahora se ejecuta en validate() de "Factura Fiscal Mexico"
	# donde sí existe el campo fm_payment_method_sat tras la migración arquitectural
	return
