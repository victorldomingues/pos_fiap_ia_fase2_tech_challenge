from __future__ import annotations

import csv
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INPUT_PATH = ROOT / "bases" / "limpa_latitude_longitude_hospitais_publicos_sao_paulo_sp.csv"
ORIGINAL_PATH = ROOT / "bases" / "hospitais_publicos_sao_paulo_sp.csv"
OUTPUT_PATH = ROOT / "bases" / "por_bairro_hospitais_publicos_sao_paulo_sp.csv"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def normalize_key(value: str | None) -> str:
    """Normaliza o bairro para detectar duplicidades sem diferenca de caixa."""
    return " ".join((value or "").strip().casefold().split())


def read_original_rows() -> tuple[dict[str, dict[str, str]], list[str]]:
    """Carrega a base oficial e retorna suas linhas indexadas e colunas."""
    with ORIGINAL_PATH.open("r", encoding="latin-1", newline="") as original_file:
        reader = csv.DictReader(original_file, delimiter=";")
        rows = {
            str(row.get("ID", "")).strip(): row
            for row in reader
            if str(row.get("ID", "")).strip()
        }
        return rows, list(reader.fieldnames or [])


def select_one_hospital_per_neighborhood() -> int:
    """Seleciona um hospital geocodificado por bairro e grava o recorte."""
    original_rows_by_id, original_fieldnames = read_original_rows()

    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file, delimiter=";")
        input_rows = list(reader)
        input_fieldnames = list(reader.fieldnames or [])

    geocoding_fieldnames = [
        fieldname
        for fieldname in input_fieldnames
        if fieldname not in {"id", "api_response"}
    ]
    output_fieldnames = original_fieldnames + ["id", "bairro"] + geocoding_fieldnames

    selected_rows: list[dict[str, str]] = []
    selected_neighborhoods: set[str] = set()
    missing_original_ids = 0
    invalid_coordinates = 0
    missing_neighborhoods = 0

    # O ID liga o resultado do geocoding aos campos originais e ao bairro oficial.
    for row in input_rows:
        record_id = str(row.get("id", "")).strip()
        latitude = str(row.get("latitude", "")).strip()
        longitude = str(row.get("longitude", "")).strip()
        original_row = original_rows_by_id.get(record_id)
        neighborhood = str(original_row.get("NO_BAIRRO", "")).strip() if original_row else ""

        if not neighborhood:
            if original_row is None:
                missing_original_ids += 1
            else:
                missing_neighborhoods += 1
            continue
        if not latitude or not longitude:
            invalid_coordinates += 1
            continue

        # Apenas o primeiro hospital encontrado representa cada bairro.
        neighborhood_key = normalize_key(neighborhood)
        if neighborhood_key in selected_neighborhoods:
            continue

        selected_neighborhoods.add(neighborhood_key)
        output_row = dict(original_row)
        output_row["id"] = record_id
        output_row["bairro"] = neighborhood
        output_row.update(
            {
                fieldname: row.get(fieldname, "")
                for fieldname in geocoding_fieldnames
            }
        )
        selected_rows.append(output_row)

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=output_fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(selected_rows)

    logging.info("Arquivo gerado: %s", OUTPUT_PATH)
    logging.info("Registros de entrada: %d", len(input_rows))
    logging.info("Hospitais selecionados: %d", len(selected_rows))
    logging.info("Bairros distintos selecionados: %d", len(selected_neighborhoods))
    logging.info("IDs sem correspondência na base original: %d", missing_original_ids)
    logging.info("Registros sem bairro: %d", missing_neighborhoods)
    logging.info("Registros sem latitude ou longitude: %d", invalid_coordinates)
    return len(selected_rows)


if __name__ == "__main__":
    select_one_hospital_per_neighborhood()
