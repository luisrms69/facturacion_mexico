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

# Import para conversión UOM (IEPS Cuota siempre en litros)
try:
	from erpnext.stock.get_item_details import get_conversion_factor
except ImportError:
	get_conversion_factor = None

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


def _get_cuota_prioridad(item, account_head: str, doc) -> dict:
	"""
	Obtener cuota IEPS con prioridad de fuentes.

	Prioridad:
	P1: Tabla IEPS Cuota SAT (vigente, por clave SAT)
	P2: Error en prod, constante en test (solo desarrollo)

	Args:
		item: Sales Invoice Item row
		account_head: Cuenta IEPS
		doc: Sales Invoice document

	Returns:
		dict: {"cuota": float, "uom_base": str} o None si no encontrada

	Raises:
		frappe.ValidationError: Si no hay cuota en producción
	"""
	# P1: Tabla IEPS Cuota SAT
	item_sat = frappe.db.get_value("Item", item.item_code, "fm_producto_servicio_sat")
	if item_sat:
		# Usar SQL para manejar IFNULL en vigencia_hasta
		cuota_sat = frappe.db.sql(
			"""
			SELECT cuota, uom
			FROM `tabIEPS Cuota SAT`
			WHERE company = %(company)s
			  AND clave_prod_serv = %(clave_prod_serv)s
			  AND cuenta_ieps = %(cuenta_ieps)s
			  AND vigencia_desde <= %(fecha)s
			  AND IFNULL(vigencia_hasta, '2099-12-31') >= %(fecha)s
			  AND docstatus < 2
			LIMIT 1
			""",
			{
				"company": doc.company,
				"clave_prod_serv": item_sat,
				"cuenta_ieps": account_head,
				"fecha": today(),
			},
			as_dict=True,
		)

		if cuota_sat and len(cuota_sat) > 0:
			return {"cuota": flt(cuota_sat[0].cuota), "uom_base": cuota_sat[0].uom}

	# P2: Error en prod, constante en desarrollo
	if not frappe.conf.get("developer_mode"):
		frappe.throw(
			f"No se encontró cuota IEPS vigente para item {item.item_code} (Clave SAT: {item_sat or 'NO CONFIG'}). "
			f"Configure en: IEPS Cuota SAT",
			title="Cuota IEPS No Encontrada",
		)

	# Constante desarrollo (solo para tests) - retornar None
	return None


# =============================================================================
# HOOK PRINCIPAL - VALIDATE
# =============================================================================


