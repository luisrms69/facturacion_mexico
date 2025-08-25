"""
Configuración de Motivos de Cancelación SAT - CFDI 4.0

Este archivo centraliza los motivos oficiales de cancelación según el SAT.
No modificar códigos sin consultar catálogo oficial SAT.

Referencia: Anexo 20 - Catálogo de Motivos de Cancelación
"""

from typing import ClassVar


class SATCancellationMotives:
	"""
	Motivos oficiales de cancelación de CFDI según SAT.

	Los códigos son oficiales del SAT y NO deben modificarse.
	Las descripciones pueden traducirse pero manteniendo el significado.
	"""

	# Códigos oficiales SAT
	ERRORES_CON_RELACION = "01"
	ERRORES_SIN_RELACION = "02"
	NO_SE_LLEVO_A_CABO = "03"
	OPERACION_NOMINATIVA = "04"

	# Mapeo código → descripción para UI
	DESCRIPTIONS: ClassVar[dict] = {
		ERRORES_CON_RELACION: "Comprobantes emitidos con errores con relación",
		ERRORES_SIN_RELACION: "Comprobantes emitidos con errores sin relación",
		NO_SE_LLEVO_A_CABO: "No se llevó a cabo la operación",
		OPERACION_NOMINATIVA: "Operación nominativa relacionada en factura global",
	}

	# Lista de todos los códigos válidos
	VALID_CODES: ClassVar[list] = [
		ERRORES_CON_RELACION,
		ERRORES_SIN_RELACION,
		NO_SE_LLEVO_A_CABO,
		OPERACION_NOMINATIVA,
	]

	# Motivos que requieren UUID de sustitución
	REQUIRES_SUBSTITUTION: ClassVar[list] = [
		ERRORES_CON_RELACION  # Solo "01" requiere UUID sustitución
	]

	@classmethod
	def get_options_for_select(cls) -> list[str]:
		"""
		Generar opciones para campo Select en formato Frappe.

		Returns:
			Lista de strings en formato "codigo\tdescripcion"
		"""
		return [f"{code}\t{description}" for code, description in cls.DESCRIPTIONS.items()]

	@classmethod
	def get_description(cls, code: str) -> str:
		"""
		Obtener descripción de un código de motivo.

		Args:
			code: Código SAT (01, 02, 03, 04)

		Returns:
			Descripción del motivo o código si no se encuentra
		"""
		return cls.DESCRIPTIONS.get(code, code)

	@classmethod
	def requires_substitution_uuid(cls, code: str) -> bool:
		"""
		Verificar si un motivo requiere UUID de sustitución.

		Args:
			code: Código SAT

		Returns:
			True si requiere UUID de sustitución
		"""
		return code in cls.REQUIRES_SUBSTITUTION

	@classmethod
	def is_valid_code(cls, code: str) -> bool:
		"""
		Validar si un código es válido según SAT.

		Args:
			code: Código a validar

		Returns:
			True si es código SAT válido
		"""
		return code in cls.VALID_CODES

	@classmethod
	def get_valid_codes(cls) -> list[str]:
		"""
		Obtener lista de códigos válidos SAT.

		Returns:
			Lista de códigos SAT válidos
		"""
		return cls.VALID_CODES.copy()

	@classmethod
	def get_config(cls) -> dict:
		"""
		Obtener configuración completa para APIs y UI.

		Returns:
			Dict con toda la configuración de motivos
		"""
		return {
			"codes": cls.VALID_CODES,
			"descriptions": cls.DESCRIPTIONS,
			"requires_substitution": cls.REQUIRES_SUBSTITUTION,
			"select_options": cls.get_options_for_select(),
		}


# Alias para compatibilidad y uso simple
SAT_MOTIVES = SATCancellationMotives
