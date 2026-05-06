import json
from datetime import date, datetime

import frappe
from frappe import _
from frappe.utils import flt, now_datetime
from frappe.utils.file_manager import save_file

# ---------------------------------------------------------------------------
# Bloque 3B — Creación manual de Complemento Pago MX desde Payment Entry
# ---------------------------------------------------------------------------


@frappe.whitelist()
def crear_complemento_pago_desde_pe(payment_entry_name: str) -> dict:
	"""
	Crea Complemento Pago MX en borrador desde un Payment Entry PPD.

	Solo llena la cabecera básica. Los documentos_relacionados se llenan en Bloque 3C.

	Args:
		payment_entry_name: Nombre del Payment Entry (ej. ACC-PAY-2026-00001)

	Returns:
		dict con complemento_name y mensaje
	"""
	pe = frappe.get_doc("Payment Entry", payment_entry_name)

	# --- Validaciones previas ---
	if pe.docstatus != 1:
		frappe.throw(_("El Payment Entry debe estar enviado (docstatus=1)."))

	if pe.get("fm_complemento_pago"):
		frappe.throw(
			_("Este Payment Entry ya tiene un Complemento de Pago: {0}").format(pe.fm_complemento_pago)
		)

	if pe.payment_type != "Receive":
		frappe.throw(_("Solo se generan complementos para pagos de tipo Receive (cobro)."))

	# --- Verificar que exista al menos una SI PPD timbrada ---
	si_ppd = _obtener_si_ppd_validas(pe)
	if not si_ppd:
		frappe.throw(
			_(
				"No hay facturas PPD timbradas válidas referenciadas en este Payment Entry. "
				"Verificar que fm_es_ppd=1 y fm_fiscal_status=TIMBRADO."
			)
		)

	# --- Obtener forma de pago SAT desde mode_of_payment ---
	# ERPNext ya tiene mode_of_payment — tomamos los primeros 2 caracteres como código SAT
	if not pe.get("mode_of_payment"):
		frappe.throw(
			_(
				"El Payment Entry no tiene Forma de Pago configurada. "
				"Configure Mode of Payment antes de crear el complemento."
			)
		)
	forma_pago_sat = (pe.mode_of_payment or "")[:2].strip()

	# --- Crear complemento ---
	complemento = frappe.new_doc("Complemento Pago MX")
	complemento.payment_entry = pe.name
	complemento.company = pe.company
	complemento.customer = pe.party if pe.party_type == "Customer" else None
	complemento.complement_status = "Pendiente"

	complemento.fecha_pago = pe.posting_date
	complemento.forma_pago_p = forma_pago_sat
	complemento.monto_p = flt(pe.paid_amount)
	complemento.moneda_p = _get_currency(pe)

	if complemento.moneda_p != "MXN":
		complemento.tipo_cambio_p = flt(pe.get("source_exchange_rate") or 1.0)

	# num_operacion — referencia bancaria opcional
	if pe.get("reference_no"):
		complemento.num_operacion = pe.reference_no

	# --- Llenar documentos_relacionados ---
	_llenar_documentos_relacionados(complemento, pe)

	# --- Llenar detalles_impuestos ---
	_llenar_detalles_impuestos(complemento, pe)

	# ignore_mandatory: folio_fiscal se asigna tras el timbrado con el PAC.
	# No puede llenarse antes — es el UUID del CFDI timbrado.
	complemento.insert(ignore_permissions=True, ignore_mandatory=True)

	# --- Actualizar Payment Entry ---
	frappe.db.set_value(
		"Payment Entry",
		pe.name,
		{
			"fm_complemento_pago": complemento.name,
			"fm_require_complement": 1,
			"fm_complement_generated": 1,
		},
	)

	frappe.logger().info(f"Complemento {complemento.name} creado para PE {pe.name}")
	return {"complemento_name": complemento.name}


