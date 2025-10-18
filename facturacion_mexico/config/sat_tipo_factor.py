"""
Configuración de Tipo de Factor SAT por Rol Fiscal

Este archivo centraliza la configuración de tipo_factor (Tasa/Cuota)
según el rol fiscal para mapeos automáticos.

NO MODIFICAR sin consultar normativa SAT y documentación FacturAPI.

Referencia:
- SAT: Catálogo c_TipoFactor
- FacturAPI: Documentación de tasas permitidas
"""

from typing import ClassVar


class SATTipoFactor:
	"""
	Configuración de tipo de factor SAT según rol fiscal.

	Define si un rol fiscal usa "Tasa" (porcentaje) o "Cuota" (monto específico)
	según normativa SAT y compatibilidad con FacturAPI.

	IMPORTANTE: Esta configuración se propaga automáticamente vía fixtures.
	No debe ser modificable por usuarios finales.
	"""

	# Tipos de factor SAT
	TASA = "Tasa"
	CUOTA = "Cuota"

	# Mapeo ROL FISCAL → TIPO FACTOR
	# Este es el catálogo autoritativo que se usa en la configuración automática
	CONFIGURACION: ClassVar[dict] = {
		# === IVA (siempre Tasa) ===
		"IVA por Pagar (16%)": {
			"tipo_factor": TASA,
			"impuesto_sat": "002",
			"nombre_sat": "IVA",
			"descripcion": "IVA General 16%",
		},
		"IVA por Pagar (8% frontera)": {
			"tipo_factor": TASA,
			"impuesto_sat": "002",
			"nombre_sat": "IVA",
			"descripcion": "IVA Frontera 8%",
		},
		"IVA por Pagar (0% exportación)": {
			"tipo_factor": TASA,
			"impuesto_sat": "002",
			"nombre_sat": "IVA",
			"descripcion": "IVA Exportación 0%",
		},
		"IVA Exento": {
			"tipo_factor": TASA,
			"impuesto_sat": "002",
			"nombre_sat": "IVA",
			"descripcion": "IVA Exento 0%",
		},
		# === IEPS Tasa (porcentajes fijos) ===
		"IEPS por Pagar (Alcohol)": {
			"tipo_factor": TASA,
			"impuesto_sat": "003",
			"nombre_sat": "IEPS",
			"descripcion": "IEPS Alcohol 26.5% (tasa fija)",
		},
		"IEPS por Pagar (Tabaco)": {
			"tipo_factor": TASA,
			"impuesto_sat": "003",
			"nombre_sat": "IEPS",
			"descripcion": "IEPS Tabaco 160% (tasa fija)",
		},
		# === IEPS Cuota (montos específicos por unidad) ===
		"IEPS por Pagar (Azúcar/Bebidas)": {
			"tipo_factor": CUOTA,
			"impuesto_sat": "003",
			"nombre_sat": "IEPS",
			"descripcion": "IEPS Bebidas $1.27/litro (cuota específica)",
		},
		"IEPS por Pagar (Combustibles)": {
			"tipo_factor": CUOTA,
			"impuesto_sat": "003",
			"nombre_sat": "IEPS",
			"descripcion": "IEPS Combustibles cuota variable (cuota específica)",
		},
		# === Retenciones IVA (siempre Tasa) ===
		"IVA Retenido (Servicios Profesionales)": {
			"tipo_factor": TASA,
			"impuesto_sat": "002",
			"nombre_sat": "IVA",
			"descripcion": "IVA Retenido 66.67% del IVA trasladado",
		},
		"IVA Retenido (Arrendamiento)": {
			"tipo_factor": TASA,
			"impuesto_sat": "002",
			"nombre_sat": "IVA",
			"descripcion": "IVA Retenido 66.67% del IVA trasladado",
		},
		"IVA Retenido (Autotransporte)": {
			"tipo_factor": TASA,
			"impuesto_sat": "002",
			"nombre_sat": "IVA",
			"descripcion": "IVA Retenido 66.67% del IVA trasladado",
		},
		"IVA Retenido (RESICO)": {
			"tipo_factor": TASA,
			"impuesto_sat": "002",
			"nombre_sat": "IVA",
			"descripcion": "IVA Retenido 66.67% del IVA trasladado",
		},
		# === Retenciones ISR (siempre Tasa) ===
		"ISR Retenido (Honorarios)": {
			"tipo_factor": TASA,
			"impuesto_sat": "001",
			"nombre_sat": "ISR",
			"descripcion": "ISR Retenido 10%",
		},
		"ISR Retenido (Arrendamiento)": {
			"tipo_factor": TASA,
			"impuesto_sat": "001",
			"nombre_sat": "ISR",
			"descripcion": "ISR Retenido 10%",
		},
		"ISR Retenido (Autotransporte)": {
			"tipo_factor": TASA,
			"impuesto_sat": "001",
			"nombre_sat": "ISR",
			"descripcion": "ISR Retenido 4%",
		},
		"ISR Retenido (RESICO)": {
			"tipo_factor": TASA,
			"impuesto_sat": "001",
			"nombre_sat": "ISR",
			"descripcion": "ISR Retenido 1.25% (configurable)",
		},
	}

	@classmethod
	def get_tipo_factor(cls, rol_fiscal: str) -> str:
		"""
		Obtener tipo de factor para un rol fiscal.

		Args:
			rol_fiscal: Nombre del rol fiscal

		Returns:
			str: "Tasa" o "Cuota"

		Raises:
			ValueError: Si el rol fiscal no existe en configuración
		"""
		config = cls.CONFIGURACION.get(rol_fiscal)
		if not config:
			raise ValueError(f"Rol fiscal '{rol_fiscal}' no encontrado en configuración SAT")
		return config["tipo_factor"]

	@classmethod
	def get_metadata_completa(cls, rol_fiscal: str) -> dict:
		"""
		Obtener metadata completa SAT para un rol fiscal.

		Args:
			rol_fiscal: Nombre del rol fiscal

		Returns:
			dict: Configuración completa con tipo_factor, impuesto_sat, nombre_sat

		Raises:
			ValueError: Si el rol fiscal no existe
		"""
		config = cls.CONFIGURACION.get(rol_fiscal)
		if not config:
			raise ValueError(f"Rol fiscal '{rol_fiscal}' no encontrado en configuración SAT")
		return config.copy()

	@classmethod
	def es_cuota(cls, rol_fiscal: str) -> bool:
		"""
		Verificar si un rol fiscal usa Cuota.

		Args:
			rol_fiscal: Nombre del rol fiscal

		Returns:
			bool: True si usa Cuota, False si usa Tasa
		"""
		return cls.get_tipo_factor(rol_fiscal) == cls.CUOTA

	@classmethod
	def es_tasa(cls, rol_fiscal: str) -> bool:
		"""
		Verificar si un rol fiscal usa Tasa.

		Args:
			rol_fiscal: Nombre del rol fiscal

		Returns:
			bool: True si usa Tasa, False si usa Cuota
		"""
		return cls.get_tipo_factor(rol_fiscal) == cls.TASA

	@classmethod
	def get_roles_por_tipo_factor(cls, tipo_factor: str) -> list[str]:
		"""
		Obtener lista de roles fiscales que usan un tipo de factor específico.

		Args:
			tipo_factor: "Tasa" o "Cuota"

		Returns:
			list: Roles fiscales que usan ese tipo de factor
		"""
		return [rol for rol, config in cls.CONFIGURACION.items() if config["tipo_factor"] == tipo_factor]

	@classmethod
	def validar_rol_fiscal(cls, rol_fiscal: str) -> bool:
		"""
		Validar si un rol fiscal existe en la configuración.

		Args:
			rol_fiscal: Nombre del rol fiscal

		Returns:
			bool: True si existe, False si no
		"""
		return rol_fiscal in cls.CONFIGURACION


# Alias para compatibilidad
SAT_TIPO_FACTOR = SATTipoFactor
