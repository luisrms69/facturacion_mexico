# facturacion_mexico/hooks_handlers/sales_invoice_ieps.py
# IEPS CUOTA CALCULATION SYSTEM - Sales Invoice
# Sistema de Cálculo IEPS por Cuota (Combustibles y Bebidas)

"""
Hooks para calcular IEPS por cuota específica en Sales Invoice.

Arquitectura (Opción C - Aprobada):
- Item Group → ITT (mantiene herencia)
- ITT marca que usa IEPS Cuota (rate=0, tipo_factor="Cuota")
- Hook detecta tax rows IEPS Cuota y recalcula como Actual
- Prioridad fuentes: Item field → Tabla SAT → Error

Flujo:
1. validate: Detectar tax rows IEPS Cuota, calcular amounts por item
2. before_save: Consolidar, cambiar a Actual, ajustar base IVA

Contexto normativo:
- Combustibles: IEPS NO integra base IVA (LIEPS Art. 2-A)
- Bebidas: IEPS SÍ integra base IVA (regla general)

Precisiones E4:
- Payload bebidas: Base=qty física (litros), TasaOCuota=cuota/litro
- Payload combustibles: Omitir nodo IEPS, Base IVA neta sin IEPS
- item_wise_tax_detail: Granularidad por item para E4
"""

import json

import frappe
from frappe.utils import flt, today

# =============================================================================
# HELPERS - CONFIGURACIÓN FISCAL
# =============================================================================


def _obtener_config_fiscal(company: str):
	"""
	Obtener Configuracion Fiscal Mexico para una empresa.

	Args:
		company: Nombre de la empresa

	Returns:
		Document: Configuracion Fiscal Mexico

	Raises:
		frappe.DoesNotExistError: Si no existe configuración
	"""
	config_name = f"CFM-{company}"
	if not frappe.db.exists("Configuracion Fiscal Mexico", config_name):
		return None

	return frappe.get_doc("Configuracion Fiscal Mexico", config_name)


def _obtener_metadata_cuenta(account_head: str, company: str) -> dict:
	"""
	Obtener metadata fiscal de una cuenta desde Mapeo Fiscal.

	Args:
		account_head: Cuenta de impuesto
		company: Empresa

	Returns:
		dict: {tipo_factor, integra_base_iva, rol_fiscal} o None
	"""
	config_fiscal = _obtener_config_fiscal(company)
	if not config_fiscal:
		return None

	for mapeo in config_fiscal.mapeo_cuentas:
		if mapeo.cuenta_impuesto == account_head:
			return {
				"tipo_factor": mapeo.get("tipo_factor", "Tasa"),
				"integra_base_iva": bool(mapeo.get("integra_base_iva", 1)),
				"rol_fiscal": mapeo.rol_fiscal,
				"es_retencion": bool(mapeo.get("es_retencion", 0)),
			}

	return None


# =============================================================================
# HELPERS - DETECCIÓN ITEMS QUE CONTRIBUYEN
# =============================================================================


def _item_contribuye_a_cuenta_ieps(item, account_head: str) -> bool:
	"""
	Verificar si un item contribuye a una cuenta IEPS específica.

	Paso A (canónico): Verificar si ITT del item incluye esta cuenta
	Paso B (fallback): Verificar si item tiene cuota vigente para esta cuenta

	Args:
		item: Sales Invoice Item row
		account_head: Cuenta IEPS a verificar

	Returns:
		bool: True si el item contribuye a esta cuenta
	"""
	# Paso A: Verificar ITT del item
	if item.get("item_tax_template"):
		try:
			itt = frappe.get_doc("Item Tax Template", item.item_tax_template)
			for itt_tax in itt.taxes:
				# itt_tax.tax_type contiene la cuenta
				if itt_tax.tax_type == account_head:
					return True
		except Exception:
			pass  # ITT no existe o error, continuar con Paso B

	# Paso B: Fallback - verificar si tiene cuota vigente
	# (se implementará en _get_cuota_prioridad)
	return False


