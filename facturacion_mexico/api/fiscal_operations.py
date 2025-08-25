import frappe
from frappe import _

# Set robusto para estados fiscales cancelados
CANCELADO_FISCAL = {"CANCELADO", "CANCELADA", "CANCELED", "CANCELLED", "CANCELLED_OK"}


def _cancel_all_linked_ffms_if_fiscally_canceled(si_name: str) -> dict:
	"""Cancela TODAS las FFMs vinculadas si fiscalmente canceladas.
	- NO desvincula campos (preserva auditoría)
	- Usa ignore_links=True para evitar LinkExistsError
	- Bloquea si encuentra FFMs activas
	"""
	related = frappe.get_all(
		"Factura Fiscal Mexico",
		filters={"sales_invoice": si_name, "docstatus": 1},
		fields=["name", "fm_fiscal_status"],
	)

	if not related:
		return {"found": 0, "canceled": 0, "blocked_active": []}

	# Clasificación estados
	ffms_activas = []
	ffms_cancelables = []

	for row in related:
		fiscal = (row.get("fm_fiscal_status") or "").upper()
		if fiscal in CANCELADO_FISCAL:
			ffms_cancelables.append(row["name"])
		else:
			ffms_activas.append(row["name"])

	# Guard: Bloquear si hay FFMs activas con estados detallados
	if ffms_activas:
		# Crear mensaje detallado con estados para soporte
		ffm_details = []
		for row in related:
			if row["name"] in ffms_activas:
				state = row.get("fm_fiscal_status") or "SIN_ESTADO"
				ffm_details.append(f"{row['name']} ({state})")

		ffm_list = ", ".join(ffm_details)
		frappe.throw(
			_(
				"No puedes cancelar el Sales Invoice mientras existan FFMs activas: {0}. "
				"Primero cancela fiscalmente en el PAC."
			).format(ffm_list)
		)

	# Cancelación masiva con preserve fields y manejo de errores
	canceled = 0
	for ffm_name in ffms_cancelables:
		ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		if ffm.docstatus == 1:  # Idempotencia
			try:
				ffm.flags.ignore_links = True  # Clave: evitar LinkExistsError
				ffm.cancel()
				canceled += 1
				ffm.add_comment(
					"Info",
					_(
						"FFM cancelada automáticamente antes de cancelar SI {0} (workflow múltiple 02/03/04)."
					).format(si_name),
				)
			except Exception as e:
				# Error individual por FFM - identificar cuál falló
				error_msg = str(e)[:200]  # Truncar para evitar CharacterLengthExceeded
				frappe.throw(
					_("Error cancelando FFM {0}: {1}. Contacta soporte técnico.").format(ffm_name, error_msg)
				)

	# Sin commits manuales - respeta atomicidad Frappe
	return {
		"found": len(related),
		"canceled": canceled,
		"blocked_active": ffms_activas,
		"cancelables_found": len(ffms_cancelables),
	}


def before_cancel_sales_invoice_orchestrator(doc, method=None):
	"""Hook para múltiples FFMs: bloquea activas, cancela fiscalmente canceladas"""
	si_name = doc.name
	metrics = _cancel_all_linked_ffms_if_fiscally_canceled(si_name)

	# Logging para debugging
	frappe.logger("facturacion_mexico").info(
		{"event": "before_cancel_si_multiple_ffms", "si": si_name, **metrics}
	)


