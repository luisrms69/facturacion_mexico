"""
Función Rectora - Cálculos Fiscales México
==========================================
Implementación única centralizada para cálculo de impuestos.

Fuente de verdad: reglas_calculo_fiscal.py (tabla maestra)
Reemplaza lógica dispersa en hooks (sales_invoice_ieps.py)

Arquitectura:
- aplicar_reglas_calculo_impuestos() - Función rectora principal
- _obtener_base() - Extrae base según regla_base
- _calcular_monto() - Calcula monto según regla_calculo
- _calcular_porcentual() - Cálculo porcentual (base x tasa / 100)
- _calcular_cuota() - Cálculo cuota (cantidad x cuota_unitaria)
- _calcular_retencion() - Cálculo retención (base x tasa / 100)

Uso desde hooks:
	from facturacion_mexico.utils.calculo_impuestos import aplicar_reglas_calculo_impuestos

	# Hook validate (antes de cálculo ERPNext)
	metadata = {
		"rol_fiscal": "IVA por Pagar (Nacional)",
		"tipo_factor": "Tasa",
		"tasa": 16.0,  # Para porcentual/retención
		"cuota_unitaria": 1.50  # Para cuota
	}
	monto = aplicar_reglas_calculo_impuestos(doc, tax_row, metadata)

Migración desde código existente:
	# ANTES (hardcoded en sales_invoice_ieps.py):
	# if metadata["tipo_factor"] == "Cuota":
	#     monto = item.qty * cuota_unitaria
	# else:
	#     monto = item.net_amount * (tasa / 100)

	# DESPUÉS (función rectora):
	monto = aplicar_reglas_calculo_impuestos(doc, tax_row, metadata)
"""

import frappe
from frappe.utils import flt


def aplicar_reglas_calculo_impuestos(doc, tax_row, metadata: dict) -> float:
	"""
	Función rectora única para aplicar reglas de cálculo fiscal.

	Lee reglas desde tabla maestra (reglas_calculo_fiscal.py) y aplica
	cálculo según configuración por rol_fiscal.

	Args:
		doc: Sales Invoice document
		tax_row: Tax row del documento (Sales Taxes and Charges)
		metadata: Diccionario con metadata fiscal
			{
				"rol_fiscal": str,          # Nombre exacto rol fiscal
				"tipo_factor": str,         # "Tasa" o "Cuota"
				"tasa": float,              # Para porcentual/retención (opcional)
				"cuota_unitaria": float,    # Para cuota (opcional)
				"integra_base_iva": bool    # Control integración base IVA
			}

	Returns:
		float: Monto calculado según reglas (redondeado 2 decimales)
			   0.0 si no hay regla o está deshabilitada

	Raises:
		frappe.ValidationError: Si faltan parámetros requeridos para el cálculo

	Examples:
		>>> # IVA Nacional 16% (porcentual)
		>>> metadata = {"rol_fiscal": "IVA por Pagar (Nacional)", "tasa": 16.0}
		>>> monto = aplicar_reglas_calculo_impuestos(doc, tax_row, metadata)

		>>> # IEPS Tabaco Cuota (cuota)
		>>> metadata = {"rol_fiscal": "IEPS por Pagar (Tabaco Cuota)", "cuota_unitaria": 0.35}
		>>> monto = aplicar_reglas_calculo_impuestos(doc, tax_row, metadata)

		>>> # Retención IVA Honorarios (retención)
		>>> metadata = {"rol_fiscal": "IVA Retenido (Honorarios)", "tasa": 66.67}
		>>> monto = aplicar_reglas_calculo_impuestos(doc, tax_row, metadata)
	"""
	from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo

	rol_fiscal = metadata.get("rol_fiscal")

	if not rol_fiscal:
		frappe.logger().warning("[FMX][Cálculo] metadata sin rol_fiscal, skipping")
		return 0.0

	# Obtener reglas desde tabla maestra
	reglas = obtener_regla_calculo(rol_fiscal)

	if not reglas:
		frappe.logger().warning(f"[FMX][Cálculo] Sin regla para {rol_fiscal}, bypass graceful")
		return 0.0

	if not reglas["habilitada"]:
		frappe.logger().info(f"[FMX][Cálculo] Regla {rol_fiscal} deshabilitada, skipping")
		return 0.0

	# Cache reglas en frappe.local para performance (evitar lookups repetidos)
	if not hasattr(frappe.local, "reglas_fiscales_cache"):
		from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_reglas_activas

		frappe.local.reglas_fiscales_cache = obtener_reglas_activas()

	# Obtener base según regla_base
	base = _obtener_base(doc, tax_row, reglas, metadata)

	if base is None or base < 0:
		frappe.logger().warning(f"[FMX][Cálculo] Base inválida ({base}) para {rol_fiscal}, retornando 0")
		return 0.0

	# Calcular monto según regla_calculo
	monto = _calcular_monto(base, reglas, metadata)

	# Redondear a 2 decimales (precisión ERPNext para currency)
	return flt(monto, 2)


