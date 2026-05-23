"""
Tests de XMLIngestionService — Fase 1.

unittest.TestCase con contexto Frappe activo (bench run-tests ya lo setea).
No usa FrappeTestCase para evitar el compat_preload_test_records_upfront que
dispara make_test_records("Company") y rompe tests por ERPNext test records
con ítems sin fm_producto_servicio_sat (deuda pre-existente en la suite).

Cleanup explícito en tearDown vía frappe.delete_doc + frappe.db.commit().
Sin red. Sin llamadas externas.
"""

import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.xml_ingestion import ingest_xml

# RFC de prueba — se setea en setUp sobre la Company del site de test
TEST_RFC_EMPRESA = "EMP9001011AA"

# XML CFDI 4.0 mínimo — receptor coincide con TEST_RFC_EMPRESA
XML_VALIDO = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
  xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Version="4.0"
  Serie="INV"
  Folio="9001"
  Fecha="2025-11-15T10:00:00"
  FormaPago="03"
  NoCertificado="30001000000300023708"
  SubTotal="2000.00"
  Moneda="MXN"
  Total="2320.00"
  TipoDeComprobante="I"
  MetodoPago="PUE"
  LugarExpedicion="06600">
  <cfdi:Emisor Rfc="PROV123456AAA" Nombre="PROVEEDOR TEST SA" RegimenFiscal="601"/>
  <cfdi:Receptor
    Rfc="EMP9001011AA"
    Nombre="EMPRESA TEST SA"
    DomicilioFiscalReceptor="06600"
    RegimenFiscalReceptor="601"
    UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="43231500" Cantidad="2.0" ClaveUnidad="E48"
      Unidad="Servicio" Descripcion="Soporte técnico" ValorUnitario="1000.00"
      Importe="2000.00" ObjetoImp="02">
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
      UUID="11111111-2222-3333-4444-555555555555"
      FechaTimbrado="2025-11-15T10:05:00"
      RfcProvCertif="SAT970701NN3"
      NoCertificadoSAT="20001000000300022816"/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""

XML_UUID_DISTINTO = XML_VALIDO.replace(
	"11111111-2222-3333-4444-555555555555",
	"AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
)

XML_RFC_INCORRECTO = XML_VALIDO.replace(
	'Rfc="EMP9001011AA"',
	'Rfc="OTRO123456789"',
).replace(
	"11111111-2222-3333-4444-555555555555",
	"FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
)

XML_33 = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/3" Version="3.3"
  Total="100.00" TipoDeComprobante="I">
  <cfdi:Emisor Rfc="EKU9003173C9" Nombre="TEST" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="EMP9001011AA" Nombre="TEST" UsoCFDI="G01"/>
  <cfdi:Conceptos/>
