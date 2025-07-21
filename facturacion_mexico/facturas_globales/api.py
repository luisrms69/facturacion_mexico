"""
Facturas Globales API - Sprint 4 Semana 1
APIs principales para el sistema de facturas globales
"""

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_datetime, getdate

from facturacion_mexico.utils.error_handling import handle_api_error


@frappe.whitelist()
def get_available_ereceipts(periodo_inicio, periodo_fin, company=None):
	"""Obtener E-Receipts disponibles para factura global."""
	try:
		if not periodo_inicio or not periodo_fin:
			return {"success": False, "message": _("Período inicio y fin son requeridos"), "data": []}

		if not company:
			company = frappe.defaults.get_user_default("Company")
			if not company:
				return {"success": False, "message": _("Company es requerido"), "data": []}

		# Validar fechas
		if getdate(periodo_inicio) > getdate(periodo_fin):
			return {
				"success": False,
				"message": _("Fecha inicio no puede ser posterior a fecha fin"),
				"data": [],
			}

		# Obtener receipts disponibles
		receipts = frappe.db.sql(
			"""
			SELECT
				er.name as ereceipt,
				er.folio,
				er.receipt_date as fecha_receipt,
				er.total_amount as monto,
				er.tax_amount,
				er.customer_name,
				er.currency,
				er.status,
				1 as available_for_global,
				CASE
					WHEN er.included_in_global = 1 THEN 0
					ELSE 1
				END as selectable
			FROM `tabEReceipt MX` er
			WHERE er.company = %(company)s
			AND er.receipt_date BETWEEN %(periodo_inicio)s AND %(periodo_fin)s
			AND er.docstatus = 1
			AND (er.included_in_global IS NULL OR er.included_in_global = 0)
			AND (er.available_for_global IS NULL OR er.available_for_global = 1)
			ORDER BY er.receipt_date, er.folio
		""",
			{"company": company, "periodo_inicio": periodo_inicio, "periodo_fin": periodo_fin},
			as_dict=True,
		)

		# Calcular totales
		total_amount = sum(
			flt(r.get("monto") if isinstance(r, dict) else r.monto)
			for r in receipts
			if (r.get("selectable") if isinstance(r, dict) else r.selectable)
		)
		total_tax = sum(
			flt(r.get("tax_amount") if isinstance(r, dict) else r.tax_amount)
			for r in receipts
			if (r.get("selectable") if isinstance(r, dict) else r.selectable)
		)

		# Agrupar por día para estadísticas
		daily_summary = {}
		for receipt in receipts:
			selectable = receipt.get("selectable") if isinstance(receipt, dict) else receipt.selectable
			if not selectable:
				continue

			fecha_receipt = (
				receipt.get("fecha_receipt") if isinstance(receipt, dict) else receipt.fecha_receipt
			)
			if hasattr(fecha_receipt, "strftime"):
				day = fecha_receipt.strftime("%Y-%m-%d")
			else:
				day = getdate(fecha_receipt).strftime("%Y-%m-%d")

			if day not in daily_summary:
				daily_summary[day] = {"count": 0, "amount": 0}

			daily_summary[day]["count"] += 1
			monto = receipt.get("monto") if isinstance(receipt, dict) else receipt.monto
			daily_summary[day]["amount"] += flt(monto)

		return {
			"success": True,
			"data": receipts,
			"summary": {
				"total_receipts": len(
					[r for r in receipts if (r.get("selectable") if isinstance(r, dict) else r.selectable)]
				),
				"total_amount": total_amount,
				"total_tax": total_tax,
				"daily_breakdown": daily_summary,
				"period": {"inicio": periodo_inicio, "fin": periodo_fin, "company": company},
			},
		}

	except Exception as e:
		frappe.log_error(f"Error obteniendo E-Receipts disponibles: {e}")
		return handle_api_error(e, "Error obteniendo E-Receipts disponibles")


