import frappe
from frappe.utils import flt

# Import tasas IEPS para generación ITT
from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import TASAS_IEPS

# Import para tabla maestra reglas cálculo
from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo

# Single source of truth - Roles fiscales
from facturacion_mexico.utils.roles_fiscales import (
	ROL_IEPS_ALC,
	ROL_IEPS_AZU,
	ROL_IEPS_COMB,
	ROL_IEPS_TAB,
	ROL_IEPS_TABQ,
	ROL_IVA_CERO,
	ROL_IVA_EXENTO,
	ROL_IVA_FRO,
	ROL_IVA_NAC,
	ROL_RET_ISR_ARR,
	ROL_RET_ISR_AUTO,
	ROL_RET_ISR_HON,
	ROL_RET_ISR_RESICO,
	ROL_RET_IVA_ARR,
	ROL_RET_IVA_AUTO,
	ROL_RET_IVA_HON,
	ROL_RET_IVA_RESICO,
)

# -----------------------------------------------------------
# CHARGE TYPE DINÁMICO (tabla maestra)
# -----------------------------------------------------------

# Mapeo regla_base → charge_type ERPNext
_MAPEO_CHARGE_TYPE = {
	"monto_neto": "On Net Total",
	"cantidad": "Actual",
	"fila_previa_monto": "On Previous Row Amount",
	"fila_previa_total": "On Previous Row Total",
	"iva_trasladado": "On Previous Row Amount",
}


def _charge_type_por_rol(rol_fiscal: str) -> str:
	"""
	Obtiene charge_type de ERPNext según rol fiscal desde tabla maestra.

	Lee reglas de cálculo de la tabla maestra y mapea regla_base al
	charge_type correspondiente de ERPNext para configuración correcta
	de filas de impuestos en STCT.

	Args:
		rol_fiscal: Rol fiscal del impuesto (e.g., ROL_IVA_NAC, ROL_IEPS_ALC)

	Returns:
		str: charge_type de ERPNext ("On Net Total", "Actual", "On Previous Row Amount", etc.)

	Ejemplo:
		>>> _charge_type_por_rol(ROL_IVA_NAC)
		"On Net Total"
		>>> _charge_type_por_rol(ROL_IEPS_AZU)
		"Actual"
	"""
	reglas = obtener_regla_calculo(rol_fiscal) or {}
	base = reglas.get("regla_base", "monto_neto")
	return _MAPEO_CHARGE_TYPE.get(base, "On Net Total")


# -----------------------------------------------------------
# NORMALIZACIÓN DE TÍTULOS
# -----------------------------------------------------------
def _normalize_title(s: str) -> str:
	"""
	Normaliza guiones y espacios en títulos STCT/ITT.

	Corrige:
	- Guión largo → guión corto (-)
	- Espacios múltiples → espacio simple
	- Espacios inconsistentes alrededor de guiones

	Args:
		s: Título a normalizar

	Returns:
		str: Título normalizado
	"""
	s = (s or "").replace("\u2013", "-").strip()  # EN DASH → HYPHEN-MINUS
	while "  " in s:
		s = s.replace("  ", " ")
	s = " - ".join(part.strip() for part in s.split("-"))
	return s


def _get_company_abbr(company: str) -> str:
	return frappe.db.get_value("Company", company, "abbr") or "TC"


def _get_account_head_by_role(company: str, rol: str) -> str:
	"""Obtener cuenta impuesto desde Configuracion Fiscal Mexico por rol fiscal."""
	# Buscar configuración fiscal de la empresa
	cfg_name = frappe.db.get_value("Configuracion Fiscal Mexico", {"company": company}, "name")
	if not cfg_name:
		frappe.throw(f"No existe Configuracion Fiscal Mexico para '{company}'")

	# Obtener todos los mapeos
	mapeos = frappe.get_all(
		"Mapeo Cuenta Fiscal Mexico", filters={"parent": cfg_name}, fields=["rol_fiscal", "cuenta_impuesto"]
	)

	# Buscar match exacto por rol_fiscal
	for m in mapeos:
		if m.rol_fiscal == rol:
			return m.cuenta_impuesto

	# Si no encuentra, error
	available = ", ".join([m.rol_fiscal for m in mapeos])
	frappe.throw(f"No se encontró mapeo para '{rol}' en '{company}'.\n" f"Roles disponibles: {available}")

	return ""  # Never reached


