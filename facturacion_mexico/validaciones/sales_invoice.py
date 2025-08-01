import frappe
from frappe import _


def validate_ppd_vs_forma_pago(doc, method):
	"""Validar compatibilidad entre PPD/PUE y forma de pago SAT basado en Mode of Payment"""

	if not doc.fm_payment_method_sat:
		return

	# Obtener forma de pago desde Payment Entry relacionado
	forma_pago_sat = None

	if hasattr(doc, "payments") and doc.payments:
		# Buscar Payment Entry relacionado
		for payment_ref in doc.payments:
			if payment_ref.reference_doctype == "Sales Invoice" and payment_ref.reference_name == doc.name:
				payment_entry = frappe.get_doc("Payment Entry", payment_ref.parent)

				if payment_entry.mode_of_payment:
					# Extraer código SAT del Mode of Payment (formato: "01 - Efectivo")
					mode_parts = payment_entry.mode_of_payment.split(" - ")
					if len(mode_parts) >= 2 and mode_parts[0].isdigit():
						forma_pago_sat = mode_parts[0]
						break

	if not forma_pago_sat:
		return

	# Determinar si es PPD basado en payment_terms_template
	is_ppd = bool(doc.payment_terms_template)

	if is_ppd:
		# PPD (Pago en Parcialidades Diferido): Solo permite "99 Por definir"
		if forma_pago_sat != "99":
			frappe.throw(
				_(
					f"Para facturas PPD (Pago en Parcialidades) solo se permite '99 - Por definir'. "
					f"Forma de pago detectada: {forma_pago_sat}"
				),
				title=_("Error Validación PPD"),
			)
	else:
		# PUE (Pago Una Exhibición): NO permite "99 Por definir"
		if forma_pago_sat == "99":
			frappe.throw(
				_(
					"Para facturas PUE (Pago Una Exhibición) no se permite '99 - Por definir'. "
					"Debe seleccionar una forma de pago específica (01, 02, 03, etc.)"
				),
				title=_("Error Validación PUE"),
			)

	frappe.logger().info(
		f"Validación PPD/PUE exitosa - Tipo: {'PPD' if is_ppd else 'PUE'}, Forma Pago: {forma_pago_sat}"
	)
