import frappe
from frappe import _


def validate_rfc_format(doc, method):
	"""Validar formato de RFC en Customer usando tax_id estándar ERPNext."""

	# Protección estándar para testing siguiendo patrón condominium_management
	if hasattr(frappe.flags, "in_test") and frappe.flags.in_test:
		return

	# Usar tax_id como único campo RFC
	rfc_field = getattr(doc, "tax_id", None)
	if not rfc_field:
		return

	# Validar formato básico con defensive handling
	try:
		rfc = str(rfc_field).strip().upper()
		doc.tax_id = rfc
	except (AttributeError, TypeError):
		frappe.throw(_("RFC debe ser un campo de texto válido"))
		return

	# Validar longitud
	if len(rfc) not in [12, 13]:
		frappe.throw(_("RFC debe tener 12 o 13 caracteres"))

	# Validar que no sea RFC genérico
	generic_rfcs = ["XAXX010101000", "XEXX010101000"]
	if rfc in generic_rfcs:
		frappe.throw(_("No se puede usar RFC genérico"))

	# Validar formato con regex básico
	import re

	if len(rfc) == 13:
		# Persona física: 4 letras + 6 dígitos + 3 caracteres
		pattern = r"^[A-Z]{4}[0-9]{6}[A-Z0-9]{3}$"
	else:
		# Persona moral: 3 letras + 6 dígitos + 3 caracteres
		pattern = r"^[A-Z]{3}[0-9]{6}[A-Z0-9]{3}$"

	if not re.match(pattern, rfc):
		frappe.throw(_("Formato de RFC inválido"))


def schedule_rfc_validation(doc, method):
	"""Programar validación de RFC con SAT después de crear Customer."""

	# Protección estándar para testing
	if hasattr(frappe.flags, "in_test") and frappe.flags.in_test:
		return

	# Usar tax_id como campo RFC
	rfc_field = getattr(doc, "tax_id", None)
	if not rfc_field:
		return

	try:
		# Programar validación asíncrona (placeholder para implementación futura)
		frappe.enqueue(
			"facturacion_mexico.validaciones.api.validate_rfc",
			rfc=str(rfc_field),
			queue="short",
			timeout=30,
			is_async=True,
		)
	except Exception as e:
		# No fallar la creación del customer por errores de validación
		frappe.log_error(
			message=f"Error programando validación RFC para {doc.name}: {e!s}",
			title="Schedule RFC Validation Error",
		)
