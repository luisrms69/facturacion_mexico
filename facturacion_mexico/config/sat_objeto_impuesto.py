"""
Configuración de Objeto de Impuesto SAT - CFDI 4.0

Este archivo centraliza el catálogo c_ObjetoImp según normativa SAT.
No modificar códigos sin consultar catálogo oficial SAT.

Referencia: Anexo 20 - Catálogo c_ObjetoImp
Última actualización catálogo: 2025-01-13 (versión 4.0)
"""

from typing import ClassVar


class SATObjetoImpuesto:
	"""
	Catálogo oficial de Objeto de Impuesto (ObjetoImp) según SAT.

	Los códigos son oficiales del SAT y NO deben modificarse.
	Las descripciones son traducción fiel del catálogo SAT.

	Actualización 2025: Se agregaron claves 06, 07, 08 (vigentes desde 2025-01-13)
	"""

	# Códigos oficiales SAT - Versión original (01-05)
	NO_OBJETO_IMPUESTO = "01"
	SI_OBJETO_IMPUESTO = "02"
	SI_OBJETO_NO_OBLIGADO_DESGLOSE = "03"
	SI_OBJETO_NO_CAUSA_IMPUESTO = "04"
	SI_OBJETO_IVA_PODEBI = "05"

	# Códigos nuevos 2025 (06-08) - Vigentes desde 2025-01-13
	SI_OBJETO_IVA_NO_TRASLADO = "06"
	NO_TRASLADO_IVA_SI_DESGLOSE_IEPS = "07"
	NO_TRASLADO_IVA_NO_DESGLOSE_IEPS = "08"

	# Mapeo código → descripción para UI (textos oficiales SAT)
	DESCRIPTIONS: ClassVar[dict] = {
		NO_OBJETO_IMPUESTO: "01 - No objeto de impuesto",
		SI_OBJETO_IMPUESTO: "02 - Sí objeto de impuesto",
		SI_OBJETO_NO_OBLIGADO_DESGLOSE: "03 - Sí objeto del impuesto y no obligado al desglose",
		SI_OBJETO_NO_CAUSA_IMPUESTO: "04 - Sí objeto del impuesto y no causa impuesto",
		SI_OBJETO_IVA_PODEBI: "05 - Sí objeto del impuesto, IVA crédito PODEBI",
		SI_OBJETO_IVA_NO_TRASLADO: "06 - Sí objeto del IVA, No traslado IVA",
		NO_TRASLADO_IVA_SI_DESGLOSE_IEPS: "07 - No traslado del IVA, Sí desglose IEPS",
		NO_TRASLADO_IVA_NO_DESGLOSE_IEPS: "08 - No traslado del IVA, No desglose IEPS",
	}

	# Descripciones cortas para uso interno
	SHORT_DESCRIPTIONS: ClassVar[dict] = {
		NO_OBJETO_IMPUESTO: "No objeto",
		SI_OBJETO_IMPUESTO: "Sí objeto (requiere desglose)",
		SI_OBJETO_NO_OBLIGADO_DESGLOSE: "Sí objeto (sin desglose)",
		SI_OBJETO_NO_CAUSA_IMPUESTO: "Sí objeto (no causa)",
		SI_OBJETO_IVA_PODEBI: "IVA PODEBI",
		SI_OBJETO_IVA_NO_TRASLADO: "IVA sin traslado",
		NO_TRASLADO_IVA_SI_DESGLOSE_IEPS: "No IVA, sí IEPS",
		NO_TRASLADO_IVA_NO_DESGLOSE_IEPS: "No IVA, no IEPS",
	}

	# Lista de todos los códigos válidos (incluye nuevos 2025)
	VALID_CODES: ClassVar[list] = [
		NO_OBJETO_IMPUESTO,
		SI_OBJETO_IMPUESTO,
		SI_OBJETO_NO_OBLIGADO_DESGLOSE,
		SI_OBJETO_NO_CAUSA_IMPUESTO,
		SI_OBJETO_IVA_PODEBI,
		SI_OBJETO_IVA_NO_TRASLADO,
		NO_TRASLADO_IVA_SI_DESGLOSE_IEPS,
		NO_TRASLADO_IVA_NO_DESGLOSE_IEPS,
	]

	# Códigos que requieren desglose de impuestos en taxes[]
	REQUIRES_TAX_BREAKDOWN: ClassVar[list] = [
		SI_OBJETO_IMPUESTO,  # "02" - Requiere taxes[] obligatorio
	]

	# Códigos que NO permiten taxes[] (incompatibles con desglose)
	FORBIDS_TAX_BREAKDOWN: ClassVar[list] = [
		NO_OBJETO_IMPUESTO,  # "01"
		SI_OBJETO_NO_OBLIGADO_DESGLOSE,  # "03"
		SI_OBJETO_NO_CAUSA_IMPUESTO,  # "04"
	]

	@classmethod
	def get_options_for_select(cls) -> str:
		"""
		Generar opciones para campo Select en formato Frappe.

		Frappe Select usa newline-separated strings.

		Returns:
			String con opciones separadas por newline
		"""
		return "\n".join(cls.VALID_CODES)

	@classmethod
	def get_options_with_description(cls) -> str:
		"""
		Generar opciones con descripción para Select en formato Frappe.

		Returns:
			String "codigo\tdescripcion" separado por newline
		"""
		options = []
		for code in cls.VALID_CODES:
			description = cls.DESCRIPTIONS.get(code, code)
			options.append(f"{code}\t{description}")
		return "\n".join(options)

	@classmethod
	def get_description(cls, code: str, short: bool = False) -> str:
		"""
		Obtener descripción de un código ObjetoImp.

		Args:
			code: Código SAT (01-08)
			short: Si True, retorna descripción corta

		Returns:
			Descripción del objeto de impuesto o código si no se encuentra
		"""
		if short:
			return cls.SHORT_DESCRIPTIONS.get(code, code)
		return cls.DESCRIPTIONS.get(code, code)

	@classmethod
	def requires_tax_breakdown(cls, code: str) -> bool:
		"""
		Verificar si un código requiere desglose de impuestos.

		Args:
			code: Código SAT

		Returns:
			True si requiere taxes[] en payload
		"""
		return code in cls.REQUIRES_TAX_BREAKDOWN

	@classmethod
	def forbids_tax_breakdown(cls, code: str) -> bool:
		"""
		Verificar si un código NO permite desglose de impuestos.

		Args:
			code: Código SAT

		Returns:
			True si NO debe incluir taxes[] en payload
		"""
		return code in cls.FORBIDS_TAX_BREAKDOWN

	@classmethod
	def is_valid_code(cls, code: str) -> bool:
		"""
		Validar si un código es válido según SAT.

		Args:
			code: Código a validar

		Returns:
			True si es código SAT válido (01-08)
		"""
		return code in cls.VALID_CODES

	@classmethod
	def get_valid_codes(cls) -> list[str]:
		"""
		Obtener lista de códigos válidos SAT.

		Returns:
			Lista de códigos SAT válidos (01-08)
		"""
		return cls.VALID_CODES.copy()

	@classmethod
	def get_config(cls) -> dict:
		"""
		Obtener configuración completa para APIs y UI.

		Returns:
			Dict con toda la configuración ObjetoImp
		"""
		return {
			"codes": cls.VALID_CODES,
			"descriptions": cls.DESCRIPTIONS,
			"short_descriptions": cls.SHORT_DESCRIPTIONS,
			"requires_tax_breakdown": cls.REQUIRES_TAX_BREAKDOWN,
			"forbids_tax_breakdown": cls.FORBIDS_TAX_BREAKDOWN,
			"select_options": cls.get_options_for_select(),
			"select_options_with_description": cls.get_options_with_description(),
		}


# Alias para compatibilidad y uso simple
SAT_OBJETO_IMP = SATObjetoImpuesto
