Tuvimos exito en el timbrado, sin embargo hay un mensaje de diferencias en montos

FFMX-2025-00169, FFAPI-LOG-2025-00208 y ACC-SINV-2025-01634

Estso son el payload y respuesta del PAC
{
  "customer": {
    "legal_name": "CONCESIONARIA VUELA COMPAÑIA DE AVIACION",
    "tax_id": "CVA041027H80",
    "email": null,
    "tax_system": "601",
    "address": {
      "street": "Antonio Dovali Jaime No. 70, Torre B, Piso 13",
      "exterior": "",
      "neighborhood": "México",
      "city": "México",
      "municipality": "México",
      "state": "Ciudad de México",
      "country": "MEX",
      "zip": "01210"
    }
  },
  "items": [
    {
      "quantity": 6,
      "product": {
        "description": "Tequila 100% Agave Reposado 750ml - Producto prueba IEPS Alcohol 26.5%\n\n🏷️ Partida SAT: 22085000\n\n📋 NOTAS FISCALES:\nIEPS 26.5% aplicable a bebidas alcohólicas destiladas &gt;20° GL según Ley IEPS Art. 2-I-A",
        "product_key": "50202304",
        "price": 550,
        "tax_included": false,
        "unit_key": "H87",
        "unit_name": "Nos",
        "taxability": "02",
        "taxes": [
          {
            "type": "IEPS",
            "factor": "Tasa",
            "withholding": false,
            "rate": 0.265
          },
          {
            "type": "IVA",
            "factor": "Tasa",
            "withholding": false,
            "rate": 0.16,
            "base": 695.75
          }
        ]
      }
    },
    {
      "quantity": 10,
      "product": {
        "description": "Cigarros rubio cajetilla 20 unidades - IEPS 160% + cuota fija\n\n🏷️ Partida SAT: 24022000\n\n📋 NOTAS FISCALES:\nIEPS 160% sobre precio enajenación + $0.35/cigarro según Art. 2-I-C Ley IEPS",
        "product_key": "53131604",
        "price": 50,
        "tax_included": false,
        "unit_key": "XPA",
        "unit_name": "XPA - Cajetilla",
        "taxability": "02",
        "taxes": [
          {
            "type": "IVA",
            "factor": "Tasa",
            "withholding": false,
            "rate": 0.16,
            "base": 50
          },
          {
            "type": "IEPS",
            "factor": "Tasa",
            "withholding": false,
            "rate": 1.6
          },
          {
            "type": "IEPS",
            "factor": "Cuota",
            "withholding": false,
            "rate": 0.35,
            "base": 20
          }
        ]
      }
    },
    {
      "quantity": 20,
      "product": {
        "description": "Refresco cola regular 600ml - IEPS $1.27/litro por alta densidad calórica\n\n🏷️ Partida SAT: 22021000\n\n📋 NOTAS FISCALES:\nIEPS $1.27 por litro (≈$0.76 por botella 600ml) - Bebida &gt;5 cal/100ml según Art. 2-I-J Ley IEPS",
        "product_key": "50202301",
        "price": 20,
        "tax_included": false,
        "unit_key": "H87",
        "unit_name": "H87 - Pieza",
        "taxability": "02",
        "taxes": [
          {
            "type": "IVA",
            "factor": "Tasa",
            "withholding": false,
            "rate": 0.16,
            "base": 20.762
          },
          {
            "type": "IEPS",
            "factor": "Cuota",
            "withholding": false,
            "rate": 1.27,
            "base": 0.6
          }
        ]
      }
    },
    {
      "quantity": 40,
      "product": {
        "description": "Gasolina Magna (Regular 87 octanos) - IEPS cuota fija + variable\n\n🏷️ Partida SAT: 27101221\n\n📋 NOTAS FISCALES:\nIEPS cuota fija $5.39/L + variable según Art. 2-I-D fracción 1 Ley IEPS",
        "product_key": "15101514",
        "price": 26,
        "tax_included": false,
        "unit_key": "LTR",
        "unit_name": "LTR - Litro",
        "taxability": "02",
        "taxes": [
          {
            "type": "IVA",
            "factor": "Tasa",
            "withholding": false,
            "rate": 0.16,
            "base": 26
          },
          {
            "type": "IEPS",
            "factor": "Cuota",
            "withholding": false,
            "rate": 5.49,
            "base": 1
          }
        ]
      }
    }
  ],
  "payment_form": "99",
  "payment_method": "PPD",
  "series": "F",
  "use": "G03",
  "type": "I"
}