@frappe.whitelist()
def refacturar_misma_si(si_name: str):
	"""
	Re-facturación con la MISMA Sales Invoice para motivos 02/03/04:
	- Verifica que la última FFM ligada al SI esté CANCELADA con motivo 02/03/04
	- Desvincula el SI (limpia fm_factura_fiscal_mx y estado fiscal local)
	- NO timbra ni crea FFM aquí. Solo prepara el SI para usar el flujo original.
	"""
	si = frappe.get_doc("Sales Invoice", si_name)

	# Precondiciones básicas
	if si.docstatus != 1:
		frappe.throw(_("La Sales Invoice debe estar enviada (docstatus=1)."))

	ffm_name = si.get("fm_factura_fiscal_mx")
	if ffm_name:
		ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		if ffm.fm_fiscal_status != "CANCELADO":
			frappe.throw(
				_(
					"Este botón solo aplica cuando la última Factura Fiscal ligada está CANCELADA (motivo 02/03/04)."
				)
			)

		# M4-02/03/04: Guard contextual - verificar motivo cancelación 02/03/04
		motivo_code = _extract_motive_code_from_reason(ffm.get("cancellation_reason") or "")
		if motivo_code not in ["02", "03", "04"]:
			frappe.throw(
				_(
					"Esta re-facturación aplica únicamente para motivos 02/03/04. "
					f"Motivo actual: {motivo_code or 'N/A'}"
				)
			)

		# Guard avanzado: verificar que no hay operaciones pendientes
		if ffm.get("fm_sync_status") == "pending":
			frappe.throw(_("Operación pendiente en FFM. Espera a que complete antes de re-facturar."))

	# IDEMPOTENCIA: Si ya está desvinculado, respuesta elegante
	if not si.get("fm_factura_fiscal_mx"):
		return {
			"ok": True,
			"already_unlinked": True,
			"message": _("Sales Invoice ya está listo. Use 'Generar Factura Fiscal' (flujo normal)."),
		}

	# DESVINCULACIÓN: Limpiar links y flags residuales para volver al flujo nativo
	ffm_anterior = si.get("fm_factura_fiscal_mx")  # Para trazabilidad

	# Limpiar vinculación principal
	si.db_set("fm_factura_fiscal_mx", "")

	# Limpiar estado fiscal local para UI limpia
	if hasattr(si, "fm_fiscal_status"):
		si.db_set("fm_fiscal_status", "")
	if hasattr(si, "fm_sync_status"):
		si.db_set("fm_sync_status", "idle")

	# Limpiar flags residuales de sustitución (si existieran)
	if hasattr(si, "ffm_substitution_source_uuid"):
		si.db_set("ffm_substitution_source_uuid", "")

	# TRAZABILIDAD MÍNIMA: Comment simple sin sobrecarga
	si.add_comment(
		"Info", _("Re-facturación 02/03/04: SI desvinculada de FFM {0}.").format(ffm_anterior or "N/A")
	)

	# M4-FIX-03: Refuerzo estado limpio para evitar validaciones residuales
	si.reload()
	# Necesario para persistir la desvinculación antes de validaciones subsiguientes (workflow M4).
	# nosemgrep
	frappe.db.commit()
	frappe.clear_cache()

	return {
		"ok": True,
		"message": _("Sales Invoice lista para re-facturar. Use 'Generar Factura Fiscal' (flujo normal)."),
	}


@frappe.whitelist()
def cancel_sales_invoice_after_ffm(si_name: str):
	"""
	DEPRECATED: Usar botón Cancel nativo.

	El workflow 02/03/04 ahora usa cancelación nativa de Frappe con interceptor backend.
	Este endpoint se mantiene por compatibilidad temporal.
	"""
	frappe.log_error("Uso de endpoint deprecated", "Cancel SI Deprecated (Use Native)")
	return {
		"success": False,
		"message": _("Usa el botón Cancel nativo. Este endpoint está deprecado."),
		"redirect_to_native": True,
	}


# CÓDIGO LEGACY DEPRECADO - MANTENER PARA REFERENCIA TEMPORAL
def _cancel_sales_invoice_after_ffm_legacy(si_name: str):
	"""
	CÓDIGO LEGACY: Implementación anterior con desvinculación manual.
	Deprecado en favor del interceptor backend before_cancel.
	"""
	# TODO: Eliminar todo este bloque en próximo refactor - reemplazado por interceptor backend
	pass