# =============================================================================
# HELPERS - PRIORIDAD FUENTES CUOTA
# =============================================================================


def _get_cuota_prioridad(item, account_head: str, doc) -> float:
	"""
	Obtener cuota IEPS con prioridad de fuentes.

	Prioridad:
	P1: Item.fm_ieps_cuota_unitaria (override explícito)
	P2: Tabla IEPS Cuota SAT (vigente, por clave SAT + UOM)
	P3: Error en prod, constante en test (solo desarrollo)

	Args:
		item: Sales Invoice Item row
		account_head: Cuenta IEPS
		doc: Sales Invoice document

	Returns:
		float: Cuota por unidad o 0 si no encontrada

	Raises:
		frappe.ValidationError: Si no hay cuota en producción
	"""
	# P1: Custom field en Item
	cuota_item = flt(item.get("fm_ieps_cuota_unitaria", 0))
	if cuota_item > 0:
		return cuota_item

	# P2: Tabla IEPS Cuota SAT
	item_sat = frappe.db.get_value("Item", item.item_code, "fm_producto_servicio_sat")
	if item_sat:
		# Usar SQL para manejar IFNULL en vigencia_hasta
		cuota_sat = frappe.db.sql(
			"""
			SELECT cuota
			FROM `tabIEPS Cuota SAT`
			WHERE company = %(company)s
			  AND clave_prod_serv = %(clave_prod_serv)s
			  AND uom = %(uom)s
			  AND cuenta_ieps = %(cuenta_ieps)s
			  AND vigencia_desde <= %(fecha)s
			  AND IFNULL(vigencia_hasta, '2099-12-31') >= %(fecha)s
			  AND docstatus < 2
			LIMIT 1
			""",
			{
				"company": doc.company,
				"clave_prod_serv": item_sat,
				"uom": item.uom,
				"cuenta_ieps": account_head,
				"fecha": today(),
			},
		)

		if cuota_sat and cuota_sat[0][0]:
			return flt(cuota_sat[0][0])

	# P3: Error en prod, constante en desarrollo
	if not frappe.conf.get("developer_mode"):
		frappe.throw(
			f"No se encontró cuota IEPS vigente para item {item.item_code} (Clave SAT: {item_sat or 'NO CONFIG'}, UOM: {item.uom}). "
			f"Configure en: IEPS Cuota SAT",
			title="Cuota IEPS No Encontrada",
		)

	# Constante desarrollo (solo para tests)
	return 0.0


# =============================================================================
# HOOK PRINCIPAL - VALIDATE
# =============================================================================