def _verificar_mapeos_disponibles(company: str) -> dict:
	"""
	Verifica qué roles fiscales están HABILITADOS (checkbox) Y tienen mapeo contable.

	LÓGICA CORRECTA:
	1. Lee checkboxes enable_* del documento Configuracion Fiscal Mexico
	2. Para cada checkbox=True, verifica si existe mapeo en mapeo_cuentas
	3. Solo marca disponible si checkbox=True AND mapeo existe con cuenta contable

	IMPORTANTE:
	- Si checkbox=False → rol NO disponible (aunque exista mapeo)
	- Si checkbox=True pero sin mapeo → rol NO disponible
	- Si checkbox=True AND mapeo existe → rol disponible

	Args:
		company: Company name

	Returns:
		dict: {
			"tiene_iva_nacional": bool,
			"tiene_iva_frontera": bool,
			"ieps_disponibles": dict,  # {"Alcohol": bool, "Azucar": bool, ...}
			"retenciones_disponibles": dict,  # {"IVA_Honorarios": bool, ...}
			"tiene_algun_ieps": bool,
			"tiene_alguna_retencion": bool,
			"mapeos_por_rol": dict  # Cache: rol → cuenta (performance)
		}
	"""
	# Obtener configuración fiscal de la company
	config_name = frappe.db.get_value("Configuracion Fiscal Mexico", {"company": company}, "name")
	if not config_name:
		# Sin configuración fiscal = sin mapeos
		return {
			"tiene_iva_nacional": False,
			"tiene_iva_frontera": False,
			"ieps_disponibles": {
				"Alcohol": False,
				"Azucar": False,
				"Combustibles": False,
				"Tabaco_Tasa": False,
				"Tabaco_Cuota": False,
			},
			"retenciones_disponibles": {
				"IVA_Honorarios": False,
				"ISR_Honorarios": False,
				"IVA_Arrendamiento": False,
				"ISR_Arrendamiento": False,
				"IVA_Autotransporte": False,
				"ISR_Autotransporte": False,
				"IVA_RESICO": False,
				"ISR_RESICO": False,
			},
			"tiene_algun_ieps": False,
			"tiene_alguna_retencion": False,
			"mapeos_por_rol": {},
		}

	# Obtener documento completo para acceder checkboxes y mapeos
	config = frappe.get_doc("Configuracion Fiscal Mexico", config_name)
	mapeos = config.mapeo_cuentas or []

	# Cache para performance - evita múltiples llamadas _get_account_head_by_role
	mapeos_por_rol = {m.rol_fiscal: m.cuenta_impuesto for m in mapeos}
	roles_disponibles = set(mapeos_por_rol.keys())

	# Helper: verifica checkbox enabled AND mapeo existe
	def _disponible(checkbox_enabled: bool, rol: str) -> bool:
		"""Retorna True solo si checkbox=True AND mapeo con cuenta existe."""
		return checkbox_enabled and rol in roles_disponibles

	# IVA Nacional (siempre obligatorio - no tiene checkbox)
	tiene_iva_nacional = ROL_IVA_NAC in roles_disponibles

	# IVA Frontera (solo si checkbox enabled)
	tiene_iva_frontera = _disponible(config.enable_frontera, ROL_IVA_FRO)

	# IEPS (granular - checkbox + mapeo)
	ieps_disponibles = {
		"Alcohol": _disponible(config.enable_ieps_alcohol, ROL_IEPS_ALC),
		"Azucar": _disponible(config.enable_ieps_azucar, ROL_IEPS_AZU),
		"Combustibles": _disponible(config.enable_ieps_combustibles, ROL_IEPS_COMB),
		"Tabaco_Tasa": _disponible(config.enable_ieps_tabaco, ROL_IEPS_TAB),
		"Tabaco_Cuota": _disponible(config.enable_ieps_tabaco, ROL_IEPS_TABQ),
	}
	tiene_algun_ieps = any(ieps_disponibles.values())

	# Retenciones (granular - checkbox + mapeo - 8 retenciones totales)
	retenciones_disponibles = {
		"IVA_Honorarios": _disponible(config.enable_ret_honorarios, ROL_RET_IVA_HON),
		"ISR_Honorarios": _disponible(config.enable_ret_honorarios, ROL_RET_ISR_HON),
		"IVA_Arrendamiento": _disponible(config.enable_ret_arrendamiento, ROL_RET_IVA_ARR),
		"ISR_Arrendamiento": _disponible(config.enable_ret_arrendamiento, ROL_RET_ISR_ARR),
		"IVA_Autotransporte": _disponible(config.enable_ret_autotransporte, ROL_RET_IVA_AUTO),
		"ISR_Autotransporte": _disponible(config.enable_ret_autotransporte, ROL_RET_ISR_AUTO),
		"IVA_RESICO": _disponible(config.enable_ret_resico, ROL_RET_IVA_RESICO),
		"ISR_RESICO": _disponible(config.enable_ret_resico, ROL_RET_ISR_RESICO),
	}
	tiene_alguna_retencion = any(retenciones_disponibles.values())

	return {
		"tiene_iva_nacional": tiene_iva_nacional,
		"tiene_iva_frontera": tiene_iva_frontera,
		"ieps_disponibles": ieps_disponibles,
		"retenciones_disponibles": retenciones_disponibles,
		"tiene_algun_ieps": tiene_algun_ieps,
		"tiene_alguna_retencion": tiene_alguna_retencion,
		"mapeos_por_rol": mapeos_por_rol,
	}


def _get_iva_rates(
	company: str, iva_nacional: float | None, iva_frontera: float | None
) -> tuple[float, float]:
	"""
	Obtiene las tasas IVA variables SIN imprimirlas en nombres ni descripciones.
	Prioridad:
	  1) kwargs recibidos
	  2) Defaults (16.0 nacional, 8.0 frontera)
	"""
	# 1) kwargs mandados por el comando
	if iva_nacional is not None and iva_frontera is not None:
		return (flt(iva_nacional), flt(iva_frontera))

	# 2) Defaults (variables por código, pero no se exponen en nombres)
	return (16.0, 8.0)


# -----------------------------------------------------------
# FILAS: nombres/descr. SEMÁNTICOS (sin números)
# -----------------------------------------------------------

# LEGACY: Función con charge_type hardcodeado - COMENTADO PARA MIGRACIÓN E1
# def fila_iva_base(account_head: str, zona: str, tasa_valor: float) -> dict:
# 	"""
# 	IVA base sobre neto. La tasa se aplica aquí (valor), pero NO se escribe en la descripción.
# 	"""
# 	return {
# 		"charge_type": "On Net Total",
# 		"row_id": None,
# 		"rate": tasa_valor,  # valor numérico, no en texto
# 		"description": f"IVA {zona} - Base (Resto)",
# 		"account_head": account_head,
# 		"add_deduct_tax": "Add",
# 		"category": "Valuation and Total",
# 	}