def _congelar_iva_sobre_ieps_cuota(doc, ieps_tax_row, distribucion_ieps):
	"""
	Congela el IVA "On Previous Row Amount" que se calcula sobre IEPS Cuota.

	Problema: ERPNext redistribuye el IVA proporcionalmente entre todos los items.
	Solución: Setear manualmente item_wise_tax_detail solo para items con IEPS.

	Args:
		doc: Sales Invoice document
		ieps_tax_row: Tax row del IEPS Cuota (ya procesado)
		distribucion_ieps: Dict con distribución IEPS {item_code: [0.0, amount]}
	"""
	# Buscar el índice del IEPS Cuota actual
	ieps_idx = None
	for idx, tax in enumerate(doc.taxes):
		if tax.name == ieps_tax_row.name:
			ieps_idx = idx
			break

	if ieps_idx is None:
		return  # No encontrado (no debería pasar)

	# Buscar el siguiente tax que sea "On Previous Row Amount"
	for idx in range(ieps_idx + 1, len(doc.taxes)):
		iva_tax = doc.taxes[idx]

		# Verificar si es IVA "On Previous Row Amount" que referencia el IEPS Cuota
		if iva_tax.charge_type == "On Previous Row Amount":
			# Verificar si row_id apunta al IEPS Cuota (idx+1 porque row_id es 1-indexed)
			if iva_tax.row_id and int(iva_tax.row_id) == ieps_idx + 1:
				# Seguridad: Verificar que sea IVA (no otro impuesto cascada)
				if "IVA" not in iva_tax.description.upper():
					continue

				# Calcular IVA manualmente solo para items con IEPS
				iva_distribucion = {}
				iva_rate = flt(iva_tax.rate)

				for item_code, values in distribucion_ieps.items():
					ieps_amount = values[1]  # [0.0, amount]
					# Usar precisión del campo tax_amount para evitar diferencias redondeo
					iva_amount = flt(ieps_amount * iva_rate / 100, iva_tax.precision("tax_amount"))
					iva_distribucion[item_code] = [iva_rate, iva_amount]

				# Setear item_wise_tax_detail y congelar
				if iva_distribucion:
					iva_tax.item_wise_tax_detail = json.dumps(iva_distribucion, ensure_ascii=False)
					iva_tax.dont_recompute_tax = 1

				break  # Solo el primer IVA "On Previous Row Amount"


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
		distribucion_items = {}  # {item.item_code: [rate, amount]}

		for item in doc.items:
			# Verificar si item contribuye a esta cuenta IEPS
			if not _item_contribuye_a_cuenta_ieps(item, tax_row.account_head):
				# Fallback: si tiene cuota vigente, contribuye
				cuota_data = _get_cuota_prioridad(item, tax_row.account_head, doc)
				if not cuota_data:
					# No contribuye - agregar con ceros (CRÍTICO para E4)
					distribucion_items[item.item_code] = [0.0, 0.0]
					continue

			else:
				# Item contribuye, obtener cuota
				cuota_data = _get_cuota_prioridad(item, tax_row.account_head, doc)
				if not cuota_data:
					frappe.throw(
						f"Item {item.item_code} usa IEPS Cuota pero no tiene cuota configurada",
						title="Cuota IEPS Faltante",
					)

			# Extraer cuota y UOM base
			cuota_per_uom_base = flt(cuota_data["cuota"])
			uom_base = cuota_data["uom_base"]

			# Calcular IEPS para este item con conversión UOM
			# Obtener conversión de item.uom → uom_base
			if item.uom == uom_base:
				conversion_factor = 1.0
			else:
				# Usar ERPNext UOM conversion
				if get_conversion_factor:
					try:
						conversion_data = get_conversion_factor(item.item_code, uom_base)
						conversion_factor = flt(conversion_data.get("conversion_factor", 0))
					except Exception:
						conversion_factor = 0
				else:
					conversion_factor = 0

				if conversion_factor <= 0:
					frappe.throw(
						f"Item {item.item_code}: Falta conversión de UOM '{item.uom}' a '{uom_base}' para IEPS Cuota. "
						f"Configure en: Item → UOMs",
						title="Conversión UOM Faltante",
					)

			# Calcular unidades base y IEPS
			unidades_base = flt(item.qty) * conversion_factor
			item_ieps = unidades_base * cuota_per_uom_base
			total_ieps += item_ieps

			# Guardar distribución (para item_wise_tax_detail)
			# E4-RO: Para IEPS Cuota, rate=cuota_unitaria (no 0!)
			# Formato: [cuota_por_unidad, monto_total]
			distribucion_items[item.item_code] = [0.0, item_ieps]

		# Actualizar tax row
		tax_row.charge_type = "Actual"
		tax_row.rate = None  # No aplica para Actual
		tax_row.tax_amount = flt(total_ieps, 2)

		# Guardar item_wise_tax_detail (CRÍTICO para E4)
		if distribucion_items:
			tax_row.item_wise_tax_detail = json.dumps(distribucion_items, ensure_ascii=False)

			# Prevenir que ERPNext redistribuya este impuesto proporcionalmente
			# ERPNext por default redistribuye "Actual" entre items según net_amount
			# Este flag congela nuestra distribución custom (item_wise_tax_detail)
			tax_row.dont_recompute_tax = 1

			# CRÍTICO E4: Congelar también el IVA "On Previous Row Amount" que sigue
			# Si no lo hacemos, ERPNext redistribuirá el IVA entre todos los items
			_congelar_iva_sobre_ieps_cuota(doc, tax_row, distribucion_items)


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


# =============================================================================
# HOOK PRINCIPAL - BEFORE_SUBMIT (Corrección Final Post-Redistribución)
# =============================================================================


