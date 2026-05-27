"""
Centraliza el cálculo de etapa de CFDI Recibido.

Dos funciones según el contexto de uso:

  compute_supplier_stage(doc)
    Hito Upload → Proveedor. Solo evalúa si hay Supplier asignado.
    Retorna: "Falta proveedor" | "Proveedor encontrado"

  compute_stage(doc)
    Flujo completo posterior al upload. Evalúa supplier → departamento → clasificación.
    Retorna: "Falta proveedor" | "Falta departamento" | "Falta clasificación" | "Clasificado"

Clasificación completa de un concepto:
  - Todos los conceptos tienen item_code asignado (por ItemResolver o manualmente).
  - Sin conceptos → vacuously clasificado.
"""

_NEXT_ACTION = {
	"Falta proveedor": "Crear proveedor",
	"Proveedor encontrado": "Asignar departamento",
	"Falta clasificación": "Clasificar conceptos",
	"Falta departamento": "Asignar departamento",
	"Clasificado": "Convertir a PI",
}

_STAGE_MESSAGE = {
	"XML inválido": "El XML no es un CFDI válido o el RFC receptor no corresponde a la empresa",
	"No aplicable": "Tipo de CFDI no aplicable a este flujo",
	"No procesar": "Excluido manualmente del flujo automático",
	"Falta proveedor": "Proveedor no encontrado por RFC",
	"Proveedor encontrado": "Proveedor asignado correctamente",
	"Falta clasificación": "Proveedor y departamento resueltos, faltan conceptos por clasificar",
	"Falta departamento": "Proveedor resuelto, falta asignar departamento",
	"Clasificado": "CFDI clasificado y listo para convertir a Purchase Invoice",
}


def compute_supplier_stage(doc) -> str:
	"""Etapa limitada al hito Upload → Proveedor. No evalúa clasificación."""
	if not doc.supplier:
		return "Falta proveedor"
	return "Proveedor encontrado"


def compute_stage(doc) -> str:
	"""Etapa completa: evalúa supplier, departamento y clasificación de conceptos."""
	if not doc.supplier:
		return "Falta proveedor"
	if not doc.department:
		return "Falta departamento"
	for concepto in doc.conceptos or []:
		if not getattr(concepto, "item_code", None):
			return "Falta clasificación"
	return "Clasificado"


def get_next_action(stage: str) -> str | None:
	return _NEXT_ACTION.get(stage)


def get_stage_message(stage: str) -> str:
	return _STAGE_MESSAGE.get(stage, stage)
