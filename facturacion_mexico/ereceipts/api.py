"""
APIs para EReceipts México - Sprint 2
Sistema de recibos electrónicos con autofacturación
"""

import calendar
from datetime import datetime

import frappe
from frappe import _


@frappe.whitelist()
def crear_ereceipt(sales_invoice_name):
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

		# Calcular fecha de vencimiento según configuración
		_calcular_fecha_vencimiento(ereceipt)

		ereceipt.insert()

		# Generar en FacturAPI si está configurado
		facturapi_result = None
		settings = frappe.get_single("Facturacion Mexico Settings")
		if settings.get("enable_ereceipts") and (settings.get("api_key") or settings.get("test_api_key")):
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
def get_ereceipt_status(ereceipt_name):
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
def get_ereceipts_for_global_invoice(date_from, date_to, customer=None):
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
def invoice_ereceipt(ereceipt_name, customer_data):
	"""Convierte E-Receipt a factura."""
	try:
		# REGLA #35: Validate required parameters
		if not ereceipt_name:
			return {"success": False, "message": "ereceipt_name parameter is required"}

		if not customer_data:
			return {"success": False, "message": "customer_data parameter is required"}

		# REGLA #35: Defensive DocType access
		try:
			ereceipt = frappe.get_doc("EReceipt MX", ereceipt_name)
		except frappe.DoesNotExistError:
			return {"success": False, "message": f"EReceipt {ereceipt_name} not found"}

		if ereceipt.status != "open":
			return {"success": False, "message": _("Solo se pueden facturar E-Receipts abiertos")}

		# Crear nueva Sales Invoice con datos del customer
		sales_invoice = frappe.copy_doc(frappe.get_doc("Sales Invoice", ereceipt.sales_invoice))

		# Actualizar datos del customer
		sales_invoice.customer = customer_data.get("customer")
		sales_invoice.customer_name = customer_data.get("customer_name")

		# Limpiar campos fiscales para nuevo timbrado
		sales_invoice.fm_fiscal_status = "Pendiente"
		sales_invoice.fm_uuid_fiscal = None
		sales_invoice.fm_factura_fiscal_mx = None

		sales_invoice.insert()

		# Marcar E-Receipt como facturado
		ereceipt.status = "invoiced"
		ereceipt.related_factura_fiscal = sales_invoice.name
		ereceipt.save()

		return {
			"success": True,
			"sales_invoice": sales_invoice.name,
			"message": _("E-Receipt convertido a factura exitosamente"),
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error convirtiendo E-Receipt")
		return {"success": False, "message": str(e)}


def _calcular_fecha_vencimiento(ereceipt):
	"""Calcula fecha de vencimiento según configuración."""
	settings = frappe.get_single("Facturacion Mexico Settings")

	expiry_type = ereceipt.get("expiry_type") or settings.get("default_expiry_type", "Fixed Days")

	if expiry_type == "Fixed Days":
		days = ereceipt.get("expiry_days") or settings.get("default_expiry_days", 3)
		ereceipt.expiry_date = frappe.utils.add_days(ereceipt.date_issued, days)

	elif expiry_type == "End of Month":
		# Último día del mes actual
		year = datetime.now().year
		month = datetime.now().month
		last_day = calendar.monthrange(year, month)[1]
		ereceipt.expiry_date = datetime(year, month, last_day).date()

	elif expiry_type == "Custom Date":
		# Se debe proporcionar expiry_date manualmente
		if not ereceipt.get("expiry_date"):
			ereceipt.expiry_date = frappe.utils.add_days(ereceipt.date_issued, 3)


def _generar_facturapi_ereceipt(ereceipt):
	"""Genera E-Receipt en FacturAPI."""
	try:
		from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client

		client = get_facturapi_client()
		sales_invoice = frappe.get_doc("Sales Invoice", ereceipt.sales_invoice)

		# Preparar datos del customer
		customer_data = {
			"legal_name": sales_invoice.customer_name or "Cliente Público en General",
			"email": sales_invoice.contact_email or "noreply@example.com",
		}

		# Si tenemos RFC del customer, agregarlo
		customer_doc = frappe.get_doc("Customer", sales_invoice.customer)
		if customer_doc.get("rfc"):
			customer_data["tax_id"] = customer_doc.rfc

		receipt_data = {
			"type": "receipt",
			"customer": customer_data,
			"items": [],
			"payment_form": "28",  # Tarjeta de crédito por defecto para e-receipts
			"folio_number": ereceipt.name,
			"expires_at": ereceipt.expiry_date.isoformat() if ereceipt.expiry_date else None,
		}

		# Agregar items de la factura
		for item in sales_invoice.items:
			receipt_data["items"].append(
				{
					"quantity": item.qty,
					"product": {
						"description": item.item_name or item.item_code,
						"product_key": "01010101",  # Genérico para pruebas
						"price": item.rate,
						"unit_key": "H87",  # Pieza
						"unit_name": "Pieza",
						"sku": item.item_code,
					},
				}
			)

		# Crear en FacturAPI
		response = client.create_receipt(receipt_data)

		# Procesar respuesta exitosa
		if response and response.get("id"):
			ereceipt.facturapi_id = response["id"]
			ereceipt.key = response.get("key")
			ereceipt.self_invoice_url = response.get("self_invoice_url")
			ereceipt.status = "open"
			ereceipt.save()

			frappe.logger().info(f"E-Receipt {ereceipt.name} creado en FacturAPI: {response['id']}")

			return {"success": True, "facturapi_id": response["id"]}
		else:
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