{
  "id": "68f9f2b5605a5535341a20cd",
  "organization": "66b1311af5541a1a8d7d4229",
  "created_at": "2025-10-23T09:17:41.043Z",
  "date": "2025-10-23T09:17:41.010Z",
  "livemode": false,
  "payment_form": "99",
  "payment_method": "PPD",
  "currency": "MXN",
  "exchange": 1,
  "uuid": "A2BBD5E8-4264-4304-A5BE-53191C2724E2",
  "customer": {
    "id": "688573ea0e92dc4c23bb01fd",
    "legal_name": "CONCESIONARIA VUELA COMPAÑIA DE AVIACION",
    "tax_system": "601",
    "tax_id": "CVA041027H80",
    "address": {
      "country": "MEX",
      "zip": "01210",
      "state": "Ciudad de México",
      "city": "México",
      "street": "Antonio Dovali Jaime No. 70, Torre B, Piso 13",
      "neighborhood": "México"
    }
  },
  "total": 8200.1,
  "total_payment_amount": 0,
  "use": "G03",
  "folio_number": 269,
  "series": "F",
  "is_ready_to_stamp": false,
  "items": [
    {
      "quantity": 6,
      "discount": 0,
      "product": {
        "description": "Tequila 100% Agave Reposado 750ml - Producto prueba IEPS Alcohol 26.5%\n\n🏷️ Partida SAT: 22085000\n\n📋 NOTAS FISCALES:\nIEPS 26.5% aplicable a bebidas alcohólicas destiladas &gt;20° GL según Ley IEPS Art. 2-I-A",
        "product_key": "50202304",
        "unit_key": "H87",
        "unit_name": "Nos",
        "price": 550,
        "tax_included": false,
        "taxes": [
          {
            "base": null,
            "rate": 0.265,
            "type": "IEPS",
            "withholding": false,
            "factor": "Tasa",
            "ieps_mode": "sum_before_taxes"
          },
          {
            "base": 695.75,
            "rate": 0.16,
            "type": "IVA",
            "withholding": false,
            "factor": "Tasa",
            "ieps_mode": "sum_before_taxes"
          }
        ],
        "taxability": "02"
      }
    },
    {
      "quantity": 10,
      "discount": 0,
      "product": {
        "description": "Cigarros rubio cajetilla 20 unidades - IEPS 160% + cuota fija\n\n🏷️ Partida SAT: 24022000\n\n📋 NOTAS FISCALES:\nIEPS 160% sobre precio enajenación + $0.35/cigarro según Art. 2-I-C Ley IEPS",
        "product_key": "53131604",
        "unit_key": "XPA",
        "unit_name": "XPA - Cajetilla",
        "price": 50,
        "tax_included": false,
        "taxes": [
          {
            "base": 50,
            "rate": 0.16,
            "type": "IVA",
            "withholding": false,
            "factor": "Tasa",
            "ieps_mode": "sum_before_taxes"
          },
          {
            "base": null,
            "rate": 1.6,
            "type": "IEPS",
            "withholding": false,
            "factor": "Tasa",
            "ieps_mode": "sum_before_taxes"
          },
          {
            "base": 20,
            "rate": 0.35,
            "type": "IEPS",
            "withholding": false,
            "factor": "Cuota",
            "ieps_mode": "sum_before_taxes"
          }
        ],
        "taxability": "02"
      }
    },
    {
      "quantity": 20,
      "discount": 0,
      "product": {
        "description": "Refresco cola regular 600ml - IEPS $1.27/litro por alta densidad calórica\n\n🏷️ Partida SAT: 22021000\n\n📋 NOTAS FISCALES:\nIEPS $1.27 por litro (≈$0.76 por botella 600ml) - Bebida &gt;5 cal/100ml según Art. 2-I-J Ley IEPS",
        "product_key": "50202301",
        "unit_key": "H87",
        "unit_name": "H87 - Pieza",
        "price": 20,
        "tax_included": false,
        "taxes": [
          {
            "base": 20.762,
            "rate": 0.16,
            "type": "IVA",
            "withholding": false,
            "factor": "Tasa",
            "ieps_mode": "sum_before_taxes"
          },
          {
            "base": 0.6,
            "rate": 1.27,
            "type": "IEPS",
            "withholding": false,
            "factor": "Cuota",
            "ieps_mode": "sum_before_taxes"
          }
        ],
        "taxability": "02"
      }
    },
    {
      "quantity": 40,
      "discount": 0,
      "product": {
        "description": "Gasolina Magna (Regular 87 octanos) - IEPS cuota fija + variable\n\n🏷️ Partida SAT: 27101221\n\n📋 NOTAS FISCALES:\nIEPS cuota fija $5.39/L + variable según Art. 2-I-D fracción 1 Ley IEPS",
        "product_key": "15101514",
        "unit_key": "LTR",
        "unit_name": "LTR - Litro",
        "price": 26,
        "tax_included": false,
        "taxes": [
          {
            "base": 26,
            "rate": 0.16,
            "type": "IVA",
            "withholding": false,
            "factor": "Tasa",
            "ieps_mode": "sum_before_taxes"
          },
          {
            "base": 1,
            "rate": 5.49,
            "type": "IEPS",
            "withholding": false,
            "factor": "Cuota",
            "ieps_mode": "sum_before_taxes"
          }
        ],
        "taxability": "02"
      }
    }
  ],
  "cfdi_version": 4,
  "address": {
    "street": "",
    "exterior": "",
    "interior": "",
    "neighborhood": "",
    "city": "Cancún",
    "municipality": "Benito Juárez",
    "state": "Quintana Roo",
    "country": "MEX",
    "zip": "77505"
  },
  "amount_due": 8200.1,
  "verification_url": "https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?id=A2BBD5E8-4264-4304-A5BE-53191C2724E2&re=CNA201211FM9&rr=CVA041027H80&tt=8200.100000&fe=xnVpzw==",
  "status": "valid",
  "type": "I",
  "issuer_type": "issuing",
  "issuer_info": {
    "legal_name": "CONSULTORIA EN NEGOCIOS Y APLICACIONES",
    "tax_id": "CNA201211FM9",
    "tax_system": "601",
    "address": {
      "street": "",
      "exterior": "",
      "interior": "",
      "neighborhood": "",
      "city": "Cancún",
      "municipality": "Benito Juárez",
      "state": "Quintana Roo",
      "country": "MEX",
      "zip": "77505"
    }
  },
  "cancellation_status": "none",
  "stamp": {
    "date": "2025-10-23T03:17:41",
    "sat_signature": "Vsz1iY58s1NqOvqe5eX9j/NIFwpBv46wChflpY/SHC09NmpXOYUwdxcjLwNJ51uaZla1LmDsTZrxZ9zcEUWW7tHWgaSizg/rWc1v2BkLZOcMFev68s72C0AO6/ChxjbGwdNt2c2FaboYVw2tRvXecQ2Q1S4OENbAh2rqYDtJKzbhVHerdkv93rNAp2c9gNOv/fW1PQqZ6VKfe0+H+O3PKaNZ+NL65b5I1fLtjmzDSYrYPUVZp36pBO/Uvk5eMMYI+QwpOmx005Gr5oAyfq8k7qN6N745O/nACDom5Fz8QplszHU333tFj2+G95WmvpnfetJWc9gGW7ctd6N/caIAVQ==",
    "sat_cert_number": "30001000000500003456",
    "signature": "Z3ZGl7lXvOGWywS4+ClNRF/350L1UCPwbKAh0+gxcqIIQRrzAKteMniQ6SukmlqY2QVjLe2UcXD4ZwVW9NirnbOd6mDTb30NY/OzvJWm+pAma9HineuiIo8uLg83xXiAnLMJAQFbNNqzUYBhs8MB7OIbCzNQbJV8khNCqoY0ATWa3DfCmGdQxbKlehAFG47Zr+H8nAPWcLQuxmgzdT29N8q7z1p71wXF3/cm4buCpke/uPDmfCEkdExwCOQCi6aHtvU6GxxsxzIRQTjr4nwV9ffeZrtsvgXS0BW1vu88W9bqkTwN1062RrVjfFiRpVq+29X9L9MVku9oiQPdxnVpzw==",
    "complement_string": "||1.1|A2BBD5E8-4264-4304-A5BE-53191C2724E2|2025-10-23T03:17:41|Z3ZGl7lXvOGWywS4+ClNRF/350L1UCPwbKAh0+gxcqIIQRrzAKteMniQ6SukmlqY2QVjLe2UcXD4ZwVW9NirnbOd6mDTb30NY/OzvJWm+pAma9HineuiIo8uLg83xXiAnLMJAQFbNNqzUYBhs8MB7OIbCzNQbJV8khNCqoY0ATWa3DfCmGdQxbKlehAFG47Zr+H8nAPWcLQuxmgzdT29N8q7z1p71wXF3/cm4buCpke/uPDmfCEkdExwCOQCi6aHtvU6GxxsxzIRQTjr4nwV9ffeZrtsvgXS0BW1vu88W9bqkTwN1062RrVjfFiRpVq+29X9L9MVku9oiQPdxnVpzw==|30001000000500003456||"
  },
  "export": "01",
  "cancellation": {
    "status": "none",
    "last_checked": "2018-11-01T00:00:00.000Z"
  },
  "payment_status": "unpaid"
}

