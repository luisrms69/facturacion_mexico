#!/usr/bin/env python3
"""
FASE 0.1: Script de Verificación Estado Actual - Riesgo Doble Timbrado
Parte del Plan de Restauración fm_factura_fiscal_mx

Ejecutar con:
bench --site facturacion.dev execute facturacion_mexico.scripts.verify_double_timbrado_risk.execute
"""

from datetime import datetime, timedelta

import frappe


def execute():
	"""Ejecutar verificación completa del riesgo de doble timbrado"""

	print("🔍 INICIANDO VERIFICACIÓN RIESGO DOBLE TIMBRADO")
	print("=" * 60)

	# 1. Verificar Sales Invoice con múltiples FacturAPI Response Log
	check_multiple_facturapi_logs()

	# 2. Verificar registros "En proceso" sin completar
	check_incomplete_processes()

	# 3. Identificar gap temporal de protección
	check_temporal_protection_gap()

	# 4. Verificar estado del sistema post-eliminación
	check_post_elimination_status()

	print("\n✅ VERIFICACIÓN COMPLETADA")


def check_multiple_facturapi_logs():
	"""Verificar si hay Sales Invoice con múltiples FacturAPI Response Log"""

	print("\n📊 1. SALES INVOICE CON MÚLTIPLES LOGS FACTURAPI")
	print("-" * 50)

	# Buscar Sales Invoice que aparezcan múltiples veces en FacturAPI Response Log
	query = """
        SELECT
            reference_name as sales_invoice,
            COUNT(*) as log_count,
            GROUP_CONCAT(name ORDER BY creation DESC) as log_names,
            GROUP_CONCAT(status ORDER BY creation DESC) as statuses,
            GROUP_CONCAT(endpoint ORDER BY creation DESC) as endpoints
        FROM `tabFacturAPI Response Log`
        WHERE reference_doctype = 'Sales Invoice'
        AND endpoint LIKE '%timbra%'
        GROUP BY reference_name
        HAVING COUNT(*) > 1
        ORDER BY log_count DESC
    """

	multiple_logs = frappe.db.sql(query, as_dict=True)

	if multiple_logs:
		print(f"⚠️ ENCONTRADAS {len(multiple_logs)} Sales Invoice con múltiples logs:")
		for record in multiple_logs[:10]:  # Mostrar solo las primeras 10
			print(f"  📄 {record.sales_invoice}: {record.log_count} logs")
			print(f"     Status: {record.statuses}")
			print(f"     Endpoints: {record.endpoints}")
			print()
	else:
		print("✅ No se encontraron Sales Invoice con múltiples logs de timbrado")


def check_incomplete_processes():
	"""Verificar registros En proceso sin completar"""

	print("\n⏳ 2. PROCESOS 'EN PROCESO' SIN COMPLETAR")
	print("-" * 50)

	# Buscar registros que quedaron "En proceso" por más de 1 hora
	one_hour_ago = datetime.now() - timedelta(hours=1)

	incomplete_query = """
        SELECT
            name,
            reference_name as sales_invoice,
            status,
            endpoint,
            creation,
            TIMESTAMPDIFF(MINUTE, creation, NOW()) as minutes_elapsed
        FROM `tabFacturAPI Response Log`
        WHERE status IN ('En proceso', 'Pendiente', 'Processing')
        AND creation < %s
        ORDER BY creation DESC
    """

	incomplete_logs = frappe.db.sql(incomplete_query, (one_hour_ago,), as_dict=True)

	if incomplete_logs:
		print(f"⚠️ ENCONTRADOS {len(incomplete_logs)} procesos incompletos:")
		for record in incomplete_logs:
			print(f"  🔄 {record.sales_invoice}: {record.status} ({record.minutes_elapsed} min)")
			print(f"     Endpoint: {record.endpoint}")
			print(f"     Creado: {record.creation}")
			print()
	else:
		print("✅ No se encontraron procesos incompletos")


