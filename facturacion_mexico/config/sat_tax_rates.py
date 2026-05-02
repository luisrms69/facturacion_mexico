"""
Configuración de Tasas Permitidas por FacturAPI

Este archivo centraliza las tasas permitidas según documentación FacturAPI.
Las tasas aquí definidas son las únicas aceptadas por el PAC.

NO MODIFICAR sin consultar documentación oficial FacturAPI.

Referencia: Error PAC "rate must be one of [...]"
Actualizado: 2025-10-17
"""

from typing import ClassVar


class FacturAPITaxRates:
	"""
	Tasas de impuestos permitidas por FacturAPI.

	FacturAPI valida que las tasas enviadas estén en listas predefinidas
	según el tipo de impuesto. Estas listas son proporcionadas por el PAC
	y NO son configurables.
	"""

	# Tasas IVA permitidas (como decimales)
	IVA_RATES: ClassVar[list[float]] = [
		0.16,  # IVA General 16%
		0.08,  # IVA Frontera 8%
		0.0,  # IVA 0% / Exento
	]

	# Tasas IEPS permitidas (como decimales)
	# Según error PAC: [0.265, 0.3, 0.53, 0.5, 1.6, 0.304, 0.25, 0.09, 0.08, 0.07, 0.06, 0.03, 0]
	IEPS_RATES: ClassVar[list[float]] = [
		0.0,  # IEPS 0%
		0.03,  # IEPS 3%
		0.06,  # IEPS 6%
		0.07,  # IEPS 7%
		0.08,  # IEPS 8%
		0.09,  # IEPS 9%
		0.25,  # IEPS 25%
		0.265,  # IEPS 26.5% - Alcohol
		0.3,  # IEPS 30%
		0.304,  # IEPS 30.4%
		0.5,  # IEPS 50%
		0.53,  # IEPS 53%
		1.6,  # IEPS 160% - Tabaco
	]

	# Tasas ISR Retención permitidas (como decimales)
	ISR_RETENCION_RATES: ClassVar[list[float]] = [
		0.01,  # ISR 1% - RESICO (mínimo)
		0.0125,  # ISR 1.25% - RESICO (default)
		0.04,  # ISR 4% - Autotransporte
		0.10,  # ISR 10% - Honorarios/Arrendamiento
	]

	# Tasas IVA Retención permitidas (como decimales)
	# Nota: IVA Retenido es 2/3 del IVA trasladado (66.6667%)
	IVA_RETENCION_RATES: ClassVar[list[float]] = [
		0.666667,  # 2/3 del IVA trasladado (valor exacto)
		0.6667,  # 2/3 del IVA trasladado (redondeado 4 decimales)
	]

	@classmethod
	def validar_rate_iva(cls, rate: float) -> bool:
		"""
		Validar si una tasa IVA es permitida por FacturAPI.

		Args:
			rate: Tasa como decimal (ej: 0.16 para 16%)

		Returns:
			bool: True si es válida, False si no
		"""
		# Redondear a 4 decimales para comparación
		rate_rounded = round(rate, 4)
		return any(abs(rate_rounded - allowed) < 0.0001 for allowed in cls.IVA_RATES)

	@classmethod
	def validar_rate_ieps(cls, rate: float) -> bool:
		"""
		Validar si una tasa IEPS es permitida por FacturAPI.

		Args:
			rate: Tasa como decimal (ej: 0.265 para 26.5%)

		Returns:
			bool: True si es válida, False si no
		"""
		# Redondear a 4 decimales para comparación
		rate_rounded = round(rate, 4)
		return any(abs(rate_rounded - allowed) < 0.0001 for allowed in cls.IEPS_RATES)

	@classmethod
	def validar_rate_isr_retencion(cls, rate: float) -> bool:
		"""
		Validar si una tasa ISR Retención es permitida.

		Args:
			rate: Tasa como decimal (ej: 0.10 para 10%)

		Returns:
			bool: True si es válida, False si no
		"""
		rate_rounded = round(rate, 4)
		return any(abs(rate_rounded - allowed) < 0.0001 for allowed in cls.ISR_RETENCION_RATES)

	@classmethod
	def validar_rate_iva_retencion(cls, rate: float) -> bool:
		"""
		Validar si una tasa IVA Retención es permitida.

		Args:
			rate: Tasa como decimal (ej: 0.6667 para 66.67%)

		Returns:
			bool: True si es válida, False si no
		"""
		rate_rounded = round(rate, 4)
		return any(abs(rate_rounded - allowed) < 0.0001 for allowed in cls.IVA_RETENCION_RATES)

	@classmethod
	def validar_rate_por_tipo(cls, tipo_impuesto: str, rate: float, es_retencion: bool = False) -> bool:
		"""
		Validar tasa según tipo de impuesto.

		Args:
			tipo_impuesto: "IVA", "IEPS", "ISR"
			rate: Tasa como decimal
			es_retencion: Si es retención (True) o traslado (False)

		Returns:
			bool: True si es válida, False si no
		"""
		if tipo_impuesto == "IVA":
			if es_retencion:
				return cls.validar_rate_iva_retencion(rate)
			return cls.validar_rate_iva(rate)
		elif tipo_impuesto == "IEPS":
			return cls.validar_rate_ieps(rate)
		elif tipo_impuesto == "ISR":
			return cls.validar_rate_isr_retencion(rate)
		return False

	@classmethod
	def get_rates_permitidas(cls, tipo_impuesto: str, es_retencion: bool = False) -> list[float]:
		"""
		Obtener lista de tasas permitidas para un tipo de impuesto.

		Args:
			tipo_impuesto: "IVA", "IEPS", "ISR"
			es_retencion: Si es retención

		Returns:
			list: Tasas permitidas como decimales
		"""
		if tipo_impuesto == "IVA":
			if es_retencion:
				return cls.IVA_RETENCION_RATES.copy()
			return cls.IVA_RATES.copy()
		elif tipo_impuesto == "IEPS":
			return cls.IEPS_RATES.copy()
		elif tipo_impuesto == "ISR":
			return cls.ISR_RETENCION_RATES.copy()
		return []

	@classmethod
	def format_rate_display(cls, rate: float) -> str:
		"""
		Formatear tasa para display (porcentaje).

		Args:
			rate: Tasa como decimal (ej: 0.16)

		Returns:
			str: Tasa formateada (ej: "16.00%")
		"""
		return f"{rate * 100:.2f}%"


# Alias para compatibilidad
FACTURAPI_RATES = FacturAPITaxRates