def _obtener_si_ppd_validas(pe) -> list:
	"""Retorna las SI PPD timbradas válidas referenciadas en el PE."""
	validas = []
	for ref in pe.get("references", []):
		if ref.reference_doctype != "Sales Invoice":
			continue
		if flt(ref.allocated_amount) <= 0:
			continue
		si = frappe.db.get_value(
			"Sales Invoice",
			ref.reference_name,
			["fm_es_ppd", "fm_fiscal_status", "fm_factura_fiscal_mx"],
			as_dict=True,
		)
		if not si:
			continue
		if si.fm_es_ppd == 1 and si.fm_fiscal_status == "TIMBRADO" and si.fm_factura_fiscal_mx:
			validas.append(ref.reference_name)
	return validas


def _get_currency(pe) -> str:
	"""Obtener moneda del pago."""
	return pe.get("paid_to_account_currency") or pe.get("paid_from_account_currency") or "MXN"


@frappe.whitelist()
def timbrar_complemento_pago(complemento_name: str) -> dict:
	"""
	Timbra un Complemento Pago MX con FacturAPI.

	Usa el payload confirmado en implementación legacy (facturacion_mx):
	  complements[0].type = "pago"
	  complements[0].data[0] = { payment_form, currency, exchange, date, related_documents }

	Args:
		complemento_name: Nombre del Complemento Pago MX

	Returns:
		dict con uuid, folio_fiscal y mensaje
	"""
	from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client

	comp = frappe.get_doc("Complemento Pago MX", complemento_name)

	# --- Validaciones previas ---
	if comp.complement_status not in ("Pendiente", "Error"):
		frappe.throw(
			_("El complemento ya fue timbrado o cancelado. Estado: {0}").format(comp.complement_status)
		)
	if comp.uuid_sat or comp.folio_fiscal:
		frappe.throw(_("El complemento ya tiene UUID/folio fiscal. No se puede timbrar de nuevo."))
	if not comp.payment_entry:
		frappe.throw(_("El complemento no está ligado a un Payment Entry."))
	if not comp.forma_pago_p:
		frappe.throw(_("Falta Forma de Pago SAT (forma_pago_p)."))
	if not comp.moneda_p:
		frappe.throw(_("Falta Moneda (moneda_p)."))
	if not comp.fecha_pago:
		frappe.throw(_("Falta Fecha de Pago (fecha_pago)."))
	if not flt(comp.monto_p) > 0:
		frappe.throw(_("El monto del pago debe ser mayor a cero."))
	if not comp.documentos_relacionados:
		frappe.throw(_("El complemento no tiene documentos relacionados. Ejecutar Bloque 3C primero."))
	for dr in comp.documentos_relacionados:
		if dr.objeto_imp_dr == "02" and not comp.detalles_impuestos:
			frappe.throw(
				_("Faltan detalles de impuestos para documento {0} con objeto_imp_dr=02.").format(
					dr.id_documento
				)
			)

	# --- Datos del cliente ---
	customer_data = _build_customer_data(comp.customer, comp.company)

	# --- Construir related_documents ---
	related_docs = []
	for dr in comp.documentos_relacionados:
		taxes_payload = []
		for det in comp.detalles_impuestos:
			if det.documento_relacionado != dr.id_documento:
				continue
			taxes_payload.append(
				{
					"base": round(flt(det.base_dr), 6),
					"type": _impuesto_sat_to_facturapi(det.impuesto),
					"rate": round(flt(det.tasa_cuota), 6),
					"factor": det.tipo_factor,
					"withholding": det.tipo_impuesto == "Retencion",
				}
			)

		related_doc = {
			"uuid": dr.id_documento,
			"folio_number": str(dr.folio) if dr.folio else "",
			"amount": round(flt(dr.imp_pagado), 2),
			"last_balance": round(flt(dr.imp_saldo_ant), 2),
			"installment": int(dr.num_parcialidad),
			"taxability": dr.objeto_imp_dr,
		}
		if taxes_payload:
			related_doc["taxes"] = taxes_payload
		related_docs.append(related_doc)

	# --- Payload FacturAPI ---
	payload = {
		"type": "P",
		"customer": customer_data,
		"complements": [
			{
				"type": "pago",
				"data": [
					{
						"payment_form": str(comp.forma_pago_p),
						"currency": str(comp.moneda_p),
						"exchange": round(flt(comp.tipo_cambio_p or 1), 6),
						"date": str(comp.fecha_pago),
						"related_documents": related_docs,
					}
				],
			}
		],
	}

	frappe.logger().info(f"Complemento {complemento_name} — payload: {json.dumps(payload, default=str)}")

	# --- Llamar FacturAPI ---
	client = get_facturapi_client()
	request_ts = now_datetime()
	success = False
	response_data = {}
	error_msg = ""

	try:
		raw = client.create_invoice(payload)
		# _make_request devuelve {'success': bool, 'status_code': int, 'raw_response': dict}
		if isinstance(raw, dict) and not raw.get("success", True):
			raise Exception(raw.get("error") or "Error desconocido en FacturAPI")
		response_data = raw.get("raw_response", raw) if isinstance(raw, dict) else raw
		success = True
	except Exception as e:
		error_msg = str(e)
		frappe.log_error(
			f"Error timbrado complemento {complemento_name}: {error_msg}", "Timbrado Complemento"
		)

	# --- Crear Response Log ---
	_crear_response_log_complemento(
		complemento_name=complemento_name,
		payload=payload,
		response=response_data,
		success=success,
		error_msg=error_msg,
		request_ts=request_ts,
	)

	if not success:
		frappe.db.set_value("Complemento Pago MX", complemento_name, "complement_status", "Error")
		frappe.throw(_("Error al timbrar: {0}").format(error_msg))

	# --- Guardar resultado ---
	uuid = response_data.get("uuid") or (response_data.get("stamp") or {}).get("uuid", "")
	folio = str(response_data.get("folio_number", ""))
	serie = response_data.get("series", "")
	facturapi_id = response_data.get("id", "")

	frappe.db.set_value(
		"Complemento Pago MX",
		complemento_name,
		{
			"uuid_sat": uuid,
			"folio_fiscal": uuid,  # folio_fiscal = UUID por convención del DocType
			"serie_folio": f"{serie}-{folio}" if serie and folio else folio,
			"facturapi_id": facturapi_id,
			"fecha_timbrado": now_datetime(),
			"estatus_sat": "Vigente",
			"complement_status": "Timbrado",
		},
	)

	frappe.get_doc("Complemento Pago MX", complemento_name).submit()

	frappe.logger().info(f"Complemento {complemento_name} timbrado. UUID: {uuid}")
	return {"uuid": uuid, "folio_fiscal": uuid, "serie_folio": f"{serie}-{folio}"}