def _obtener_base(doc, tax_row, reglas: dict, metadata: dict) -> float:
	"""
	Obtiene la base de cálculo según regla_base.

	Args:
		doc: Sales Invoice document
		tax_row: Tax row actual
		reglas: Diccionario con reglas de cálculo
		metadata: Metadata adicional

	Returns:
		float: Base de cálculo
			   None si no se puede determinar

	Reglas soportadas:
		- monto_neto: Suma net_amount de todos los items
		- cantidad: Suma qty de todos los items
		- fila_previa_monto: Monto de fila anterior (tax_amount)
		- fila_previa_total: Total acumulado hasta fila anterior
		- iva_trasladado: IVA trasladado del documento (para retenciones)
	"""
	regla_base = reglas["regla_base"]

	# ==========================================
	# CASO 1: monto_neto (más común)
	# ==========================================
	if regla_base == "monto_neto":
		# Suma net_amount de todos los items
		total = 0.0
		for item in doc.items:
			total += flt(item.net_amount, 2)
		return total

	# ==========================================
	# CASO 2: cantidad (para cuotas)
	# ==========================================
	elif regla_base == "cantidad":
		# Suma qty de todos los items
		total = 0.0
		for item in doc.items:
			total += flt(item.qty, 6)  # qty con 6 decimales
		return total

	# ==========================================
	# CASO 3: iva_trasladado (para retenciones IVA)
	# ==========================================
	elif regla_base == "iva_trasladado":
		# Buscar filas IVA en taxes y sumar tax_amount
		total_iva = 0.0

		for tax in doc.taxes:
			# Identificar si es IVA (Nacional o Frontera)
			# TODO: Mejorar detección usando metadata en lugar de nombre cuenta
			account_name = str(tax.account_head or "").lower()
			if "iva" in account_name and "retenid" not in account_name:
				total_iva += flt(tax.tax_amount, 2)

		return total_iva

	# ==========================================
	# CASO 4: fila_previa_monto (IVA cascada sobre IEPS)
	# ==========================================
	elif regla_base == "fila_previa_monto":
		# Obtener tax_amount de la fila inmediatamente anterior
		idx = _get_tax_row_index(doc, tax_row)

		if idx is None or idx == 0:
			frappe.logger().warning("[FMX][Cálculo] fila_previa_monto solicitada pero no hay fila anterior")
			return 0.0

		fila_anterior = doc.taxes[idx - 1]
		return flt(fila_anterior.tax_amount, 2)

	# ==========================================
	# CASO 5: fila_previa_total (total acumulado)
	# ==========================================
	elif regla_base == "fila_previa_total":
		# Total acumulado hasta fila anterior
		idx = _get_tax_row_index(doc, tax_row)

		if idx is None or idx == 0:
			frappe.logger().warning("[FMX][Cálculo] fila_previa_total solicitada pero no hay fila anterior")
			return 0.0

		fila_anterior = doc.taxes[idx - 1]
		return flt(fila_anterior.total, 2)

	# ==========================================
	# CASO DEFAULT: No soportado
	# ==========================================
	else:
		frappe.logger().error(f"[FMX][Cálculo] regla_base '{regla_base}' no soportada")
		return None


def _calcular_monto(base: float, reglas: dict, metadata: dict) -> float:
	"""
	Calcula monto del impuesto según regla_calculo.

	Args:
		base: Base de cálculo
		reglas: Diccionario con reglas de cálculo
		metadata: Metadata con tasa/cuota

	Returns:
		float: Monto calculado

	Reglas soportadas:
		- porcentual: base x tasa / 100
		- cuota: cantidad x cuota_unitaria
		- retención: base x tasa_retención / 100
	"""
	regla_calculo = reglas["regla_calculo"]

	# ==========================================
	# CASO 1: porcentual (IVA, IEPS Tasa)
	# ==========================================
	if regla_calculo == "porcentual":
		tasa = metadata.get("tasa")

		if tasa is None:
			frappe.throw(
				f"[FMX][Cálculo] Falta 'tasa' en metadata para regla_calculo='porcentual' ({reglas.get('rol_fiscal')})"
			)

		return _calcular_porcentual(base, tasa)

	# ==========================================
	# CASO 2: cuota (IEPS Cuota)
	# ==========================================
	elif regla_calculo == "cuota":
		cuota_unitaria = metadata.get("cuota_unitaria")

		if cuota_unitaria is None:
			frappe.throw(
				f"[FMX][Cálculo] Falta 'cuota_unitaria' en metadata para regla_calculo='cuota' ({reglas.get('rol_fiscal')})"
			)

		return _calcular_cuota(base, cuota_unitaria)

	# ==========================================
	# CASO 3: retención (IVA/ISR retenido)
	# ==========================================
	elif regla_calculo == "retención":
		tasa_retencion = metadata.get("tasa")

		if tasa_retencion is None:
			frappe.throw(
				f"[FMX][Cálculo] Falta 'tasa' en metadata para regla_calculo='retención' ({reglas.get('rol_fiscal')})"
			)

		return _calcular_retencion(base, tasa_retencion)

	# ==========================================
	# CASO DEFAULT: No soportado
	# ==========================================
	else:
		frappe.logger().error(f"[FMX][Cálculo] regla_calculo '{regla_calculo}' no soportada")
		return 0.0


