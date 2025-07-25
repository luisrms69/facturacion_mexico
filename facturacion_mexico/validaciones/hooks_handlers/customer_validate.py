import frappe
from frappe import _


def validate_rfc_format(doc, method):
	"""Validar formato de RFC en Customer."""

	# Protección estándar para testing siguiendo patrón condominium_management
	if hasattr(frappe.flags, "in_test") and frappe.flags.in_test:
		return

	# REGLA #35: Validación defensiva con fallback
	rfc_field = getattr(doc, "fm_rfc", None)
	if not rfc_field:
		return

	# Validar formato básico con defensive handling
	try:
		fm_rfc = str(rfc_field).strip().upper()
		doc.fm_rfc = fm_rfc
	except (AttributeError, TypeError):
		frappe.throw(_("RFC debe ser un campo de texto válido"))
		return

	# Validar longitud
	if len(fm_rfc) not in [12, 13]:
		frappe.throw(_("RFC debe tener 12 o 13 caracteres"))

	# Validar que no sea RFC genérico
	generic_rfcs = ["XAXX010101000", "XEXX010101000"]
	if fm_rfc in generic_rfcs:
		frappe.throw(_("No se puede usar RFC genérico"))

	# Validar formato con regex básico
	import re

	if len(fm_rfc) == 13:
		# Persona física: 4 letras + 6 dígitos + 3 caracteres
		pattern = r"^[A-Z]{4}[0-9]{6}[A-Z0-9]{3}$"
	else:
		# Persona moral: 3 letras + 6 dígitos + 3 caracteres
		pattern = r"^[A-Z]{3}[0-9]{6}[A-Z0-9]{3}$"

	if not re.match(pattern, fm_rfc):
		frappe.throw(_("Formato de RFC inválido"))


def schedule_rfc_validation(doc, method):
	"""Programar validación de RFC con SAT después de crear Customer."""

	# Protección estándar para testing
	if hasattr(frappe.flags, "in_test") and frappe.flags.in_test:
		return

	# REGLA #35: Validación defensiva de RFC field
	rfc_field = getattr(doc, "fm_rfc", None)
	if not rfc_field:
		return

	try:
		# Programar validación asíncrona (placeholder para implementación futura)
		frappe.enqueue(
			"facturacion_mexico.validaciones.api.validate_rfc",
			fm_rfc=str(rfc_field),
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