@frappe.whitelist()
def cancelar_complemento_pago(complemento_name: str, motivo: str = "02") -> dict:
	"""
	Cancela un Complemento Pago MX timbrado con FacturAPI.

	Args:
		complemento_name: Nombre del Complemento Pago MX
		motivo: Código motivo SAT ("02" por default)

	Returns:
		dict con nuevo complement_status y mensaje
	"""
	from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client

	comp = frappe.get_doc("Complemento Pago MX", complemento_name)

	if comp.complement_status != "Timbrado":
		frappe.throw(
			_("Solo se pueden cancelar complementos en estado Timbrado. Estado actual: {0}").format(
				comp.complement_status
			)
		)
	if not comp.uuid_sat:
		frappe.throw(_("El complemento no tiene UUID SAT. No se puede cancelar."))
	if not comp.facturapi_id:
		frappe.throw(_("El complemento no tiene ID de FacturAPI. No se puede cancelar automáticamente."))

	client = get_facturapi_client()
	request_ts = now_datetime()
	success = False
	response_data = {}
	error_msg = ""

	try:
		raw = client.cancel_invoice(comp.facturapi_id, motivo)
		if isinstance(raw, dict) and not raw.get("success", True):
			raise Exception(raw.get("error") or "Error desconocido en FacturAPI")
		response_data = raw.get("raw_response", raw) if isinstance(raw, dict) else raw
		success = True
	except Exception as e:
		error_msg = str(e)
		frappe.log_error(
			f"Error cancelación complemento {complemento_name}: {error_msg}", "Cancelación Complemento"
		)

	# --- Crear Response Log ---
	try:
		log = frappe.new_doc("FacturAPI Response Log")
		log.operation_type = "Cancelación Complemento Pago"
		log.complemento_pago_mx = complemento_name
		log.request_id = f"CANCEL-{complemento_name}"
		log.request_timestamp = request_ts
		log.request_payload = json.dumps(
			{"invoice_id": comp.facturapi_id, "motive": motivo}, ensure_ascii=False
		)
		log.success = 1 if success else 0
		log.facturapi_response = (
			json.dumps(response_data, default=str, ensure_ascii=False) if response_data else ""
		)
		if not success:
			log.error_message = error_msg
		log.insert(ignore_permissions=True)
	except Exception as le:
		frappe.log_error(
			f"Error creando response log cancelación: {le}", "Response Log Cancelación Complemento"
		)

	if not success:
		frappe.db.set_value("Complemento Pago MX", complemento_name, "complement_status", "Error")
		frappe.throw(_("Error al cancelar: {0}").format(error_msg))

	# --- Interpretar respuesta PAC ---
	status_facturapi = response_data.get("status", "")
	cancellation_status = response_data.get("cancellation_status", "")

	if status_facturapi == "canceled" or cancellation_status == "accepted":
		nuevo_status = "Cancelado"
		nuevo_estatus_sat = "Cancelado"
	elif cancellation_status == "pending":
		nuevo_status = "Pendiente Cancelación"
		nuevo_estatus_sat = "Pendiente Cancelación"
	elif cancellation_status == "rejected":
		nuevo_status = "Timbrado"  # PAC rechazó — mantener timbrado
		nuevo_estatus_sat = "Vigente"
	else:
		nuevo_status = "Pendiente Cancelación"  # fallback conservador
		nuevo_estatus_sat = "Pendiente Cancelación"

	frappe.db.set_value(
		"Complemento Pago MX",
		complemento_name,
		{
			"complement_status": nuevo_status,
			"estatus_sat": nuevo_estatus_sat,
		},
	)

	frappe.logger().info(f"Complemento {complemento_name} cancelado. Status: {nuevo_status}")
	return {"complement_status": nuevo_status, "cancellation_status": cancellation_status}


