# Hooks - Integraciones ERPNext

Documentación de hooks y validaciones automáticas integradas con ERPNext.

## Configuración de Hooks

::: facturacion_mexico.hooks
    options:
      show_source: true
      show_root_heading: true
      show_root_toc_entry: false
      docstring_style: google

## Facturas Globales

### Factura Global MX

::: facturacion_mexico.facturas_globales.doctype.factura_global_mx.factura_global_mx
    options:
      show_source: true
      show_root_heading: true
      show_root_toc_entry: false
      docstring_style: google

### Procesadores

#### CFDI Global Builder

::: facturacion_mexico.facturas_globales.processors.cfdi_global_builder
    options:
      show_source: false
      show_root_heading: true
      show_root_toc_entry: false
      docstring_style: google
      filters:
        - "!^_"

#### E-Receipt Aggregator

::: facturacion_mexico.facturas_globales.processors.ereceipt_aggregator
    options:
      show_source: false
      show_root_heading: true
      show_root_toc_entry: false
      docstring_style: google
      filters:
        - "!^_"

## APIs Públicas

::: facturacion_mexico.facturas_globales.api
    options:
      show_source: false
      show_root_heading: true
      show_root_toc_entry: false
      docstring_style: google
      filters:
        - "!^_"