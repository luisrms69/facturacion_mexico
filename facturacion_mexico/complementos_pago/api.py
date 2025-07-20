import json
from datetime import datetime

import frappe
from frappe import _
from frappe.utils.file_manager import save_file


@frappe.whitelist()
def crear_complemento_desde_payment_entry(payment_entry_name):
	"""
	Crea un Complemento de Pago MX basado en un Payment Entry de ERPNext
	"""
	try:
		payment_entry = frappe.get_doc("Payment Entry", payment_entry_name)

		# Validar que el Payment Entry esté en estado válido
		if payment_entry.docstatus != 1:
			frappe.throw(_("El Payment Entry debe estar en estado 'Submitted'"))

		# Crear el complemento de pago
		complemento = frappe.new_doc("Complemento Pago MX")

		# Información general del pago
		complemento.fecha_pago = payment_entry.posting_date
		complemento.forma_pago_p = obtener_forma_pago_sat(payment_entry.mode_of_payment)
		complemento.moneda_p = payment_entry.paid_from_account_currency or "MXN"
		complemento.monto_p = payment_entry.paid_amount

		# Tipo de cambio si es moneda extranjera
		if complemento.moneda_p != "MXN":
			complemento.tipo_cambio_p = payment_entry.source_exchange_rate or 1.0

		# Información bancaria si existe
		if payment_entry.bank_account:
			bank_account = frappe.get_doc("Bank Account", payment_entry.bank_account)
			complemento.cta_ordenante = bank_account.bank_account_no

		# Agregar documentos relacionados
		if payment_entry.payment_type == "Receive":
			agregar_documentos_relacionados_receive(complemento, payment_entry)
		elif payment_entry.payment_type == "Pay":
			agregar_documentos_relacionados_pay(complemento, payment_entry)

		complemento.insert()

		return {
			"success": True,
			"complemento_name": complemento.name,
			"message": f"Complemento de pago creado exitosamente: {complemento.name}",
		}

	except Exception as e:
		frappe.log_error(f"Error creando complemento de pago: {e!s}")
		return {"success": False, "message": f"Error: {e!s}"}


def obtener_forma_pago_sat(mode_of_payment):
	"""
	Mapea el modo de pago de ERPNext a la forma de pago SAT
	"""
	mapping = {
		"Cash": "01",  # Efectivo
		"Check": "02",  # Cheque nominativo
		"Wire Transfer": "03",  # Transferencia electrónica
		"Credit Card": "04",  # Tarjeta de crédito
		"Debit Card": "28",  # Tarjeta de débito
	}

	# Buscar mapeo personalizado en configuración
	sat_form = frappe.db.get_value("Mode of Payment", mode_of_payment, "custom_forma_pago_sat")
	if sat_form:
		return sat_form

	return mapping.get(mode_of_payment, "99")  # Otros por defecto


def agregar_documentos_relacionados_receive(complemento, payment_entry):
	"""
	Agrega documentos relacionados para pagos recibidos (facturas de venta)
	"""
	for reference in payment_entry.references:
		if reference.reference_doctype == "Sales Invoice":
			invoice = frappe.get_doc("Sales Invoice", reference.reference_name)

			doc_relacionado = complemento.append("documentos_relacionados", {})
			doc_relacionado.id_documento = invoice.custom_folio_fiscal or invoice.name
			doc_relacionado.serie = invoice.custom_serie_sat or ""
			doc_relacionado.folio = invoice.custom_folio_sat or ""
			doc_relacionado.moneda_dr = invoice.currency
			doc_relacionado.equivalencia_dr = invoice.conversion_rate if invoice.currency != "MXN" else 1.0
			doc_relacionado.num_parcialidad = obtener_numero_parcialidad(
				invoice.name, reference.outstanding_amount
			)
			doc_relacionado.imp_saldo_ant = reference.outstanding_amount + reference.allocated_amount
			doc_relacionado.imp_pagado = reference.allocated_amount
			doc_relacionado.imp_saldo_insoluto = reference.outstanding_amount
			doc_relacionado.objeto_imp_dr = "02"  # Sí objeto de impuestos
			doc_relacionado.tipo_documento = "Sales Invoice"
			doc_relacionado.referencia_documento = reference.reference_name


