# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import date, datetime, timedelta

import frappe
from frappe import _


def execute(filters=None):
	"""
	Reporte de Auditoría Fiscal
	Timeline de eventos fiscales y cumplimiento regulatorio
	"""
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	"""Definir columnas del reporte"""
	return [
		{"label": _("Fecha Evento"), "fieldname": "event_date", "fieldtype": "Date", "width": 120},
		{"label": _("Tipo Documento"), "fieldname": "document_type", "fieldtype": "Data", "width": 140},
		{
			"label": _("Documento"),
			"fieldname": "document_name",
			"fieldtype": "Dynamic Link",
			"options": "document_type",
			"width": 140,
		},
		{"label": _("Evento"), "fieldname": "event_type", "fieldtype": "Data", "width": 150},
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": _("UUID SAT"), "fieldname": "uuid_sat", "fieldtype": "Data", "width": 160},
		{"label": _("Monto"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Cliente/Proveedor"), "fieldname": "party", "fieldtype": "Data", "width": 180},
		{"label": _("Cumplimiento"), "fieldname": "compliance_status", "fieldtype": "Data", "width": 120},
		{"label": _("Observaciones"), "fieldname": "observations", "fieldtype": "Text", "width": 250},
	]


def get_data(filters):
	"""Obtener datos del reporte"""
	if not filters:
		filters = {}

	# Obtener eventos fiscales de diferentes fuentes
	audit_events = []

	# 1. Eventos de Facturación
	invoice_events = get_invoice_events(filters)
	audit_events.extend(invoice_events)

	# 2. Eventos de Complementos PPD
	ppd_events = get_ppd_events(filters)
	audit_events.extend(ppd_events)

	# 3. Eventos de E-Receipts
	ereceipt_events = get_ereceipt_events(filters)
	audit_events.extend(ereceipt_events)

	# 4. Eventos de Facturas Globales
	global_invoice_events = get_global_invoice_events(filters)
	audit_events.extend(global_invoice_events)

	# 5. Eventos de Validación (Motor de Reglas)
	validation_events = get_validation_events(filters)
	audit_events.extend(validation_events)

	# Ordenar por fecha descendente
	audit_events.sort(key=lambda x: x["event_date"], reverse=True)

	return audit_events


def get_invoice_events(filters):
	"""Obtener eventos de facturación"""
	where_conditions = get_where_conditions_base(filters)

	query = f"""
        SELECT
            si.posting_date as event_date,
            'Sales Invoice' as document_type,
            si.name as document_name,
            CASE
                WHEN si.fm_cfdi_uuid IS NOT NULL THEN 'Timbrado'
                WHEN si.fm_timbrado_status = 'Error' THEN 'Error Timbrado'
                ELSE 'Facturación'
            END as event_type,
            COALESCE(si.fm_timbrado_status, 'Sin Timbrar') as status,
            si.fm_cfdi_uuid as uuid_sat,
            si.grand_total as amount,
            si.customer_name as party,
            CASE
                WHEN si.fm_cfdi_uuid IS NOT NULL THEN '✅ Cumple'
                WHEN DATEDIFF(CURDATE(), si.posting_date) <= 1 THEN '⏳ En Proceso'
                ELSE '❌ Incumple'
            END as compliance_status,
            COALESCE(si.fm_timbrado_error, 'Sin observaciones') as observations
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
        {where_conditions}
    """

	return frappe.db.sql(query, filters, as_dict=True)


def get_ppd_events(filters):
	"""Obtener eventos de complementos PPD"""
	where_conditions = get_where_conditions_base(filters, table_alias="pe")

	query = f"""
        SELECT
            pe.posting_date as event_date,
            'Payment Entry' as document_type,
            pe.name as document_name,
            CASE
                WHEN pe.fm_complemento_uuid IS NOT NULL THEN 'Complemento Generado'
                WHEN pe.fm_ppd_status = 'Error' THEN 'Error Complemento'
                ELSE 'Pago Registrado'
            END as event_type,
            COALESCE(pe.fm_ppd_status, 'Pendiente') as status,
            pe.fm_complemento_uuid as uuid_sat,
            pe.paid_amount as amount,
            pe.party_name as party,
            CASE
                WHEN pe.fm_complemento_uuid IS NOT NULL THEN '✅ Cumple'
                WHEN DATEDIFF(CURDATE(), pe.posting_date) <= 30 THEN '⏳ En Plazo'
                ELSE '❌ Vencido'
            END as compliance_status,
            CASE
                WHEN pe.fm_complemento_uuid IS NOT NULL THEN 'Complemento generado correctamente'
                WHEN DATEDIFF(CURDATE(), pe.posting_date) > 30 THEN 'Complemento vencido (>30 días)'
                ELSE 'Dentro del plazo SAT'
            END as observations
        FROM `tabPayment Entry` pe
        WHERE pe.docstatus = 1
        AND pe.payment_type = 'Receive'
        {where_conditions}
    """

	return frappe.db.sql(query, filters, as_dict=True)


def get_ereceipt_events(filters):
	"""Obtener eventos de E-Receipts"""
	where_conditions = get_where_conditions_base(filters, table_alias="er")

	try:
		query = f"""
            SELECT
                er.creation as event_date,
                'EReceipt MX' as document_type,
                er.name as document_name,
                CASE
                    WHEN er.status = 'Completed' THEN 'E-Receipt Procesado'
                    WHEN er.status = 'Error' THEN 'Error E-Receipt'
                    ELSE 'E-Receipt Creado'
                END as event_type,
                er.status as status,
                er.uuid_sat as uuid_sat,
                er.total_amount as amount,
                er.customer as party,
                CASE
                    WHEN er.status = 'Completed' THEN '✅ Cumple'
                    WHEN er.status = 'Processing' THEN '⏳ En Proceso'
                    ELSE '❌ Error'
                END as compliance_status,
                COALESCE(er.processing_notes, 'Sin observaciones') as observations
            FROM `tabEReceipt MX` er
            WHERE er.docstatus = 1
            {where_conditions}
        """

		return frappe.db.sql(query, filters, as_dict=True)
	except Exception:
		# Si la tabla no existe, retornar lista vacía
		return []


def get_global_invoice_events(filters):
	"""Obtener eventos de facturas globales"""
	where_conditions = get_where_conditions_base(filters, table_alias="fg", date_field="creation")

	try:
		query = f"""
            SELECT
                fg.creation as event_date,
                'Factura Global MX' as document_type,
                fg.name as document_name,
                CASE
                    WHEN fg.consolidation_status = 'Completed' THEN 'Factura Global Completada'
                    WHEN fg.consolidation_status = 'Error' THEN 'Error Consolidación'
                    ELSE 'Factura Global Iniciada'
                END as event_type,
                fg.consolidation_status as status,
                fg.cfdi_uuid as uuid_sat,
                fg.total_amount as amount,
                'Múltiples E-Receipts' as party,
                CASE
                    WHEN fg.consolidation_status = 'Completed' AND fg.billing_status = 'Success' THEN '✅ Cumple'
                    WHEN fg.consolidation_status = 'Processing' THEN '⏳ En Proceso'
                    ELSE '❌ Error'
                END as compliance_status,
                CONCAT('E-Receipts consolidados: ', COALESCE(fg.ereceipts_count, 0)) as observations
            FROM `tabFactura Global MX` fg
            WHERE fg.docstatus = 1
            {where_conditions}
        """

		return frappe.db.sql(query, filters, as_dict=True)
	except Exception:
		return []


def get_validation_events(filters):
	"""Obtener eventos del motor de reglas"""
	where_conditions = get_where_conditions_base(filters, table_alias="rel", date_field="creation")

	try:
		query = """
            SELECT
                rel.creation as event_date,
                rel.document_type as document_type,
                rel.document_name as document_name,
                'Validación Aplicada' as event_type,
                CASE
                    WHEN rel.execution_status = 'Success' THEN 'Aprobado'
                    WHEN rel.execution_status = 'Warning' THEN 'Con Alertas'
                    ELSE 'Rechazado'
                END as status,
                NULL as uuid_sat,
                NULL as amount,
                rel.document_name as party,
                CASE
                    WHEN rel.execution_status = 'Success' THEN '✅ Cumple'
                    WHEN rel.execution_status = 'Warning' THEN '⚠️ Alertas'
                    ELSE '❌ Incumple'
                END as compliance_status,
                CONCAT('Regla: ', rel.rule_name, ' - ', COALESCE(rel.execution_summary, '')) as observations
            FROM `tabRule Execution Log` rel
            {where_conditions}
            ORDER BY rel.creation DESC
            LIMIT 100
        """.format(where_conditions=(where_conditions and f"WHERE {where_conditions[4:]}") or "")

		return frappe.db.sql(query, filters, as_dict=True)
	except Exception:
		return []


def get_where_conditions_base(filters, table_alias="si", date_field="posting_date"):
	"""Construir condiciones WHERE basadas en filtros"""
	conditions = []

	if filters.get("company"):
		conditions.append(f"AND {table_alias}.company = %(company)s")

	if filters.get("from_date"):
		conditions.append(f"AND {table_alias}.{date_field} >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append(f"AND {table_alias}.{date_field} <= %(to_date)s")

	return " ".join(conditions)


def get_chart_data(data, filters):
	"""Datos para gráfico del reporte"""
	if not data:
		return None

	# Agrupar eventos por tipo
	event_counts = {}
	compliance_counts = {"✅ Cumple": 0, "⏳ En Proceso": 0, "❌ Incumple": 0, "⚠️ Alertas": 0}

	for row in data:
		event_type = row["event_type"]
		compliance = row["compliance_status"]

		event_counts[event_type] = event_counts.get(event_type, 0) + 1
		if compliance in compliance_counts:
			compliance_counts[compliance] += 1

	return {
		"data": {
			"labels": ["Cumple", "En Proceso", "Incumple", "Con Alertas"],
			"datasets": [
				{
					"name": "Estado de Cumplimiento",
					"values": [
						compliance_counts["✅ Cumple"],
						compliance_counts["⏳ En Proceso"] + compliance_counts["⏳ En Plazo"],
						compliance_counts["❌ Incumple"]
						+ compliance_counts["❌ Vencido"]
						+ compliance_counts["❌ Error"],
						compliance_counts["⚠️ Alertas"],
					],
				}
			],
		},
		"type": "pie",
		"height": 300,
		"colors": ["#28a745", "#ffc107", "#dc3545", "#fd7e14"],
	}


def get_summary_data(data):
	"""Datos de resumen para el reporte"""
	if not data:
		return []

	total_events = len(data)
	compliant_events = sum(1 for row in data if "✅ Cumple" in row["compliance_status"])
	non_compliant_events = sum(1 for row in data if "❌" in row["compliance_status"])

	# Calcular compliance rate
	compliance_rate = (compliant_events / total_events * 100) if total_events > 0 else 0

	# Contar tipos de documentos únicos
	document_types = set(row["document_type"] for row in data)

	# Identificar eventos críticos recientes (últimos 7 días)
	week_ago = date.today() - timedelta(days=7)
	recent_critical = sum(
		1 for row in data if row["event_date"] >= week_ago and "❌" in row["compliance_status"]
	)

	return [
		{"label": _("Total de Eventos Fiscales"), "value": total_events, "indicator": "Blue"},
		{
			"label": _("Tasa de Cumplimiento"),
			"value": f"{compliance_rate:.1f}%",
			"indicator": "Green" if compliance_rate >= 90 else ("Yellow" if compliance_rate >= 70 else "Red"),
		},
		{
			"label": _("Eventos No Conformes"),
			"value": non_compliant_events,
			"indicator": "Red" if non_compliant_events > 0 else "Green",
		},
		{"label": _("Tipos de Documento"), "value": len(document_types), "indicator": "Blue"},
		{
			"label": _("Críticos Recientes (7d)"),
			"value": recent_critical,
			"indicator": "Red" if recent_critical > 0 else "Green",
		},
	]


# Filtros del reporte
def get_filters():
	"""Definir filtros disponibles para el reporte"""
	return [
		{
			"fieldname": "company",
			"label": _("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
		},
		{
			"fieldname": "from_date",
			"label": _("Desde Fecha"),
			"fieldtype": "Date",
			"default": (date.today() - timedelta(days=90)).strftime("%Y-%m-%d"),
		},
		{
			"fieldname": "to_date",
			"label": _("Hasta Fecha"),
			"fieldtype": "Date",
			"default": date.today().strftime("%Y-%m-%d"),
		},
	]
