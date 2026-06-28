"""Resolución canónica del correo destinatario fiscal (CFDI ingreso y Complemento de Pago).

Fuente única de verdad para decidir a qué correo se envía un comprobante fiscal por email.
Tanto Factura Fiscal Mexico (envío manual y automático post-timbrado) como Complemento de
Pago deben usar `resolve_fiscal_recipient_email` para garantizar el MISMO criterio.

Prioridad real aplicada (estricta, sin fallbacks inventados):
    1. `to` explícito SI es un correo válido (override programático; la UI hoy siempre envía None).
       Un `to` inválido NUNCA se usa como destinatario: se ignora y la resolución continúa con
       los pasos siguientes (jamás se intenta enviar a un valor inválido).
    2. `stored_email` (FFM.fm_email_facturacion) SI es un correo válido. Para la FFM este valor
       ya ES el correo de la dirección principal capturado al poblar el documento; por eso, cuando
       es válido, NO se vuelve a consultar la dirección (evita una consulta redundante o
       contradictoria). El Complemento no pasa `stored_email`, así que cae directo al paso 2b.
    2b. Correo válido de la dirección principal del Customer (`Address.email_id`).
    3. `customer_email_fallback` de Facturacion Mexico Company Settings para la company recibida.
    4. None.

No se aceptan placeholders, advertencias ni textos que no sean un correo válido.
No se usan: Payment Entry.contact_email, Customer.email_id, Contact.email_id, primeros
contactos relacionados, ni la compañía default global.
"""

from __future__ import annotations

import frappe


def _is_valid_email(value: str | None) -> bool:
	"""True solo si `value` parece un correo real (descarta vacíos, placeholders y avisos)."""
	if not value or not isinstance(value, str):
		return False
	email = value.strip()
	if not email or " " in email:
		return False
	# Un correo válido tiene exactamente un '@' con texto a ambos lados y un punto en el dominio.
	if email.count("@") != 1:
		return False
	local, _, domain = email.partition("@")
	if not local or "." not in domain:
		return False
	# Descarta explícitamente placeholders/avisos (emojis o caracteres no ASCII de aviso).
	return email.isascii()


def get_customer_primary_address_email(customer: str | None) -> str | None:
	"""Correo de la dirección principal del Customer (misma fuente que FFM).

	Resolución de la dirección principal:
	    1) Address con `is_primary_address=1` ligada al Customer por Dynamic Link.
	    2) `Customer.customer_primary_address`.
	    3) Primera Address ligada por Dynamic Link.
	Devuelve `Address.email_id` si es un correo válido, de lo contrario None.
	"""
	if not customer:
		return None

	addr_name = None
	primary_addresses = frappe.get_all("Address", filters={"is_primary_address": 1}, pluck="name")
	for name in primary_addresses:
		if frappe.db.exists(
			"Dynamic Link",
			{
				"link_doctype": "Customer",
				"link_name": customer,
				"parent": name,
				"parenttype": "Address",
			},
		):
			addr_name = name
			break

	if not addr_name:
		addr_name = frappe.db.get_value("Customer", customer, "customer_primary_address")

	if not addr_name:
		linked = frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
			pluck="parent",
		)
		if linked:
			addr_name = linked[0]

	if not addr_name:
		return None

	email = frappe.db.get_value("Address", addr_name, "email_id")
	return email.strip() if _is_valid_email(email) else None


def get_company_fallback_email(company: str | None) -> str | None:
	"""`customer_email_fallback` de Facturacion Mexico Company Settings para `company`.

	Multi-company estricto: NO usa la company default global. Si no se recibe `company`,
	no hay fallback (devuelve None).
	"""
	if not company:
		return None
	fallback = frappe.db.get_value(
		"Facturacion Mexico Company Settings",
		{"company": company},
		"customer_email_fallback",
	)
	return fallback.strip() if _is_valid_email(fallback) else None


def resolve_fiscal_recipient_email(
	*,
	customer: str | None = None,
	company: str | None = None,
	to: str | None = None,
	stored_email: str | None = None,
) -> str | None:
	"""Resuelve el destinatario fiscal según la prioridad canónica. Ver docstring del módulo."""
	# 1. override explícito
	if _is_valid_email(to):
		return to.strip()
	# 2. correo ya almacenado en el documento (FFM.fm_email_facturacion) si es real
	if _is_valid_email(stored_email):
		return stored_email.strip()
	# 2b. correo real de la dirección principal del Customer
	address_email = get_customer_primary_address_email(customer)
	if address_email:
		return address_email
	# 3. fallback por company
	fallback = get_company_fallback_email(company)
	if fallback:
		return fallback
	# 4. sin destinatario
	return None