def agregar_documentos_relacionados_pay(complemento, payment_entry):
	"""
	Agrega documentos relacionados para pagos realizados (facturas de compra)
	"""
	for reference in payment_entry.references:
		if reference.reference_doctype == "Purchase Invoice":
			invoice = frappe.get_doc("Purchase Invoice", reference.reference_name)

			doc_relacionado = complemento.append("documentos_relacionados", {})
			doc_relacionado.id_documento = invoice.custom_folio_fiscal or invoice.name
			doc_relacionado.serie = invoice.custom_serie_sat or ""
			doc_relacionado.folio = invoice.custom_folio_sat or ""
			doc_relacionado.moneda_dr = invoice.currency
			doc_relacionado.equivalencia_dr = invoice.conversion_rate if invoice.currency != "MXN" else 1.0
			doc_relacionado.num_parcialidad = obtener_numero_parcialidad(
				invoice.name, reference.outstanding_amount
			)
			doc_relacionado.imp_saldo_ant = reference.outstanding_amount + reference.allocated_amount
			doc_relacionado.imp_pagado = reference.allocated_amount
			doc_relacionado.imp_saldo_insoluto = reference.outstanding_amount
			doc_relacionado.objeto_imp_dr = "02"  # Sí objeto de impuestos
			doc_relacionado.tipo_documento = "Purchase Invoice"
			doc_relacionado.referencia_documento = reference.reference_name


def obtener_numero_parcialidad(invoice_name, outstanding_amount):
	"""
	Calcula el número de parcialidad basado en complementos de pago existentes
	"""
	parcialidades_existentes = frappe.db.sql(
		"""
		SELECT COUNT(*) as count
		FROM `tabDocumento Relacionado Pago MX` dr
		JOIN `tabComplemento Pago MX` cp ON dr.parent = cp.name
		WHERE dr.referencia_documento = %s
		AND cp.docstatus = 1
	""",
		(invoice_name,),
		as_dict=True,
	)

	return (parcialidades_existentes[0].count or 0) + 1


@frappe.whitelist()
def consultar_estatus_complemento(complemento_id):
	"""
	Consulta el estatus de un complemento de pago en el SAT
	"""
	try:
		complemento = frappe.get_doc("Complemento Pago MX", complemento_id)

		if not complemento.folio_fiscal:
			frappe.throw(_("El complemento no tiene folio fiscal para consultar"))

		# Configuración del servicio SAT
		sat_config = frappe.get_single("Configuracion SAT MX")

		# Preparar datos para consulta
		consulta_data = {
			"uuid": complemento.folio_fiscal,
			"rfc_emisor": sat_config.rfc_empresa,
			"rfc_receptor": obtener_rfc_receptor(complemento),
			"total": str(complemento.monto_p),
		}

		# Realizar consulta al SAT (simulado - reemplazar con servicio real)
		resultado = realizar_consulta_sat(consulta_data)

		# Actualizar estatus del complemento
		complemento.db_set("estatus_sat", resultado.get("estatus", "No Encontrado"))
		complemento.db_set("fecha_certificacion_sat", resultado.get("fecha_certificacion"))

		frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist SAT status update after external API query

		return {
			"success": True,
			"estatus": resultado.get("estatus"),
			"message": f"Estatus actualizado: {resultado.get('estatus')}",
		}

	except Exception as e:
		frappe.log_error(f"Error consultando estatus SAT: {e!s}")
		return {"success": False, "message": f"Error: {e!s}"}


def obtener_rfc_receptor(complemento):
	"""
	Obtiene el RFC del receptor basado en los documentos relacionados
	"""
	if complemento.documentos_relacionados:
		primer_doc = complemento.documentos_relacionados[0]
		if primer_doc.tipo_documento == "Sales Invoice":
			invoice = frappe.get_doc("Sales Invoice", primer_doc.referencia_documento)
			customer = frappe.get_doc("Customer", invoice.customer)
			return customer.tax_id
		elif primer_doc.tipo_documento == "Purchase Invoice":
			invoice = frappe.get_doc("Purchase Invoice", primer_doc.referencia_documento)
			supplier = frappe.get_doc("Supplier", invoice.supplier)
			return supplier.tax_id

	return ""


def realizar_consulta_sat(consulta_data):
	"""
	Realiza la consulta al SAT (implementación simulada)
	TODO: Integrar con servicio real del SAT
	"""
	# Simulación de respuesta del SAT
	return {
		"estatus": "Vigente",
		"fecha_certificacion": datetime.now(),
		"codigo_estatus": "S - Comprobante consultado correctamente",
	}


