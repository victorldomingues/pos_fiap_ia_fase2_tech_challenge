from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from servicos.open_route import OpenRouteServiceClient

INPUT_PATH = ROOT / "bases" / "por_bairro_hospitais_publicos_sao_paulo_sp.csv"
OUTPUT_PATH = ROOT / "bases" / "matriz_distacias.csv"
CACHE_DIR = ROOT / "bases" / ".cache" / "openrouteservice"
REQUEST_DELAY_SECONDS = 2.0
LAST_REQUEST_AT = 0.0


def load_env_file() -> None:
	"""Carrega variáveis simples do arquivo .env na raiz do projeto."""
	env_path = ROOT / ".env"
	if not env_path.exists():
		return

	for raw_line in env_path.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue

		key, value = line.split("=", 1)
		key = key.strip()
		value = value.strip()
		if not key or key in os.environ:
			continue
		if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
			value = value[1:-1]
		os.environ[key] = value


def carregar_hospitais() -> list[dict[str, Any]]:
	"""Carrega hospitais geocodificados com coordenadas numericas."""
	hospitais: list[dict[str, Any]] = []
	with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as input_file:
		reader = csv.DictReader(input_file, delimiter=";")
		for row in reader:
			latitude = float(row["latitude"])
			longitude = float(row["longitude"])
			hospitais.append(
				{
					"id": str(row["id"]).strip(),
					"hospital": str(row.get("hospital", "")).strip(),
					"bairro": str(row.get("bairro", "")).strip(),
					"lat": latitude,
					"lng": longitude,
				}
			)
	if not hospitais:
		raise ValueError(f"Nenhum hospital encontrado em {INPUT_PATH}")
	return hospitais


def wait_for_request_delay() -> None:
	"""Controla o intervalo minimo entre chamadas ao servico de rotas."""
	global LAST_REQUEST_AT
	now = time.monotonic()
	if LAST_REQUEST_AT:
		remaining = REQUEST_DELAY_SECONDS - (now - LAST_REQUEST_AT)
		if remaining > 0:
			time.sleep(remaining)
	LAST_REQUEST_AT = time.monotonic()


def cache_path_for(
	origins: list[dict[str, Any]],
	destinations: list[dict[str, Any]],
) -> Path:
	"""Calcula um caminho de cache deterministico para um par de lotes."""
	value = json.dumps(
		{
			"origins": [(item["id"], item["lat"], item["lng"]) for item in origins],
			"destinations": [(item["id"], item["lat"], item["lng"]) for item in destinations],
		},
		sort_keys=True,
	)
	cache_key = hashlib.sha256(value.encode("utf-8")).hexdigest()
	return CACHE_DIR / f"{cache_key}.json"


def duration_to_seconds(duration: str | int | float) -> float:
	"""Converte duracao textual ou numerica para segundos."""
	if isinstance(duration, str):
		return float(duration.rstrip("s"))
	return float(duration)


def load_or_request_matrix(
	origins: list[dict[str, Any]],
	destinations: list[dict[str, Any]],
	api_key: str,
	service: OpenRouteServiceClient,
) -> dict[str, Any]:
	"""Le a resposta da matriz do cache ou consulta o OpenRouteService."""
	cache_path = cache_path_for(origins, destinations)
	if cache_path.exists():
		try:
			cached = json.loads(cache_path.read_text(encoding="utf-8"))
			if isinstance(cached, dict):
				print(f"Cache ORS: {cache_path.name}")
				return cached
		except (OSError, json.JSONDecodeError):
			pass

	wait_for_request_delay()
	result = service.matrix(origins, destinations, api_key)
	CACHE_DIR.mkdir(parents=True, exist_ok=True)
	cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
	return result