def fila_iva_base(account_head: str, zona: str, tasa_valor: float, rol_fiscal: str) -> dict:
	"""
	IVA base sobre neto con charge_type dinámico desde tabla maestra.

	La tasa se aplica aquí (valor), pero NO se escribe en la descripción.
	Migración E1: Lee charge_type desde tabla maestra vía rol_fiscal.

	Args:
		account_head: Cuenta contable del impuesto
		zona: "Nacional" o "Frontera"
		tasa_valor: Tasa IVA numérica (16.0 o 8.0)
		rol_fiscal: Rol fiscal para obtener charge_type dinámico (ROL_IVA_NAC, ROL_IVA_FRO)

	Returns:
		dict: Configuración fila impuesto para STCT
	"""
	return {
		"charge_type": _charge_type_por_rol(rol_fiscal),  # Dinámico desde tabla maestra
		"row_id": None,
		"rate": tasa_valor,  # valor numérico, no en texto
		"description": f"IVA {zona} - Base (Resto)",
		"account_head": account_head,
		"add_deduct_tax": "Add",
		"category": "Valuation and Total",
	}


# LEGACY: Función con charge_type hardcodeado - COMENTADO PARA MIGRACIÓN E1
# def fila_ieps_tasa(account_head: str, concepto: str) -> dict:
# 	"""IEPS tasa via ITT (rate=0 aquí; lo fija el ITT/ítem)."""
# 	return {
# 		"charge_type": "On Net Total",
# 		"row_id": None,
# 		"rate": 0.0,
# 		"description": f"IEPS {concepto} - Tasa (via ITT)",
# 		"account_head": account_head,
# 		"add_deduct_tax": "Add",
# 		"category": "Valuation and Total",
# 	}


def fila_ieps_tasa(account_head: str, concepto: str, rol_fiscal: str) -> dict:
	"""
	IEPS tasa via ITT con charge_type dinámico desde tabla maestra.

	rate=0 aquí; el ITT/ítem fija la tasa específica heredada desde Item Group.
	Migración E1: Lee charge_type desde tabla maestra vía rol_fiscal.

	Args:
		account_head: Cuenta contable del IEPS
		concepto: Descripción del concepto (e.g., "Alcohol", "Tabaco")
		rol_fiscal: Rol fiscal para obtener charge_type dinámico (ROL_IEPS_ALC, ROL_IEPS_TAB)

	Returns:
		dict: Configuración fila impuesto para STCT
	"""
	return {
		"charge_type": _charge_type_por_rol(rol_fiscal),  # Dinámico desde tabla maestra
		"row_id": None,
		"rate": 0.0,
		"description": f"IEPS {concepto} - Tasa (via ITT)",
		"account_head": account_head,
		"add_deduct_tax": "Add",
		"category": "Valuation and Total",
	}


# LEGACY: Función con charge_type hardcodeado - COMENTADO PARA MIGRACIÓN E1
# def fila_ieps_cuota(account_head: str, concepto: str) -> dict:
# 	"""IEPS cuota (Actual; el monto lo calcula el hook existente)."""
# 	return {
# 		"charge_type": "Actual",
# 		"row_id": None,
# 		"rate": 0.0,
# 		"description": f"IEPS {concepto} - Cuota (via ITT)",
# 		"account_head": account_head,
# 		"add_deduct_tax": "Add",
# 		"category": "Valuation and Total",
# 	}


def fila_ieps_cuota(account_head: str, concepto: str, rol_fiscal: str) -> dict:
	"""
	IEPS cuota con charge_type dinámico desde tabla maestra.

	El monto lo calcula el hook existente basado en cantidad.
	Hook setea tax_amount dinámicamente según cuota IEPS del item.
	Migración E1: Lee charge_type desde tabla maestra vía rol_fiscal.

	Args:
		account_head: Cuenta contable del IEPS
		concepto: Descripción del concepto (e.g., "Azúcar/Bebidas", "Combustibles", "Tabaco")
		rol_fiscal: Rol fiscal para obtener charge_type dinámico (ROL_IEPS_AZU, ROL_IEPS_COMB, ROL_IEPS_TABQ)

	Returns:
		dict: Configuración fila impuesto para STCT
	"""
	return {
		"charge_type": _charge_type_por_rol(rol_fiscal),  # Dinámico desde tabla maestra
		"row_id": None,
		"rate": 0.0,
		"description": f"IEPS {concepto} - Cuota (via ITT)",
		"account_head": account_head,
		"add_deduct_tax": "Add",
		"category": "Valuation and Total",
	}


# LEGACY: Función con charge_type hardcodeado - COMENTADO PARA MIGRACIÓN E1
# def fila_retencion(account_head: str, desc: str, rate: float | None = None) -> dict:
# 	"""
# 	Retenciones; si vienen por ITT, deja rate=0 y el ITT/hook lo fija.
# 	"""
# 	return {
# 		"charge_type": "On Net Total",
# 		"row_id": None,
# 		"rate": flt(rate) if rate is not None else 0.0,
# 		"description": desc,
# 		"account_head": account_head,
# 		"add_deduct_tax": "Deduct",
# 		"category": "Total",
# 	}


def fila_retencion(account_head: str, desc: str, rol_fiscal: str, rate: float | None = None) -> dict:
	"""
	Retenciones con charge_type dinámico desde tabla maestra.

	Si vienen por ITT, deja rate=0 y el ITT/hook lo fija.
	Migración E1: Lee charge_type desde tabla maestra vía rol_fiscal.

	Args:
		account_head: Cuenta contable de la retención
		desc: Descripción de la retención
		rol_fiscal: Rol fiscal para obtener charge_type dinámico (ROL_RET_*)
		rate: Tasa de retención (opcional, default 0.0 para ITT)

	Returns:
		dict: Configuración fila retención para STCT
	"""
	return {
		"charge_type": _charge_type_por_rol(rol_fiscal),  # Dinámico desde tabla maestra
		"row_id": None,
		"rate": flt(rate) if rate is not None else 0.0,
		"description": desc,
		"account_head": account_head,
		"add_deduct_tax": "Deduct",
		"category": "Total",
	}