@frappe.whitelist()
def create_global_invoice(periodo_inicio, periodo_fin, periodicidad, company=None, ereceipt_list=None):
	"""Crear factura global con receipts seleccionados."""
	try:
		if not all([periodo_inicio, periodo_fin, periodicidad]):
			return {"success": False, "message": _("Período inicio, fin y periodicidad son requeridos")}

		if not company:
			company = frappe.defaults.get_user_default("Company")

		# Crear documento de factura global
		global_invoice = frappe.get_doc(
			{
				"doctype": "Factura Global MX",
				"company": company,
				"periodo_inicio": periodo_inicio,
				"periodo_fin": periodo_fin,
				"periodicidad": periodicidad,
				"status": "Draft",
			}
		)

		# Agregar receipts seleccionados o todos los disponibles
		if ereceipt_list:
			# Lista específica de receipts
			if isinstance(ereceipt_list, str):
				import json

				ereceipt_list = json.loads(ereceipt_list)

			for ereceipt_name in ereceipt_list:
				if frappe.db.exists("EReceipt MX", ereceipt_name):
					from facturacion_mexico.facturas_globales.doctype.factura_global_detail.factura_global_detail import (
						FacturaGlobalDetail,
					)

					detail_data = FacturaGlobalDetail.create_from_receipt(ereceipt_name)
					global_invoice.append("receipts_detail", detail_data)
		else:
			# Todos los receipts disponibles del período
			available_result = get_available_ereceipts(periodo_inicio, periodo_fin, company)
			if available_result["success"]:
				for receipt in available_result["data"]:
					if receipt.get("selectable"):
						global_invoice.append(
							"receipts_detail",
							{
								"ereceipt": receipt["ereceipt"],
								"folio_receipt": receipt["folio"],
								"fecha_receipt": receipt["fecha_receipt"],
								"monto": receipt["monto"],
								"customer_name": receipt["customer_name"],
								"included_in_cfdi": 1,
							},
						)

		# Validar que hay receipts
		if not global_invoice.receipts_detail:
			return {
				"success": False,
				"message": _("No hay E-Receipts disponibles para el período seleccionado"),
			}

		# Guardar documento
		global_invoice.insert()

		return {
			"success": True,
			"message": _("Factura global creada exitosamente"),
			"name": global_invoice.name,
			"data": {
				"total_receipts": len(global_invoice.receipts_detail),
				"total_amount": global_invoice.total_periodo,
				"status": global_invoice.status,
			},
		}

	except Exception as e:
		frappe.log_error(f"Error creando factura global: {e}")
		return handle_api_error(e, "Error creando factura global")


@frappe.whitelist()
def preview_global_invoice(periodo_inicio, periodo_fin, company=None):
	"""Preview de factura global sin crear."""
	try:
		# Obtener receipts disponibles
		receipts_result = get_available_ereceipts(periodo_inicio, periodo_fin, company)

		if not receipts_result["success"]:
			return receipts_result

		receipts = receipts_result["data"]
		selectable_receipts = [r for r in receipts if r.get("selectable")]

		if not selectable_receipts:
			return {
				"success": True,
				"preview": {
					"receipts": [],
					"totals": {"count": 0, "amount": 0, "tax": 0},
					"warnings": ["No hay E-Receipts disponibles en el período"],
				},
			}

		# Calcular totales
		total_amount = sum(flt(r.monto) for r in selectable_receipts)
		total_tax = sum(flt(r.tax_amount) for r in selectable_receipts)

		# Validaciones
		warnings = []

		# Verificar continuidad de folios si aplica
		folios = [r.folio for r in selectable_receipts if r.folio]
		if folios and len(set(folios)) != len(folios):
			warnings.append("Existen folios duplicados")

		# Verificar montos mínimos
		if total_amount < 100:
			warnings.append("El monto total es muy bajo (< $100)")

		return {
			"success": True,
			"preview": {
				"receipts": selectable_receipts[:20],  # Primeros 20 para preview
				"totals": {
					"count": len(selectable_receipts),
					"amount": total_amount,
					"tax": total_tax,
					"currency": "MXN",
				},
				"period": {
					"inicio": periodo_inicio,
					"fin": periodo_fin,
					"days": (getdate(periodo_fin) - getdate(periodo_inicio)).days + 1,
				},
				"warnings": warnings,
				"daily_summary": receipts_result["summary"]["daily_breakdown"],
			},
		}

	except Exception as e:
		frappe.log_error(f"Error en preview de factura global: {e}")
		return handle_api_error(e, "Error generando preview")


