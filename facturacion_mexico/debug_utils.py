"""Debug utilities for facturacion_mexico app"""

import frappe


def debug_ffm_cancelacion_issue():
	"""Debug FFMX-2025-00060 cancelation issue"""

	try:
		# Verificar estado de la factura fiscal
		ffm = frappe.get_doc("Factura Fiscal Mexico", "FFMX-2025-00060")
		print("=== ESTADO ACTUAL FFMX-2025-00060 ===")
		print(f"FFM Status: {ffm.fm_fiscal_status}")
		print(f"Sales Invoice: {ffm.sales_invoice}")
		print(f"UUID: {ffm.fm_uuid}")
		print(f"Last Response Log: {ffm.fm_last_response_log}")
		print(f"Sync Status: {ffm.fm_sync_status}")

		# Verificar último log de respuesta
		if ffm.fm_last_response_log:
			log = frappe.get_doc("FacturAPI Response Log", ffm.fm_last_response_log)
			print(f"Último Log - Operation: {log.operation_type}")
			print(f"Último Log - Success: {log.success}")
			print(f"Último Log - Status Code: {log.status_code}")
			print(f"Último Log - Error: {log.error_message}")
			print(f"Último Log - Timestamp: {log.timestamp}")
		else:
			print("No hay último log registrado")

		# Buscar logs recientes de cancelación
		recent_logs = frappe.get_all(
			"FacturAPI Response Log",
			filters={"factura_fiscal_mexico": ffm.name, "operation_type": "Solicitud Cancelación"},
			fields=["name", "timestamp", "success", "status_code", "error_message"],
			order_by="timestamp desc",
			limit=5,
		)

		print(f"\n=== LOGS RECIENTES CANCELACIÓN ({len(recent_logs)}) ===")
		for log in recent_logs:
			print(f"{log.timestamp}: {log.name} - Success: {log.success} - Status: {log.status_code}")
			if log.error_message:
				print(f"  Error: {log.error_message}")

		# Verificar si hay logs más recientes que no están vinculados al último log
		all_recent_logs = frappe.get_all(
			"FacturAPI Response Log",
			filters={"factura_fiscal_mexico": ffm.name},
			fields=["name", "timestamp", "operation_type", "success", "status_code"],
			order_by="timestamp desc",
			limit=3,
		)

		print(f"\n=== TODOS LOS LOGS RECIENTES ({len(all_recent_logs)}) ===")
		for log in all_recent_logs:
			print(f"{log.timestamp}: {log.name} - {log.operation_type} - Success: {log.success}")

		return {
			"ffm_status": ffm.fm_fiscal_status,
			"last_log": ffm.fm_last_response_log,
			"recent_cancelation_logs": len(recent_logs),
			"sync_status": ffm.fm_sync_status,
		}

	except Exception as e:
		print(f"ERROR: {e}")
		frappe.log_error(f"Debug error: {e}", "Debug FFM Cancelation")
		return {"error": str(e)}


def debug_motive_parameter_issue():
	"""Debug why motive parameter is not reaching FacturAPI"""

	print("\n=== DEBUG: ANÁLISIS PARÁMETRO MOTIVE ===")

	# Verificar enum SAT existe
	try:
		from facturacion_mexico.config.sat_cancellation_motives import SATCancellationMotives

		print("✅ Enum SAT Cancellation Motives importado correctamente")
		print(f"Códigos disponibles: {SATCancellationMotives.get_valid_codes()}")

		# Test validación código
		test_code = "02"
		is_valid = SATCancellationMotives.is_valid_code(test_code)
		print(f'Código "02" válido: {is_valid}')

		# Test config completa
		config = SATCancellationMotives.get_config()
		print(
			f'Config completa: {len(config.get("codes", []))} códigos, {len(config.get("select_options", []))} opciones select'
		)

	except Exception as e:
		print(f"❌ Error importando enum SAT: {e}")
		import traceback

		traceback.print_exc()

	# Verificar API endpoint cancelación SAT
	try:
		from facturacion_mexico.facturacion_fiscal.timbrado_api import get_sat_cancellation_motives

		motives = get_sat_cancellation_motives()
		print("✅ API motivos SAT funcional")
		print(f'  - Códigos: {len(motives.get("codes", []))}')
		print(f'  - Opciones select: {len(motives.get("select_options", []))}')
		print(f'  - Descripciones: {len(motives.get("descriptions", {}))}')
		if motives.get("select_options"):
			print(f'  - Primera opción: {motives["select_options"][0]}')

	except Exception as e:
		print(f"❌ Error API motivos SAT: {e}")
		import traceback

		traceback.print_exc()

	# Verificar si api_client tiene debug logging activo
	try:
		from facturacion_mexico.facturacion_fiscal.api_client import FacturAPIClient

		print("✅ FacturAPIClient importado correctamente")
		print("Debug logging debería estar activo en cancel_invoice()")

	except Exception as e:
		print(f"❌ Error importando FacturAPIClient: {e}")

	return True