Este es el xml de la factura fiscal
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd" Version="4.0" Folio="269" Fecha="2025-10-23T04:17:41" TipoDeComprobante="I" Moneda="MXN" SubTotal="5240.00" Total="8200.10" LugarExpedicion="77505" NoCertificado="00001000000719510211" Certificado="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" FormaPago="99" MetodoPago="PPD" Serie="F" Exportacion="01" Sello="Z3ZGl7lXvOGWywS4+ClNRF/350L1UCPwbKAh0+gxcqIIQRrzAKteMniQ6SukmlqY2QVjLe2UcXD4ZwVW9NirnbOd6mDTb30NY/OzvJWm+pAma9HineuiIo8uLg83xXiAnLMJAQFbNNqzUYBhs8MB7OIbCzNQbJV8khNCqoY0ATWa3DfCmGdQxbKlehAFG47Zr+H8nAPWcLQuxmgzdT29N8q7z1p71wXF3/cm4buCpke/uPDmfCEkdExwCOQCi6aHtvU6GxxsxzIRQTjr4nwV9ffeZrtsvgXS0BW1vu88W9bqkTwN1062RrVjfFiRpVq+29X9L9MVku9oiQPdxnVpzw==">
<cfdi:Emisor Rfc="CNA201211FM9" RegimenFiscal="601" Nombre="CONSULTORIA EN NEGOCIOS Y APLICACIONES"/>
<cfdi:Receptor Rfc="CVA041027H80" Nombre="CONCESIONARIA VUELA COMPAÑIA DE AVIACION" DomicilioFiscalReceptor="01210" RegimenFiscalReceptor="601" UsoCFDI="G03"/>
<cfdi:Conceptos>
<cfdi:Concepto ClaveProdServ="50202304" Cantidad="6" ClaveUnidad="H87" Descripcion="Tequila 100% Agave Reposado 750ml - Producto prueba IEPS Alcohol 26.5% 🏷️ Partida SAT: 22085000 📋 NOTAS FISCALES: IEPS 26.5% aplicable a bebidas alcohólicas destiladas &gt;20° GL según Ley IEPS Art. 2-I-A" ValorUnitario="550.000000" Importe="3300.000000" ObjetoImp="02" Unidad="Nos">
<cfdi:Impuestos>
<cfdi:Traslados>
<cfdi:Traslado Base="3300.000000" Impuesto="003" TipoFactor="Tasa" TasaOCuota="0.265000" Importe="874.500000"/>
<cfdi:Traslado Base="4174.500000" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="667.920000"/>
</cfdi:Traslados>
</cfdi:Impuestos>
</cfdi:Concepto>
<cfdi:Concepto ClaveProdServ="53131604" Cantidad="10" ClaveUnidad="XPA" Descripcion="Cigarros rubio cajetilla 20 unidades - IEPS 160% + cuota fija 🏷️ Partida SAT: 24022000 📋 NOTAS FISCALES: IEPS 160% sobre precio enajenación + $0.35/cigarro según Art. 2-I-C Ley IEPS" ValorUnitario="50.000000" Importe="500.000000" ObjetoImp="02" Unidad="XPA - Cajetilla">
<cfdi:Impuestos>
<cfdi:Traslados>
<cfdi:Traslado Base="500.000000" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="80.000000"/>
<cfdi:Traslado Base="500.000000" Impuesto="003" TipoFactor="Tasa" TasaOCuota="1.600000" Importe="800.000000"/>
<cfdi:Traslado Base="200.000000" Impuesto="003" TipoFactor="Cuota" TasaOCuota="0.350000" Importe="70.000000"/>
</cfdi:Traslados>
</cfdi:Impuestos>
</cfdi:Concepto>
<cfdi:Concepto ClaveProdServ="50202301" Cantidad="20" ClaveUnidad="H87" Descripcion="Refresco cola regular 600ml - IEPS $1.27/litro por alta densidad calórica 🏷️ Partida SAT: 22021000 📋 NOTAS FISCALES: IEPS $1.27 por litro (≈$0.76 por botella 600ml) - Bebida &gt;5 cal/100ml según Art. 2-I-J Ley IEPS" ValorUnitario="20.000000" Importe="400.000000" ObjetoImp="02" Unidad="H87 - Pieza">
<cfdi:Impuestos>
<cfdi:Traslados>
<cfdi:Traslado Base="415.240000" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="66.438400"/>
<cfdi:Traslado Base="12.000000" Impuesto="003" TipoFactor="Cuota" TasaOCuota="1.270000" Importe="15.240000"/>
</cfdi:Traslados>
</cfdi:Impuestos>
</cfdi:Concepto>
<cfdi:Concepto ClaveProdServ="15101514" Cantidad="40" ClaveUnidad="LTR" Descripcion="Gasolina Magna (Regular 87 octanos) - IEPS cuota fija + variable 🏷️ Partida SAT: 27101221 📋 NOTAS FISCALES: IEPS cuota fija $5.39/L + variable según Art. 2-I-D fracción 1 Ley IEPS" ValorUnitario="26.000000" Importe="1040.000000" ObjetoImp="02" Unidad="LTR - Litro">
<cfdi:Impuestos>
<cfdi:Traslados>
<cfdi:Traslado Base="1040.000000" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="166.400000"/>
<cfdi:Traslado Base="40.000000" Impuesto="003" TipoFactor="Cuota" TasaOCuota="5.490000" Importe="219.600000"/>
</cfdi:Traslados>
</cfdi:Impuestos>
</cfdi:Concepto>
</cfdi:Conceptos>
<cfdi:Impuestos TotalImpuestosTrasladados="2960.10">
<cfdi:Traslados>
<cfdi:Traslado Base="3300.00" Impuesto="003" TipoFactor="Tasa" TasaOCuota="0.265000" Importe="874.50"/>
<cfdi:Traslado Base="6129.74" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="980.76"/>
<cfdi:Traslado Base="500.00" Impuesto="003" TipoFactor="Tasa" TasaOCuota="1.600000" Importe="800.00"/>
<cfdi:Traslado Base="200.00" Impuesto="003" TipoFactor="Cuota" TasaOCuota="0.350000" Importe="70.00"/>
<cfdi:Traslado Base="12.00" Impuesto="003" TipoFactor="Cuota" TasaOCuota="1.270000" Importe="15.24"/>
<cfdi:Traslado Base="40.00" Impuesto="003" TipoFactor="Cuota" TasaOCuota="5.490000" Importe="219.60"/>
</cfdi:Traslados>
</cfdi:Impuestos>
<cfdi:Complemento>
<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" FechaTimbrado="2025-10-23T03:17:41" NoCertificadoSAT="30001000000500003456" RfcProvCertif="PPD101129EA3" SelloCFD="Z3ZGl7lXvOGWywS4+ClNRF/350L1UCPwbKAh0+gxcqIIQRrzAKteMniQ6SukmlqY2QVjLe2UcXD4ZwVW9NirnbOd6mDTb30NY/OzvJWm+pAma9HineuiIo8uLg83xXiAnLMJAQFbNNqzUYBhs8MB7OIbCzNQbJV8khNCqoY0ATWa3DfCmGdQxbKlehAFG47Zr+H8nAPWcLQuxmgzdT29N8q7z1p71wXF3/cm4buCpke/uPDmfCEkdExwCOQCi6aHtvU6GxxsxzIRQTjr4nwV9ffeZrtsvgXS0BW1vu88W9bqkTwN1062RrVjfFiRpVq+29X9L9MVku9oiQPdxnVpzw==" SelloSAT="Vsz1iY58s1NqOvqe5eX9j/NIFwpBv46wChflpY/SHC09NmpXOYUwdxcjLwNJ51uaZla1LmDsTZrxZ9zcEUWW7tHWgaSizg/rWc1v2BkLZOcMFev68s72C0AO6/ChxjbGwdNt2c2FaboYVw2tRvXecQ2Q1S4OENbAh2rqYDtJKzbhVHerdkv93rNAp2c9gNOv/fW1PQqZ6VKfe0+H+O3PKaNZ+NL65b5I1fLtjmzDSYrYPUVZp36pBO/Uvk5eMMYI+QwpOmx005Gr5oAyfq8k7qN6N745O/nACDom5Fz8QplszHU333tFj2+G95WmvpnfetJWc9gGW7ctd6N/caIAVQ==" UUID="A2BBD5E8-4264-4304-A5BE-53191C2724E2" Version="1.1" xsi:schemaLocation="http://www.sat.gob.mx/TimbreFiscalDigital http://www.sat.gob.mx/sitio_internet/cfd/timbrefiscaldigital/TimbreFiscalDigitalv11.xsd"/>
</cfdi:Complemento>
</cfdi:Comprobante>



Timbrado Exitoso
⚠️ ADVERTENCIA: Discrepancia significativa en montos
Total PAC: $8,200.10
Total ERPNext (sin IVA): $5,240.00
Total ERPNext (con IVA): $9,377.97
Diferencia: $1,177.87
✅ Factura Timbrada Exitosamente
UUID: A2BBD5E8-4264-4304-A5BE-53191C2724E2

Serie-Folio: F-269

Total: $8,200.10


Revisa a detalle (renglon de impuestos por renglon de impuestos) reporta la diferncia enter SI y PAC, propon e informa, no implementes