def create_facturacion_roles():
	"""Crear roles del sistema de facturación México."""
	import frappe

	roles_to_create = [
		"Facturacion Mexico User",
		"Facturacion Mexico Manager",
		"Facturacion Mexico System Manager",
	]

	created_roles = []
	existing_roles = []

	for role_name in roles_to_create:
		if not frappe.db.exists("Role", role_name):
			role_doc = frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1})
			role_doc.insert()
			created_roles.append(role_name)
			print(f"✅ Rol creado: {role_name}")
		else:
			existing_roles.append(role_name)
			print(f"⚠️ Rol ya existe: {role_name}")

	frappe.db.commit()
	print(f"\n✅ PASO 1 COMPLETADO: {len(created_roles)} roles creados, {len(existing_roles)} ya existían")

	return {"success": True, "created_roles": created_roles, "existing_roles": existing_roles}


def assign_facturacion_permissions():
	"""Asignar permisos específicos para los roles de facturación."""
	import frappe

	# Configuración de permisos según instrucciones
	permissions_config = [
		# DocType: Factura Fiscal Mexico
		{
			"doctype": "Factura Fiscal Mexico",
			"role": "Facturacion Mexico User",
			"perms": {"read": 1, "write": 1, "create": 1, "submit": 1},
		},
		{
			"doctype": "Factura Fiscal Mexico",
			"role": "Facturacion Mexico Manager",
			"perms": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1},
		},
		{
			"doctype": "Factura Fiscal Mexico",
			"role": "Facturacion Mexico System Manager",
			"perms": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1},
		},
		# DocType: Sales Invoice
		{"doctype": "Sales Invoice", "role": "Facturacion Mexico User", "perms": {"read": 1}},
		{"doctype": "Sales Invoice", "role": "Facturacion Mexico Manager", "perms": {"read": 1, "cancel": 1}},
		{
			"doctype": "Sales Invoice",
			"role": "Facturacion Mexico System Manager",
			"perms": {"read": 1, "cancel": 1},
		},
	]

	created_permissions = []

	for perm_config in permissions_config:
		doctype_name = perm_config["doctype"]
		role_name = perm_config["role"]
		perms = perm_config["perms"]

		# Verificar si ya existe el permiso
		existing_perm = frappe.get_all(
			"DocPerm", filters={"parent": doctype_name, "role": role_name}, limit=1
		)

		if existing_perm:
			# Actualizar permisos existentes
			perm_doc = frappe.get_doc("DocPerm", existing_perm[0].name)
			for perm_key, perm_value in perms.items():
				setattr(perm_doc, perm_key, perm_value)
			perm_doc.save()
			print(f"✅ Permisos actualizados: {role_name} en {doctype_name}")
		else:
			# Crear nuevos permisos
			perm_doc = frappe.get_doc(
				{
					"doctype": "DocPerm",
					"parent": doctype_name,
					"parenttype": "DocType",
					"parentfield": "permissions",
					"role": role_name,
					**perms,
				}
			)
			perm_doc.insert()
			created_permissions.append(f"{role_name} → {doctype_name}")
			print(f"✅ Permisos creados: {role_name} en {doctype_name}")

	frappe.db.commit()
	print(f"\n✅ PASO 2 COMPLETADO: Permisos asignados para {len(permissions_config)} configuraciones")

	return {"success": True, "created_permissions": created_permissions}


def test_interceptor_backend():
	"""Testing interceptor backend - Caso C final."""
	import frappe

	try:
		si = frappe.get_doc("Sales Invoice", "ACC-SINV-2025-01493")
		print(f"✅ CASO C - SI encontrado: {si.name}, docstatus: {si.docstatus}")

		# Ejecutar cancelación (activará nuestro interceptor)
		si.cancel()

		# Verificar estado post-cancelación
		si.reload()
		ffm = frappe.get_doc("Factura Fiscal Mexico", si.fm_factura_fiscal_mx or "")

		print(f"✅ SUCCESS CASO C: SI docstatus: {si.docstatus}, FFM docstatus: {ffm.docstatus}")
		return {"success": True, "si_status": si.docstatus, "ffm_status": ffm.docstatus}

	except Exception as e:
		print(f"❌ ERROR: {type(e).__name__}: {e!s}")
		return {"success": False, "error": f"{e!s}"}


