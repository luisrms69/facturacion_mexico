"""
Complete Test Suite Runner - Dashboard Fiscal
Ejecuta todos los layers de testing del Framework Testing Granular
"""

import sys
import time
import unittest
from datetime import datetime

import frappe

# Import all test layers
from facturacion_mexico.dashboard_fiscal.tests.test_layer2_cache_integration import (
	run_tests as run_layer2_cache,
)
from facturacion_mexico.dashboard_fiscal.tests.test_layer2_modules_integration import (
	run_tests as run_layer2_modules,
)
from facturacion_mexico.dashboard_fiscal.tests.test_layer3_performance import run_tests as run_layer3_perf
from facturacion_mexico.dashboard_fiscal.tests.test_layer3_system import run_tests as run_layer3_system
from facturacion_mexico.dashboard_fiscal.tests.test_layer4_acceptance import (
	run_tests as run_layer4_acceptance,
)
from facturacion_mexico.dashboard_fiscal.tests.test_layer4_e2e import run_tests as run_layer4_e2e


class DashboardFiscalTestSuiteRunner:
	"""Runner para suite completa de tests Dashboard Fiscal"""

	def __init__(self):
		self.results = {}
		self.start_time = None
		self.total_time = 0
		self.summary = {
			"layers_executed": 0,
			"total_tests": 0,
			"tests_passed": 0,
			"tests_failed": 0,
			"tests_errors": 0,
			"tests_skipped": 0,
			"success_rate": 0.0,
		}

	def run_complete_suite(self, layers_to_run=None):
		"""
		Ejecutar suite completa de testing

		Args:
			layers_to_run (list): Lista de layers a ejecutar ['layer1', 'layer2', 'layer3', 'layer4']
						         Si None, ejecuta todos los layers
		"""
		self.start_time = time.time()

		# Define all available test layers
		available_layers = {
			"layer2_cache": {"name": "Layer 2 - Cache Integration", "runner": run_layer2_cache},
			"layer2_modules": {"name": "Layer 2 - Modules Integration", "runner": run_layer2_modules},
			"layer3_system": {"name": "Layer 3 - System Integration", "runner": run_layer3_system},
			"layer3_performance": {"name": "Layer 3 - Performance Tests", "runner": run_layer3_perf},
			"layer4_e2e": {"name": "Layer 4 - E2E Tests", "runner": run_layer4_e2e},
			"layer4_acceptance": {"name": "Layer 4 - Acceptance Tests", "runner": run_layer4_acceptance},
		}

		# Determine which layers to run
		if layers_to_run is None:
			layers_to_execute = available_layers
		else:
			layers_to_execute = {k: v for k, v in available_layers.items() if k in layers_to_run}

		print("\n" + "=" * 80)
		print("🧪 DASHBOARD FISCAL - COMPLETE TEST SUITE")
		print("=" * 80)
		print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
		print(f"🎯 Layers to execute: {len(layers_to_execute)}")
		print("🏗️  Framework: Testing Granular (4-Layer Architecture)")
		print("-" * 80)

		# Execute each layer
		for layer_key, layer_info in layers_to_execute.items():
			self._execute_test_layer(layer_key, layer_info)

		# Calculate totals and summary
		self._calculate_final_summary()

		# Print final results
		self._print_final_results()

		return self.summary

	def _execute_test_layer(self, layer_key, layer_info):
		"""Ejecutar un layer específico de tests"""
		print(f"\n🔄 Executing {layer_info['name']}...")
		print("-" * 50)

		layer_start_time = time.time()

		try:
			# Execute the layer test runner
			result = layer_info["runner"]()

			# Process results
			layer_result = {
				"name": layer_info["name"],
				"tests_run": result.testsRun,
				"failures": len(result.failures),
				"errors": len(result.errors),
				"skipped": len(getattr(result, "skipped", [])),
				"success": result.wasSuccessful(),
				"execution_time": time.time() - layer_start_time,
			}

			# Calculate passed tests
			layer_result["passed"] = (
				layer_result["tests_run"]
				- layer_result["failures"]
				- layer_result["errors"]
				- layer_result["skipped"]
			)

			self.results[layer_key] = layer_result

			# Print layer summary
			print(f"✅ {layer_info['name']} completed")
			print(f"   Tests run: {layer_result['tests_run']}")
			print(f"   Passed: {layer_result['passed']}")
			print(f"   Failed: {layer_result['failures']}")
			print(f"   Errors: {layer_result['errors']}")
			print(f"   Skipped: {layer_result['skipped']}")
			print(f"   Time: {layer_result['execution_time']:.2f}s")
			print(f"   Status: {'✅ SUCCESS' if layer_result['success'] else '❌ FAILED'}")

		except Exception as e:
			# Handle layer execution errors
			error_result = {
				"name": layer_info["name"],
				"tests_run": 0,
				"failures": 0,
				"errors": 1,
				"skipped": 0,
				"passed": 0,
				"success": False,
				"execution_time": time.time() - layer_start_time,
				"error_message": str(e),
			}

			self.results[layer_key] = error_result

			print(f"❌ {layer_info['name']} FAILED WITH ERROR")
			print(f"   Error: {e!s}")
			print(f"   Time: {error_result['execution_time']:.2f}s")

	def _calculate_final_summary(self):
		"""Calcular resumen final de todos los layers"""
		self.total_time = time.time() - self.start_time
		self.summary["layers_executed"] = len(self.results)

		for layer_result in self.results.values():
			self.summary["total_tests"] += layer_result["tests_run"]
			self.summary["tests_passed"] += layer_result["passed"]
			self.summary["tests_failed"] += layer_result["failures"]
			self.summary["tests_errors"] += layer_result["errors"]
			self.summary["tests_skipped"] += layer_result["skipped"]

		# Calculate success rate
		total_executed = self.summary["total_tests"] - self.summary["tests_skipped"]
		if total_executed > 0:
			self.summary["success_rate"] = self.summary["tests_passed"] / total_executed

		# Overall success determination
		self.summary["overall_success"] = (
			self.summary["tests_failed"] == 0
			and self.summary["tests_errors"] == 0
			and self.summary["success_rate"] >= 0.95  # 95% minimum success rate
		)

	def _print_final_results(self):
		"""Imprimir resultados finales de la suite completa"""
		print("\n" + "=" * 80)
		print("📊 FINAL TEST SUITE RESULTS")
		print("=" * 80)

		# Overall status
		overall_status = "✅ PASSED" if self.summary["overall_success"] else "❌ FAILED"
		print(f"🎯 Overall Status: {overall_status}")
		print(f"⏱️  Total Execution Time: {self.total_time:.2f} seconds")
		print(f"🏗️  Layers Executed: {self.summary['layers_executed']}")

		print("\n📈 TEST STATISTICS:")
		print(f"   Total Tests: {self.summary['total_tests']}")
		print(f"   ✅ Passed: {self.summary['tests_passed']}")
		print(f"   ❌ Failed: {self.summary['tests_failed']}")
		print(f"   🚫 Errors: {self.summary['tests_errors']}")
		print(f"   ⏭️  Skipped: {self.summary['tests_skipped']}")
		print(f"   📊 Success Rate: {self.summary['success_rate']:.1%}")

		print("\n🔍 LAYER BREAKDOWN:")
		for _layer_key, result in self.results.items():
			status_icon = "✅" if result["success"] else "❌"
			print(
				f"   {status_icon} {result['name']:<35} "
				f"({result['passed']}/{result['tests_run']} tests, "
				f"{result['execution_time']:.1f}s)"
			)

		# Print recommendations
		self._print_recommendations()

		print("=" * 80)

	def _print_recommendations(self):
		"""Imprimir recomendaciones basadas en resultados"""
		print("\n💡 RECOMMENDATIONS:")

		if self.summary["overall_success"]:
			print("   🎉 All tests passed! Dashboard Fiscal is ready for deployment.")
			print("   🚀 Consider setting up CI/CD pipeline with these test layers.")
		else:
			print("   ⚠️  Some tests failed. Review failed tests before deployment:")

			failed_layers = [result["name"] for result in self.results.values() if not result["success"]]

			for layer in failed_layers:
				print(f"      - Review and fix issues in: {layer}")

		# Performance recommendations
		slow_layers = [
			result
			for result in self.results.values()
			if result["execution_time"] > 30  # > 30 seconds
		]

		if slow_layers:
			print("   ⏱️  Performance optimization recommended for:")
			for layer in slow_layers:
				print(f"      - {layer['name']}: {layer['execution_time']:.1f}s")

		# Coverage recommendations
		if self.summary["success_rate"] < 1.0:
			print(
				f"   📊 Success rate is {self.summary['success_rate']:.1%}. "
				f"Aim for 100% for production deployment."
			)

	def run_specific_layer(self, layer_name):
		"""
		Ejecutar un layer específico solamente

		Args:
			layer_name (str): Nombre del layer a ejecutar
		"""
		return self.run_complete_suite(layers_to_run=[layer_name])

	def run_integration_layers_only(self):
		"""Ejecutar solo layers de integración (Layer 2 y 3)"""
		integration_layers = ["layer2_cache", "layer2_modules", "layer3_system", "layer3_performance"]
		return self.run_complete_suite(layers_to_run=integration_layers)

	def run_acceptance_layers_only(self):
		"""Ejecutar solo layers de acceptance (Layer 4)"""
		acceptance_layers = ["layer4_e2e", "layer4_acceptance"]
		return self.run_complete_suite(layers_to_run=acceptance_layers)


def main():
	"""Main function para ejecutar desde command line"""
	suite_runner = DashboardFiscalTestSuiteRunner()

	# Check command line arguments
	if len(sys.argv) > 1:
		layer_arg = sys.argv[1].lower()

		if layer_arg == "integration":
			print("🎯 Running Integration Layers Only...")
			suite_runner.run_integration_layers_only()
		elif layer_arg == "acceptance":
			print("🎯 Running Acceptance Layers Only...")
			suite_runner.run_acceptance_layers_only()
		elif layer_arg.startswith("layer"):
			print(f"🎯 Running Specific Layer: {layer_arg}...")
			suite_runner.run_specific_layer(layer_arg)
		else:
			print(f"❌ Unknown argument: {layer_arg}")
			print(
				"💡 Usage: python run_complete_test_suite.py [integration|acceptance|layer1|layer2|layer3|layer4]"
			)
			return 1
	else:
		print("🎯 Running Complete Test Suite...")
		suite_runner.run_complete_suite()

	# Return exit code based on success
	return 0 if suite_runner.summary.get("overall_success", False) else 1


if __name__ == "__main__":
	exit_code = main()
	sys.exit(exit_code)