def fila_iva_cascada_ieps(account_head: str, concepto_ieps: str, iva_rate: float, rol_fiscal: str) -> dict:
	"""
	IVA cascada sobre IEPS (calcula IVA sobre el monto del IEPS anterior).

	HARDCODEA charge_type "On Previous Row Amount" porque IVA cascada sobre IEPS:
	- NO es un rol fiscal independiente (usa misma cuenta IVA)
	- SIEMPRE calcula sobre fila previa (IEPS)
	- Es lógica específica de generador templates, no de tabla maestra

	Args:
		account_head: Cuenta contable del IVA
		concepto_ieps: Descripción del concepto IEPS (e.g., "Alcohol", "Tabaco")
		iva_rate: Tasa IVA numérica (16.0 o 8.0)
		rol_fiscal: Rol fiscal IVA (no usado actualmente, para compatibilidad futura)

	Returns:
		dict: Configuración fila IVA cascada para STCT

	Ejemplo:
		# Después de fila IEPS Alcohol ($874.50)
		# Esta fila calcula: $874.50 * 16% = $139.92
	"""
	return {
		"charge_type": "On Previous Row Amount",  # HARDCODE - IVA cascada siempre usa prev row
		"row_id": None,  # Se asigna después en _build_rows()
		"rate": iva_rate,
		"description": f"IVA sobre IEPS {concepto_ieps}",
		"account_head": account_head,
		"add_deduct_tax": "Add",
		"category": "Valuation and Total",
	}