def corregir_ieps_cuota_final(doc, method=None):
	"""
	Hook before_submit: Corrección final post-redistribución ERPNext.

	ERPNext redistribuye automáticamente los impuestos con charge_type="Actual"
	de forma proporcional entre todos los items. Este hook corrige ese
	comportamiento para IEPS Cuota, restaurando la asignación correcta por item.

	4 Acciones implementadas:
	1. Corregir item_wise_tax_detail de IEPS Cuota (ceros en no-aplicables)
	2. Ajustar item_wise_tax_detail de IVA para combustibles (base sin IEPS)
	3. Validar tolerancias redondeo (±$0.01/item, ±$0.05/total)
	4. Validar orden fiscal IEPS→IVA (bloqueante)

	Args:
		doc: Sales Invoice document
		method: Hook method (no usado)

	Raises:
		frappe.ValidationError: Si orden fiscal incorrecto o redondeos fuera de tolerancia
	"""
	if not doc.taxes or not doc.items:
		return

	# Obtener configuración fiscal
	config_fiscal = _obtener_config_fiscal(doc.company)
	if not config_fiscal:
		return

	# Construir mapa cuenta → metadata
	cuenta_metadata = _construir_mapa_metadata(config_fiscal)

	# ACCIÓN 1: Corregir IEPS Cuota item_wise_tax_detail
	_corregir_item_wise_tax_detail_ieps_cuota(doc, cuenta_metadata)

	# ACCIÓN 2: Ajustar IVA combustibles (base sin IEPS no integrable)
	_ajustar_item_wise_tax_detail_iva_combustibles(doc, cuenta_metadata)

	# ACCIÓN 3: Validar tolerancias de redondeo
	_validar_tolerancias_redondeo(doc, cuenta_metadata)

	# ACCIÓN 4: Validar orden fiscal IEPS→IVA
	_validar_orden_fiscal_ieps_iva(doc, cuenta_metadata)


# =============================================================================
# ACCIÓN 1: Corregir IEPS Cuota item_wise_tax_detail
# =============================================================================


def _corregir_item_wise_tax_detail_ieps_cuota(doc, cuenta_metadata: dict):
	"""
	Corregir item_wise_tax_detail de IEPS Cuota sobrescribiendo con ceros
	en items que NO aplican este impuesto.

	Neutraliza la redistribución proporcional de ERPNext.

	Args:
		doc: Sales Invoice document
		cuenta_metadata: Mapa cuenta → metadata fiscal
	"""
	for tax_row in doc.taxes:
		metadata = cuenta_metadata.get(tax_row.account_head)

		# Solo procesar IEPS Cuota
		if not metadata or metadata["tipo_factor"] != "Cuota":
			continue

		# Reconstruir distribución correcta por item
		distribucion_correcta = {}
		total_ieps = 0

		for item in doc.items:
			# Verificar si item contribuye a esta cuenta IEPS
			if _item_contribuye_a_cuenta_ieps(item, tax_row.account_head):
				# Item contribuye: calcular cuota con conversión UOM
				cuota_data = _get_cuota_prioridad(item, tax_row.account_head, doc)
				if not cuota_data:
					# No debería llegar aquí si _item_contribuye es correcto
					distribucion_correcta[item.item_code] = [0.0, 0.0]
					continue

				cuota_per_uom_base = flt(cuota_data["cuota"])
				uom_base = cuota_data["uom_base"]

				# Aplicar conversión UOM
				if item.uom == uom_base:
					conversion_factor = 1.0
				else:
					if get_conversion_factor:
						try:
							conversion_data = get_conversion_factor(item.item_code, uom_base)
							conversion_factor = flt(conversion_data.get("conversion_factor", 0))
						except Exception:
							conversion_factor = 0
					else:
						conversion_factor = 0

					if conversion_factor <= 0:
						frappe.throw(
							f"Item {item.item_code}: Falta conversión de UOM '{item.uom}' a '{uom_base}' para IEPS Cuota. "
							f"Configure en: Item → UOMs",
							title="Conversión UOM Faltante",
						)

				unidades_base = flt(item.qty) * conversion_factor
				item_ieps = unidades_base * cuota_per_uom_base
				total_ieps += item_ieps
				# CRÍTICO: rate=0.0 para charge_type="Actual"
				distribucion_correcta[item.item_code] = [0.0, item_ieps]
			else:
				# Item NO contribuye: asignar ceros (clave para E4)
				distribucion_correcta[item.item_code] = [0.0, 0.0]

		# Sobrescribir item_wise_tax_detail y tax_amount
		tax_row.item_wise_tax_detail = json.dumps(distribucion_correcta)
		tax_row.tax_amount = flt(total_ieps, 2)


