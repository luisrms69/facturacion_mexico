"""
Test Configuration for Addendas Module
Configuración y constantes para el framework de testing
"""

from typing import ClassVar

import frappe


class TestConfig:
	"""Configuración centralizada para tests del módulo de addendas."""

	# Thresholds de rendimiento (en segundos)
	PERFORMANCE_THRESHOLDS: ClassVar[dict] = {
		"xml_generation": 2.0,
		"xml_validation": 1.0,
		"api_response": 3.0,
		"batch_processing": 10.0,
		"concurrent_requests": 5.0,
		"memory_limit_mb": 100,
	}

	# Configuración de datos de prueba
	TEST_DATA: ClassVar[dict] = {
		"customer": {
			"name": "Test Customer Addenda",
			"customer_type": "Company",
			"customer_group": "Commercial",
			"territory": "Mexico",
			"tax_id": "TEST123456789",
		},
		"items": [
			{
				"item_code": "TEST-ITEM-001",
				"item_name": "Test Item for Addenda",
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_sales_item": 1,
			},
			{
				"item_code": "TEST-ITEM-002",
				"item_name": "Test Service Item",
				"item_group": "Services",
				"stock_uom": "Nos",
				"is_sales_item": 1,
			},
		],
		"addenda_types": [
			{
				"name": "Generic Test",
				"description": "Tipo genérico para pruebas",
				"version": "1.0",
				"namespace": "http://test.addenda.mx/generic",
				"is_active": 1,
				"requires_product_mapping": 0,
			},
			{
				"name": "Liverpool Test",
				"description": "Tipo Liverpool para pruebas",
				"version": "2.1",
				"namespace": "http://test.addenda.mx/liverpool",
				"is_active": 1,
				"requires_product_mapping": 1,
			},
		],
	}

	# Templates XML de prueba
	XML_TEMPLATES: ClassVar[dict] = {
		"basic": """<?xml version="1.0" encoding="UTF-8"?>
<addenda>
	<informacion>
		<folio>{{ cfdi_uuid }}</folio>
		<fecha>{{ cfdi_fecha }}</fecha>
		<total>{{ cfdi_total }}</total>
	</informacion>
	<proveedor>
		<fm_rfc>{{ emisor_rfc }}</fm_rfc>
		<nombre>{{ emisor_nombre }}</nombre>
	</proveedor>
</addenda>""",
		"complex": """<?xml version="1.0" encoding="UTF-8"?>
<addenda xmlns="http://test.addenda.mx">
	<header>
		<documentInfo>
			<uuid>{{ cfdi_uuid }}</uuid>
			<issueDate>{{ cfdi_fecha }}</issueDate>
			<totalAmount>{{ cfdi_total }}</totalAmount>
		</documentInfo>
		<parties>
			<supplier>
				<taxId>{{ emisor_rfc }}</taxId>
				<name>{{ emisor_nombre }}</name>
				<address>{{ emisor_direccion }}</address>
			</supplier>
			<customer>
				<taxId>{{ receptor_rfc }}</taxId>
				<name>{{ receptor_nombre }}</name>
				<customerCode>{{ cliente_codigo }}</customerCode>
			</customer>
		</parties>
	</header>
	<details>
		{% for concepto in conceptos %}
		<lineItem>
			<description>{{ concepto.descripcion }}</description>
			<quantity>{{ concepto.cantidad }}</quantity>
			<unitPrice>{{ concepto.valor_unitario }}</unitPrice>
			<totalAmount>{{ concepto.importe }}</totalAmount>
			<customerProductCode>{{ concepto.codigo_cliente }}</customerProductCode>
		</lineItem>
		{% endfor %}
	</details>
	<totals>
		<subtotal>{{ cfdi_subtotal }}</subtotal>
		<taxes>{{ cfdi_impuestos }}</taxes>
		<total>{{ cfdi_total }}</total>
	</totals>
</addenda>""",
	}

	# Esquemas XSD de prueba
	XSD_SCHEMAS: ClassVar[dict] = {
		"basic": """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="http://test.addenda.mx"
           xmlns:tns="http://test.addenda.mx"
           elementFormDefault="qualified">

  <xs:element name="addenda">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="informacion">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="folio" type="xs:string"/>
              <xs:element name="fecha" type="xs:date"/>
              <xs:element name="total" type="xs:decimal"/>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
        <xs:element name="proveedor">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="fm_rfc" type="xs:string"/>
              <xs:element name="nombre" type="xs:string"/>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>""",
		"complex": """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="http://test.addenda.mx"
           xmlns:tns="http://test.addenda.mx"
           elementFormDefault="qualified">

  <xs:element name="addenda">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="header">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="documentInfo">
                <xs:complexType>
                  <xs:sequence>
                    <xs:element name="uuid" type="xs:string"/>
                    <xs:element name="issueDate" type="xs:date"/>
                    <xs:element name="totalAmount" type="xs:decimal"/>
                  </xs:sequence>
                </xs:complexType>
              </xs:element>
              <xs:element name="parties">
                <xs:complexType>
                  <xs:sequence>
                    <xs:element name="supplier" type="tns:PartyType"/>
                    <xs:element name="customer" type="tns:CustomerType"/>
                  </xs:sequence>
                </xs:complexType>
              </xs:element>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
        <xs:element name="details">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="lineItem" type="tns:LineItemType" maxOccurs="unbounded"/>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
        <xs:element name="totals">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="subtotal" type="xs:decimal"/>
              <xs:element name="taxes" type="xs:decimal"/>
              <xs:element name="total" type="xs:decimal"/>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>

  <xs:complexType name="PartyType">
    <xs:sequence>
      <xs:element name="taxId" type="xs:string"/>
      <xs:element name="name" type="xs:string"/>
      <xs:element name="address" type="xs:string" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="CustomerType">
    <xs:complexContent>
      <xs:extension base="tns:PartyType">
        <xs:sequence>
          <xs:element name="customerCode" type="xs:string" minOccurs="0"/>
        </xs:sequence>
      </xs:extension>
    </xs:complexContent>
  </xs:complexType>

  <xs:complexType name="LineItemType">
    <xs:sequence>
      <xs:element name="description" type="xs:string"/>
      <xs:element name="quantity" type="xs:decimal"/>
      <xs:element name="unitPrice" type="xs:decimal"/>
      <xs:element name="totalAmount" type="xs:decimal"/>
      <xs:element name="customerProductCode" type="xs:string" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>""",
	}

	# Datos CFDI de muestra
	SAMPLE_CFDI_DATA: ClassVar[dict] = {
		"uuid": "12345678-1234-1234-1234-123456789012",
		"fecha": "2025-07-20T10:30:00",
		"total": "1000.00",
		"subtotal": "862.07",
		"impuestos": "137.93",
		"emisor_rfc": "TEST123456789",
		"emisor_nombre": "Test Company S.A. de C.V.",
		"emisor_direccion": "Calle Test 123, Col. Prueba, Ciudad de México",
		"receptor_rfc": "XAXX010101000",
		"receptor_nombre": "Test Cliente S.A.",
		"cliente_codigo": "CLI001",
		"conceptos": [
			{
				"descripcion": "Producto de prueba 1",
				"cantidad": "1.00",
				"valor_unitario": "500.00",
				"importe": "500.00",
				"codigo_cliente": "PROD001",
			},
			{
				"descripcion": "Producto de prueba 2",
				"cantidad": "2.00",
				"valor_unitario": "250.00",
				"importe": "500.00",
				"codigo_cliente": "PROD002",
			},
		],
	}

	# Configuración de ambiente de pruebas
	TEST_ENV: ClassVar[dict] = {
		"disable_emails": True,
		"disable_logging": False,
		"cleanup_after_tests": True,
		"max_test_duration": 300,  # 5 minutos máximo por test
		"memory_threshold_mb": 500,  # Threshold de memoria para warnings
	}

	@classmethod
	def get_test_threshold(cls, test_type: str) -> float:
		"""Obtener threshold de rendimiento para un tipo de test."""
		return cls.PERFORMANCE_THRESHOLDS.get(test_type, 5.0)

	@classmethod
	def get_test_template(cls, template_name: str) -> str:
		"""Obtener template XML de prueba."""
		return cls.XML_TEMPLATES.get(template_name, cls.XML_TEMPLATES["basic"])

	@classmethod
	def get_test_schema(cls, schema_name: str) -> str:
		"""Obtener esquema XSD de prueba."""
		return cls.XSD_SCHEMAS.get(schema_name, cls.XSD_SCHEMAS["basic"])

	@classmethod
	def setup_test_environment(cls):
		"""Configurar ambiente de pruebas."""
		# Deshabilitar emails si está configurado
		if cls.TEST_ENV["disable_emails"]:
			frappe.flags.in_test = True

		# Configurar logging
		if cls.TEST_ENV["disable_logging"]:
			import logging

			logging.getLogger("frappe").setLevel(logging.ERROR)

	@classmethod
	def cleanup_test_environment(cls):
		"""Limpiar ambiente de pruebas."""
		if cls.TEST_ENV["cleanup_after_tests"]:
			cls._cleanup_test_data()

	@classmethod
	def _cleanup_test_data(cls):
		"""Limpiar datos de prueba."""
		test_doctypes = ["Addenda Configuration", "Addenda Template", "Addenda Product Mapping"]

		for doctype in test_doctypes:
			# Eliminar documentos de prueba
			test_docs = frappe.get_all(doctype, filters={"name": ["like", "%Test%"]}, pluck="name")

			for doc_name in test_docs:
				try:
					frappe.delete_doc(doctype, doc_name, force=True, ignore_permissions=True)
				except Exception:
					pass

		# Limpiar facturas de prueba
		test_invoices = frappe.get_all(
			"Sales Invoice", filters={"customer": ["like", "%Test%"]}, pluck="name"
		)

		for invoice in test_invoices:
			try:
				frappe.delete_doc("Sales Invoice", invoice, force=True, ignore_permissions=True)
			except Exception:
				pass