# -----------------------------------------------------------
# CONSTRUCCIÓN DE CADA VARIANTE (solo filas necesarias)
# -----------------------------------------------------------
def _build_rows(
	company: str, zona: str, iva_rate: float, variant: str, mapeos_disponibles: dict
) -> tuple[list[dict], list[str]]:
	"""
	Construye filas para variante STCT con generación parcial.

	Solo agrega filas para las que existe mapeo contable. Reporta omisiones.

	Args:
		company: Company name
		zona: "Nacional" o "Frontera"
		iva_rate: Tasa IVA (16.0 o 8.0)
		variant: "Básico", "IEPS", "Retenciones", "Total"
		mapeos_disponibles: Dict de _verificar_mapeos_disponibles()

	Returns:
		tuple[list[dict], list[str]]: (rows, omitted_rows)
		rows: Filas tax rows generadas
		omitted_rows: Lista descriptiva de filas omitidas (por falta mapeo)
	"""
	rows = []
	omitted = []

	# IVA base (obligatorio)
	rol_iva = ROL_IVA_NAC if zona == "Nacional" else ROL_IVA_FRO
	tiene_iva = (
		mapeos_disponibles["tiene_iva_nacional"]
		if zona == "Nacional"
		else mapeos_disponibles["tiene_iva_frontera"]
	)

	if not tiene_iva:
		return [], [f"IVA {zona} (obligatorio)"]

	# Usar cache de mapeos (performance)
	iva_acc = mapeos_disponibles["mapeos_por_rol"].get(rol_iva)
	if not iva_acc:
		# Fallback a búsqueda tradicional si cache no tiene
		iva_acc = _get_account_head_by_role(company, rol_iva)

	# IVA Base PRIMERO - truco ERPNext: primera fila con (account_head, add_deduct, charge_type) gana
	# Si IVA Base está primero, ERPNext NO la reemplaza con filas del ITT
	rows.append(fila_iva_base(iva_acc, zona, iva_rate, rol_iva))

	# IEPS (parcial - agregar solo disponibles) + IVA cascada
	if variant in ("IEPS", "Total"):
		ieps = mapeos_disponibles["ieps_disponibles"]
		mapeos_cache = mapeos_disponibles["mapeos_por_rol"]

		if ieps["Alcohol"]:
			acc = mapeos_cache.get(ROL_IEPS_ALC) or _get_account_head_by_role(company, ROL_IEPS_ALC)
			rows.append(fila_ieps_tasa(acc, "Alcohol", ROL_IEPS_ALC))  # Migración E1: + rol_fiscal
			# IVA cascada sobre IEPS Alcohol (E1: nueva fila)
			# row_id apunta al idx de la fila IEPS recién agregada
			ieps_row_idx = len(rows)  # idx será len(rows) porque se asigna en _make_stct
			fila_iva = fila_iva_cascada_ieps(iva_acc, "Alcohol", iva_rate, rol_iva)
			fila_iva["row_id"] = ieps_row_idx  # Asignar row_id explícito
			rows.append(fila_iva)
		else:
			omitted.append("IEPS Alcohol (tasa)")

		if ieps["Azucar"]:
			acc = mapeos_cache.get(ROL_IEPS_AZU) or _get_account_head_by_role(company, ROL_IEPS_AZU)
			rows.append(fila_ieps_cuota(acc, "Azúcar/Bebidas", ROL_IEPS_AZU))  # Migración E1: + rol_fiscal
			# IVA cascada sobre IEPS Azúcar (E1: nueva fila)
			ieps_row_idx = len(rows)
			fila_iva = fila_iva_cascada_ieps(iva_acc, "Azúcar/Bebidas", iva_rate, rol_iva)
			fila_iva["row_id"] = ieps_row_idx
			rows.append(fila_iva)
		else:
			omitted.append("IEPS Azúcar (cuota)")

		if ieps["Combustibles"]:
			acc = mapeos_cache.get(ROL_IEPS_COMB) or _get_account_head_by_role(company, ROL_IEPS_COMB)
			rows.append(fila_ieps_cuota(acc, "Combustibles", ROL_IEPS_COMB))  # Migración E1: + rol_fiscal
			# IVA cascada sobre IEPS Combustibles (E1: nueva fila)
			ieps_row_idx = len(rows)
			fila_iva = fila_iva_cascada_ieps(iva_acc, "Combustibles", iva_rate, rol_iva)
			fila_iva["row_id"] = ieps_row_idx
			rows.append(fila_iva)
		else:
			omitted.append("IEPS Combustibles (cuota)")

		if ieps["Tabaco_Tasa"]:
			acc = mapeos_cache.get(ROL_IEPS_TAB) or _get_account_head_by_role(company, ROL_IEPS_TAB)
			rows.append(fila_ieps_tasa(acc, "Tabaco", ROL_IEPS_TAB))  # Migración E1: + rol_fiscal
			# IVA cascada sobre IEPS Tabaco Tasa (E1: nueva fila)
			ieps_row_idx = len(rows)
			fila_iva = fila_iva_cascada_ieps(iva_acc, "Tabaco (Tasa)", iva_rate, rol_iva)
			fila_iva["row_id"] = ieps_row_idx
			rows.append(fila_iva)
		else:
			omitted.append("IEPS Tabaco (tasa)")

		if ieps["Tabaco_Cuota"]:
			acc = mapeos_cache.get(ROL_IEPS_TABQ) or _get_account_head_by_role(company, ROL_IEPS_TABQ)
			rows.append(fila_ieps_cuota(acc, "Tabaco", ROL_IEPS_TABQ))  # Migración E1: + rol_fiscal
			# IVA cascada sobre IEPS Tabaco Cuota (E1: nueva fila)
			ieps_row_idx = len(rows)
			fila_iva = fila_iva_cascada_ieps(iva_acc, "Tabaco (Cuota)", iva_rate, rol_iva)
			fila_iva["row_id"] = ieps_row_idx
			rows.append(fila_iva)
		else:
			omitted.append("IEPS Tabaco (cuota)")

	# Retenciones (parcial - agregar solo disponibles - 8 retenciones totales)
	if variant in ("Retenciones", "Total"):
		rets = mapeos_disponibles["retenciones_disponibles"]
		mapeos_cache = mapeos_disponibles["mapeos_por_rol"]

		# Retenciones Honorarios
		if rets["IVA_Honorarios"]:
			acc = mapeos_cache.get(ROL_RET_IVA_HON) or _get_account_head_by_role(company, ROL_RET_IVA_HON)
			rows.append(fila_retencion(acc, "Retención IVA - Honorarios", ROL_RET_IVA_HON))  # Migración E1
		else:
			omitted.append("Retención IVA Honorarios")

		if rets["ISR_Honorarios"]:
			acc = mapeos_cache.get(ROL_RET_ISR_HON) or _get_account_head_by_role(company, ROL_RET_ISR_HON)
			rows.append(fila_retencion(acc, "Retención ISR - Honorarios", ROL_RET_ISR_HON))  # Migración E1
		else:
			omitted.append("Retención ISR Honorarios")

		# Retenciones Arrendamiento
		if rets["IVA_Arrendamiento"]:
			acc = mapeos_cache.get(ROL_RET_IVA_ARR) or _get_account_head_by_role(company, ROL_RET_IVA_ARR)
			rows.append(fila_retencion(acc, "Retención IVA - Arrendamiento", ROL_RET_IVA_ARR))  # Migración E1
		else:
			omitted.append("Retención IVA Arrendamiento")

		if rets["ISR_Arrendamiento"]:
			acc = mapeos_cache.get(ROL_RET_ISR_ARR) or _get_account_head_by_role(company, ROL_RET_ISR_ARR)
			rows.append(fila_retencion(acc, "Retención ISR - Arrendamiento", ROL_RET_ISR_ARR))  # Migración E1
		else:
			omitted.append("Retención ISR Arrendamiento")

		# Retenciones Autotransporte
		if rets["IVA_Autotransporte"]:
			acc = mapeos_cache.get(ROL_RET_IVA_AUTO) or _get_account_head_by_role(company, ROL_RET_IVA_AUTO)
			rows.append(
				fila_retencion(acc, "Retención IVA - Autotransporte", ROL_RET_IVA_AUTO)
			)  # Migración E1
		else:
			omitted.append("Retención IVA Autotransporte")

		if rets["ISR_Autotransporte"]:
			acc = mapeos_cache.get(ROL_RET_ISR_AUTO) or _get_account_head_by_role(company, ROL_RET_ISR_AUTO)
			rows.append(
				fila_retencion(acc, "Retención ISR - Autotransporte", ROL_RET_ISR_AUTO)
			)  # Migración E1
		else:
			omitted.append("Retención ISR Autotransporte")

		# Retenciones RESICO
		if rets["IVA_RESICO"]:
			acc = mapeos_cache.get(ROL_RET_IVA_RESICO) or _get_account_head_by_role(
				company, ROL_RET_IVA_RESICO
			)
			rows.append(fila_retencion(acc, "Retención IVA - RESICO", ROL_RET_IVA_RESICO))  # Migración E1
		else:
			omitted.append("Retención IVA RESICO")

		if rets["ISR_RESICO"]:
			acc = mapeos_cache.get(ROL_RET_ISR_RESICO) or _get_account_head_by_role(
				company, ROL_RET_ISR_RESICO
			)
			rows.append(fila_retencion(acc, "Retención ISR - RESICO", ROL_RET_ISR_RESICO))  # Migración E1
		else:
			omitted.append("Retención ISR RESICO")

	return rows, omitted