</cfdi:Comprobante>"""


def _get_company():
	return frappe.defaults.get_global_default("company") or "Test Quality Company"


def _cleanup_uuid(uuid: str):
	name = frappe.db.get_value("CFDI Recibido", {"uuid": uuid}, "name")
	if name:
		frappe.delete_doc("CFDI Recibido", name, force=True)
		frappe.db.commit()


class TestXMLIngestionExitosa(unittest.TestCase):
	def setUp(self):
		self.company = _get_company()
		frappe.db.set_value("Company", self.company, "tax_id", TEST_RFC_EMPRESA)
		frappe.db.commit()
		self.xml_bytes = XML_VALIDO.encode("utf-8")

	def tearDown(self):
		_cleanup_uuid("11111111-2222-3333-4444-555555555555")

	def test_status_ok(self):
		result = ingest_xml(self.xml_bytes, self.company, "test.xml")
		self.assertEqual(result["status"], "ok")

	def test_crea_cfdi_recibido(self):
		result = ingest_xml(self.xml_bytes, self.company, "test.xml")
		self.assertIsNotNone(result["cfdi_recibido"])
		doc = frappe.get_doc("CFDI Recibido", result["cfdi_recibido"])
		self.assertEqual(doc.uuid, "11111111-2222-3333-4444-555555555555")
		self.assertEqual(doc.status, "Parseado")
		self.assertEqual(doc.supplier_rfc, "PROV123456AAA")
		self.assertEqual(doc.receiver_rfc, "EMP9001011AA")
		self.assertEqual(doc.uso_cfdi, "G03")
		self.assertEqual(doc.cfdi_type, "I")

	def test_guarda_xml_hash(self):
		result = ingest_xml(self.xml_bytes, self.company, "test.xml")
		doc = frappe.get_doc("CFDI Recibido", result["cfdi_recibido"])
		self.assertIsNotNone(doc.xml_hash)
		self.assertEqual(len(doc.xml_hash), 64)

	def test_adjunta_xml(self):
		result = ingest_xml(self.xml_bytes, self.company, "test.xml")
		doc = frappe.get_doc("CFDI Recibido", result["cfdi_recibido"])
		self.assertIsNotNone(doc.xml_file)

	def test_crea_conceptos(self):
		result = ingest_xml(self.xml_bytes, self.company, "test.xml")
		doc = frappe.get_doc("CFDI Recibido", result["cfdi_recibido"])
		self.assertEqual(len(doc.conceptos), 1)
		c = doc.conceptos[0]
		self.assertEqual(c.sat_product_key, "43231500")
		self.assertEqual(c.description, "Soporte técnico")
		self.assertAlmostEqual(c.quantity, 2.0)
		self.assertAlmostEqual(c.amount, 2000.0)

	def test_totales_impuestos(self):
		result = ingest_xml(self.xml_bytes, self.company, "test.xml")
		doc = frappe.get_doc("CFDI Recibido", result["cfdi_recibido"])
		self.assertAlmostEqual(doc.total_impuestos_trasladados, 320.0)
		self.assertAlmostEqual(doc.total_impuestos_retenidos, 0.0)

	def test_timbre_guardado(self):
		result = ingest_xml(self.xml_bytes, self.company, "test.xml")
		doc = frappe.get_doc("CFDI Recibido", result["cfdi_recibido"])
		self.assertEqual(doc.rfc_pac, "SAT970701NN3")
		self.assertEqual(doc.no_certificado_sat, "20001000000300022816")
		self.assertIsNotNone(doc.fecha_timbrado)

	def test_uuid_en_resultado(self):
		result = ingest_xml(self.xml_bytes, self.company, "test.xml")
		self.assertEqual(result["uuid"], "11111111-2222-3333-4444-555555555555")


class TestXMLIngestionDuplicado(unittest.TestCase):
	def setUp(self):
		self.company = _get_company()
		frappe.db.set_value("Company", self.company, "tax_id", TEST_RFC_EMPRESA)
		frappe.db.commit()
		self.xml_bytes = XML_VALIDO.encode("utf-8")
		self._first = ingest_xml(self.xml_bytes, self.company, "primero.xml")

	def tearDown(self):
		_cleanup_uuid("11111111-2222-3333-4444-555555555555")

	def test_segundo_intento_es_duplicado(self):
		result = ingest_xml(self.xml_bytes, self.company, "segundo.xml")
		self.assertEqual(result["status"], "duplicado")

	def test_no_crea_segundo_doc(self):
		ingest_xml(self.xml_bytes, self.company, "segundo.xml")
		count = frappe.db.count("CFDI Recibido", {"uuid": "11111111-2222-3333-4444-555555555555"})
		self.assertEqual(count, 1)

	def test_duplicado_retorna_nombre_existente(self):
		result = ingest_xml(self.xml_bytes, self.company, "segundo.xml")
		self.assertEqual(result["cfdi_recibido"], self._first["cfdi_recibido"])


class TestXMLIngestionRFCIncorrecto(unittest.TestCase):
	def setUp(self):
		self.company = _get_company()
		frappe.db.set_value("Company", self.company, "tax_id", TEST_RFC_EMPRESA)
		frappe.db.commit()

	def tearDown(self):
		_cleanup_uuid("FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF")

	def test_status_error(self):
		result = ingest_xml(XML_RFC_INCORRECTO.encode(), self.company, "rfc_mal.xml")
		self.assertEqual(result["status"], "error")

	def test_doc_creado_en_estado_error(self):
		result = ingest_xml(XML_RFC_INCORRECTO.encode(), self.company, "rfc_mal.xml")
		self.assertIsNotNone(result["cfdi_recibido"])
		doc = frappe.get_doc("CFDI Recibido", result["cfdi_recibido"])
		self.assertEqual(doc.status, "Error")

	def test_mensaje_error_descriptivo(self):
		result = ingest_xml(XML_RFC_INCORRECTO.encode(), self.company, "rfc_mal.xml")
		doc = frappe.get_doc("CFDI Recibido", result["cfdi_recibido"])
		self.assertIn("no corresponde", doc.error_message.lower())


class TestXMLIngestionVersionInvalida(unittest.TestCase):
	def setUp(self):
		self.company = _get_company()
		frappe.db.set_value("Company", self.company, "tax_id", TEST_RFC_EMPRESA)
		frappe.db.commit()

	def test_cfdi_33_retorna_error(self):
		result = ingest_xml(XML_33.encode(), self.company, "cfdi33.xml")
		self.assertEqual(result["status"], "error")

	def test_cfdi_33_no_crea_doc(self):
		# CFDI 3.3 falla en el parser antes de crear el doc
		ingest_xml(XML_33.encode(), self.company, "cfdi33.xml")
		count = frappe.db.count("CFDI Recibido", {"supplier_rfc": "EKU9003173C9"})
		self.assertEqual(count, 0)

	def test_cfdi_33_mensaje_menciona_version(self):
		result = ingest_xml(XML_33.encode(), self.company, "cfdi33.xml")
		self.assertIn("4.0", result["message"])


class TestIngestResultadosEstructura(unittest.TestCase):
	def setUp(self):
		self.company = _get_company()
		frappe.db.set_value("Company", self.company, "tax_id", TEST_RFC_EMPRESA)
		frappe.db.commit()

	def tearDown(self):
		for uuid in [
			"11111111-2222-3333-4444-555555555555",
			"AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
		]:
			_cleanup_uuid(uuid)

	def test_resultado_tiene_campos_esperados(self):
		result = ingest_xml(XML_VALIDO.encode(), self.company, "a.xml")
		self.assertIn("status", result)
		self.assertIn("cfdi_recibido", result)
		self.assertIn("uuid", result)
		self.assertIn("message", result)

	def test_dos_xmls_distintos_crea_dos_docs(self):
		r1 = ingest_xml(XML_VALIDO.encode(), self.company, "a.xml")
		r2 = ingest_xml(XML_UUID_DISTINTO.encode(), self.company, "b.xml")
		self.assertEqual(r1["status"], "ok")
		self.assertEqual(r2["status"], "ok")
		self.assertNotEqual(r1["cfdi_recibido"], r2["cfdi_recibido"])
