# Integraciones del Dashboard Fiscal con módulos existentes


def setup_all_integrations():
	"""Setup de todas las integraciones del dashboard"""
	import frappe

	try:
		from .addendas_integration import setup as setup_addendas
		from .ereceipts_integration import setup as setup_ereceipts
		from .facturas_globales_integration import setup as setup_facturas_globales
		from .motor_reglas_integration import setup as setup_motor_reglas
		from .ppd_integration import setup as setup_ppd
		from .timbrado_integration import setup as setup_timbrado

		# Setup de todas las integraciones
		setup_timbrado()
		setup_ppd()
		setup_motor_reglas()
		setup_ereceipts()
		setup_addendas()
		setup_facturas_globales()

		frappe.logger().info("Todas las integraciones del dashboard configuradas")

	except Exception as e:
		frappe.log_error("Error configurando integraciones dashboard", str(e))
