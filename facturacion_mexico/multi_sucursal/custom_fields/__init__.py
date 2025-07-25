# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Custom Fields Module - Multi Sucursal
Módulo para gestión de campos personalizados del sistema multi-sucursal
"""

# Import main functions for easy access
from .branch_fiscal_fields import (
	after_branch_insert,
	create_branch_fiscal_custom_fields,
	on_branch_update,
	remove_branch_fiscal_custom_fields,
	validate_branch_fiscal_configuration,
)

__all__ = [
	"after_branch_insert",
	"create_branch_fiscal_custom_fields",
	"on_branch_update",
	"remove_branch_fiscal_custom_fields",
	"validate_branch_fiscal_configuration",
]
