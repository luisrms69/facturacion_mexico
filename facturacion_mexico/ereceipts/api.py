"""
APIs para EReceipts México - Sprint 2
Sistema de recibos electrónicos con autofacturación
"""

import calendar
from datetime import datetime

import frappe
from frappe import _

from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client


@frappe.whitelist()
def crear_ereceipt(sales_invoice_name: str | None = None):
	"""Crea E-Receipt desde Sales Invoice."""
	try:
		# REGLA #35: Validate required parameters
		if not sales_invoice_name:
			return {"success": False, "message": "sales_invoice_name parameter is required"}

		# Validar que no exista e-receipt previo
		existing = frappe.db.exists("EReceipt MX", {"sales_invoice": sales_invoice_name})
		if existing:
			return {
				"success": False,
				"message": _("Ya existe un E-Receipt para esta factura: {0}").format(existing),
			}

		# REGLA #35: Defensive DocType access with validation
		try:
			sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
		except frappe.DoesNotExistError:
			return {"success": False, "message": _("Sales Invoice {0} not found").format(sales_invoice_name)}

		# Validar que no tenga factura fiscal
		if sales_invoice.get("fm_factura_fiscal_mx"):
			return {"success": False, "message": _("Esta factura ya tiene factura fiscal asociada")}

		# Crear E-Receipt
		ereceipt = frappe.new_doc("EReceipt MX")
		ereceipt.sales_invoice = sales_invoice_name
		ereceipt.company = sales_invoice.company
		ereceipt.total = sales_invoice.grand_total
		ereceipt.date_issued = frappe.utils.today()

		# Poblar info fiscal desde SI (transitorio — issue #182 para modelo line-level)
		from facturacion_mexico.utils.calculo_impuestos import extract_iva_info_from_si_taxes

		tax_rate, has_ieps = extract_iva_info_from_si_taxes(sales_invoice.taxes or [])
		ereceipt.tax_rate = tax_rate  # None si no determinable
		ereceipt.has_ieps = 1 if has_ieps else 0

		# Calcular fecha de vencimiento según configuración
		_calcular_fecha_vencimiento(ereceipt)

		ereceipt.insert()

		# Generar en FacturAPI
		facturapi_result = _generar_facturapi_ereceipt(ereceipt)

		if not facturapi_result.get("success"):
			# E-Receipt creado localmente pero falló en FacturAPI
			return {
				"success": True,
				"ereceipt_name": ereceipt.name,
				"message": _("E-Receipt creado (sin sincronizar con FacturAPI): {0}").format(
					facturapi_result.get("message", "")
				),
				"warning": True,
			}

		message = _("E-Receipt creado exitosamente")
		if facturapi_result and facturapi_result.get("success"):
			message += f" - FacturAPI ID: {facturapi_result.get('facturapi_id', 'N/A')}"

		return {
			"success": True,
			"ereceipt_name": ereceipt.name,
			"message": message,
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error creando E-Receipt")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_ereceipt_status(ereceipt_name: str | None = None):
	"""Consulta status de E-Receipt."""
	try:
		# REGLA #35: Validate required parameters
		if not ereceipt_name:
			return {"success": False, "message": "ereceipt_name parameter is required"}

		# REGLA #35: Defensive DocType access
		try:
			ereceipt = frappe.get_doc("EReceipt MX", ereceipt_name)
		except frappe.DoesNotExistError:
			return {"success": False, "message": f"EReceipt {ereceipt_name} not found"}

		# Verificar si ha expirado
		if ereceipt.status == "open" and ereceipt.expiry_date < frappe.utils.today():
			ereceipt.status = "expired"
			ereceipt.save()

		return {
			"success": True,
			"status": ereceipt.status,
			"expiry_date": ereceipt.expiry_date,
			"self_invoice_url": ereceipt.get("self_invoice_url"),
			"facturapi_id": ereceipt.get("facturapi_id"),
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error consultando E-Receipt")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def expire_ereceipts():
	"""Marca E-Receipts expirados (llamada por scheduler)."""
	try:
		today = frappe.utils.today()

		frappe.db.sql(
			"""
			UPDATE `tabEReceipt MX`
			SET status = 'expired'
			WHERE status = 'open'
			AND expiry_date < %s
		""",
			(today,),
		)

		frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist bulk status updates for scheduled operation

		count = frappe.db.sql(
			"""
			SELECT COUNT(*) as count
			FROM `tabEReceipt MX`
			WHERE status = 'expired'
			AND DATE(modified) = %s
		""",
			(today,),
		)[0][0]

		return {
			"success": True,
			"expired_count": count,
			"message": _("E-Receipts expirados procesados: {0}").format(count),
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error expirando E-Receipts")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_ereceipts_for_global_invoice(
	date_from: str | None = None, date_to: str | None = None, customer: str | None = None
):
	"""Obtiene E-Receipts para factura global."""
	try:
		filters = {
			"status": "open",
			"date_issued": ["between", [date_from, date_to]],
			"included_in_global": 0,
		}

		if customer:
			# Obtener invoices del customer
			customer_invoices = frappe.db.get_list(
				"Sales Invoice", filters={"customer": customer}, pluck="name"
			)
			filters["sales_invoice"] = ["in", customer_invoices]

		ereceipts = frappe.db.get_list(
			"EReceipt MX",
			filters=filters,
			fields=["name", "sales_invoice", "total", "date_issued", "expiry_date", "key"],
		)

		return {"success": True, "ereceipts": ereceipts, "count": len(ereceipts)}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error obteniendo E-Receipts para global")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def invoice_ereceipt(ereceipt_name: str | None = None, customer_data: str | None = None):
	"""Factura individualmente un E-Receipt via FacturAPI.

	Pendiente Fase 3 — usar POST /receipts/{id}/invoice de FacturAPI.
	No crea Sales Invoice local ni usa flujo FFM.
	"""
	return {
		"success": False,
		"message": _(
			"Facturación individual de E-Receipt no implementada aún. "
			"Use el portal de autofactura (self_invoice_url). Pendiente Fase 3."
		),
	}


def _calcular_fecha_vencimiento(ereceipt):
	"""Calcula fecha de vencimiento según configuración de Company Settings."""
	company = ereceipt.get("company")
	cs = (
		frappe.db.get_value(
			"Facturacion Mexico Company Settings",
			{"company": company},
			["ereceipt_expiry_type_default", "ereceipt_expiry_days_default"],
			as_dict=True,
		)
		or {}
	)

	expiry_type = ereceipt.get("expiry_type") or cs.get("ereceipt_expiry_type_default") or "Fixed Days"

	if expiry_type == "Fixed Days":
		days = ereceipt.get("expiry_days") or cs.get("ereceipt_expiry_days_default") or 3
		ereceipt.expiry_date = frappe.utils.add_days(ereceipt.date_issued, days)

	elif expiry_type == "End of Month":
		year = datetime.now().year
		month = datetime.now().month
		last_day = calendar.monthrange(year, month)[1]
		ereceipt.expiry_date = datetime(year, month, last_day).date()

	elif expiry_type == "Custom Date":
		if not ereceipt.get("expiry_date"):
			ereceipt.expiry_date = frappe.utils.add_days(ereceipt.date_issued, 3)


def _get_payment_form_for_ereceipt(sales_invoice, company):
	"""Obtener forma de pago para el E-Receipt.
	Prioridad: Payment Entry vinculado → Company Settings → default '28'.
	"""
	# Intentar obtener del Payment Entry vinculado
	pe = frappe.db.get_value(
		"Payment Entry Reference",
		{"reference_doctype": "Sales Invoice", "reference_name": sales_invoice.name},
		"parent",
	)
	if pe:
		mode = frappe.db.get_value("Payment Entry", pe, "mode_of_payment")
		if mode:
			# Intentar mapear Mode of Payment → código SAT via Forma Pago SAT
			sat_code = frappe.db.get_value("Mode of Payment", mode, "fm_codigo_sat")
			if sat_code:
				return sat_code

	# Fallback: Company Settings
	company_default = frappe.db.get_value(
		"Facturacion Mexico Company Settings",
		{"company": company},
		"ereceipt_payment_form_default",
	)
	return company_default or "28"


def _build_item_taxes_for_receipt(tax_rate):
	"""Construye nodo de impuestos para un item de receipt.

	Si tax_rate es None (no determinable desde el SI), no se envían taxes.
	FacturAPI soporta taxes en receipts para que la autofactura del portal
	genere un CFDI con IVA correcto.
	"""
	if tax_rate is None:
		return []
	return [{"type": "IVA", "rate": float(tax_rate) / 100, "factor": "Tasa", "withholding": False}]


def _get_product_key_for_item(item_code):
	"""Lee clave SAT del producto desde el Item.

	Lanza ValidationError si falta fm_producto_servicio_sat — el receipt puede convertirse
	en CFDI (portal, individual o Factura Global) y debe nacer con payload fiscal correcto.
	"""
	product_key = frappe.db.get_value("Item", item_code, "fm_producto_servicio_sat")
	if not product_key:
		frappe.throw(
			_(
				"El Item {0} no tiene Clave SAT Producto/Servicio (fm_producto_servicio_sat). "
				"Configurar en la ficha del Item antes de crear el E-Receipt."
			).format(item_code)
		)
	return product_key


def _get_unit_key_for_item(uom):
	"""Lee clave SAT de unidad desde UOM usando el mismo patrón que el timbrado normal."""
	from facturacion_mexico.facturacion_fiscal.timbrado_api import _extract_sat_code_from_uom

	return _extract_sat_code_from_uom(uom)


def _generar_facturapi_ereceipt(ereceipt):
	"""Genera E-Receipt en FacturAPI con payload fiscal correcto."""
	try:
		from facturacion_mexico.config.fiscal_states_config import FiscalStates

		company = ereceipt.company
		client = get_facturapi_client(company=company)
		sales_invoice = frappe.get_doc("Sales Invoice", ereceipt.sales_invoice)

		# RFC del cliente: usar tax_id (campo correcto en Customer)
		customer_doc = frappe.get_doc("Customer", sales_invoice.customer)
		customer_data = {
			"legal_name": sales_invoice.customer_name or "Público en General",
		}
		if customer_doc.get("tax_id"):
			customer_data["tax_id"] = customer_doc.tax_id

		# Email solo si existe y es real (nunca mandar fallback falso)
		email = sales_invoice.contact_email or customer_doc.get("customer_primary_contact")
		if not email:
			email = frappe.db.get_value("Customer", sales_invoice.customer, "customer_primary_contact")
		if email and "@" in email and "noreply" not in email.lower() and "example" not in email.lower():
			customer_data["email"] = email

		payment_form = _get_payment_form_for_ereceipt(sales_invoice, company)

		receipt_data = {
			"type": "receipt",
			"customer": customer_data,
			"items": [],
			"payment_form": payment_form,
			"folio_number": ereceipt.name,
		}
		if ereceipt.expiry_date:
			receipt_data["expires_at"] = ereceipt.expiry_date.isoformat()

		# Impuestos: usar tax_rate del EReceipt (poblado por populate_fiscal_info)
		taxes = _build_item_taxes_for_receipt(ereceipt.get("tax_rate"))

		# Construir items con datos fiscales reales
		for item in sales_invoice.items:
			item_data = {
				"quantity": item.qty,
				"product": {
					"description": item.item_name or item.item_code,
					"product_key": _get_product_key_for_item(item.item_code),
					"price": item.rate,
					"unit_key": _get_unit_key_for_item(item.uom),
					"sku": item.item_code,
				},
			}
			if taxes:
				item_data["product"]["taxes"] = taxes
			receipt_data["items"].append(item_data)

		response = client.create_receipt(receipt_data)

		if response and response.get("id"):
			ereceipt.facturapi_id = response["id"]
			ereceipt.key = response.get("key")
			ereceipt.self_invoice_url = response.get("self_invoice_url")
			ereceipt.status = "open"

			# Si FacturAPI devuelve expires_at, usarlo como fuente de verdad
			if response.get("expires_at"):
				try:
					from frappe.utils import getdate

					ereceipt.expiry_date = getdate(response["expires_at"][:10])
				except Exception:
					pass

			ereceipt.save()

			# Escribir trazabilidad en Sales Invoice
			if ereceipt.sales_invoice:
				frappe.db.set_value(
					"Sales Invoice",
					ereceipt.sales_invoice,
					{
						"fm_ereceipt_mx": ereceipt.name,
						"fm_fiscal_status": FiscalStates.E_RECEIPT,
					},
				)

			frappe.logger().info(f"E-Receipt {ereceipt.name} creado en FacturAPI: {response['id']}")
			return {"success": True, "facturapi_id": response["id"]}

		frappe.log_error(
			message=f"Respuesta inválida de FacturAPI: {response}", title="FacturAPI E-Receipt Error"
		)
		return {"success": False, "message": "Respuesta inválida de FacturAPI"}

	except Exception as e:
		error_msg = str(e)
		frappe.log_error(
			message=f"Error generando E-Receipt en FacturAPI: {error_msg}\nE-Receipt: {ereceipt.name}",
			title="Error FacturAPI E-Receipt",
		)
		return {"success": False, "message": error_msg}