def check_temporal_protection_gap():
	"""Identificar gap temporal de protección"""

	print("\n🕐 3. GAP TEMPORAL DE PROTECCIÓN")
	print("-" * 50)

	# Verificar si existe algún mecanismo actual de prevención concurrencia
	print("Verificando mecanismos actuales de protección:")

	# 3.1 Verificar campo fm_factura_fiscal_mx
	field_exists = frappe.db.exists("Custom Field", "Sales Invoice-fm_factura_fiscal_mx")
	print(f"  📋 Campo fm_factura_fiscal_mx existe: {field_exists}")

	# 3.2 Verificar DocType Factura Fiscal Mexico
	ffm_exists = frappe.db.exists("DocType", "Factura Fiscal Mexico")
	print(f"  📄 DocType Factura Fiscal Mexico existe: {ffm_exists}")

	if ffm_exists:
		ffm_count = frappe.db.count("Factura Fiscal Mexico")
		print(f"  📊 Total Factura Fiscal Mexico: {ffm_count}")

	# 3.3 Verificar FacturAPI Response Log como protección
	frl_exists = frappe.db.exists("DocType", "FacturAPI Response Log")
	print(f"  📝 DocType FacturAPI Response Log existe: {frl_exists}")

	if frl_exists:
		frl_count = frappe.db.count("FacturAPI Response Log")
		print(f"  📊 Total FacturAPI Response Log: {frl_count}")

		# Verificar estados disponibles
		states_query = """
            SELECT DISTINCT status, COUNT(*) as count
            FROM `tabFacturAPI Response Log`
            GROUP BY status
            ORDER BY count DESC
        """
		states = frappe.db.sql(states_query, as_dict=True)
		print("  📊 Estados en FacturAPI Response Log:")
		for state in states:
			print(f"     - {state.status}: {state.count} registros")


def check_post_elimination_status():
	"""Verificar estado del sistema post-eliminación"""

	print("\n🗑️ 4. ESTADO POST-ELIMINACIÓN")
	print("-" * 50)

	# 4.1 Verificar si existe DocType Fiscal Attempt Log (debería estar eliminado)
	fal_exists = frappe.db.exists("DocType", "Fiscal Attempt Log")
	print(f"  ❌ DocType Fiscal Attempt Log existe: {fal_exists}")

	# 4.2 Verificar si existe Custom Field fm_fiscal_attempts (debería estar eliminado)
	fa_field_exists = frappe.db.exists("Custom Field", "Sales Invoice-fm_fiscal_attempts")
	print(f"  ❌ Custom Field fm_fiscal_attempts existe: {fa_field_exists}")

	# 4.3 Verificar integridad de Sales Invoice
	si_count = frappe.db.count("Sales Invoice")
	print(f"  📊 Total Sales Invoice: {si_count}")

	# 4.4 Buscar Sales Invoice creadas después de la eliminación (post 2025-08-04)
	post_elimination_query = """
        SELECT COUNT(*) as count
        FROM `tabSales Invoice`
        WHERE creation > '2025-08-04 12:13:34'
    """
	post_elimination = frappe.db.sql(post_elimination_query, as_dict=True)[0]
	print(f"  📅 Sales Invoice post-eliminación: {post_elimination.count}")

	if post_elimination.count > 0:
		print("  ⚠️ HAY FACTURAS CREADAS DESPUÉS DE LA ELIMINACIÓN")
		print("     Estas facturas están en riesgo de doble timbrado")


def generate_summary_report():
	"""Generar reporte resumen para toma de decisiones"""

	print("\n📋 RESUMEN PARA TOMA DE DECISIONES")
	print("=" * 60)

	# Resumen de hallazgos críticos - pendiente implementar
	# summary = {
	#     "multiple_logs_found": False,
	#     "incomplete_processes_found": False,
	#     "protection_mechanisms": [],
	#     "risk_level": "BAJO",
	# }

	# Lógica de evaluación de riesgo se implementaría aquí
	# basada en los resultados de las verificaciones anteriores

	print("📊 NIVEL DE RIESGO: Se determinará basado en hallazgos")
	print("📋 RECOMENDACIÓN: Pendiente análisis completo FASE 0.2 y 0.3")


if __name__ == "__main__":
	execute()