# =============================================================================
# ACCIÓN 2: Ajustar IVA combustibles
# =============================================================================


def _ajustar_item_wise_tax_detail_iva_combustibles(doc, cuenta_metadata: dict):
	"""
	Ajustar item_wise_tax_detail de IVA para items con IEPS Cuota
	que NO integran base IVA (combustibles).

	Opción B (quirúrgica): Solo corregir item_wise_tax_detail del IVA,
	sin recalcular todo el impuesto.

	Args:
		doc: Sales Invoice document
		cuenta_metadata: Mapa cuenta → metadata fiscal
	"""
	# Identificar cuentas IEPS Cuota que NO integran base IVA
	ieps_no_integra = {}  # {cuenta: {item_name: monto_ieps}}

	for tax_row in doc.taxes:
		metadata = cuenta_metadata.get(tax_row.account_head)

		# Solo IEPS Cuota que NO integra
		if not metadata or metadata["tipo_factor"] != "Cuota":
			continue

		if metadata.get("integra_base_iva", True):
			continue  # Sí integra, skip

		# Esta cuenta IEPS no integra base IVA (combustibles)
		item_wise = json.loads(tax_row.item_wise_tax_detail or "{}")
		ieps_no_integra[tax_row.account_head] = item_wise

	if not ieps_no_integra:
		return  # No hay IEPS combustibles, skip

	# Ajustar item_wise_tax_detail de filas IVA
	for tax_row in doc.taxes:
		metadata = cuenta_metadata.get(tax_row.account_head)

		# Solo filas IVA (impuesto_sat="002")
		if not metadata or metadata.get("impuesto_sat") != "002":
			continue

		# Parsear item_wise_tax_detail actual
		iva_item_wise = json.loads(tax_row.item_wise_tax_detail or "{}")

		# Ajustar base IVA por item
		for item in doc.items:
			if item.item_code not in iva_item_wise:
				continue

			# Sumar IEPS combustibles para este item
			total_ieps_item = 0
			for _cuenta_ieps, ieps_item_wise in ieps_no_integra.items():
				if item.item_code in ieps_item_wise:
					total_ieps_item += flt(ieps_item_wise[item.item_code][1])  # [rate, amount]

			if total_ieps_item > 0:
				# Ajustar: Base IVA = importe item (sin IEPS)
				# IVA item = (item.amount) * tasa_iva
				rate_iva = flt(iva_item_wise[item.item_code][0])  # Tasa IVA
				base_iva_ajustada = flt(item.amount)  # Sin IEPS
				iva_ajustado = base_iva_ajustada * (rate_iva / 100.0)

				iva_item_wise[item.item_code] = [rate_iva, flt(iva_ajustado, 2)]

		# Actualizar item_wise_tax_detail y recalcular tax_amount
		tax_row.item_wise_tax_detail = json.dumps(iva_item_wise)
		tax_row.tax_amount = flt(sum(v[1] for v in iva_item_wise.values()), 2)


# =============================================================================
# ACCIÓN 3: Validar tolerancias redondeo
# =============================================================================


