"""
Utilidades para testing - Verificación de precondiciones
"""

import frappe


def verify_cancellation_preconditions():
	"""Verificar precondiciones para testing ciclo cancelaciones"""

	# Sales Invoice
	si = frappe.get_doc("Sales Invoice", "ACC-SINV-2025-01475")

	# Factura Fiscal México
	ffm = frappe.get_doc("Factura Fiscal Mexico", "FFMX-2025-00064")

	print("=== VERIFICACIÓN PRECONDICIONES ===")
	print(f"Sales Invoice: {si.name}")
	print(f"  Status: {si.docstatus}")
	print(f"  Fiscal Status: {si.fm_fiscal_status}")
	print("  UUID Fields:")
	print(f'    - uuid_fiscal: {getattr(si, "uuid_fiscal", "N/A")}')
	print(f'    - fm_uuid_fiscal: {getattr(si, "fm_uuid_fiscal", "N/A")}')
	print(f'    - fm_ffm_uuid: {getattr(si, "fm_ffm_uuid", "N/A")}')
	print(f"  FFM Link: {si.fm_factura_fiscal_mx}")
	print(f"  Total: {si.grand_total}")

	print(f"\nFactura Fiscal Mexico: {ffm.name}")
	print(f"  Status: {ffm.fm_fiscal_status}")
	print("  UUID Fields:")
	print(f'    - uuid: {getattr(ffm, "uuid", "N/A")}')
	print(f'    - fm_uuid_fiscal: {getattr(ffm, "fm_uuid_fiscal", "N/A")}')
	print(f'    - fm_uuid: {getattr(ffm, "fm_uuid", "N/A")}')
	print(f"  Sales Invoice: {ffm.sales_invoice}")
	print(f"  Total: {ffm.total_fiscal}")

	# Verificar que al menos uno tenga UUID válido
	all_uuids = [
		getattr(si, "uuid_fiscal", None),
		getattr(si, "fm_uuid_fiscal", None),
		getattr(si, "fm_ffm_uuid", None),
		getattr(ffm, "uuid", None),
		getattr(ffm, "fm_uuid_fiscal", None),
		getattr(ffm, "fm_uuid", None),
	]

	valid_uuids = [uuid for uuid in all_uuids if uuid and len(uuid) >= 30]

	if valid_uuids:
		print(f"\n✅ PRECONDICIONES VERIFICADAS - UUID ENCONTRADO: {valid_uuids[0][:8]}...")
		print("🚀 READY PARA TESTING CANCELACIÓN")
	else:
		print("\n❌ ERROR: NO SE ENCONTRÓ UUID VÁLIDO - FACTURA NO ESTÁ TIMBRADA")
		print("⚠️ TESTING CANCELACIÓN NO POSIBLE")

	return len(valid_uuids) > 0
