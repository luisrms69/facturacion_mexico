import frappe
from frappe.utils import flt

# -----------------------------------------------------------
# RESOLUCIÓN DE CUENTAS POR "ROL" (ajusta si tus nombres difieren)
# -----------------------------------------------------------
ROL_IVA_NAC = "IVA por Pagar (Nacional)"
ROL_IVA_FRO = "IVA por Pagar (Frontera)"

ROL_IEPS_ALC = "IEPS por Pagar (Alcohol)"
ROL_IEPS_AZU = "IEPS por Pagar (Azúcar/Bebidas)"
ROL_IEPS_COMB = "IEPS por Pagar (Combustibles)"
ROL_IEPS_TAB = "IEPS por Pagar (Tabaco)"
ROL_IEPS_TABQ = "IEPS por Pagar (Tabaco Cuota)"

ROL_RET_IVA_HON = "Retención IVA Honorarios"
ROL_RET_ISR_HON = "Retención ISR Honorarios"


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

	# Buscar primero match exacto
	for m in mapeos:
		if m.rol_fiscal == rol:
			return m.cuenta_impuesto

	# Si no encuentra exacto, buscar con lógica fuzzy para roles legacy con porcentajes
	role_keywords = {
		"IVA por Pagar (Nacional)": ["IVA por Pagar", "16"],
		"IVA por Pagar (Frontera)": ["IVA por Pagar", "frontera"],
		"Retención IVA Honorarios": ["IVA Retenido", "Profesionales"],
		"Retención ISR Honorarios": ["ISR Retenido", "Honorarios"],
	}

	keywords = role_keywords.get(rol, [])
	if keywords:
		for m in mapeos:
			if all(kw.lower() in m.rol_fiscal.lower() for kw in keywords):
				return m.cuenta_impuesto

	# Si aún no encuentra, error
	available = ", ".join([m.rol_fiscal for m in mapeos])
	frappe.throw(f"No se encontró mapeo para '{rol}' en '{company}'.\n" f"Roles disponibles: {available}")

	return ""  # Never reached


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
def fila_iva_base(account_head: str, zona: str, tasa_valor: float) -> dict:
	"""
	IVA base sobre neto. La tasa se aplica aquí (valor), pero NO se escribe en la descripción.
	"""
	return {
		"charge_type": "On Net Total",
		"row_id": None,
		"rate": tasa_valor,  # valor numérico, no en texto
		"description": f"IVA {zona} - Base (Resto)",
		"account_head": account_head,
		"add_deduct_tax": "Add",
		"category": "Valuation and Total",
	}


def fila_ieps_tasa(account_head: str, concepto: str) -> dict:
	"""IEPS tasa via ITT (rate=0 aquí; lo fija el ITT/ítem)."""
	return {
		"charge_type": "On Net Total",
		"row_id": None,
		"rate": 0.0,
		"description": f"IEPS {concepto} - Tasa (via ITT)",
		"account_head": account_head,
		"add_deduct_tax": "Add",
		"category": "Valuation and Total",
	}


def fila_ieps_cuota(account_head: str, concepto: str) -> dict:
	"""IEPS cuota (Actual; el monto lo calcula el hook existente)."""
	return {
		"charge_type": "Actual",
		"row_id": None,
		"rate": 0.0,
		"description": f"IEPS {concepto} - Cuota (via ITT)",
		"account_head": account_head,
		"add_deduct_tax": "Add",
		"category": "Valuation and Total",
	}


def fila_retencion(account_head: str, desc: str, rate: float | None = None) -> dict:
	"""
	Retenciones; si vienen por ITT, deja rate=0 y el ITT/hook lo fija.
	"""
	return {
		"charge_type": "On Net Total",
		"row_id": None,
		"rate": flt(rate) if rate is not None else 0.0,
		"description": desc,
		"account_head": account_head,
		"add_deduct_tax": "Deduct",
		"category": "Total",
	}


# -----------------------------------------------------------
# CONSTRUCCIÓN DE CADA VARIANTE (solo filas necesarias)
# -----------------------------------------------------------
def _build_rows(company: str, zona: str, iva_rate: float, variant: str) -> list[dict]:
	rows: list[dict] = []

	# IVA base (una sola fila por variante)
	iva_acc = _get_account_head_by_role(company, ROL_IVA_NAC if zona == "Nacional" else ROL_IVA_FRO)
	rows.append(fila_iva_base(iva_acc, zona, iva_rate))

	# IEPS (solo si aplica)
	if variant in ("IEPS", "Total"):
		rows.append(fila_ieps_tasa(_get_account_head_by_role(company, ROL_IEPS_ALC), "Alcohol"))
		rows.append(fila_ieps_cuota(_get_account_head_by_role(company, ROL_IEPS_AZU), "Azúcar/Bebidas"))
		rows.append(fila_ieps_cuota(_get_account_head_by_role(company, ROL_IEPS_COMB), "Combustibles"))
		rows.append(fila_ieps_tasa(_get_account_head_by_role(company, ROL_IEPS_TAB), "Tabaco"))
		rows.append(fila_ieps_cuota(_get_account_head_by_role(company, ROL_IEPS_TABQ), "Tabaco"))

	# Retenciones (solo si aplica)
	if variant in ("Retenciones", "Total"):
		rows.append(
			fila_retencion(_get_account_head_by_role(company, ROL_RET_IVA_HON), "Retención IVA - Honorarios")
		)
		rows.append(
			fila_retencion(_get_account_head_by_role(company, ROL_RET_ISR_HON), "Retención ISR - Honorarios")
		)

	return rows


