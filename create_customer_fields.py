#!/usr/bin/env python3
"""
Script para crear custom fields de Customer siguiendo mejores prácticas de Frappe
Uso: bench --site facturacion.dev execute facturacion_mexico.create_customer_fields.create_fields
"""

import frappe

def create_fields():
    """Crear custom fields para Customer unificados en Tax tab"""
    
    # Lista de campos a crear
    fields_to_create = [
        {
            "fieldname": "fm_informacion_fiscal_mx_section",
            "label": "Información Fiscal México",
            "fieldtype": "Section Break",
            "insert_after": "tax_id",
            "collapsible": 1
        },
        {
            "fieldname": "fm_regimen_fiscal", 
            "label": "Régimen Fiscal",
            "fieldtype": "Data",
            "insert_after": "fm_informacion_fiscal_mx_section"
        },
        {
            "fieldname": "fm_uso_cfdi_default",
            "label": "Uso CFDI por Defecto", 
            "fieldtype": "Data",
            "insert_after": "fm_regimen_fiscal"
        },
        {
            "fieldname": "fm_column_break_validacion_sat",
            "label": None,
            "fieldtype": "Column Break",
            "insert_after": "fm_uso_cfdi_default"
        }
    ]
    
    created_fields = []
    
    for field_config in fields_to_create:
        field_name = f"Customer-{field_config['fieldname']}"
        
        # Verificar si el campo ya existe
        if frappe.db.exists("Custom Field", field_name):
            print(f"Campo {field_name} ya existe, saltando...")
            continue
            
        try:
            # Crear el custom field
            doc = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Customer",
                "fieldname": field_config["fieldname"],
                "fieldtype": field_config["fieldtype"],
                "label": field_config["label"],
                "insert_after": field_config["insert_after"],
                "collapsible": field_config.get("collapsible", 0)
            })
            
            doc.insert()
            created_fields.append(field_name)
            print(f"✅ Creado: {field_name}")
            
        except Exception as e:
            print(f"❌ Error creando {field_name}: {str(e)}")
    
    # Commit cambios
    frappe.db.commit()
    
    print(f"\n🎉 Creados {len(created_fields)} campos:")
    for field in created_fields:
        print(f"  - {field}")
    
    print("\n📝 Próximos pasos:")
    print("1. bench --site facturacion.dev export-fixtures --app facturacion_mexico")
    print("2. Actualizar hooks.py con los nombres correctos")
    
    return created_fields

if __name__ == "__main__":
    create_fields()