@frappe.whitelist()
def generate_global_cfdi(factura_global_name):
	"""Generar CFDI en FacturAPI.io."""
	try:
		if not factura_global_name:
			return {"success": False, "message": _("Nombre de factura global es requerido")}

		if not frappe.db.exists("Factura Global MX", factura_global_name):
			return {"success": False, "message": _("Factura global no encontrada")}

		# Obtener documento
		global_doc = frappe.get_doc("Factura Global MX", factura_global_name)

		# Validar estado
		if global_doc.docstatus != 0:
			return {"success": False, "message": _("Solo se pueden timbrar facturas en estado Draft")}

		if global_doc.status == "Stamped":
			return {"success": False, "message": _("La factura ya está timbrada")}

		# Enviar documento (esto activará el método generate_global_cfdi)
		global_doc.submit()

		return {
			"success": True,
			"message": _("CFDI global generado exitosamente"),
			"data": {
				"uuid": global_doc.uuid,
				"folio": global_doc.folio,
				"facturapi_id": global_doc.facturapi_id,
				"status": global_doc.status,
				"processing_time": global_doc.processing_time,
				"pdf_url": global_doc.pdf_file,
				"xml_url": global_doc.xml_file,
			},
		}

	except Exception as e:
		frappe.log_error(f"Error generando CFDI global: {e}")
		return handle_api_error(e, "Error generando CFDI global")


@frappe.whitelist()
def get_global_invoice_stats(year=None, month=None, company=None):
	"""Estadísticas de facturas globales."""
	try:
		if not company:
			company = frappe.defaults.get_user_default("Company")

		# Filtros base
		filters = {"company": company, "docstatus": 1}

		if year:
			filters["YEAR(periodo_inicio)"] = year
		if month:
			filters["MONTH(periodo_inicio)"] = month

		# Obtener estadísticas
		stats = frappe.db.sql(
			"""
			SELECT
				COUNT(*) as total_facturas,
				SUM(total_periodo) as total_facturado,
				SUM(cantidad_receipts) as total_receipts,
				AVG(processing_time) as avg_processing_time,
				MIN(periodo_inicio) as primer_periodo,
				MAX(periodo_fin) as ultimo_periodo,
				COUNT(CASE WHEN status = 'Stamped' THEN 1 END) as facturas_timbradas,
				COUNT(CASE WHEN status = 'Error' THEN 1 END) as facturas_error
			FROM `tabFactura Global MX`
			WHERE company = %(company)s
			AND docstatus = 1
			{year_filter}
			{month_filter}
		""".format(
				year_filter="AND YEAR(periodo_inicio) = %(year)s" if year else "",
				month_filter="AND MONTH(periodo_inicio) = %(month)s" if month else "",
			),
			{"company": company, "year": year, "month": month},
			as_dict=True,
		)

		base_stats = stats[0] if stats else {}

		# Estadísticas por periodicidad
		periodicidad_stats = frappe.db.sql(
			"""
			SELECT
				periodicidad,
				COUNT(*) as count,
				SUM(total_periodo) as total_amount,
				AVG(cantidad_receipts) as avg_receipts
			FROM `tabFactura Global MX`
			WHERE company = %(company)s
			AND docstatus = 1
			{year_filter}
			{month_filter}
			GROUP BY periodicidad
		""".format(
				year_filter="AND YEAR(periodo_inicio) = %(year)s" if year else "",
				month_filter="AND MONTH(periodo_inicio) = %(month)s" if month else "",
			),
			{"company": company, "year": year, "month": month},
			as_dict=True,
		)

		# Tendencia mensual
		monthly_trend = frappe.db.sql(
			"""
			SELECT
				YEAR(periodo_inicio) as year,
				MONTH(periodo_inicio) as month,
				COUNT(*) as facturas,
				SUM(total_periodo) as total_amount,
				SUM(cantidad_receipts) as total_receipts
			FROM `tabFactura Global MX`
			WHERE company = %(company)s
			AND docstatus = 1
			AND periodo_inicio >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
			GROUP BY YEAR(periodo_inicio), MONTH(periodo_inicio)
			ORDER BY year, month
		""",
			{"company": company},
			as_dict=True,
		)

		return {
			"success": True,
			"data": {
				"general": base_stats,
				"por_periodicidad": periodicidad_stats,
				"tendencia_mensual": monthly_trend,
				"filtros_aplicados": {"company": company, "year": year, "month": month},
			},
		}

	except Exception as e:
		frappe.log_error(f"Error obteniendo estadísticas de facturas globales: {e}")
		return handle_api_error(e, "Error obteniendo estadísticas")


