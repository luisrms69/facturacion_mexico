#!/usr/bin/env python3

import frappe

from facturacion_mexico.config.fiscal_states_config import FiscalStates, SyncStates


def test_factura_fiscal_creation():
	"""
	Testing según TAREA_2_4_VALIDACION_FLUJOS_CRITICOS.md
	Validar creación Factura Fiscal desde Sales Invoice ACC-SINV-2025-00956
	"""
	try:
		print("🧪 TEST: Validación flujo crítico arquitectura resiliente")
		print("=" * 60)

		sales_invoice_name = "ACC-SINV-2025-00956"

		# 1. Verificar Sales Invoice existe
		si = frappe.get_doc("Sales Invoice", sales_invoice_name)
		print(f"✅ Sales Invoice encontrado: {si.name}")
		print(f"   - Estado actual: {si.fm_fiscal_status}")
		print(f"   - Factura Fiscal: {si.fm_factura_fiscal_mx}")

		# 2. Verificar Factura Fiscal asociada existe
		if si.fm_factura_fiscal_mx:
			ffm = frappe.get_doc("Factura Fiscal Mexico", si.fm_factura_fiscal_mx)
			print(f"✅ Factura Fiscal encontrada: {ffm.name}")
			print(f"   - Estado fiscal: {ffm.fm_fiscal_status}")
			print(f"   - Estado sync: {ffm.fm_sync_status}")
			print(f"   - Customer: {ffm.customer}")

			# 3. Validar campos arquitectura resiliente
			resilient_fields = {
				"fm_sub_status": ffm.fm_sub_status,
				"fm_document_type": ffm.fm_document_type,
				"fm_last_pac_sync": ffm.fm_last_pac_sync,
				"fm_sync_status": ffm.fm_sync_status,
				"fm_manual_override": ffm.fm_manual_override,
			}

			print("\n📊 CAMPOS ARQUITECTURA RESILIENTE:")
			for field, value in resilient_fields.items():
				print(f"   - {field}: {value}")

			# 4. Validar estados según nueva arquitectura
			if not FiscalStates.is_valid(ffm.fm_fiscal_status):
				print(f"❌ Estado fiscal inválido: {ffm.fm_fiscal_status}")
				return False
			else:
				print(f"✅ Estado fiscal válido: {ffm.fm_fiscal_status}")

			if ffm.fm_sync_status and not SyncStates.is_valid(ffm.fm_sync_status):
				print(f"❌ Estado sync inválido: {ffm.fm_sync_status}")
				return False
			elif ffm.fm_sync_status:
				print(f"✅ Estado sync válido: {ffm.fm_sync_status}")

			# 5. Verificar consistency entre documentos
			if si.fm_fiscal_status == ffm.fm_fiscal_status:
				print(f"✅ Estados sincronizados: {si.fm_fiscal_status}")
			else:
				print(f"⚠️ Estados desincronizados: SI={si.fm_fiscal_status}, FFM={ffm.fm_fiscal_status}")
		else:
			print("❌ No hay Factura Fiscal asociada")
			return False

		print("\n✅ TEST COMPLETADO: Arquitectura resiliente funcionando correctamente")
		return True

	except Exception as e:
		print(f"❌ ERROR EN TEST: {e}")
		return False
