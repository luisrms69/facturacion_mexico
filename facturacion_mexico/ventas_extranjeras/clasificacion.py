"""Clasificación territorial de una Sales Invoice: receptor nacional vs extranjero.

Separada del tratamiento fiscal (IVA/ObjetoImp/STCT/exportación): esto SOLO decide
territorialidad para el ruteo de la cuenta de ingreso. Usa datos nativos y auditables,
nunca Customer Group, currency, Tax Category ni ``fm_tax_regime``.

Prioridad (diseño aprobado):
1. ``XEXX010101000`` en ``Customer.tax_id`` — RFC genérico para operaciones con
   residentes en el extranjero: señal FUERTE, resuelve inconsistencias de Address.
2. País de la dirección: ``Sales Invoice.customer_address`` → ``Address.country``;
   si falta, la dirección primaria del Customer → ``Address.country``. Se compara
   contra ``Company.country``.
3. Fallback: ``Customer.territory == "Rest Of The World"``.
4. Sin evidencia suficiente → ``INDETERMINADO`` (no se inventa clasificación).

Un RFC mexicano normal NO basta por sí solo para afirmar residencia nacional si no
existe otra evidencia territorial (por eso NACIONAL exige país == Company.country).
"""

import frappe

# Resultados posibles de la clasificación.
EXTRANJERA = "EXTRANJERA"
NACIONAL = "NACIONAL"
INDETERMINADO = "INDETERMINADO"

# RFC genérico SAT para receptores residentes en el extranjero.
RFC_GENERICO_EXTRANJERO = "XEXX010101000"
# Territory estándar de ERPNext usado como fallback de residencia extranjera.
TERRITORY_RESTO_DEL_MUNDO = "Rest Of The World"

# Flag transitorio (no persistente) donde el importador cfdi_emitidos deposita la
# evidencia territorial del XML histórico. Cuando está presente, es AUTORITATIVA:
# la historia no se reinterpreta con datos maestros actuales que la contradigan.
FLAG_EVIDENCIA_CFDI = "fm_cfdi_territorial"


def clasificar_desde_cfdi(evidencia: dict) -> str:
	"""Clasificar territorialidad desde la evidencia del CFDI (fuente de verdad histórica).

	Extranjero si: RFC receptor == XEXX, o hay ``ResidenciaFiscal``, o hay ``NumRegIdTrib``.
	En otro caso el CFDI describe un receptor nacional (RFC mexicano, sin residencia
	extranjera) → NACIONAL. Nunca INDETERMINADO: el XML siempre trae el RFC del receptor.
	"""
	rfc = (evidencia.get("receptor_rfc") or "").strip().upper()
	if rfc == RFC_GENERICO_EXTRANJERO:
		return EXTRANJERA
	if (evidencia.get("receptor_residencia_fiscal") or "").strip():
		return EXTRANJERA
	if (evidencia.get("receptor_num_reg_id_trib") or "").strip():
		return EXTRANJERA
	return NACIONAL


def _pais_direccion(doc, customer: str) -> str | None:
	"""País de la dirección más relevante de la operación.

	Preferencia: la dirección del propio documento (``customer_address``), luego la
	dirección primaria del Customer, y como último recurso cualquier dirección
	vinculada con país definido. Devuelve ``None`` si no hay país en ninguna.
	"""
	# 1) Dirección del documento
	addr = doc.get("customer_address") if hasattr(doc, "get") else getattr(doc, "customer_address", None)
	if addr:
		pais = frappe.db.get_value("Address", addr, "country")
		if pais:
			return pais

	# 2) Dirección primaria del Customer
	prim = frappe.db.get_value("Customer", customer, "customer_primary_address")
	if prim:
		pais = frappe.db.get_value("Address", prim, "country")
		if pais:
			return pais

	# 3) Cualquier dirección vinculada al Customer con país definido
	enlaces = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
		fields=["parent"],
	)
	for e in enlaces:
		pais = frappe.db.get_value("Address", e.get("parent"), "country")
		if pais:
			return pais

	return None


def clasificar_territorialidad(doc) -> str:
	"""Clasificar la Sales Invoice como EXTRANJERA / NACIONAL / INDETERMINADO.

	No modifica el documento. Ver el docstring del módulo para la prioridad exacta.
	"""
	# 0) Evidencia del CFDI histórico (transitoria en flags): AUTORITATIVA si está presente.
	flags = getattr(doc, "flags", None)
	evidencia = getattr(flags, FLAG_EVIDENCIA_CFDI, None) if flags is not None else None
	if evidencia:
		return clasificar_desde_cfdi(evidencia)

	company = doc.get("company") if hasattr(doc, "get") else getattr(doc, "company", None)
	customer = doc.get("customer") if hasattr(doc, "get") else getattr(doc, "customer", None)
	if not company or not customer:
		return INDETERMINADO

	# 1) Señal fuerte: RFC genérico extranjero (override de inconsistencias de Address)
	tax_id = (frappe.db.get_value("Customer", customer, "tax_id") or "").strip().upper()
	if tax_id == RFC_GENERICO_EXTRANJERO:
		return EXTRANJERA

	# 2) País de la dirección vs país de la empresa
	company_country = frappe.db.get_value("Company", company, "country")
	pais = _pais_direccion(doc, customer)
	if pais and company_country:
		return EXTRANJERA if pais != company_country else NACIONAL

	# 3) Fallback por Territory
	territory = frappe.db.get_value("Customer", customer, "territory")
	if territory == TERRITORY_RESTO_DEL_MUNDO:
		return EXTRANJERA

	# 4) Sin evidencia territorial suficiente: no adivinar
	return INDETERMINADO