def _make_stct(company: str, title: str, rows: list[dict]) -> str:
	"""
	Crea o actualiza Sales Taxes and Charges Template.

	Características:
	- Normaliza title (guiones, espacios)
	- Usa método install.py (Frappe auto-naming agrega abbr)
	- Actualiza existentes (reutiliza templates)
	- Idempotente: re-ejecutar no crea duplicados

	Args:
		company: Company name
		title: Template title (SIN abbr - Frappe lo agrega automáticamente)
		rows: Tax rows configuration

	Returns:
		str: Template name (title + " - " + abbr)
	"""
	# Normalizar title (guiones, espacios)
	title = _normalize_title(title)

	# Obtener company abbr para búsqueda
	company_abbr = frappe.db.get_value("Company", company, "abbr")
	if not company_abbr:
		frappe.throw(f"No se encontró company abbr para {company}")

	# Buscar template existente por title CON abbr (como Frappe lo guarda)
	title_with_abbr = f"{title} - {company_abbr}"
	existing_name = frappe.db.get_value(
		"Sales Taxes and Charges Template", {"title": title_with_abbr, "company": company}, "name"
	)

	if existing_name:
		# ACTUALIZAR template existente (reutilizar)
		doc = frappe.get_doc("Sales Taxes and Charges Template", existing_name)
		doc.title = title_with_abbr  # Asegurar title normalizado con abbr
		doc.company = company
		doc.is_sales_tax_template = 1
		doc.disabled = 0
		# Limpiar taxes viejas
		doc.set("taxes", [])
	else:
		# CREAR nuevo template - método install.py
		# NO pre-establecer 'name' - Frappe maneja auto-naming (agrega abbr)
		doc = frappe.get_doc(
			{
				"doctype": "Sales Taxes and Charges Template",
				"title": title,  # ← Solo title, Frappe auto-naming agrega abbr
				"company": company,
				"is_sales_tax_template": 1,
				"disabled": 0,
			}
		)

	# Agregar filas taxes (común para create/update)
	for idx, r in enumerate(rows, start=1):
		r["idx"] = idx
		doc.append("taxes", r)

	# Guardar (insert para nuevos, save para existentes)
	if existing_name:
		doc.save()
	else:
		doc.insert()

	frappe.db.commit()
	return doc.name


def _disable_old_percent_named_templates(company: str):
	"""
	Deshabilita STCT viejos que tengan '16%' o '8%' en el TÍTULO (solo el título).
	No borra nada.
	"""
	# Buscar templates con 16% o 8% en el título usando SQL directo
	olds = frappe.db.sql(
		"""
        SELECT name
        FROM `tabSales Taxes and Charges Template`
        WHERE company = %s
        AND (title LIKE %s OR title LIKE %s)
        AND disabled = 0
    """,
		(company, "%16%", "%8%"),
		as_list=True,
	)

	for (name,) in olds:
		frappe.db.set_value("Sales Taxes and Charges Template", name, "disabled", 1)

	if olds:
		frappe.db.commit()


def _mostrar_resumen_generacion(result: dict):
	"""
	Muestra resumen consolidado de generación templates al usuario.

	Args:
		result: Dict retornado por generate_8_stct_for_company() con:
			- created: list[str] - Templates creados
			- skipped: list[dict] - Templates omitidos {template, reason}
			- omitted_rows_por_template: dict - Filas omitidas por template
			- disabled_old: bool
	"""
	created = result.get("created", [])
	skipped = result.get("skipped", [])
	omitted_rows = result.get("omitted_rows_por_template", {})

	# Construir mensaje HTML consolidado
	msg_parts = []

	# SECCIÓN 1: Templates creados exitosamente
	if created:
		msg_parts.append(f"<h4 style='color: green;'>✅ Templates creados ({len(created)}):</h4>")
		msg_parts.append("<ul>")
		for name in created:
			# Indicar si tiene filas omitidas
			if name in omitted_rows:
				msg_parts.append(
					f"<li><b>{name}</b> <span style='color: orange;'>(con filas parciales)</span></li>"
				)
			else:
				msg_parts.append(f"<li><b>{name}</b></li>")
		msg_parts.append("</ul>")

	# SECCIÓN 2: Templates omitidos
	if skipped:
		msg_parts.append(f"<h4 style='color: orange;'>⚠️ Templates omitidos ({len(skipped)}):</h4>")
		msg_parts.append("<ul>")
		for item in skipped:
			template = item.get("template", "Desconocido")
			reason = item.get("reason", "Sin razón")
			msg_parts.append(f"<li><b>{template}</b>: {reason}</li>")
		msg_parts.append("</ul>")

	# SECCIÓN 3: Filas omitidas por template
	if omitted_rows:
		msg_parts.append("<h4 style='color: blue;'>📋 Filas omitidas por template:</h4>")
		msg_parts.append("<ul>")
		for template, rows in omitted_rows.items():
			msg_parts.append(f"<li><b>{template}</b>:")
			msg_parts.append("<ul>")
			for row in rows:
				msg_parts.append(f"<li>{row}</li>")
			msg_parts.append("</ul>")
			msg_parts.append("</li>")
		msg_parts.append("</ul>")

	# SECCIÓN 4: Mensaje consolidado final
	total_esperados = 8  # Siempre se intentan generar 8 templates
	total_creados = len(created)
	total_omitidos = len(skipped)

	msg_parts.append("<hr>")
	msg_parts.append(f"<p><b>Resumen:</b> {total_creados}/{total_esperados} templates generados")
	if total_omitidos > 0:
		msg_parts.append(f", {total_omitidos} omitidos")
	if omitted_rows:
		msg_parts.append(f", {len(omitted_rows)} templates con filas parciales")
	msg_parts.append(".</p>")

	# Recomendación si hay omisiones
	if skipped or omitted_rows:
		msg_parts.append(
			"<p style='color: orange;'><b>Recomendación:</b> "
			"Configure los mapeos faltantes en <b>Mapeo Cuenta Fiscal Mexico</b> "
			"para obtener templates completos.</p>"
		)

	# Mostrar mensaje consolidado
	final_msg = "".join(msg_parts)
	frappe.msgprint(
		final_msg,
		title="Generación Templates STCT - Reporte",
		indicator="blue" if (skipped or omitted_rows) else "green",
		wide=True,
	)