def gerar_matriz(
	hospitais: list[dict[str, Any]],
	api_key: str,
	batch_size: int = 25,
	service: OpenRouteServiceClient | None = None,
) -> list[dict[str, Any]]:
	"""Gera distancias e duracoes para todos os pares, processando em lotes."""
	if batch_size <= 0:
		raise ValueError("batch_size deve ser maior que zero")

	service = service or OpenRouteServiceClient()
	total = len(hospitais)
	distance_matrix = np.full((total, total), np.nan, dtype=float)
	duration_matrix = np.full((total, total), np.nan, dtype=float)
	distance_matrix[np.diag_indices(total)] = 0.0
	duration_matrix[np.diag_indices(total)] = 0.0

	# A matriz e direcionada: cada bloco preserva origem e destino independentes.
	for origin_start in range(0, total, batch_size):
		origins = hospitais[origin_start : origin_start + batch_size]
		for destination_start in range(0, total, batch_size):
			destinations = hospitais[destination_start : destination_start + batch_size]
			print(
				f"Consultando origens {origin_start + 1}-{origin_start + len(origins)} "
				f"e destinos {destination_start + 1}-{destination_start + len(destinations)}"
			)
			try:
				result = load_or_request_matrix(origins, destinations, api_key, service)
				distances = result["distances"]
				durations = result["durations"]
				for local_origin, row in enumerate(distances):
					for local_destination, distance in enumerate(row):
						origin_index = origin_start + local_origin
						destination_index = destination_start + local_destination
						if distance is not None:
							# O ORS retorna quilômetros; o CSV mantém metros.
							distance_matrix[origin_index, destination_index] = float(distance) * 1000
						if durations[local_origin][local_destination] is not None:
							duration_matrix[origin_index, destination_index] = duration_to_seconds(durations[local_origin][local_destination])
			except (OSError, KeyError, IndexError, TypeError, ValueError) as error:
				print(f"Erro no bloco ORS: {error}")

	rows: list[dict[str, Any]] = []
	for origin_index, origin in enumerate(hospitais):
		for destination_index, destination in enumerate(hospitais):
			distance = distance_matrix[origin_index, destination_index]
			duration = duration_matrix[origin_index, destination_index]
			rows.append(
				{
					"origin_id": origin["id"],
					"origin_hospital": origin["hospital"],
					"origin_bairro": origin["bairro"],
					"origin_latitude": origin["lat"],
					"origin_longitude": origin["lng"],
					"destination_id": destination["id"],
					"destination_hospital": destination["hospital"],
					"destination_bairro": destination["bairro"],
					"destination_latitude": destination["lat"],
					"destination_longitude": destination["lng"],
					"distance_meters": "" if np.isnan(distance) else int(distance),
					"distance_km": "" if np.isnan(distance) else round(float(distance) / 1000, 3),
					"duration_seconds": "" if np.isnan(duration) else int(duration),
					"duration_minutes": "" if np.isnan(duration) else round(float(duration) / 60, 2),
					"status": "ok" if not np.isnan(distance) and not np.isnan(duration) else "error",
					"error_message": "" if not np.isnan(distance) and not np.isnan(duration) else "Resposta sem distância ou duração",
				}
			)
	return rows


def salvar_matriz(rows: list[dict[str, Any]]) -> None:
	"""Persiste as relacoes origem-destino no CSV usado pelas visualizacoes."""
	fieldnames = [
		"origin_id",
		"origin_hospital",
		"origin_bairro",
		"origin_latitude",
		"origin_longitude",
		"destination_id",
		"destination_hospital",
		"destination_bairro",
		"destination_latitude",
		"destination_longitude",
		"distance_meters",
		"distance_km",
		"duration_seconds",
		"duration_minutes",
		"status",
		"error_message",
	]
	with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as output_file:
		writer = csv.DictWriter(output_file, fieldnames=fieldnames, delimiter=";")
		writer.writeheader()
		writer.writerows(rows)


def main() -> None:
	"""Carrega configuracao, calcula a matriz e grava o resultado final."""
	load_env_file()
	api_key = os.getenv("ORS_API_KEY", "").strip()
	if not api_key:
		raise RuntimeError("Defina a variável de ambiente ORS_API_KEY no .env ou no ambiente.")

	hospitais = carregar_hospitais()
	rows = gerar_matriz(hospitais, api_key)
	salvar_matriz(rows)
	print(f"Matriz gerada: {OUTPUT_PATH}")
	print(f"Hospitais: {len(hospitais)} | Relações: {len(rows)}")


if __name__ == "__main__":
	main()
