"""
Test Runner for Addendas Module - 4-Layer Testing Framework
Ejecutor de tests para el sistema de addendas
"""

import sys
import time
import unittest
from io import StringIO


class AddendaTestRunner:
	"""Ejecutor de tests para el módulo de addendas."""

	def __init__(self):
		self.test_layers = {
			"unit": [
				"facturacion_mexico.addendas.tests.test_unit_validators",
				"facturacion_mexico.addendas.tests.test_unit_parsers",
			],
			"business_logic": [
				"facturacion_mexico.addendas.tests.test_business_logic",
			],
			"integration": [
				"facturacion_mexico.addendas.tests.test_integration",
			],
			"performance": [
				"facturacion_mexico.addendas.tests.test_performance",
			],
		}

	def run_layer(self, layer_name: str, verbose: bool = True) -> dict:
		"""Ejecutar una capa específica de tests."""
		if layer_name not in self.test_layers:
			raise ValueError(
				f"Layer '{layer_name}' not found. Available layers: {list(self.test_layers.keys())}"
			)

		print(f"\n{'='*60}")
		print(f"RUNNING {layer_name.upper()} TESTS")
		print(f"{'='*60}")

		results = {
			"layer": layer_name,
			"total_tests": 0,
			"passed": 0,
			"failed": 0,
			"errors": 0,
			"skipped": 0,
			"execution_time": 0,
			"details": [],
		}

		start_time = time.time()

		for test_module in self.test_layers[layer_name]:
			print(f"\nRunning module: {test_module}")

			# Crear test suite para el módulo
			loader = unittest.TestLoader()
			try:
				suite = loader.loadTestsFromName(test_module)
			except Exception as e:
				print(f"Error loading test module {test_module}: {e}")
				results["errors"] += 1
				continue

			# Ejecutar tests
			stream = StringIO()
			runner = unittest.TextTestRunner(stream=stream, verbosity=2 if verbose else 1)

			module_result = runner.run(suite)

			# Recopilar resultados del módulo
			module_details = {
				"module": test_module,
				"tests_run": module_result.testsRun,
				"failures": len(module_result.failures),
				"errors": len(module_result.errors),
				"skipped": len(module_result.skipped) if hasattr(module_result, "skipped") else 0,
				"output": stream.getvalue(),
			}

			results["details"].append(module_details)
			results["total_tests"] += module_result.testsRun
			results["failed"] += len(module_result.failures)
			results["errors"] += len(module_result.errors)
			results["skipped"] += (
				getattr(module_result, "skipped", 0) if hasattr(module_result, "skipped") else 0
			)

			# Mostrar output si es verbose
			if verbose:
				print(stream.getvalue())

		results["passed"] = (
			results["total_tests"] - results["failed"] - results["errors"] - results["skipped"]
		)
		results["execution_time"] = time.time() - start_time

		# Mostrar resumen de la capa
		self.print_layer_summary(results)

		return results

	def run_all_layers(self, verbose: bool = True, stop_on_failure: bool = False) -> dict:
		"""Ejecutar todas las capas de tests."""
		print(f"\n{'='*80}")
		print("RUNNING COMPLETE 4-LAYER TEST SUITE - ADDENDAS MODULE")
		print(f"{'='*80}")

		overall_results = {
			"total_execution_time": 0,
			"layers": {},
			"summary": {"total_tests": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0},
		}

		start_time = time.time()

		# Ejecutar cada capa en orden
		layer_order = ["unit", "business_logic", "integration", "performance"]

		for layer in layer_order:
			layer_results = self.run_layer(layer, verbose)
			overall_results["layers"][layer] = layer_results

			# Acumular estadísticas
			for key in ["total_tests", "passed", "failed", "errors", "skipped"]:
				overall_results["summary"][key] += layer_results[key]

			# Parar en caso de falla si está configurado
			if stop_on_failure and (layer_results["failed"] > 0 or layer_results["errors"] > 0):
				print(f"\nStopping execution due to failures in {layer} layer")
				break

		overall_results["total_execution_time"] = time.time() - start_time

		# Mostrar resumen final
		self.print_overall_summary(overall_results)

		return overall_results

	def run_specific_test(
		self, test_class: str, test_method: str | None = None, verbose: bool = True
	) -> dict:
		"""Ejecutar un test específico."""
		test_name = f"{test_class}.{test_method}" if test_method else test_class
		print(f"\n{'='*60}")
		print(f"RUNNING SPECIFIC TEST: {test_name}")
		print(f"{'='*60}")

		loader = unittest.TestLoader()
		suite = unittest.TestSuite()

		try:
			if test_method:
				suite.addTest(loader.loadTestsFromName(f"{test_class}.{test_method}"))
			else:
				suite.addTest(loader.loadTestsFromName(test_class))
		except Exception as e:
			print(f"Error loading test {test_name}: {e}")
			return {"success": False, "error": str(e)}

		stream = StringIO()
		runner = unittest.TextTestRunner(stream=stream, verbosity=2 if verbose else 1)

		start_time = time.time()
		result = runner.run(suite)
		execution_time = time.time() - start_time

		if verbose:
			print(stream.getvalue())

		test_results = {
			"success": result.wasSuccessful(),
			"tests_run": result.testsRun,
			"failures": len(result.failures),
			"errors": len(result.errors),
			"execution_time": execution_time,
			"output": stream.getvalue(),
		}

		print(f"\nTest completed in {execution_time:.3f}s")
		print(f"Tests run: {result.testsRun}, Failures: {len(result.failures)}, Errors: {len(result.errors)}")

		return test_results

	def print_layer_summary(self, results: dict):
		"""Imprimir resumen de una capa."""
		print(f"\n{'-'*50}")
		print(f"LAYER SUMMARY: {results['layer'].upper()}")
		print(f"{'-'*50}")
		print(f"Total tests: {results['total_tests']}")
		print(f"Passed: {results['passed']}")
		print(f"Failed: {results['failed']}")
		print(f"Errors: {results['errors']}")
		print(f"Skipped: {results['skipped']}")
		print(f"Execution time: {results['execution_time']:.3f}s")

		if results["failed"] > 0 or results["errors"] > 0:
			print(f"❌ LAYER {results['layer'].upper()} FAILED")
		else:
			print(f"✅ LAYER {results['layer'].upper()} PASSED")

	def print_overall_summary(self, results: dict):
		"""Imprimir resumen general."""
		print(f"\n{'='*80}")
		print("OVERALL TEST SUMMARY")
		print(f"{'='*80}")

		summary = results["summary"]
		print(f"Total execution time: {results['total_execution_time']:.3f}s")
		print(f"Total tests: {summary['total_tests']}")
		print(f"Passed: {summary['passed']}")
		print(f"Failed: {summary['failed']}")
		print(f"Errors: {summary['errors']}")
		print(f"Skipped: {summary['skipped']}")

		print("\nLAYER BREAKDOWN:")
		for layer_name, layer_data in results["layers"].items():
			status = "✅ PASS" if layer_data["failed"] == 0 and layer_data["errors"] == 0 else "❌ FAIL"
			print(
				f"  {layer_name.upper().ljust(15)}: {layer_data['passed']}/{layer_data['total_tests']} passed ({layer_data['execution_time']:.3f}s) {status}"
			)

		overall_success = summary["failed"] == 0 and summary["errors"] == 0
		if overall_success:
			print("\n🎉 ALL TESTS PASSED! 🎉")
		else:
			print("\n💥 SOME TESTS FAILED 💥")

		print(f"{'='*80}")

	def generate_report(self, results: dict, output_file: str | None = None):
		"""Generar reporte detallado de tests."""
		if output_file is None:
			output_file = f"addenda_test_report_{int(time.time())}.txt"

		with open(output_file, "w", encoding="utf-8") as f:
			f.write("ADDENDA MODULE - 4-LAYER TEST REPORT\n")
			f.write("=" * 80 + "\n\n")
			f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
			f.write(f"Total execution time: {results['total_execution_time']:.3f}s\n\n")

			# Resumen general
			summary = results["summary"]
			f.write("SUMMARY\n")
			f.write("-" * 40 + "\n")
			f.write(f"Total tests: {summary['total_tests']}\n")
			f.write(f"Passed: {summary['passed']}\n")
			f.write(f"Failed: {summary['failed']}\n")
			f.write(f"Errors: {summary['errors']}\n")
			f.write(f"Skipped: {summary['skipped']}\n\n")

			# Detalles por capa
			for layer_name, layer_data in results["layers"].items():
				f.write(f"LAYER: {layer_name.upper()}\n")
				f.write("-" * 40 + "\n")
				f.write(f"Execution time: {layer_data['execution_time']:.3f}s\n")
				f.write(f"Tests: {layer_data['total_tests']}\n")
				f.write(
					f"Results: {layer_data['passed']} passed, {layer_data['failed']} failed, {layer_data['errors']} errors\n\n"
				)

				# Detalles por módulo
				for module_detail in layer_data["details"]:
					f.write(f"  Module: {module_detail['module']}\n")
					f.write(f"  Tests run: {module_detail['tests_run']}\n")
					f.write(f"  Failures: {module_detail['failures']}\n")
					f.write(f"  Errors: {module_detail['errors']}\n")
					f.write(f"  Output:\n{module_detail['output']}\n")
					f.write("-" * 20 + "\n")

		print(f"\nDetailed report generated: {output_file}")


def main():
	"""Función principal para ejecutar desde línea de comandos."""
	import argparse

	parser = argparse.ArgumentParser(description="Run Addenda Module Tests")
	parser.add_argument("--layer", help="Run specific layer (unit, business_logic, integration, performance)")
	parser.add_argument("--test", help="Run specific test class")
	parser.add_argument("--method", help="Run specific test method (requires --test)")
	parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
	parser.add_argument("--stop-on-failure", action="store_true", help="Stop on first failure")
	parser.add_argument("--report", help="Generate report file")

	args = parser.parse_args()

	runner = AddendaTestRunner()

	try:
		if args.test:
			results = runner.run_specific_test(args.test, args.method, args.verbose)
		elif args.layer:
			results = runner.run_layer(args.layer, args.verbose)
		else:
			results = runner.run_all_layers(args.verbose, args.stop_on_failure)

		if args.report and isinstance(results, dict) and "layers" in results:
			runner.generate_report(results, args.report)

	except Exception as e:
		print(f"Error running tests: {e}")
		sys.exit(1)


if __name__ == "__main__":
	main()