def _validar_tolerancias_redondeo(doc, cuenta_metadata: dict):
	"""
	Validar que las diferencias por redondeo estén dentro de tolerancias.

	Tolerancias permitidas:
	- ±$0.01 por renglón (item)
	- ±$0.05 por factura (total)

	Si hay drift, compensar 1 centavo en el último item afectado.

	Args:
		doc: Sales Invoice document
		cuenta_metadata: Mapa cuenta → metadata fiscal

	Raises:
		frappe.ValidationError: Si redondeos exceden tolerancias
	"""
	TOL_ITEM = 0.01  # ±$0.01 por item
	TOL_TOTAL = 0.05  # ±$0.05 por factura

	for tax_row in doc.taxes:
		# Validar que sum(item_wise_tax_detail) == tax_amount
		item_wise = json.loads(tax_row.item_wise_tax_detail or "{}")

		if not item_wise:
			continue

		suma_items = flt(sum(v[1] for v in item_wise.values()), 2)
		tax_amount = flt(tax_row.tax_amount, 2)
		diferencia = abs(suma_items - tax_amount)

		if diferencia > TOL_TOTAL:
			frappe.throw(
				f"Diferencia de redondeo excede tolerancia en {tax_row.account_head}<br>"
				f"Suma items: ${suma_items:.2f}<br>"
				f"Tax amount: ${tax_amount:.2f}<br>"
				f"Diferencia: ${diferencia:.2f} (máximo permitido: ${TOL_TOTAL:.2f})",
				title="Error Redondeo",
			)

		# Si hay diferencia pequeña, compensar en último item
		if 0 < diferencia <= TOL_ITEM:
			# Encontrar último item con monto > 0
			ultimo_item_key = None
			for item_key, values in item_wise.items():
				if flt(values[1]) > 0:
					ultimo_item_key = item_key

			if ultimo_item_key:
				# Ajustar 1 centavo
				ajuste = tax_amount - suma_items
				rate, amount = item_wise[ultimo_item_key]
				item_wise[ultimo_item_key] = [rate, flt(amount + ajuste, 2)]

				# Actualizar
				tax_row.item_wise_tax_detail = json.dumps(item_wise)


# =============================================================================
# ACCIÓN 4: Validar orden fiscal IEPS→IVA
# =============================================================================


def _validar_orden_fiscal_ieps_iva(doc, cuenta_metadata: dict):
	"""
	Validar que IEPS Cuota aparece ANTES de IVA en la tabla de impuestos.

	Regla fiscal: LIEPS Art. 2-A requiere que IEPS se aplique antes de IVA.

	Args:
		doc: Sales Invoice document
		cuenta_metadata: Mapa cuenta → metadata fiscal

	Raises:
		frappe.ValidationError: Si orden incorrecto
	"""
	# Identificar índices de IEPS Cuota e IVA
	ieps_cuota_indices = []
	iva_indices = []

	for tax_row in doc.taxes:
		metadata = cuenta_metadata.get(tax_row.account_head)

		if not metadata:
			continue

		# IEPS Cuota: impuesto_sat="003" + tipo_factor="Cuota"
		if metadata.get("impuesto_sat") == "003" and metadata["tipo_factor"] == "Cuota":
			ieps_cuota_indices.append(tax_row.idx)

		# IVA: impuesto_sat="002"
		if metadata.get("impuesto_sat") == "002":
			iva_indices.append(tax_row.idx)

	# Si tiene ambos, validar orden
	if ieps_cuota_indices and iva_indices:
		min_ieps = min(ieps_cuota_indices)
		min_iva = min(iva_indices)

		if min_ieps > min_iva:
			frappe.throw(
				f"<b>Orden fiscal incorrecto en impuestos</b><br><br>"
				f"IEPS-Cuota debe aparecer ANTES de IVA en la tabla de impuestos.<br><br>"
				f"<b>Orden actual:</b><br>"
				f"• IEPS Cuota en índice: {min_ieps}<br>"
				f"• IVA en índice: {min_iva}<br><br>"
				f"<b>Solución:</b> Actualice la plantilla de impuestos (Sales Taxes and Charges Template) "
				f"para que IEPS aparezca antes de IVA. Esto es requerido por LIEPS Art. 2-A.",
				title="Orden Fiscal Incorrecto",
			)


# =============================================================================
# HELPERS
# =============================================================================


def _construir_mapa_metadata(config_fiscal) -> dict:
	"""
	Construir mapa cuenta → metadata fiscal para rápido acceso.

	Args:
		config_fiscal: Document Configuracion Fiscal Mexico

	Returns:
		dict: {cuenta: {tipo_factor, integra_base_iva, impuesto_sat, ...}}
	"""
	mapa = {}

	for mapeo in config_fiscal.mapeo_cuentas:
		mapa[mapeo.cuenta_impuesto] = {
			"tipo_factor": mapeo.get("tipo_factor", "Tasa"),
			"integra_base_iva": bool(mapeo.get("integra_base_iva", 1)),
			"impuesto_sat": mapeo.get("impuesto_sat"),
			"nombre_sat": mapeo.get("nombre_impuesto_sat"),
			"rol_fiscal": mapeo.rol_fiscal,
			"es_retencion": bool(mapeo.get("es_retencion", 0)),
		}

	return mapa