def _make_stct(company: str, title: str, rows: list[dict]) -> str:
	exists = frappe.db.exists("Sales Taxes and Charges Template", {"title": title, "company": company})
	if exists:
		return exists

	doc = frappe.new_doc("Sales Taxes and Charges Template")
	doc.company = company
	doc.title = title  # << SIN números de tasa
	doc.is_sales_tax_template = 1
	doc.disabled = 0
	for idx, r in enumerate(rows, start=1):
		r["idx"] = idx
		doc.append("taxes", r)
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


@frappe.whitelist()
def generate_8_stct_for_company(
	company: str,
	abbr: str | None = None,
	iva_nacional_rate: float | None = None,
	iva_frontera_rate: float | None = None,
):
	"""
    Crea 8 STCT (Nacional/Frontera x Básico/IEPS/Retenciones/Total) con nombres SEMÁNTICOS
    ('IVA Nacional - ...', 'IVA Frontera - ...') y sin números de tasa en títulos/descripciones.

    USO (bench):
    bench --site <site> execute facturacion_mexico.facturacion_fiscal.setup.stct8.generate_8_stct_for_company \
      --kwargs "{'company':'Mi Empresa SA de CV','abbr':'_TC','iva_nacional_rate':16,'iva_frontera_rate':8}"
    """
	abbr = abbr or _get_company_abbr(company)
	iva_nat, iva_fro = _get_iva_rates(company, iva_nacional_rate, iva_frontera_rate)

	created = []
	for zona, rate in (("Nacional", iva_nat), ("Frontera", iva_fro)):
		for variant in ("Básico", "IEPS", "Retenciones", "Total"):
			title = f"IVA {zona} - {variant} - {abbr}"
			rows = _build_rows(company, zona, rate, variant)
			name = _make_stct(company, title, rows)
			created.append(name)

	_disable_old_percent_named_templates(company)
	return {"created": created, "disabled_old": True}


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
			"ITT IVA 16%",
			[{"rol_fiscal": "IVA por Pagar (16%)", "tax_rate": 16.0}],
			mapeo_cuentas,
		)
	)

	created.append(
		_crear_o_actualizar_itt(
			company,
			abbr,
			"ITT IVA 0%",
			[
				{"rol_fiscal": "IVA por Pagar (16%)", "tax_rate": 0},
				{"rol_fiscal": "IVA por Pagar (8% frontera)", "tax_rate": 0},
				{"rol_fiscal": "IVA por Pagar (0% exportación)", "tax_rate": 0},
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
				{"rol_fiscal": "IVA por Pagar (16%)", "tax_rate": 0},
				{"rol_fiscal": "IVA por Pagar (8% frontera)", "tax_rate": 0},
				{"rol_fiscal": "IVA Exento", "tax_rate": 0},
			],
			mapeo_cuentas,
		)
	)

	# ITT IVA Frontera 8%
	if cfg.enable_frontera:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IVA 8% Frontera",
				[{"rol_fiscal": "IVA por Pagar (8% frontera)", "tax_rate": 8.0}],
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
				[{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": 0}],  # Tasa se fija en ITT del item
				mapeo_cuentas,
			)
		)

	if cfg.enable_ieps_azucar:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IEPS Azúcar",
				[{"rol_fiscal": "IEPS por Pagar (Azúcar/Bebidas)", "tax_rate": 0}],
				mapeo_cuentas,
			)
		)

	if cfg.enable_ieps_combustibles:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IEPS Combustibles",
				[{"rol_fiscal": "IEPS por Pagar (Combustibles)", "tax_rate": 0}],
				mapeo_cuentas,
			)
		)

	if cfg.enable_ieps_tabaco:
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IEPS Tabaco",
				[{"rol_fiscal": "IEPS por Pagar (Tabaco)", "tax_rate": 0}],
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
				[{"rol_fiscal": "ISR Retenido (Honorarios)", "tax_rate": 0}],
				mapeo_cuentas,
			)
		)
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IVA Retenido Servicios",
				[{"rol_fiscal": "IVA Retenido (Servicios Profesionales)", "tax_rate": 0}],
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
					{"rol_fiscal": "ISR Retenido (Honorarios)", "tax_rate": 0},
					{"rol_fiscal": "IVA Retenido (Servicios Profesionales)", "tax_rate": 0},
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
				[{"rol_fiscal": "ISR Retenido (Arrendamiento)", "tax_rate": 0}],
				mapeo_cuentas,
			)
		)
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IVA Retenido Arrendamiento",
				[{"rol_fiscal": "IVA Retenido (Arrendamiento)", "tax_rate": 0}],
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
					{"rol_fiscal": "ISR Retenido (Arrendamiento)", "tax_rate": 0},
					{"rol_fiscal": "IVA Retenido (Arrendamiento)", "tax_rate": 0},
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
				[{"rol_fiscal": "ISR Retenido (Autotransporte)", "tax_rate": 0}],
				mapeo_cuentas,
			)
		)
		created.append(
			_crear_o_actualizar_itt(
				company,
				abbr,
				"ITT IVA Retenido Autotransporte",
				[{"rol_fiscal": "IVA Retenido (Autotransporte)", "tax_rate": 0}],
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
					{"rol_fiscal": "ISR Retenido (Autotransporte)", "tax_rate": 0},
					{"rol_fiscal": "IVA Retenido (Autotransporte)", "tax_rate": 0},
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
					{"rol_fiscal": "ISR Retenido (RESICO)", "tax_rate": 0},
					{"rol_fiscal": "IVA Retenido (RESICO)", "tax_rate": 0},
				],
				mapeo_cuentas,
			)
		)

	return {"created": created, "company": company}