def test_idempotencia_cancel():
	"""Testing idempotencia - múltiples clicks Cancel."""
	import frappe

	try:
		# Intentar cancelar documento ya cancelado
		si = frappe.get_doc("Sales Invoice", "ACC-SINV-2025-01491")
		print(f"✅ SI estado actual: {si.name}, docstatus: {si.docstatus}")

		if si.docstatus == 2:
			print("⚠️ SI ya cancelado - testing idempotencia")
			# Intentar cancelar nuevamente (debería ser seguro)
			try:
				si.cancel()  # Esto debería fallar elegantemente
				print("❌ ERROR: Cancel en documento ya cancelado debería fallar")
			except Exception as e:
				print(f"✅ SUCCESS: Prevención correcta - {type(e).__name__}")
				return {"success": True, "idempotent": True}
		else:
			print(f"SI aún activo (docstatus={si.docstatus}) - usar para testing normal")
			return {"success": True, "ready_for_cancel": True}

	except Exception as e:
		print(f"❌ ERROR: {type(e).__name__}: {e!s}")
		return {"success": False, "error": f"{e!s}"}


def test_e2e_workflow_caso_c():
	"""Testing end-to-end workflow UI - Caso C."""
	import frappe

	try:
		si = frappe.get_doc("Sales Invoice", "ACC-SINV-2025-01493")
		print(f"✅ CASO C - SI: {si.name}, docstatus: {si.docstatus}")

		ffm = frappe.get_doc("Factura Fiscal Mexico", si.fm_factura_fiscal_mx or "")
		print(f"✅ FFM: {ffm.name}, docstatus: {ffm.docstatus}, fiscal_status: {ffm.fm_fiscal_status}")

		# Verificar precondiciones para UI testing
		if si.docstatus != 1:
			return {"error": "SI no está submitted", "si_docstatus": si.docstatus}

		if ffm.fm_fiscal_status != "CANCELADO":
			return {"error": "FFM no está cancelada fiscalmente", "fiscal_status": ffm.fm_fiscal_status}

		print("✅ PRECONDICIONES CORRECTAS para testing UI:")
		print(f"  - SI {si.name} submitted (docstatus=1)")
		print(f"  - FFM {ffm.name} cancelada fiscalmente (status=CANCELADO)")
		print(f"  - Links bidireccionales: SI->FFM: {si.fm_factura_fiscal_mx}, FFM->SI: {ffm.sales_invoice}")

		# Información para testing manual UI
		return {
			"success": True,
			"ready_for_ui_testing": True,
			"si_name": si.name,
			"ffm_name": ffm.name,
			"ui_url": f"http://facturacion.dev/app/sales-invoice/{si.name}",
			"testing_steps": [
				"1. Abrir URL en browser",
				"2. Verificar botón Cancel nativo VISIBLE",
				"3. Click Cancel → seleccionar 'Cancel All Documents'",
				"4. Verificar ambos documentos cancelados",
			],
		}

	except Exception as e:
		print(f"❌ ERROR: {type(e).__name__}: {e!s}")
		return {"success": False, "error": f"{e!s}"}


def _extract_motive_code_from_reason(cancellation_reason: str) -> str:
	"""Extrae código motivo de 'cancellation_reason' formato '02 - Descripción'."""
	if not cancellation_reason:
		return ""

	# Buscar patrón "NN - " al inicio
	import re

	match = re.match(r"^(\d{2})\s*-", cancellation_reason.strip())
	return match.group(1) if match else ""
