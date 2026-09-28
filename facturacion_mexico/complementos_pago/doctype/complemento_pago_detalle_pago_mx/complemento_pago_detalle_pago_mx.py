# Copyright (c) 2026, Buzola and contributors

from frappe.model.document import Document


class ComplementoPagoDetallePagoMX(Document):
	"""Un renglón por nodo pago20:Pago de un CFDI de pago (REP 2.0).

	Representación CANÓNICA del Pago a nivel de detalle. Los campos escalares del padre
	`Complemento Pago MX` se mantienen solo por compatibilidad legacy (Pago único implícito)."""

	pass
