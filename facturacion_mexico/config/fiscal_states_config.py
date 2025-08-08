"""
Configuración centralizada de estados fiscales para Facturación México.
Este archivo es la ÚNICA fuente de verdad para todos los estados fiscales.

IMPORTANTE: NO modificar estados sin actualizar TODAS las referencias en:
- Python: Importar desde este archivo
- JavaScript: Usar API endpoint get_fiscal_states_config
- DocType JSON: Mantener sincronizado manualmente (ver comentarios en JSON)

Fecha: 2025-08-08
Autor: Sistema Buzola
"""

from typing import ClassVar


class FiscalStates:
	"""
	Estados fiscales válidos para Factura Fiscal México.
	Arquitectura resiliente de estados fiscales.
	"""

	# Estados principales
	BORRADOR = "BORRADOR"
	PROCESANDO = "PROCESANDO"
	TIMBRADO = "TIMBRADO"
	ERROR = "ERROR"
	CANCELADO = "CANCELADO"
	PENDIENTE_CANCELACION = "PENDIENTE_CANCELACION"
	ARCHIVADO = "ARCHIVADO"

	# Lista de todos los estados válidos
	ALL_STATES: ClassVar[list] = [
		BORRADOR,
		PROCESANDO,
		TIMBRADO,
		ERROR,
		CANCELADO,
		PENDIENTE_CANCELACION,
		ARCHIVADO,
	]

	# Estados que permiten timbrado
	TIMBRABLE_STATES: ClassVar[list] = [BORRADOR, ERROR]

	# Estados que permiten cancelación
	CANCELABLE_STATES: ClassVar[list] = [TIMBRADO]

	# Estados finales (no se pueden modificar)
	FINAL_STATES: ClassVar[list] = [CANCELADO, ARCHIVADO]

	# Estados de error recuperables
	RECOVERABLE_ERROR_STATES: ClassVar[list] = [ERROR, PROCESANDO]

	@classmethod
	def is_valid(cls, state):
		"""Valida si un estado es válido."""
		return state in cls.ALL_STATES

	@classmethod
	def can_timbrar(cls, state):
		"""Verifica si se puede timbrar desde este estado."""
		return state in cls.TIMBRABLE_STATES

	@classmethod
	def can_cancelar(cls, state):
		"""Verifica si se puede cancelar desde este estado."""
		return state in cls.CANCELABLE_STATES

	@classmethod
	def is_final(cls, state):
		"""Verifica si es un estado final."""
		return state in cls.FINAL_STATES

	@classmethod
	def is_recoverable_error(cls, state):
		"""Verifica si es un error recuperable."""
		return state in cls.RECOVERABLE_ERROR_STATES

	@classmethod
	def get_next_state(cls, current_state, action):
		"""
		Determina el siguiente estado basado en la acción.

		Args:
		    current_state: Estado actual
		    action: Acción a realizar (timbrar, cancelar, error, etc.)

		Returns:
		    Nuevo estado o None si transición no válida
		"""
		transitions = {
			(cls.BORRADOR, "timbrar"): cls.PROCESANDO,
			(cls.PROCESANDO, "success"): cls.TIMBRADO,
			(cls.PROCESANDO, "error"): cls.ERROR,
			(cls.ERROR, "retry"): cls.PROCESANDO,
			(cls.ERROR, "timbrar"): cls.PROCESANDO,
			(cls.TIMBRADO, "cancelar"): cls.PENDIENTE_CANCELACION,
			(cls.PENDIENTE_CANCELACION, "confirmed"): cls.CANCELADO,
			(cls.PENDIENTE_CANCELACION, "error"): cls.TIMBRADO,
		}

		return transitions.get((current_state, action))

	@classmethod
	def to_dict(cls):
		"""
		Retorna diccionario con toda la configuración.
		Útil para exponer a JavaScript via API.
		"""
		return {
			"states": {
				"BORRADOR": cls.BORRADOR,
				"PROCESANDO": cls.PROCESANDO,
				"TIMBRADO": cls.TIMBRADO,
				"ERROR": cls.ERROR,
				"CANCELADO": cls.CANCELADO,
				"PENDIENTE_CANCELACION": cls.PENDIENTE_CANCELACION,
				"ARCHIVADO": cls.ARCHIVADO,
			},
			"all_states": cls.ALL_STATES,
			"timbrable_states": cls.TIMBRABLE_STATES,
			"cancelable_states": cls.CANCELABLE_STATES,
			"final_states": cls.FINAL_STATES,
			"recoverable_error_states": cls.RECOVERABLE_ERROR_STATES,
		}


