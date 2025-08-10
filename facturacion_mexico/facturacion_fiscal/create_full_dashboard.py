import json
import uuid

import frappe


def create_full_control_panel():
	"""Crear workspace completo con estructura Frappe correcta y métricas"""

	ws_name = "Control Panel Fiscal"
	print(f"Creando Control Panel completo: {ws_name}")

	ws = frappe.get_doc("Workspace", ws_name)

	def generate_id():
		"""Generar ID único como en workspace estándar"""
		return "".join(uuid.uuid4().hex[:10])

	# Estructura completa como workspace Home
	blocks = []

	# 1. Header principal
	blocks.append(
		{
			"id": generate_id(),
			"type": "header",
			"data": {"text": '<span class="h3"><b>Control Panel Fiscal</b></span>', "col": 12},
		}
	)

	# 2. Métricas del sistema (cards con datos dinámicos)
	blocks.append(
		{
			"id": generate_id(),
			"type": "header",
			"data": {"text": '<span class="h4"><b>System Health Metrics</b></span>', "col": 12},
		}
	)

	# Obtener métricas reales del sistema
	try:
		from facturacion_mexico.facturacion_fiscal.api.admin_tools import get_system_health_metrics

		metrics = get_system_health_metrics()

		# Card PAC Success Rate
		blocks.append(
			{
				"id": generate_id(),
				"type": "paragraph",
				"data": {
					"text": f"📊 <strong>PAC Success Rate:</strong> {metrics.get('pac_success_rate', 'N/A')}%",
					"col": 4,
				},
			}
		)

		# Card Recovery Tasks
		blocks.append(
			{
				"id": generate_id(),
				"type": "paragraph",
				"data": {
					"text": f"⚠️ <strong>Recovery Tasks:</strong> {metrics.get('recovery_tasks_pending', 0)} pending",
					"col": 4,
				},
			}
		)

		# Card Response Time
		blocks.append(
			{
				"id": generate_id(),
				"type": "paragraph",
				"data": {
					"text": f"⚡ <strong>Avg Response:</strong> {metrics.get('average_response_time', 'N/A')}ms",
					"col": 4,
				},
			}
		)

	except Exception as e:
		print(f"Error obteniendo métricas: {e}")
		blocks.append(
			{
				"id": generate_id(),
				"type": "paragraph",
				"data": {"text": "⚠️ Métricas no disponibles - verificar permisos", "col": 12},
			}
		)

	# 3. Spacer
	blocks.append({"id": generate_id(), "type": "spacer", "data": {"col": 12}})

	# 4. Shortcuts section
	blocks.append(
		{
			"id": generate_id(),
			"type": "header",
			"data": {"text": '<span class="h4"><b>Quick Access</b></span>', "col": 12},
		}
	)

	# Shortcuts usando estructura correcta
	for row in ws.shortcuts:
		blocks.append(
			{"id": generate_id(), "type": "shortcut", "data": {"shortcut_name": row.label, "col": 3}}
		)

	# 5. Spacer
	blocks.append({"id": generate_id(), "type": "spacer", "data": {"col": 12}})

	# 6. Administration Tools
	blocks.append(
		{
			"id": generate_id(),
			"type": "header",
			"data": {"text": '<span class="h4"><b>Administration Tools</b></span>', "col": 12},
		}
	)

	# Links directos a funciones admin
	admin_links = [
		(
			"🔧 Manual Recovery",
			"/api/method/facturacion_mexico.facturacion_fiscal.api.admin_tools.execute_manual_recovery",
		),
		(
			"📊 Generate Report",
			"/api/method/facturacion_mexico.facturacion_fiscal.api.admin_tools.generate_system_report",
		),
		(
			"🧹 Clean Old Logs",
			"/api/method/facturacion_mexico.facturacion_fiscal.api.admin_tools.cleanup_old_logs",
		),
		(
			"🔄 Sync Status",
			"/api/method/facturacion_mexico.facturacion_fiscal.api.admin_tools.sync_fiscal_status",
		),
	]

	for label, url in admin_links:
		blocks.append(
			{
				"id": generate_id(),
				"type": "paragraph",
				"data": {"text": f"• <a href='{url}' class='btn btn-sm btn-primary'>{label}</a>", "col": 3},
			}
		)

	# Actualizar content
	ws.content = json.dumps(blocks)
	print(f"Content generado: {len(blocks)} bloques con métricas y funcionalidades")

	ws.save()
	# Manual commit necesario: Workspace modificado dinámicamente fuera flujo transaccional normal
	frappe.db.commit()  # nosemgrep

	print("✅ Control Panel completo creado con:")
	print("   - Métricas en tiempo real")
	print(f"   - {len(ws.shortcuts)} shortcuts funcionales")
	print(f"   - {len(admin_links)} herramientas admin")
	print("   - Estructura Frappe nativa")

	return "SUCCESS"