@frappe.whitelist()
def generar_xml_complemento(complemento_name):
	"""
	Genera el XML del complemento de pago según estándar SAT
	"""
	try:
		complemento = frappe.get_doc("Complemento Pago MX", complemento_name)

		# Generar estructura XML
		xml_structure = {
			"cfdi:Comprobante": {
				"@Version": "4.0",
				"@TipoDeComprobante": "P",
				"@Exportacion": "01",
				"@Fecha": complemento.fecha_pago.isoformat(),
				"@Folio": complemento.name,
				"@Moneda": "XXX",
				"@Total": "0",
				"@SubTotal": "0",
				"cfdi:Complemento": {
					"pago20:Pagos": {
						"@Version": "2.0",
						"pago20:Totales": {"@MontoTotalPagos": str(complemento.monto_p)},
						"pago20:Pago": generar_datos_pago(complemento),
					}
				},
			}
		}

		# Convertir a XML (implementación simplificada)
		xml_content = json.dumps(xml_structure, indent=2)

		# Guardar archivo XML
		file_doc = save_file(
			fname=f"{complemento.name}_complemento.xml",
			content=xml_content,
			dt="Complemento Pago MX",
			dn=complemento.name,
			is_private=0,
		)

		return {"success": True, "file_url": file_doc.file_url, "message": "XML generado exitosamente"}

	except Exception as e:
		frappe.log_error(f"Error generando XML: {e!s}")
		return {"success": False, "message": f"Error: {e!s}"}


def generar_datos_pago(complemento):
	"""
	Genera la estructura de datos del pago para el XML
	"""
	pago_data = {
		"@FechaPago": complemento.fecha_pago.isoformat(),
		"@FormaDePagoP": complemento.forma_pago_p,
		"@MonedaP": complemento.moneda_p,
		"@Monto": str(complemento.monto_p),
	}

	if complemento.tipo_cambio_p and complemento.moneda_p != "MXN":
		pago_data["@TipoCambioP"] = str(complemento.tipo_cambio_p)

	# Agregar documentos relacionados
	documentos_relacionados = []
	for doc in complemento.documentos_relacionados:
		doc_data = {
			"@IdDocumento": doc.id_documento,
			"@MonedaDR": doc.moneda_dr,
			"@NumParcialidad": str(doc.num_parcialidad),
			"@ImpSaldoAnt": str(doc.imp_saldo_ant),
			"@ImpPagado": str(doc.imp_pagado),
			"@ImpSaldoInsoluto": str(doc.imp_saldo_insoluto),
			"@ObjetoImpDR": doc.objeto_imp_dr,
		}
		documentos_relacionados.append(doc_data)

	pago_data["pago20:DoctoRelacionado"] = documentos_relacionados

	return pago_data


@frappe.whitelist()
def obtener_complementos_pendientes_timbrado():
	"""
	Obtiene complementos de pago pendientes de timbrado
	"""
	complementos = frappe.get_all(
		"Complemento Pago MX",
		filters={
			"docstatus": 1,
			"estatus_sat": ["in", ["", "No Encontrado"]],
			"fecha_timbrado": ["is", "not set"],
		},
		fields=["name", "folio_fiscal", "fecha_pago", "monto_p", "creation"],
	)

	return complementos


@frappe.whitelist()
def reporte_complementos_periodo(fecha_inicio, fecha_fin):
	"""
	Genera reporte de complementos de pago por período
	"""
	complementos = frappe.db.sql(
		"""
		SELECT
			name,
			folio_fiscal,
			fecha_pago,
			forma_pago_p,
			moneda_p,
			monto_p,
			estatus_sat,
			fecha_timbrado
		FROM `tabComplemento Pago MX`
		WHERE docstatus = 1
		AND fecha_pago BETWEEN %s AND %s
		ORDER BY fecha_pago DESC
	""",
		(fecha_inicio, fecha_fin),
		as_dict=True,
	)

	# Calcular totales
	total_monto = sum([comp.monto_p for comp in complementos])
	total_documentos = len(complementos)

	return {
		"complementos": complementos,
		"resumen": {
			"total_documentos": total_documentos,
			"total_monto": total_monto,
			"periodo": f"{fecha_inicio} - {fecha_fin}",
		},
	}