class SyncStates:
	"""Estados de sincronización para fm_sync_status."""

	PENDING = "pending"
	SYNCED = "synced"
	ERROR = "error"

	ALL_STATES: ClassVar[list] = [PENDING, SYNCED, ERROR]

	@classmethod
	def is_valid(cls, state):
		"""Valida si un estado de sync es válido."""
		return state in cls.ALL_STATES


class DocumentTypes:
	"""Tipos de documento fiscal."""

	INVOICE = "invoice"
	ERECEIPT = "ereceipt"
	COMPLEMENT = "complement"
	GLOBAL = "global"
	PAYROLL = "payroll"

	ALL_TYPES: ClassVar[list] = [INVOICE, ERECEIPT, COMPLEMENT, GLOBAL, PAYROLL]

	@classmethod
	def is_valid(cls, doc_type):
		"""Valida si un tipo de documento es válido."""
		return doc_type in cls.ALL_TYPES


class OperationTypes:
	"""Tipos de operación con PAC."""

	TIMBRADO = "Timbrado"
	CANCELACION = "Cancelación"
	CONSULTA = "Consulta"
	VALIDACION = "Validación"

	ALL_TYPES: ClassVar[list] = [TIMBRADO, CANCELACION, CONSULTA, VALIDACION]

	@classmethod
	def is_valid(cls, operation):
		"""Valida si un tipo de operación es válido."""
		return operation in cls.ALL_TYPES


# Mapeo de estados FacturAPI a estados internos
FACTURAPI_STATE_MAPPING = {
	"valid": FiscalStates.TIMBRADO,
	"canceled": FiscalStates.CANCELADO,
	"pending_cancellation": FiscalStates.PENDIENTE_CANCELACION,
	"draft": FiscalStates.BORRADOR,
	"expired": FiscalStates.ARCHIVADO,
	"invoiced": FiscalStates.TIMBRADO,
	"validation_error": FiscalStates.ERROR,
	"pac_error": FiscalStates.ERROR,
	# Estados especiales
	"timeout": FiscalStates.PROCESANDO,
	"pending": FiscalStates.PROCESANDO,
}


def get_state_from_facturapi(facturapi_status):
	"""
	Convierte estado de FacturAPI a estado interno.

	Args:
	    facturapi_status: Estado retornado por FacturAPI

	Returns:
	    Estado interno correspondiente
	"""
	return FACTURAPI_STATE_MAPPING.get(facturapi_status, FiscalStates.ERROR)


def get_complete_config():
	"""
	Retorna configuración completa para uso en APIs.
	"""
	return {
		"fiscal_states": FiscalStates.to_dict(),
		"sync_states": {
			"pending": SyncStates.PENDING,
			"synced": SyncStates.SYNCED,
			"error": SyncStates.ERROR,
		},
		"document_types": {
			"invoice": DocumentTypes.INVOICE,
			"ereceipt": DocumentTypes.ERECEIPT,
			"complement": DocumentTypes.COMPLEMENT,
			"global": DocumentTypes.GLOBAL,
			"payroll": DocumentTypes.PAYROLL,
		},
		"operation_types": {
			"timbrado": OperationTypes.TIMBRADO,
			"cancelacion": OperationTypes.CANCELACION,
			"consulta": OperationTypes.CONSULTA,
			"validacion": OperationTypes.VALIDACION,
		},
		"facturapi_mapping": FACTURAPI_STATE_MAPPING,
	}