def debug_last_log_update_issue():
	"""Debug why last response log field is not updating"""

	print("\n=== DEBUG: ANÁLISIS ÚLTIMO LOG NO SE ACTUALIZA ===")

	# Obtener FFM
	ffm = frappe.get_doc("Factura Fiscal Mexico", "FFMX-2025-00059")
	current_last_log = ffm.fm_last_response_log

	# Encontrar el log más reciente
	latest_log = frappe.get_all(
		"FacturAPI Response Log",
		filters={"factura_fiscal_mexico": ffm.name},
		fields=["name", "timestamp", "operation_type"],
		order_by="timestamp desc",
		limit=1,
	)

	if latest_log:
		latest_log_name = latest_log[0]["name"]
		print(f"Último log actual en FFM: {current_last_log}")
		print(f"Log más reciente en BD: {latest_log_name}")
		print(f'Timestamp más reciente: {latest_log[0]["timestamp"]}')
		print(f'Operación más reciente: {latest_log[0]["operation_type"]}')

		if current_last_log != latest_log_name:
			print("❌ PROBLEMA CONFIRMADO: Campo fm_last_response_log NO se actualiza")
			print("Analizando lógica en PACResponseWriter._update_factura_fiscal()...")

			# Verificar si _update_factura_fiscal se ejecuta
			try:
				# Simular actualización del campo manualmente para verificar permisos
				frappe.db.set_value(
					"Factura Fiscal Mexico", ffm.name, "fm_last_response_log", latest_log_name
				)
				frappe.db.commit()
				print("✅ Actualización manual exitosa - NO es problema de permisos")

				# Revertir para no alterar datos
				frappe.db.set_value(
					"Factura Fiscal Mexico", ffm.name, "fm_last_response_log", current_last_log
				)
				frappe.db.commit()
				print("✅ Dato revertido a estado original")

			except Exception as e:
				print(f"❌ Error en actualización manual: {e}")
		else:
			print("✅ Campo fm_last_response_log está actualizado correctamente")

	return True


def analyze_error_log():
	"""Analyze the specific error log to understand the payload issue"""

	print("\n=== ANÁLISIS LOG DE ERROR ESPECÍFICO ===")

	try:
		# Obtener el log de error de cancelación
		log = frappe.get_doc("FacturAPI Response Log", "FAPI-LOG-2025-00081")
		print(f"Operation Type: {log.operation_type}")
		print(f"Success: {log.success}")
		print(f"Status Code: {log.status_code}")
		print(f"Error Message: {log.error_message}")
		print(f"Timestamp: {log.timestamp}")

		# Revisar request payload enviado
		if log.request_payload:
			import json

			request_data = json.loads(log.request_payload)
			print("\n=== REQUEST PAYLOAD ENVIADO ===")
			print(json.dumps(request_data, indent=2, ensure_ascii=False))
		else:
			print("\n❌ No hay request_payload en el log")

		# Revisar response recibido
		if log.facturapi_response:
			import json

			response_data = json.loads(log.facturapi_response)
			print("\n=== RESPONSE RECIBIDO ===")
			print(json.dumps(response_data, indent=2, ensure_ascii=False))
		else:
			print("\n❌ No hay facturapi_response en el log")

	except Exception as e:
		print(f"❌ Error analizando log: {e}")
		import traceback

		traceback.print_exc()

	return True