@frappe.whitelist()
def generate_8_stct_for_company(
	company: str,
	abbr: str | None = None,
	iva_nacional_rate: float | None = None,
	iva_frontera_rate: float | None = None,
):
	"""
	Genera 8 STCT (Nacional/Frontera x Básico/IEPS/Retenciones/Total) con lógica parcial.

	Cambios E1 (IEPS parcial):
	- Verificación granular de mapeos disponibles (por cada IEPS/Retención)
	- Generación parcial: templates con solo las filas cuyos mapeos existan
	- Reporte detallado: created/skipped/omitted_rows_por_template
	- Try-catch per template: errores no detienen el batch

	Args:
		company: Company name
		abbr: Company abbreviation (auto-detected if None)
		iva_nacional_rate: IVA rate Nacional (auto-detected if None)
		iva_frontera_rate: IVA rate Frontera (auto-detected if None)

	Returns:
		dict: {
			"created": list[str],  # Template names creados
			"skipped": list[dict],  # {template, reason}
			"omitted_rows_por_template": dict,  # {template: [omitted_rows]}
			"disabled_old": bool
		}

	USO (bench):
	bench --site <site> execute facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal.generate_8_stct_for_company \
	  --kwargs "{'company':'Mi Empresa SA de CV','abbr':'_TC','iva_nacional_rate':16,'iva_frontera_rate':8}"
	"""
	abbr = abbr or _get_company_abbr(company)
	iva_nat, iva_fro = _get_iva_rates(company, iva_nacional_rate, iva_frontera_rate)

	# PASO 1: Verificar mapeos disponibles (única vez, cache)
	mapeos_disponibles = _verificar_mapeos_disponibles(company)

	# PASO 2: Validación obligatoria - IVA Nacional debe existir
	if not mapeos_disponibles["tiene_iva_nacional"]:
		frappe.throw(
			"No se puede generar templates STCT: falta mapeo obligatorio <b>IVA Nacional</b>.<br>"
			"Configure el mapeo en <b>Mapeo Cuenta Fiscal Mexico</b> antes de continuar."
		)

	# PASO 3: Generación con lógica parcial
	created = []
	skipped = []
	omitted_rows_por_template = {}

	for zona, rate in (("Nacional", iva_nat), ("Frontera", iva_fro)):
		# Verificar si zona tiene IVA disponible
		tiene_iva_zona = (
			mapeos_disponibles["tiene_iva_nacional"]
			if zona == "Nacional"
			else mapeos_disponibles["tiene_iva_frontera"]
		)

		if not tiene_iva_zona:
			# Skip toda la zona si no tiene IVA
			for variant in ("Básico", "IEPS", "Retenciones", "Total"):
				title = f"IVA {zona} - {variant}"
				skipped.append({"template": title, "reason": f"Sin mapeo IVA {zona}"})
			continue

		for variant in ("Básico", "IEPS", "Retenciones", "Total"):
			title = f"IVA {zona} - {variant}"

			try:
				# PASO 3.1: Build rows con lógica parcial (retorna tuple)
				rows, omitted = _build_rows(company, zona, rate, variant, mapeos_disponibles)

				# PASO 3.2: Verificar si hay filas para crear
				if not rows:
					# Sin filas disponibles - skip template
					skipped.append(
						{
							"template": title,
							"reason": f"Sin mapeos disponibles: {', '.join(omitted) if omitted else 'desconocido'}",
						}
					)
					continue

				# PASO 3.3: Crear/actualizar template (con filas parciales)
				name = _make_stct(company, title, rows)
				created.append(name)

				# PASO 3.4: Registrar filas omitidas (si las hay)
				if omitted:
					omitted_rows_por_template[title] = omitted

			except Exception as e:
				# Try-catch per template: errores no detienen batch
				skipped.append({"template": title, "reason": f"Error: {e!s}"})
				frappe.log_error(
					message=f"Error generando template {title}: {e!s}",
					title=f"STCT Generation Error - {title}",
				)

	# PASO 4: Deshabilitar templates viejos con porcentajes
	_disable_old_percent_named_templates(company)

	# PASO 5: Preparar resultado detallado
	result = {
		"created": created,
		"skipped": skipped,
		"omitted_rows_por_template": omitted_rows_por_template,
		"disabled_old": True,
	}

	# PASO 6: Mostrar resumen consolidado al usuario
	_mostrar_resumen_generacion(result)

	# PASO 7: Return para uso programático
	return result


# =============================================================================
# GENERACIÓN DE ITEM TAX TEMPLATES (ITT)
# =============================================================================


def _crear_o_actualizar_itt(
	company: str, abbr: str, title: str, taxes_config: list[dict], mapeo_cuentas: dict
) -> str:
	"""Crear o actualizar Item Tax Template."""
	full_title = f"{title} - {abbr}"

	# Buscar existente
	existing = frappe.db.exists("Item Tax Template", {"title": full_title, "company": company})

	if existing:
		doc = frappe.get_doc("Item Tax Template", existing)
		doc.taxes = []  # limpiar para rearmar
	else:
		doc = frappe.new_doc("Item Tax Template")
		doc.title = full_title
		doc.company = company
		doc.taxes = []

	# Reconstruir taxes
	for idx, tax_config in enumerate(taxes_config, start=1):
		rol_fiscal = tax_config["rol_fiscal"]
		cuenta_impuesto = mapeo_cuentas.get(rol_fiscal)
		if not cuenta_impuesto:
			continue  # Skip si no hay mapeo
		doc.append(
			"taxes",
			{
				"tax_type": cuenta_impuesto,
				"tax_rate": tax_config.get("tax_rate", 0.0),
				"idx": idx,
			},
		)

	# Guardar
	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
	return doc.name


