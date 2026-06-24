# apps/facturacion_mexico/tests/legacy_allowlist.py

# Campos históricos *intencionalmente* sin prefijo fm_
# No añadir aquí campos nuevos; solo legados ya existentes.
LEGACY_CF_ALLOWLIST = {
	"ffm_substitution_source_uuid",
	# Campo externo inyectado por upstream (Frappe CRM) sobre Customer.
	# No es propiedad de facturacion_mexico; aparece según la versión de
	# frappe/erpnext instalada en CI. Se excluye de la regla de prefijo fm_.
	"crm_deal",
}
