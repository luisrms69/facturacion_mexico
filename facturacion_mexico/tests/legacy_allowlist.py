# apps/facturacion_mexico/tests/legacy_allowlist.py

# Campos históricos *intencionalmente* sin prefijo fm_
# No añadir aquí campos nuevos; solo legados ya existentes.
LEGACY_CF_ALLOWLIST = {
    "ffm_substitution_source_uuid",
}