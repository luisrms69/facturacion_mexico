import frappe
from frappe import _


def validate_rfc_format(doc, method):
	"""Validar formato de RFC en Customer."""

	# Solo validar si tiene RFC
	if not doc.rfc:
		return

	# Validar formato básico
	rfc = doc.rfc.strip().upper()
	doc.rfc = rfc

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