def debug_facturapi_id_issue():
	"""Debug what ID we're sending to FacturAPI and if payload logging is correct"""

	print("\n=== ANÁLISIS ID ENVIADO A FACTURAPI ===")

	try:
		# Verificar qué ID estamos enviando a FacturAPI
		ffm = frappe.get_doc("Factura Fiscal Mexico", "FFMX-2025-00059")
		print(f"FFM Name: {ffm.name}")
		print(f"Sales Invoice: {ffm.sales_invoice}")
		print(f"UUID SAT: {ffm.fm_uuid}")

		# Verificar si existe el campo facturapi_id
		facturapi_id = ffm.get("facturapi_id")
		print(f"FacturAPI ID: {facturapi_id}")

		if not facturapi_id:
			print("❌ PROBLEMA: NO hay facturapi_id almacenado")
			print("Esto significa que no sabemos qué ID usar para cancelar en FacturAPI")

		# Buscar en los logs de timbrado exitoso el ID que devolvió FacturAPI
		timbrado_logs = frappe.get_all(
			"FacturAPI Response Log",
			filters={"factura_fiscal_mexico": ffm.name, "operation_type": "Timbrado", "success": 1},
			fields=["name", "facturapi_response"],
			order_by="timestamp desc",
			limit=1,
		)

		if timbrado_logs:
			import json

			log = frappe.get_doc("FacturAPI Response Log", timbrado_logs[0]["name"])
			if log.facturapi_response:
				response = json.loads(log.facturapi_response)
				print("\n=== RESPUESTA TIMBRADO EXITOSO ===")
				# Buscar el ID que devolvió FacturAPI
				if "raw_response" in response:
					raw = response["raw_response"]
					print(f'FacturAPI devolvió ID: {raw.get("id")}')
					print(f'UUID devuelto: {raw.get("uuid")}')

					if raw.get("id") != facturapi_id:
						print(
							f'❌ PROBLEMA: ID almacenado ({facturapi_id}) != ID de FacturAPI ({raw.get("id")})'
						)
				elif "id" in response:
					print(f'FacturAPI devolvió ID: {response.get("id")}')
		else:
			print("❌ No hay logs de timbrado exitoso para verificar el ID correcto")

		# Verificar qué ID está usando la función de cancelación
		print("\n=== CÓDIGO DE CANCELACIÓN ===")
		print("Revisando timbrado_api.py línea 829...")
		print("self.client.cancel_invoice(factura_fiscal.facturapi_id, motivo, substitution_uuid)")
		print(f"Significa que está enviando: {facturapi_id}")

	except Exception as e:
		print(f"❌ Error: {e}")
		import traceback

		traceback.print_exc()

	return True


def debug_payload_logging_vs_real():
	"""Debug difference between logged payload and real payload sent to FacturAPI"""

	print("\n=== ANÁLISIS PAYLOAD LOGGING VS REAL ===")

	print("PROBLEMA IDENTIFICADO:")
	print("1. pac_request (logging) contiene datos ERPNext: sales_invoice, factura_fiscal, etc.")
	print("2. Payload REAL a FacturAPI es solo query parameters: ?motive=02")
	print("3. Son dos cosas completamente diferentes")

	print("\nPAC_REQUEST (para auditoría interna):")
	print("  - factura_fiscal: FFMX-2025-00059")
	print("  - sales_invoice: ACC-SINV-2025-01470")
	print("  - motive: 02")
	print("  - Otros datos internos ERPNext")

	print("\nPAYLOAD REAL a FacturAPI:")
	print("  - Endpoint: DELETE /invoices/{facturapi_id}?motive=02")
	print("  - Body: None (vacío)")
	print("  - Solo query parameters")

	print("\n✅ CONCLUSIÓN:")
	print("El pac_request NO es el payload real a FacturAPI.")
	print("Es solo para logging/auditoría interna del sistema.")
	print("El payload real se construye en api_client.py línea 201.")

	return True


def debug_facturapi_id_none_issue():
	"""Debug why FacturAPI ID is None for FFMX-2025-00060"""

	print("\n=== DEBUG: FACTURAPI ID = NONE ===")

	try:
		# Verificar FacturAPI ID de la nueva factura
		ffm = frappe.get_doc("Factura Fiscal Mexico", "FFMX-2025-00060")
		print(f"FFM Name: {ffm.name}")
		print(f'FacturAPI ID: {ffm.get("facturapi_id")}')
		print(f'Tipo: {type(ffm.get("facturapi_id"))}')

		# Buscar en el log de timbrado exitoso el ID real
		log = frappe.get_doc("FacturAPI Response Log", "FAPI-LOG-2025-00066")
		if log.facturapi_response:
			import json

			response = json.loads(log.facturapi_response)
			print("\n=== RESPUESTA TIMBRADO EXITOSO ===")
			if "raw_response" in response:
				raw = response["raw_response"]
				print(f'ID en raw_response: {raw.get("id")}')
				print(f'UUID en raw_response: {raw.get("uuid")}')
			elif "id" in response:
				print(f'ID directo en response: {response.get("id")}')
			else:
				print("Keys disponibles:", list(response.keys())[:10])

			# Verificar si el ID está en algún lado
			print("\n=== BÚSQUEDA EXHAUSTIVA DEL ID ===")
			response_str = str(response)
			if "689d75" in response_str or "66b13" in response_str:
				print("✅ ID tipo FacturAPI encontrado en response")
			else:
				print("❌ No se encuentra ID típico de FacturAPI")

		# Verificar si el campo existe en el DocType
		print("\n=== VERIFICACIÓN CAMPO DOCTYPE ===")
		meta = frappe.get_meta("Factura Fiscal Mexico")
		facturapi_field = meta.get_field("facturapi_id")
		if facturapi_field:
			print(f"✅ Campo facturapi_id existe: {facturapi_field.fieldtype}")
		else:
			print("❌ Campo facturapi_id NO existe en DocType")

	except Exception as e:
		print(f"❌ Error: {e}")
		import traceback

		traceback.print_exc()

	return True