def _build_customer_data(customer_name: str, company: str) -> dict:
	"""Construye customer payload para FacturAPI desde Customer DocType."""
	if not customer_name:
		frappe.throw(_("El complemento no tiene cliente configurado."))

	customer = frappe.get_doc("Customer", customer_name)

	if not customer.tax_id:
		frappe.throw(_("El cliente {0} no tiene RFC configurado (tax_id).").format(customer_name))

	# Tax system desde fm_tax_regime (campo custom SAT) o tax_category como fallback
	tax_system = None
	fm_tax_regime = customer.get("fm_tax_regime") or ""
	if fm_tax_regime:
		# fm_tax_regime formato: "601 - General de Ley Personas Morales" → tomar código
		tax_system = fm_tax_regime.split(" - ")[0].strip()
	if not tax_system and customer.tax_category:
		tax_system = str(customer.tax_category)
	if not tax_system:
		frappe.throw(
			_("El cliente {0} no tiene régimen fiscal SAT configurado (fm_tax_regime).").format(customer_name)
		)

	# Email
	email = customer.email_id or ""
	if not email:
		contacts = frappe.get_all(
			"Contact",
			filters={"link_doctype": "Customer", "link_name": customer_name},
			fields=["email_id"],
			limit=1,
		)
		email = contacts[0].email_id if contacts else ""

	# Dirección principal — código postal obligatorio
	addresses = frappe.get_all(
		"Address",
		filters={"link_doctype": "Customer", "link_name": customer_name, "is_primary_address": 1},
		fields=["pincode", "city", "state", "country"],
		limit=1,
	)
	if not addresses or not addresses[0].pincode:
		frappe.throw(
			_("El cliente {0} no tiene dirección principal con código postal.").format(customer_name)
		)

	addr = addresses[0]
	return {
		"legal_name": customer.customer_name,
		"tax_id": customer.tax_id,
		"tax_system": tax_system,
		"email": email,
		"address": {"zip": addr.pincode},
	}


