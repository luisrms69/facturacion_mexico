"""Boot hooks de facturacion_mexico."""

from facturacion_mexico.facturacion_fiscal.pac_environment import get_fm_environment


def add_fiscal_environment_to_boot(bootinfo):
	"""Publicar el ambiente fiscal del sitio en el boot (issue #171).

	Reutiliza la única fuente de verdad de #215 (`get_fm_environment`, por-sitio desde
	`site_config.json`). El indicador visual del Desk (franja de la navbar) lee
	`frappe.boot.fm_environment` sin llamadas adicionales al servidor ni polling.

	Valores posibles: `"production"`, `"sandbox"`, o cadena vacía (ausente/inválido).
	"""
	bootinfo.fm_environment = get_fm_environment()