@frappe.whitelist()
def generate_itt_for_company(company: str) -> dict:
	"""
	Generar Item Tax Templates para una empresa basándose en Configuracion Fiscal Mexico.

	Returns:
		dict: {"created": [list of ITT names], "company": company}
	"""
	# Obtener configuración fiscal
	cfg_name = frappe.db.get_value("Configuracion Fiscal Mexico", {"company": company}, "name")
	if not cfg_name:
		frappe.throw(f"No existe Configuracion Fiscal Mexico para '{company}'")

	cfg = frappe.get_doc("Configuracion Fiscal Mexico", cfg_name)
	abbr = _get_company_abbr(company)

	# Construir mapeo de cuentas
	mapeo_cuentas = {}
	for m in cfg.mapeo_cuentas:
		if m.rol_fiscal and m.cuenta_impuesto:
			mapeo_cuentas[m.rol_fiscal] = m.cuenta_impuesto

	created = []

	# ITT Base - IVA
	created.append(
		_crear_o_actualizar_itt(
			company,
			abbr,
			"ITT IVA Nacional",
			[{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 16.0}],
			mapeo_cuentas,
		)
	)

	created.append(
		_crear_o_actualizar_itt(
			company,
			abbr,
			"ITT IVA 0%",
			[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 0},
				{"rol_fiscal": ROL_IVA_FRO, "tax_rate": 0},
				{"rol_fiscal": ROL_IVA_CERO, "tax_rate": 0},
			],
			mapeo_cuentas,
		)
	)

	created.append(
		_crear_o_actualizar_itt(
			company,
			abbr,
			"ITT Exento",
			[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 0},
				{"rol_fiscal": ROL_IVA_FRO, "tax_rate": 0},
				{"rol_fiscal": ROL_IVA_EXENTO, "tax_rate": 0},
			],
			mapeo_cuentas,
		)
	)

	# ITT IVA Frontera
	if cfg.enable_frontera:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IVA Frontera",
				[{"rol_fiscal": ROL_IVA_FRO, "tax_rate": 8.0}],
				mapeo_cuentas,
			)
		)

	# ITT IEPS
	if cfg.enable_ieps_alcohol:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IEPS Alcohol",
				[
					{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": TASAS_IEPS["alcohol"]["tasa"]}
				],  # Tasa desde constantes - heredada por items vía Item Group
				mapeo_cuentas,
			)
		)

	if cfg.enable_ieps_azucar:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IEPS Azúcar",
				[
					{"rol_fiscal": "IEPS por Pagar (Azúcar/Bebidas)", "tax_rate": 0}
				],  # Rate 0 correcto: hook calcular_ieps_cuota() asigna monto dinámicamente
				mapeo_cuentas,
			)
		)

	if cfg.enable_ieps_combustibles:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IEPS Combustibles",
				[
					{"rol_fiscal": "IEPS por Pagar (Combustibles)", "tax_rate": 0}
				],  # Rate 0 correcto: hook calcular_ieps_cuota() asigna monto dinámicamente
				mapeo_cuentas,
			)
		)

	if cfg.enable_ieps_tabaco:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IEPS Tabaco",
				[
					{"rol_fiscal": "IEPS por Pagar (Tabaco)", "tax_rate": TASAS_IEPS["tabaco"]["tasa"]}
				],  # Tasa desde constantes - heredada por items vía Item Group
				mapeo_cuentas,
			)
		)

	# ITT Retenciones Honorarios
	if cfg.enable_ret_honorarios:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT ISR Honorarios",
				[{"rol_fiscal": ROL_RET_ISR_HON, "tax_rate": 0}],
				mapeo_cuentas,
			)
		)
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IVA Retenido Honorarios",
				[{"rol_fiscal": ROL_RET_IVA_HON, "tax_rate": 0}],
				mapeo_cuentas,
			)
		)
		# Combinado
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT ISR + IVA Ret Honorarios",
				[
					{"rol_fiscal": ROL_RET_ISR_HON, "tax_rate": 0},
					{"rol_fiscal": ROL_RET_IVA_HON, "tax_rate": 0},
				],
				mapeo_cuentas,
			)
		)

	# ITT Retenciones Arrendamiento
	if cfg.enable_ret_arrendamiento:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT ISR Arrendamiento",
				[{"rol_fiscal": ROL_RET_ISR_ARR, "tax_rate": 0}],
				mapeo_cuentas,
			)
		)
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IVA Retenido Arrendamiento",
				[{"rol_fiscal": ROL_RET_IVA_ARR, "tax_rate": 0}],
				mapeo_cuentas,
			)
		)
		# Combinado
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT ISR + IVA Ret Arrendamiento",
				[
					{"rol_fiscal": ROL_RET_ISR_ARR, "tax_rate": 0},
					{"rol_fiscal": ROL_RET_IVA_ARR, "tax_rate": 0},
				],
				mapeo_cuentas,
			)
		)

	# ITT Retenciones Autotransporte
	if cfg.enable_ret_autotransporte:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT ISR Autotransporte",
				[{"rol_fiscal": ROL_RET_ISR_AUTO, "tax_rate": 0}],
				mapeo_cuentas,
			)
		)
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IVA Retenido Autotransporte",
				[{"rol_fiscal": ROL_RET_IVA_AUTO, "tax_rate": 0}],
				mapeo_cuentas,
			)
		)
		# Combinado
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT ISR + IVA Ret Autotransporte",
				[
					{"rol_fiscal": ROL_RET_ISR_AUTO, "tax_rate": 0},
					{"rol_fiscal": ROL_RET_IVA_AUTO, "tax_rate": 0},
				],
				mapeo_cuentas,
			)
		)

	# ITT Retenciones RESICO
	if cfg.enable_ret_resico:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT ISR + IVA Ret RESICO",
				[
					{"rol_fiscal": ROL_RET_ISR_RESICO, "tax_rate": 0},
					{"rol_fiscal": ROL_RET_IVA_RESICO, "tax_rate": 0},
				],
				mapeo_cuentas,
			)
		)

	return {"created": created, "company": company}