def _impuesto_sat_to_facturapi(impuesto_sat_code: str) -> str:
	"""Convierte código Impuesto SAT (001/002/003) al tipo FacturAPI (ISR/IVA/IEPS)."""
	mapping = {"001": "ISR", "002": "IVA", "003": "IEPS"}
	return mapping.get(str(impuesto_sat_code), str(impuesto_sat_code))


def _crear_response_log_complemento(
	complemento_name: str,
	payload: dict,
	response: dict,
	success: bool,
	error_msg: str,
	request_ts,
):
	"""Crea FacturAPI Response Log para operación de complemento."""
	try:
		log = frappe.new_doc("FacturAPI Response Log")
		log.operation_type = "Timbrado Complemento Pago"
		log.complemento_pago_mx = complemento_name
		log.request_id = f"COMP-{complemento_name}"
		log.request_timestamp = request_ts
		log.request_payload = json.dumps(payload, default=str, ensure_ascii=False)
		log.success = 1 if success else 0
		log.facturapi_response = json.dumps(response, default=str, ensure_ascii=False) if response else ""
		if not success:
			log.error_message = error_msg
		log.insert(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(f"Error creando response log de complemento: {e}", "Response Log Complemento")


def _llenar_documentos_relacionados(complemento, pe):
	"""
	Agrega una fila en documentos_relacionados por cada SI PPD válida
	referenciada en el Payment Entry.

	Calcula:
	  imp_saldo_ant   = grand_total - pagos previos (excluye este PE)
	  imp_pagado      = allocated_amount del PE actual
	  imp_saldo_insoluto = imp_saldo_ant - imp_pagado
	  num_parcialidad = count(pagos previos) + 1
	"""
	for ref in pe.get("references", []):
		if ref.reference_doctype != "Sales Invoice":
			continue
		if flt(ref.allocated_amount) <= 0:
			continue

		si = frappe.db.get_value(
			"Sales Invoice",
			ref.reference_name,
			[
				"fm_es_ppd",
				"fm_fiscal_status",
				"fm_factura_fiscal_mx",
				"currency",
				"conversion_rate",
				"grand_total",
				"outstanding_amount",
			],
			as_dict=True,
		)
		if not si:
			continue
		if si.fm_es_ppd != 1 or si.fm_fiscal_status != "TIMBRADO":
			continue

		if not si.fm_factura_fiscal_mx:
			frappe.throw(
				_("La factura {0} no tiene Factura Fiscal Mexico vinculada.").format(ref.reference_name)
			)

		# UUID y serie/folio desde la FFM
		ffm = frappe.db.get_value(
			"Factura Fiscal Mexico",
			si.fm_factura_fiscal_mx,
			["fm_uuid", "serie", "folio", "fm_serie_folio"],
			as_dict=True,
		)
		if not ffm or not ffm.fm_uuid:
			frappe.throw(
				_("La Factura Fiscal Mexico {0} no tiene UUID. No se puede generar el complemento.").format(
					si.fm_factura_fiscal_mx
				)
			)

		# imp_saldo_ant: saldo antes del pago
		# ERPNext guarda en per.outstanding_amount el saldo DESPUÉS del pago,
		# así que: saldo_antes = allocated + outstanding
		imp_pagado = round(flt(ref.allocated_amount), 2)
		imp_saldo_insoluto = round(max(flt(ref.outstanding_amount), 0), 2)
		imp_saldo_ant = round(imp_pagado + imp_saldo_insoluto, 2)

		# num_parcialidad: posición de este PE en la lista de PEs de la SI
		pes_de_la_si = frappe.db.sql(
			"""
			SELECT DISTINCT per.parent
			FROM `tabPayment Entry Reference` per
			JOIN `tabPayment Entry` pe ON pe.name = per.parent
			WHERE per.reference_name = %s
			  AND per.reference_doctype = 'Sales Invoice'
			  AND pe.docstatus = 1
			ORDER BY pe.posting_date ASC, pe.name ASC
			""",
			(ref.reference_name,),
			pluck="parent",
		)
		try:
			num_parcialidad = pes_de_la_si.index(pe.name) + 1
		except ValueError:
			num_parcialidad = len(pes_de_la_si) + 1

		# Objeto de impuesto: 02 si la SI tiene taxes, 01 si no
		tiene_taxes = frappe.db.count(
			"Sales Taxes and Charges",
			{"parent": ref.reference_name, "tax_amount": [">", 0]},
		)
		objeto_imp = "02" if tiene_taxes else "01"

		# Serie y folio por separado si están disponibles
		serie = ffm.serie or (
			ffm.fm_serie_folio.split("-")[0] if ffm.fm_serie_folio and "-" in ffm.fm_serie_folio else ""
		)
		folio = (
			str(ffm.folio)
			if ffm.folio
			else (
				ffm.fm_serie_folio.split("-")[-1] if ffm.fm_serie_folio and "-" in ffm.fm_serie_folio else ""
			)
		)

		complemento.append(
			"documentos_relacionados",
			{
				"id_documento": ffm.fm_uuid,
				"serie": serie,
				"folio": folio,
				"moneda_dr": si.currency or "MXN",
				"equivalencia_dr": flt(si.conversion_rate) if si.currency != "MXN" else 1.0,
				"num_parcialidad": num_parcialidad,
				"imp_saldo_ant": imp_saldo_ant,
				"imp_pagado": imp_pagado,
				"imp_saldo_insoluto": imp_saldo_insoluto,
				"objeto_imp_dr": objeto_imp,
				"tipo_documento": "Sales Invoice",
				"referencia_documento": ref.reference_name,
			},
		)


def _llenar_detalles_impuestos(complemento, pe):
	"""
	Llena detalles_impuestos con los traslados reales de cada SI PPD.

	Por cada SI válida:
	  - Lee sus tax rows
	  - Calcula los montos proporcionales al imp_pagado
	  - Agrega una fila en detalles_impuestos por impuesto (IVA, IEPS)

	Campos:
	  tipo_impuesto = Traslado | Retencion
	  impuesto      = Link → Impuesto SAT (001=ISR, 002=IVA, 003=IEPS)
	  tipo_factor   = Tasa | Cuota | Exento
	  tasa_cuota    = decimal SAT (0.16 para IVA 16%)
	  base_dr       = base proporcional
	  importe_dr    = impuesto proporcional
	  documento_relacionado = UUID de la FFM (id_documento del doc relacionado)
	"""
	for ref in pe.get("references", []):
		if ref.reference_doctype != "Sales Invoice":
			continue
		if flt(ref.allocated_amount) <= 0:
			continue

		si = frappe.db.get_value(
			"Sales Invoice",
			ref.reference_name,
			["fm_es_ppd", "fm_fiscal_status", "fm_factura_fiscal_mx", "grand_total"],
			as_dict=True,
		)
		if not si or si.fm_es_ppd != 1 or si.fm_fiscal_status != "TIMBRADO":
			continue
		if not si.fm_factura_fiscal_mx:
			continue

		uuid = frappe.db.get_value("Factura Fiscal Mexico", si.fm_factura_fiscal_mx, "fm_uuid")
		if not uuid:
			continue

		grand_total = flt(si.grand_total)
		proporcion = flt(ref.allocated_amount) / grand_total if grand_total else 0

		# Leer impuestos reales de la SI
		taxes = frappe.db.get_all(
			"Sales Taxes and Charges",
			filters={"parent": ref.reference_name},
			fields=["account_head", "rate", "tax_amount", "base_tax_amount"],
		)

		for tax in taxes:
			if flt(tax.tax_amount) == 0:
				continue

			impuesto_sat = _get_impuesto_sat(tax.account_head, pe.company)
			if not impuesto_sat:
				continue  # cuenta no mapeada a catálogo SAT — omitir silenciosamente

			tipo_impuesto, impuesto_code, tipo_factor = impuesto_sat

			tasa = flt(tax.rate)
			importe_prop = round(flt(tax.tax_amount) * proporcion, 2)
			# base = importe / tasa (si tasa > 0) o base_tax_amount proporcional
			if tasa > 0:
				base_prop = round(importe_prop / (tasa / 100), 2)
			else:
				base_prop = round(flt(tax.base_tax_amount) * proporcion, 2)

			complemento.append(
				"detalles_impuestos",
				{
					"tipo_impuesto": tipo_impuesto,
					"impuesto": impuesto_code,
					"tipo_factor": tipo_factor,
					"tasa_cuota": round(tasa / 100, 6),  # formato SAT: 0.16 no 16
					"base_dr": base_prop,
					"importe_dr": importe_prop,
					"documento_relacionado": uuid,
				},
			)


def _get_impuesto_sat(account_head: str, company: str):
	"""
	Mapea account_head → (tipo_impuesto, impuesto_sat_code, tipo_factor).

	Estrategia:
	1. Buscar en Configuracion Fiscal Mexico mapeo_cuentas → rol_fiscal
	2. Derivar tipo de impuesto desde el rol_fiscal
	3. Fallback: nombre de cuenta
	"""
	# Buscar rol_fiscal en Configuracion Fiscal Mexico
	cfg_name = frappe.db.get_value("Configuracion Fiscal Mexico", {"company": company}, "name")
	rol_fiscal = None
	if cfg_name:
		rol_fiscal = frappe.db.get_value(
			"Mapeo Cuenta Fiscal Mexico",
			{"parent": cfg_name, "cuenta_impuesto": account_head},
			"rol_fiscal",
		)

	# Si no hay mapeo en CFM, intentar por nombre de cuenta
	fuente = (rol_fiscal or account_head or "").upper()

	if "IVA" in fuente and "RETEN" not in fuente:
		return ("Traslado", "002", "Tasa")
	if "IEPS" in fuente:
		return ("Traslado", "003", "Tasa")
	if "ISR" in fuente or "RETEN" in fuente:
		return ("Retencion", "001", "Tasa")

	return None  # cuenta no reconocida


# ---------------------------------------------------------------------------
# Funciones legacy previas al Bloque 3B
# ---------------------------------------------------------------------------


def process_pending_complements():
	"""Procesar complementos de pago pendientes - scheduled task."""
	try:
		frappe.logger().info("Ejecutando proceso de complementos pendientes...")
		# TODO: Implementar lógica real cuando esté disponible
		return {"status": "success", "message": "Proceso completado (placeholder)"}
	except Exception as e:
		frappe.log_error(f"Error procesando complementos pendientes: {e}")
		return {"status": "error", "message": str(e)}


def reconcile_payment_tracking():
	"""Reconciliar seguimiento de pagos - scheduled task."""
	try:
		frappe.logger().info("Ejecutando reconciliación de seguimiento de pagos...")
		# TODO: Implementar lógica real cuando esté disponible
		return {"status": "success", "message": "Reconciliación completada (placeholder)"}
	except Exception as e:
		frappe.log_error(f"Error en reconciliación de pagos: {e}")
		return {"status": "error", "message": str(e)}


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