def _calcular_porcentual(base: float, tasa: float) -> float:
	"""
	Cálculo porcentual: base x tasa / 100.

	Args:
		base: Base de cálculo
		tasa: Tasa porcentual (ej: 16.0 para 16%)

	Returns:
		float: Monto calculado

	Examples:
		>>> _calcular_porcentual(1000.0, 16.0)
		160.0
		>>> _calcular_porcentual(5000.0, 8.0)
		400.0
	"""
	return flt(base * tasa / 100.0, 2)


def _calcular_cuota(cantidad: float, cuota_unitaria: float) -> float:
	"""
	Cálculo cuota: cantidad x cuota_unitaria.

	Args:
		cantidad: Cantidad total (suma de qty)
		cuota_unitaria: Cuota por unidad (ej: $1.6451 por litro)

	Returns:
		float: Monto calculado

	Examples:
		>>> _calcular_cuota(100.0, 1.6451)
		164.51
		>>> _calcular_cuota(500.0, 0.35)
		175.0
	"""
	return flt(cantidad * cuota_unitaria, 2)


def _calcular_retencion(base: float, tasa_retencion: float) -> float:
	"""
	Cálculo retención: base x tasa_retención / 100.

	Nota: Idéntico a cálculo porcentual, separado por semántica.

	Args:
		base: Base de cálculo (ej: IVA trasladado o monto neto)
		tasa_retencion: Tasa de retención (ej: 66.67 para 2/3)

	Returns:
		float: Monto calculado (positivo, se marca como retención en otro lugar)

	Examples:
		>>> _calcular_retencion(160.0, 66.67)  # 2/3 de IVA
		106.67
		>>> _calcular_retencion(1000.0, 10.0)  # 10% ISR
		100.0
	"""
	return flt(base * tasa_retencion / 100.0, 2)


def _get_tax_row_index(doc, tax_row) -> int | None:
	"""
	Obtiene el índice de una tax row en doc.taxes.

	Args:
		doc: Sales Invoice document
		tax_row: Tax row a buscar

	Returns:
		int: Índice (0-based) o None si no se encuentra
	"""
	for idx, tax in enumerate(doc.taxes):
		if tax.name == tax_row.name:
			return idx

	return None


# =============================================================================
# HELPERS DE CACHE (opcional, para optimización futura)
# =============================================================================


def obtener_reglas_activas_cached():
	"""
	Obtiene reglas activas con cache en frappe.local.

	Evita lookups repetidos durante procesamiento de documento con múltiples tax rows.

	Returns:
		dict: Diccionario rol_fiscal → reglas (solo habilitadas)
	"""
	if not hasattr(frappe.local, "reglas_fiscales_cache"):
		from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_reglas_activas

		frappe.local.reglas_fiscales_cache = obtener_reglas_activas()

	return frappe.local.reglas_fiscales_cache


def limpiar_cache_reglas():
	"""
	Limpia cache de reglas fiscales en frappe.local.

	Útil para tests o después de modificar configuración fiscal.
	"""
	if hasattr(frappe.local, "reglas_fiscales_cache"):
		del frappe.local.reglas_fiscales_cache


# =============================================================================
# UTILIDAD PARA ERECEIPT MX — EXTRACCIÓN DE TASA IVA
# =============================================================================
# Modelo transitorio: almacena una tasa IVA plana por recibo.
# El modelo definitivo (issue #182) usará impuestos por línea para soportar
# IVA + IEPS + exento + tasa 0 + zona fronteriza con mezcla por producto.
# =============================================================================


def extract_iva_info_from_si_taxes(taxes) -> tuple[float | None, bool]:
	"""Extrae tasa IVA y detecta IEPS de las filas de impuestos de un Sales Invoice.

	Args:
		taxes: iterable de tax rows con campos account_head, description, rate

	Returns:
		(tax_rate_percent, has_ieps)
		- tax_rate_percent: tasa en porcentaje (16.0, 8.0, 0.0) o None si
		  no determinable. None obliga a bloqueo — nunca se asume exento por
		  ausencia de filas. Solo retorna 0.0 si existe fila IVA con rate=0
		  (tasa cero confirmada). Ver issue #182 para distinción exento vs
		  tasa 0 a nivel de línea.
		- has_ieps: True si existe alguna fila IEPS en las taxes.
	"""
	iva_rates = set()
	has_ieps = False

	for row in taxes or []:
		account = (row.get("account_head") or "").upper()
		desc = (row.get("description") or "").upper()

		is_ieps = "IEPS" in account or "IEPS" in desc
		is_iva = ("IVA" in account or "IVA" in desc) and not is_ieps

		if is_ieps:
			has_ieps = True
		elif is_iva:
			iva_rates.add(flt(row.get("rate") or 0))

	if len(iva_rates) == 0:
		return None, has_ieps

	if len(iva_rates) == 1:
		return iva_rates.pop(), has_ieps

	# Múltiples tasas IVA distintas en el mismo recibo — no determinable
	return None, has_ieps
