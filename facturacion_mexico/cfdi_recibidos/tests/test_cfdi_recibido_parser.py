"""
Tests unitarios de CFDIRecibidoParser.

Sin red. Sin BD. Sin FacturAPI.
Los XMLs de prueba son mínimos pero fiscalmente válidos en estructura.
"""

import json
import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.parsers.cfdi_recibido_parser import CFDIRecibidoParser

# ---------------------------------------------------------------------------
# XML mínimo CFDI 4.0 con IVA trasladado y datos completos de timbre
# ---------------------------------------------------------------------------

XML_CFDI_4_BASICO = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
  xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  Version="4.0"
  Serie="A"
  Folio="1234"
  Fecha="2025-11-15T10:00:00"
  FormaPago="03"
  NoCertificado="30001000000300023708"
  SubTotal="1000.00"
  Descuento="0.00"
  Moneda="MXN"
  TipoCambio="1"
  Total="1160.00"
  TipoDeComprobante="I"
  MetodoPago="PUE"
  LugarExpedicion="06600">
  <cfdi:Emisor
    Rfc="EKU9003173C9"
    Nombre="EMPRESA EMISORA SA DE CV"
    RegimenFiscal="601"/>
  <cfdi:Receptor
    Rfc="XAXX010101000"
    Nombre="EMPRESA RECEPTORA SA DE CV"
    DomicilioFiscalReceptor="06600"
    RegimenFiscalReceptor="601"
    UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto
      ClaveProdServ="43231500"
      Cantidad="1.0"
      ClaveUnidad="E48"
      Unidad="Servicio"
      Descripcion="Servicio de consultoría"
      ValorUnitario="1000.00"
      Importe="1000.00"
      ObjetoImp="02">
      <cfdi:Impuestos>
        <cfdi:Traslados>
          <cfdi:Traslado
            Base="1000.00"
            Impuesto="002"
            TipoFactor="Tasa"
            TasaOCuota="0.160000"
            Importe="160.00"/>
        </cfdi:Traslados>
      </cfdi:Impuestos>
    </cfdi:Concepto>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="160.00">
    <cfdi:Traslados>
      <cfdi:Traslado
        Base="1000.00"
        Impuesto="002"
        TipoFactor="Tasa"
        TasaOCuota="0.160000"
        Importe="160.00"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital
      xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
      Version="1.1"
      UUID="6128b5b6-8b9e-4f4e-9e62-4e1c6a5b7d8f"
      FechaTimbrado="2025-11-15T10:05:00"
      RfcProvCertif="SAT970701NN3"
      NoCertificadoSAT="20001000000300022816"/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""

# XML con retenciones ISR+IVA (honorarios)
XML_CFDI_4_CON_RETENCIONES = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
  xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Version="4.0"
  Serie="B"
  Folio="5678"
  Fecha="2025-11-20T09:00:00"
  FormaPago="03"
  NoCertificado="30001000000300023708"
  SubTotal="5000.00"
  Moneda="MXN"
  Total="4650.00"
  TipoDeComprobante="I"
  MetodoPago="PUE"
  LugarExpedicion="06600">
  <cfdi:Emisor Rfc="PEHJ800101AA1" Nombre="PROF HONORARIOS" RegimenFiscal="612"/>
  <cfdi:Receptor Rfc="EMP123456789" Nombre="EMPRESA CONTRATANTE" DomicilioFiscalReceptor="06600" RegimenFiscalReceptor="601" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="81111800" Cantidad="1.0" ClaveUnidad="E48"
      Unidad="Servicio" Descripcion="Honorarios asesoría legal" ValorUnitario="5000.00"
      Importe="5000.00" ObjetoImp="02">
      <cfdi:Impuestos>
        <cfdi:Traslados>
          <cfdi:Traslado Base="5000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="800.00"/>
        </cfdi:Traslados>
        <cfdi:Retenciones>
          <cfdi:Retencion Base="5000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.106667" Importe="533.00"/>
          <cfdi:Retencion Base="5000.00" Impuesto="001" TipoFactor="Tasa" TasaOCuota="0.100000" Importe="500.00"/>
        </cfdi:Retenciones>
      </cfdi:Impuestos>
    </cfdi:Concepto>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="800.00" TotalImpuestosRetenidos="1033.00">
    <cfdi:Traslados>
      <cfdi:Traslado Base="5000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="800.00"/>
    </cfdi:Traslados>
    <cfdi:Retenciones>
      <cfdi:Retencion Base="5000.00" Impuesto="002" Importe="533.00"/>
      <cfdi:Retencion Base="5000.00" Impuesto="001" Importe="500.00"/>
    </cfdi:Retenciones>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital Version="1.1"
      UUID="aabbccdd-1234-5678-9abc-def012345678"
      FechaTimbrado="2025-11-20T09:05:00"
      RfcProvCertif="SAT970701NN3"
      NoCertificadoSAT="20001000000300022816"/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""

