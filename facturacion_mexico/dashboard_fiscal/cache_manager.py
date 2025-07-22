"""
Cache Manager - Sistema de Cache Inteligente para Dashboard Fiscal
Aplicando patrones de performance del Custom Fields Migration Sprint
Intelligent Caching con invalidación automática y graceful degradation
"""

import hashlib
import json
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, ClassVar

import frappe


class DashboardCache:
	"""Sistema de cache inteligente con TTL y invalidación por patrones"""

	_lock = threading.Lock()
	_cache: ClassVar[dict[str, dict]] = {}
	_stats: ClassVar[dict[str, int]] = {"hits": 0, "misses": 0, "errors": 0, "invalidations": 0}

	@staticmethod
	def _generate_cache_key(prefix: str, params: dict) -> str:
		"""Generar clave de cache consistente"""
		try:
			# Ordenar parámetros para consistencia
			sorted_params = json.dumps(params, sort_keys=True, default=str)
			param_hash = hashlib.md5(sorted_params.encode()).hexdigest()[:8]
			return f"dashboard_cache:{prefix}:{param_hash}"
		except Exception:
			# Fallback a timestamp si hay error
			return f"dashboard_cache:{prefix}:{int(time.time())}"

	@staticmethod
	def get_or_set(key: str, fetcher_function: Callable, ttl: int = 3600, **kwargs) -> Any:
		"""
		Cache inteligente con TTL y graceful degradation

		Args:
			key: Clave base del cache
			fetcher_function: Función para obtener datos si no están en cache
			ttl: Time to live en segundos (default: 1 hora)
			**kwargs: Argumentos para la función fetcher

		Returns:
			Datos del cache o resultado de fetcher_function
		"""
		try:
			# Generar clave completa
			cache_key = DashboardCache._generate_cache_key(key, kwargs)

			with DashboardCache._lock:
				# Verificar si existe en cache y no está expirado
				if cache_key in DashboardCache._cache:
					cache_entry = DashboardCache._cache[cache_key]

					if time.time() < cache_entry["expires_at"]:
						DashboardCache._stats["hits"] += 1
						frappe.logger().debug(f"Cache HIT: {cache_key}")
						return cache_entry["data"]
					else:
						# Expirado, remover
						del DashboardCache._cache[cache_key]

			# Cache miss o expirado, obtener datos frescos
			DashboardCache._stats["misses"] += 1
			frappe.logger().debug(f"Cache MISS: {cache_key}")

			# Aplicar patrón: Error handling robusto del Custom Fields Migration
			try:
				fresh_data = fetcher_function(**kwargs)

				# Guardar en cache con TTL
				cache_entry = {
					"data": fresh_data,
					"created_at": time.time(),
					"expires_at": time.time() + ttl,
					"key": cache_key,
				}

				with DashboardCache._lock:
					DashboardCache._cache[cache_key] = cache_entry

				return fresh_data

			except Exception as e:
				DashboardCache._stats["errors"] += 1
				frappe.log_error(
					title=f"Error en Cache Manager - {key}",
					message=f"Error ejecutando fetcher_function: {e!s}\nKwargs: {kwargs}",
				)

				# Graceful degradation: retornar None o valor por defecto
				return None

		except Exception as e:
			DashboardCache._stats["errors"] += 1
			frappe.log_error(title="Error crítico en Cache Manager", message=f"Error en get_or_set: {e!s}")

			# Fallback: intentar ejecutar función directamente
			try:
				return fetcher_function(**kwargs)
			except Exception:
				return None

	@staticmethod
	def invalidate_pattern(pattern: str) -> int:
		"""
		Invalidar cache por patrón

		Args:
			pattern: Patrón para buscar claves (ej: "timbrado", "dashboard_cache:kpis")

		Returns:
			Número de entradas invalidadas
		"""
		try:
			invalidated_count = 0

			with DashboardCache._lock:
				keys_to_remove = []

				for cache_key in DashboardCache._cache:
					if pattern in cache_key:
						keys_to_remove.append(cache_key)

				for key in keys_to_remove:
					del DashboardCache._cache[key]
					invalidated_count += 1

			DashboardCache._stats["invalidations"] += invalidated_count

			if invalidated_count > 0:
				frappe.logger().info(
					f"Cache invalidado: {invalidated_count} entradas para patrón '{pattern}'"
				)

			return invalidated_count

		except Exception as e:
			frappe.log_error(title="Error invalidando cache", message=f"Error con patrón '{pattern}': {e!s}")
			return 0

	@staticmethod
	def get_cache_stats() -> dict[str, int | float | dict]:
		"""Obtener estadísticas completas de uso de cache"""
		try:
			with DashboardCache._lock:
				cache_size = len(DashboardCache._cache)

				# Calcular hit ratio
				total_requests = DashboardCache._stats["hits"] + DashboardCache._stats["misses"]
				hit_ratio = (
					(DashboardCache._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
				)

				# Analizar antigüedad de entradas
				current_time = time.time()
				expired_count = 0
				oldest_entry = None
				newest_entry = None

				for entry in DashboardCache._cache.values():
					if current_time >= entry["expires_at"]:
						expired_count += 1

					if oldest_entry is None or entry["created_at"] < oldest_entry:
						oldest_entry = entry["created_at"]

					if newest_entry is None or entry["created_at"] > newest_entry:
						newest_entry = entry["created_at"]

				# Memoria aproximada (básico)
				memory_estimate = sum(
					len(json.dumps(entry, default=str)) for entry in DashboardCache._cache.values()
				)

				return {
					"cache_size": cache_size,
					"hit_ratio": round(hit_ratio, 2),
					"stats": DashboardCache._stats.copy(),
					"expired_entries": expired_count,
					"memory_estimate_bytes": memory_estimate,
					"oldest_entry_age_seconds": int(current_time - oldest_entry) if oldest_entry else 0,
					"newest_entry_age_seconds": int(current_time - newest_entry) if newest_entry else 0,
				}

		except Exception as e:
			frappe.log_error(title="Error obteniendo estadísticas de cache", message=f"Error: {e!s}")
			return {"error": "Unable to get cache stats"}

	@staticmethod
	def cleanup_expired() -> int:
		"""Limpiar entradas expiradas del cache"""
		try:
			current_time = time.time()
			removed_count = 0

			with DashboardCache._lock:
				expired_keys = []

				for cache_key, entry in DashboardCache._cache.items():
					if current_time >= entry["expires_at"]:
						expired_keys.append(cache_key)

				for key in expired_keys:
					del DashboardCache._cache[key]
					removed_count += 1

			if removed_count > 0:
				frappe.logger().info(f"Cache cleanup: {removed_count} entradas expiradas removidas")

			return removed_count

		except Exception as e:
			frappe.log_error(title="Error en cleanup de cache", message=f"Error: {e!s}")
			return 0

	@staticmethod
	def warmup_cache(warmup_functions: list[dict[str, Any]]):
		"""
		Pre-cargar cache con datos comunes (Background job pattern)

		Args:
			warmup_functions: Lista de funciones para pre-cargar
				[{"key": "kpi_timbrado", "function": func, "kwargs": {}, "ttl": 3600}]
		"""
		try:
			warmed_count = 0

			for warmup_config in warmup_functions:
				try:
					key = warmup_config.get("key")
					function = warmup_config.get("function")
					kwargs = warmup_config.get("kwargs", {})
					ttl = warmup_config.get("ttl", 3600)

					if not key or not function:
						continue

					# Pre-cargar usando get_or_set
					DashboardCache.get_or_set(key, function, ttl, **kwargs)
					warmed_count += 1

				except Exception as e:
					frappe.logger().warning(
						f"Error pre-cargando cache para {warmup_config.get('key', 'unknown')}: {e}"
					)

			frappe.logger().info(f"Cache warmup completado: {warmed_count} entradas pre-cargadas")

		except Exception as e:
			frappe.log_error(title="Error en warmup de cache", message=f"Error: {e!s}")

	@staticmethod
	def clear_all_cache():
		"""Limpiar todo el cache (usar solo para testing o emergencias)"""
		with DashboardCache._lock:
			cache_size = len(DashboardCache._cache)
			DashboardCache._cache.clear()
			DashboardCache._stats = {"hits": 0, "misses": 0, "errors": 0, "invalidations": 0}

		frappe.logger().info(f"Cache completamente limpiado: {cache_size} entradas removidas")

	@staticmethod
	def get_cache_entry(key: str, **kwargs) -> dict | None:
		"""Obtener entrada específica del cache para debugging"""
		try:
			cache_key = DashboardCache._generate_cache_key(key, kwargs)

			with DashboardCache._lock:
				if cache_key in DashboardCache._cache:
					entry = DashboardCache._cache[cache_key].copy()
					entry["is_expired"] = time.time() >= entry["expires_at"]
					entry["age_seconds"] = int(time.time() - entry["created_at"])
					return entry

			return None

		except Exception as e:
			frappe.log_error(title="Error obteniendo entrada de cache", message=f"Key: {key}, Error: {e!s}")
			return None


# Funciones de conveniencia para APIs


def cached_kpi(kpi_name: str, ttl: int = 900):
	"""Decorator para cachear KPIs automáticamente (15 min default)"""

	def decorator(func: Callable) -> Callable:
		def wrapper(*args, **kwargs):
			return DashboardCache.get_or_set(f"kpi_{kpi_name}", func, ttl=ttl, args=args, kwargs=kwargs)

		return wrapper

	return decorator


def cached_report(report_name: str, ttl: int = 1800):
	"""Decorator para cachear reportes automáticamente (30 min default)"""

	def decorator(func: Callable) -> Callable:
		def wrapper(*args, **kwargs):
			return DashboardCache.get_or_set(f"report_{report_name}", func, ttl=ttl, args=args, kwargs=kwargs)

		return wrapper

	return decorator