def calcular_ieps_cuota(doc, method=None):
	"""
	Hook validate: Detectar y calcular tax rows IEPS Cuota.

	Flujo:
	1. Identificar tax rows con tipo_factor="Cuota" (desde Mapeo Fiscal)
	2. Para cada tax row IEPS Cuota:
	   - Identificar items que contribuyen (ITT o cuota vigente)
	   - Calcular: qty x cuota (con validación UOM)
	   - Sumar total IEPS
	   - Guardar distribución por item

	Args:
		doc: Sales Invoice document
		method: Hook method name (no usado)
	"""
	if not doc.taxes or not doc.items:
		return

	# Identificar tax rows IEPS Cuota
	for tax_row in doc.taxes:
		metadata = _obtener_metadata_cuenta(tax_row.account_head, doc.company)

		if not metadata or metadata["tipo_factor"] != "Cuota":
			continue  # No es IEPS Cuota, skip

		# Esta tax row es IEPS Cuota, recalcular amount
		total_ieps = 0
		distribucion_items = {}  # {item.name: [rate, amount]}

		for item in doc.items:
			# Verificar si item contribuye a esta cuenta IEPS
			if not _item_contribuye_a_cuenta_ieps(item, tax_row.account_head):
				# Fallback: si tiene cuota vigente, contribuye
				cuota = _get_cuota_prioridad(item, tax_row.account_head, doc)
				if cuota <= 0:
					continue  # No contribuye

			else:
				# Item contribuye, obtener cuota
				cuota = _get_cuota_prioridad(item, tax_row.account_head, doc)
				if cuota <= 0:
					frappe.throw(
						f"Item {item.item_code} usa IEPS Cuota pero no tiene cuota configurada",
						title="Cuota IEPS Faltante",
					)

			# Calcular IEPS para este item
			# TODO: Validar UOM y aplicar conversiones si es necesario
			qty = flt(item.qty)
			item_ieps = qty * cuota
			total_ieps += item_ieps

			# Guardar distribución (para item_wise_tax_detail)
			# E4-RO: Para IEPS Cuota, rate=cuota_unitaria (no 0!)
			# Formato: [cuota_por_unidad, monto_total]
			distribucion_items[item.name] = [cuota, item_ieps]

		# Actualizar tax row
		tax_row.charge_type = "Actual"
		tax_row.rate = None  # No aplica para Actual
		tax_row.tax_amount = flt(total_ieps, 2)

		# Guardar item_wise_tax_detail (CRÍTICO para E4)
		if distribucion_items:
			tax_row.item_wise_tax_detail = json.dumps(distribucion_items)


# =============================================================================
# HOOK SECUNDARIO - BEFORE_SAVE
# =============================================================================


def ajustar_base_iva_combustibles(doc, method=None):
	"""
	Hook before_save: Ajustar base IVA para IEPS que no integran base.

	Se ejecuta después de calcular_ieps_cuota() para ajustar base IVA
	de filas que tienen IEPS con integra_base_iva=0 (combustibles).

	Args:
		doc: Sales Invoice document
		method: Hook method (no usado)

	Lógica:
		- Combustibles: IEPS NO integra base IVA (LIEPS Art. 2-A)
		- Bebidas: IEPS SÍ integra base IVA (regla general)

	Flujo:
		1. Identificar filas IEPS con integra_base_iva=0
		2. Sumar total IEPS no integrable
		3. Reducir base IVA proporcionalmente en filas IVA
	"""
	if not doc.taxes:
		return

	# Construir mapa cuenta → metadata
	cuenta_metadata = {}
	config_fiscal = _obtener_config_fiscal(doc.company)

	if not config_fiscal:
		return

	for mapeo in config_fiscal.mapeo_cuentas:
		cuenta_metadata[mapeo.cuenta_impuesto] = {
			"integra_base_iva": bool(mapeo.get("integra_base_iva", 1)),
			"rol_fiscal": mapeo.rol_fiscal,
			"tipo_factor": mapeo.get("tipo_factor", "Tasa"),
		}

	# Identificar total IEPS que NO integra base IVA
	total_ieps_no_integra = 0.0

	for tax_row in doc.taxes:
		metadata = cuenta_metadata.get(tax_row.account_head)

		if not metadata:
			continue

		# Verificar si es IEPS Cuota que no integra base IVA
		if metadata["tipo_factor"] == "Cuota" and not metadata["integra_base_iva"]:
			tax_amount = flt(tax_row.tax_amount, 2)
			total_ieps_no_integra += tax_amount

	# Si no hay IEPS no integrable, no hacer nada
	if total_ieps_no_integra <= 0:
		return

	# Ajustar base IVA en todas las filas IVA
	# Nota: Esta lógica puede necesitar refinamiento según cómo ERPNext
	# calcula las bases en tax rows con charge_type diferentes
	# Por ahora, registramos el ajuste para que el payload lo use

	# TODO: Implementar ajuste real de base IVA
	# Esto puede requerir modificar item_wise_tax_detail de filas IVA
	# o usar un campo custom temporal para guardar el ajuste