# XML con NoIdentificacion en concepto
XML_CFDI_4_CON_NO_IDENTIFICACION = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
  xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Version="4.0"
  Fecha="2025-12-01T08:00:00"
  FormaPago="03"
  NoCertificado="30001000000300023708"
  SubTotal="2000.00"
  Moneda="MXN"
  Total="2320.00"
  TipoDeComprobante="I"
  MetodoPago="PUE"
  LugarExpedicion="06600">
  <cfdi:Emisor Rfc="PROV123456789" Nombre="PROVEEDOR TEST" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="XAXX010101000" Nombre="RECEPTOR TEST" DomicilioFiscalReceptor="06600"
    RegimenFiscalReceptor="601" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto
      ClaveProdServ="43231500"
      NoIdentificacion="SKU-001-PROV"
      Cantidad="2.0"
      ClaveUnidad="H87"
      Unidad="Pieza"
      Descripcion="Producto con código interno"
      ValorUnitario="1000.00"
      Importe="2000.00"
      ObjetoImp="02">
      <cfdi:Impuestos>
        <cfdi:Traslados>
          <cfdi:Traslado Base="2000.00" Impuesto="002" TipoFactor="Tasa"
            TasaOCuota="0.160000" Importe="320.00"/>
        </cfdi:Traslados>
      </cfdi:Impuestos>
    </cfdi:Concepto>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="320.00">
    <cfdi:Traslados>
      <cfdi:Traslado Base="2000.00" Impuesto="002" TipoFactor="Tasa"
        TasaOCuota="0.160000" Importe="320.00"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital Version="1.1"
      UUID="ccddee00-0000-1111-2222-333344445555"
      FechaTimbrado="2025-12-01T08:05:00"
      RfcProvCertif="SAT970701NN3"
      NoCertificadoSAT="20001000000300022816"/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""

# XML versión 3.3 — debe ser rechazado
XML_CFDI_33 = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/3" Version="3.3"
  Total="100.00" TipoDeComprobante="I">
  <cfdi:Emisor Rfc="EKU9003173C9" Nombre="TEST" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="XAXX010101000" Nombre="TEST" UsoCFDI="G01"/>
  <cfdi:Conceptos/>