@frappe.whitelist()
def cancel_global_invoice(factura_global_name, reason="Cancelación manual"):
	"""Cancelar factura global."""
	try:
		if not frappe.db.exists("Factura Global MX", factura_global_name):
			return {"success": False, "message": _("Factura global no encontrada")}

		global_doc = frappe.get_doc("Factura Global MX", factura_global_name)

		if global_doc.docstatus != 1:
			return {"success": False, "message": _("Solo se pueden cancelar facturas enviadas")}

		# Cancelar documento
		global_doc.cancel()

		return {
			"success": True,
			"message": _("Factura global cancelada exitosamente"),
			"data": {
				"name": factura_global_name,
				"status": "Cancelled",
				"receipts_released": len(global_doc.receipts_detail),
			},
		}

	except Exception as e:
		frappe.log_error(f"Error cancelando factura global: {e}")
		return handle_api_error(e, "Error cancelando factura global")


@frappe.whitelist()
def get_suggested_periods(company=None, periodicidad="Mensual"):
	"""Obtener períodos sugeridos para facturas globales."""
	try:
		if not company:
			company = frappe.defaults.get_user_default("Company")

		from frappe.utils import add_months, get_first_day, get_last_day, today

		periods = []
		current_date = getdate(today())

		# Generar períodos según periodicidad
		if periodicidad == "Mensual":
			for i in range(3):  # Últimos 3 meses
				month_start = add_months(get_first_day(current_date), -i)
				month_end = get_last_day(month_start)

				# Verificar si ya existe factura global para este período
				existing = frappe.db.exists(
					"Factura Global MX",
					{
						"company": company,
						"periodo_inicio": month_start,
						"periodo_fin": month_end,
						"docstatus": ["!=", 2],
					},
				)

				periods.append(
					{
						"periodo_inicio": month_start,
						"periodo_fin": month_end,
						"description": month_start.strftime("%B %Y"),
						"has_existing": bool(existing),
						"existing_invoice": existing,
					}
				)

		elif periodicidad == "Semanal":
			# Últimas 4 semanas
			for i in range(4):
				week_start = add_days(current_date, -(current_date.weekday() + 7 * i))
				week_end = add_days(week_start, 6)

				existing = frappe.db.exists(
					"Factura Global MX",
					{
						"company": company,
						"periodo_inicio": week_start,
						"periodo_fin": week_end,
						"docstatus": ["!=", 2],
					},
				)

				periods.append(
					{
						"periodo_inicio": week_start,
						"periodo_fin": week_end,
						"description": f"Semana del {week_start.strftime('%d/%m')} al {week_end.strftime('%d/%m/%Y')}",
						"has_existing": bool(existing),
						"existing_invoice": existing,
					}
				)

		return {"success": True, "data": periods, "periodicidad": periodicidad, "company": company}

	except Exception as e:
		frappe.log_error(f"Error obteniendo períodos sugeridos: {e}")
		return handle_api_error(e, "Error obteniendo períodos sugeridos")