</cfdi:Comprobante>"""


class TestCFDIRecibidoParserBasico(unittest.TestCase):
	def setUp(self):
		self.parser = CFDIRecibidoParser(XML_CFDI_4_BASICO)
		self.data = self.parser.parse()

	def test_version_extraida(self):
		self.assertEqual(self.data["version"], "4.0")

	def test_tipo_comprobante(self):
		self.assertEqual(self.data["cfdi_type"], "I")

	def test_serie_folio(self):
		self.assertEqual(self.data["serie"], "A")
		self.assertEqual(self.data["folio"], "1234")

	def test_fecha_emision(self):
		self.assertEqual(self.data["issue_date"], "2025-11-15")

	def test_moneda_y_tipo_cambio(self):
		self.assertEqual(self.data["currency"], "MXN")
		self.assertEqual(self.data["exchange_rate"], 1.0)

	def test_metodo_y_forma_pago(self):
		self.assertEqual(self.data["fm_payment_method_sat"], "PUE")
		self.assertEqual(self.data["fm_payment_form_sat"], "03")

	def test_totales(self):
		self.assertAlmostEqual(self.data["subtotal"], 1000.0)
		self.assertAlmostEqual(self.data["total"], 1160.0)
		self.assertAlmostEqual(self.data["total_impuestos_trasladados"], 160.0)
		self.assertAlmostEqual(self.data["total_impuestos_retenidos"], 0.0)

	def test_emisor(self):
		self.assertEqual(self.data["supplier_rfc"], "EKU9003173C9")
		self.assertEqual(self.data["supplier_name"], "EMPRESA EMISORA SA DE CV")
		self.assertEqual(self.data["supplier_tax_regime"], "601")

	def test_receptor(self):
		self.assertEqual(self.data["receiver_rfc"], "XAXX010101000")
		self.assertEqual(self.data["receiver_name"], "EMPRESA RECEPTORA SA DE CV")
		self.assertEqual(self.data["uso_cfdi"], "G03")

	def test_timbre(self):
		self.assertEqual(self.data["uuid"], "6128b5b6-8b9e-4f4e-9e62-4e1c6a5b7d8f")
		self.assertEqual(self.data["fecha_timbrado"], "2025-11-15T10:05:00")
		self.assertEqual(self.data["rfc_pac"], "SAT970701NN3")
		self.assertEqual(self.data["no_certificado_sat"], "20001000000300022816")
		self.assertEqual(self.data["no_certificado_emisor"], "30001000000300023708")

	def test_conceptos_count(self):
		self.assertEqual(len(self.data["conceptos"]), 1)

	def test_concepto_campos(self):
		c = self.data["conceptos"][0]
		self.assertEqual(c["sat_product_key"], "43231500")
		self.assertEqual(c["description"], "Servicio de consultoría")
		self.assertAlmostEqual(c["quantity"], 1.0)
		self.assertEqual(c["unit_key"], "E48")
		self.assertAlmostEqual(c["amount"], 1000.0)
		self.assertEqual(c["tax_object"], "02")

	def test_concepto_taxes_json(self):
		c = self.data["conceptos"][0]
		taxes = json.loads(c["taxes_json"])
		self.assertIn("traslados", taxes)
		self.assertEqual(len(taxes["traslados"]), 1)
		self.assertEqual(taxes["traslados"][0]["impuesto"], "002")
		self.assertAlmostEqual(taxes["traslados"][0]["importe"], 160.0)

	def test_impuestos_json_global(self):
		imp = json.loads(self.data["impuestos_json"])
		self.assertIn("traslados", imp)
		self.assertEqual(len(imp["traslados"]), 1)
		self.assertIn("retenciones", imp)
		self.assertEqual(len(imp["retenciones"]), 0)


class TestCFDIRecibidoParserRetenciones(unittest.TestCase):
	def setUp(self):
		self.parser = CFDIRecibidoParser(XML_CFDI_4_CON_RETENCIONES)
		self.data = self.parser.parse()

	def test_uuid(self):
		self.assertEqual(self.data["uuid"], "aabbccdd-1234-5678-9abc-def012345678")

	def test_totales_retenciones(self):
		self.assertAlmostEqual(self.data["total_impuestos_trasladados"], 800.0)
		self.assertAlmostEqual(self.data["total_impuestos_retenidos"], 1033.0)

	def test_retenciones_en_impuestos_json(self):
		imp = json.loads(self.data["impuestos_json"])
		self.assertEqual(len(imp["retenciones"]), 2)
		impuestos = {r["impuesto"] for r in imp["retenciones"]}
		self.assertIn("001", impuestos)  # ISR
		self.assertIn("002", impuestos)  # IVA retenido

	def test_concepto_retenciones(self):
		c = self.data["conceptos"][0]
		taxes = json.loads(c["taxes_json"])
		self.assertEqual(len(taxes["retenciones"]), 2)

	def test_concepto_retencion_tipo_factor(self):
		"""Retenciones por concepto deben incluir tipo_factor."""
		c = self.data["conceptos"][0]
		taxes = json.loads(c["taxes_json"])
		for r in taxes["retenciones"]:
			self.assertIn("tipo_factor", r)
			self.assertEqual(r["tipo_factor"], "Tasa")

	def test_concepto_retencion_tasa_cuota(self):
		"""Retenciones por concepto deben incluir tasa_cuota."""
		c = self.data["conceptos"][0]
		taxes = json.loads(c["taxes_json"])
		tasa_cuotas = {r["tasa_cuota"] for r in taxes["retenciones"]}
		self.assertIn("0.106667", tasa_cuotas)  # IVA retenido
		self.assertIn("0.100000", tasa_cuotas)  # ISR


class TestCFDIRecibidoParserVersionInvalida(unittest.TestCase):
	def test_rechaza_cfdi_33(self):
		"""CFDI 3.3 debe lanzar ValidationError."""
		with self.assertRaises(Exception) as ctx:
			parser = CFDIRecibidoParser(XML_CFDI_33)
			parser.parse()
		self.assertIn("4.0", str(ctx.exception))

	def test_version_en_mensaje(self):
		"""El mensaje de error debe mencionar la versión no soportada."""
		try:
			CFDIRecibidoParser(XML_CFDI_33).parse()
		except Exception as e:
			self.assertIn("3.3", str(e))


class TestCFDIRecibidoParserNoIdentificacion(unittest.TestCase):
	def setUp(self):
		self.parser = CFDIRecibidoParser(XML_CFDI_4_CON_NO_IDENTIFICACION)
		self.data = self.parser.parse()

	def test_no_identificacion_se_parsea(self):
		"""no_identificacion se extrae del atributo NoIdentificacion del concepto."""
		c = self.data["conceptos"][0]
		self.assertEqual(c["no_identificacion"], "SKU-001-PROV")

	def test_sin_no_identificacion_retorna_vacio(self):
		"""XML sin NoIdentificacion devuelve cadena vacía, no KeyError."""
		parser = CFDIRecibidoParser(XML_CFDI_4_BASICO)
		data = parser.parse()
		c = data["conceptos"][0]
		self.assertIn("no_identificacion", c)
		self.assertEqual(c["no_identificacion"], "")


class TestCFDIRecibidoParserFechas(unittest.TestCase):
	def test_parse_date_con_hora(self):
		self.assertEqual(CFDIRecibidoParser._parse_date("2025-11-15T10:00:00"), "2025-11-15")

	def test_parse_date_vacia(self):
		self.assertEqual(CFDIRecibidoParser._parse_date(""), "")

	def test_parse_date_solo_fecha(self):
		self.assertEqual(CFDIRecibidoParser._parse_date("2025-11-15"), "2025-11-15")
