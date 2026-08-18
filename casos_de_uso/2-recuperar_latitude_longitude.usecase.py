from __future__ import annotations

import csv
import json
import logging
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from servicos.open_street_map import OpenStreetMapGeocoder

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

SOURCE_PATH = ROOT / "bases" / "normaliza_hospitais_publicos_sao_paulo_sp.csv"
ORIGINAL_SOURCE_PATH = ROOT / "bases" / "hospitais_publicos_sao_paulo_sp.csv"
OUTPUT_PATH = ROOT / "bases" / "latitude_longitude_hospitais_publicos_sao_paulo_sp.csv"
CLEAN_OUTPUT_PATH = ROOT / "bases" / "limpa_latitude_longitude_hospitais_publicos_sao_paulo_sp.csv"
CACHE_DIR = ROOT / "bases" / ".cache" / "nominatim"
DELAY_SECONDS = 2.5
LAST_REQUEST_AT = 0.0


def normalize_query_parts(*parts: str) -> str:
    """Remove separadores vazios e junta partes para formar uma consulta."""
    normalized_parts = [part.strip(" ,") for part in parts if part and part.strip(" ,")]
    return ", ".join(normalized_parts)


def address_has_sao_paulo_suffix(endereco: str) -> bool:
    """Verifica se o endereco ja termina com cidade e UF do recorte."""
    return bool(
        re.search(
            r"(?:^|,)\s*s[aã]o paulo\s*,\s*sp(?:\s*,\s*brasil)?\s*$",
            endereco or "",
            re.IGNORECASE,
        )
    )


def build_location_query(endereco: str) -> str:
    """Garante que a consulta de endereco tenha contexto geografico suficiente."""
    if address_has_sao_paulo_suffix(endereco):
        return normalize_query_parts(endereco)
    return normalize_query_parts(endereco, "São Paulo", "SP", "Brasil")


def build_query(hospital: str, endereco: str) -> str:
    """Combina nome e endereco para uma consulta textual ao geocoder."""
    return normalize_query_parts(hospital, build_location_query(endereco))


def build_official_address_query(original_row: dict[str, str]) -> str:
    """Monta uma consulta usando os campos de endereco da base oficial."""
    street = original_row.get("NO_LOGRADOURO", "")
    number = original_row.get("NU_ENDERECO", "")
    neighborhood = original_row.get("NO_BAIRRO", "")
    city = original_row.get("MUNICIPIO", "")
    state = original_row.get("UF", "")
    postcode = str(original_row.get("CO_CEP", "")).strip()
    if postcode:
        postcode = postcode.zfill(8)

    street_address = normalize_query_parts(street, number)
    city_state = " - ".join(part for part in (city, state) if part)
    locality = normalize_query_parts(neighborhood, city_state)
    address = " - ".join(part for part in (street_address, locality) if part)
    return normalize_query_parts(address, postcode, "Brasil")


def build_structured_query(original_row: dict[str, str]) -> str:
    """Monta uma consulta detalhada com nome, endereco, CEP e localidade."""
    name = original_row.get("NOME_ESTABELECIMENTO", "")
    street = original_row.get("NO_LOGRADOURO", "")
    number = original_row.get("NU_ENDERECO", "")
    neighborhood = original_row.get("NO_BAIRRO", "")
    city = original_row.get("MUNICIPIO", "")
    state = original_row.get("UF", "")
    postcode = str(original_row.get("CO_CEP", "")).strip().zfill(8)

    street_address = normalize_query_parts(street, number)
    return normalize_query_parts(
        name,
        street_address,
        neighborhood,
        city,
        state,
        postcode,
        "Brasil",
    )


def build_street_postcode_query(original_row: dict[str, str]) -> str:
    """Monta a consulta mais especifica baseada em logradouro e CEP."""
    street_address = normalize_query_parts(
        original_row.get("NO_LOGRADOURO", ""),
        original_row.get("NU_ENDERECO", ""),
    )
    postcode = str(original_row.get("CO_CEP", "")).strip().zfill(8)
    if not street_address or not postcode:
        return ""
    return f"{street_address} - {postcode}"


def build_cep_number_query(original_row: dict[str, str]) -> str:
    """Monta uma consulta alternativa baseada em CEP, numero e localidade."""
    postcode = str(original_row.get("CO_CEP", "")).strip().zfill(8)
    number = str(original_row.get("NU_ENDERECO", "")).strip()
    city = original_row.get("MUNICIPIO", "")
    state = original_row.get("UF", "")
    if not postcode or not number:
        return ""
    return normalize_query_parts(postcode, number, city, state, "Brasil")


def read_original_rows() -> dict[str, dict[str, str]]:
    """Carrega a base oficial indexada pelo ID para rastreabilidade."""
    with ORIGINAL_SOURCE_PATH.open("r", encoding="latin-1", newline="") as original_file:
        reader = csv.DictReader(original_file, delimiter=";")
        return {
            str(row.get("ID", "")).strip(): row
            for row in reader
            if str(row.get("ID", "")).strip()
        }


def extract_cep_and_number(endereco: str) -> tuple[str, str]:
    """Extrai CEP e numero de um endereco ja normalizado."""
    cep_match = re.search(r"\b\d{5}-?\d{3}\b", endereco or "")
    number_match = re.search(r"(?:,|\bN[º°.]?\s*)\s*(\d+)\b", endereco or "", re.IGNORECASE)
    cep = cep_match.group(0) if cep_match else ""
    number = number_match.group(1) if number_match else ""
    return cep, number


def build_cep_query(endereco: str) -> str:
    """Cria uma consulta alternativa usando CEP e numero extraidos do texto."""
    cep, number = extract_cep_and_number(endereco)
    if not cep or not number:
        return ""
    return normalize_query_parts(f"CEP {cep}", f"número {number}", "São Paulo", "SP", "Brasil")


def cache_path_for(record_id: str) -> Path:
    """Retorna o caminho deterministico do cache associado ao registro."""
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(record_id).strip()) or "record"
    return CACHE_DIR / f"{safe_id}.json"


def read_cache(record_id: str) -> dict | None:
    """Le um resultado persistido sem interromper o pipeline por cache invalido."""
    path = cache_path_for(record_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def write_cache(record_id: str, payload: dict) -> None:
    """Persiste o resultado de uma tentativa de geocodificacao em JSON."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path_for(record_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def wait_for_delay() -> None:
    """Respeita o intervalo minimo entre chamadas ao Nominatim."""
    global LAST_REQUEST_AT
    now = time.monotonic()
    elapsed = now - LAST_REQUEST_AT
    if LAST_REQUEST_AT and elapsed < DELAY_SECONDS:
        time.sleep(DELAY_SECONDS - elapsed)
    LAST_REQUEST_AT = time.monotonic()


def should_fetch_from_api(payload: dict | None) -> bool:
    """Indica se o cache precisa ser atualizado por nova consulta externa."""
    if payload is None:
        return True
    if payload.get("status") != "ok":
        return True
    lat = payload.get("lat")
    lon = payload.get("lon")
    if lat in (None, "") or lon in (None, ""):
        return True
    return False


def determine_accuracy(result: dict | None) -> str:
    """Classifica a precisao estimada pelo tipo e importancia do resultado."""
    if not result:
        return "not_found"
    place_type = (result.get("type") or "").lower()
    if place_type in {"hospital", "clinic", "doctors", "medical_center"}:
        return "high"
    if float(result.get("importance", 0.0)) >= 0.7:
        return "medium"
    return "low"


def extract_address_fields(result: dict | None) -> dict[str, str]:
    """Extrai cidade, estado e pais do endereco retornado pelo Nominatim."""
    address = (result or {}).get("address", {})
    return {
        "address_city": str(address.get("city") or address.get("town") or address.get("municipality") or "").strip(),
        "address_state": str(address.get("state") or "").strip(),
        "address_country": str(address.get("country") or "").strip(),
    }


def buscar_resultado_geografico(
    record_id: str,
    hospital: str,
    endereco: str,
    geocoder: OpenStreetMapGeocoder,
    original_row: dict[str, str] | None = None,
) -> tuple[dict | None, str, bool, int, str]:
    """Busca resultado geográfico com tratamento de cache.
    
    Retorna:
        tuple: (result, query_used, api_error, status_code, observacao)
    """
    cached_payload = read_cache(record_id)
    if not should_fetch_from_api(cached_payload):
        result = cached_payload.get("result") if isinstance(cached_payload.get("result"), dict) else cached_payload
        cache_status = cached_payload.get("status", "unknown")
        cache_msg = cached_payload.get("message", "")
        status_code = cached_payload.get("status_code", 0)
        observacao = cached_payload.get("observacao", "")
        logging.info(f"[CACHE_HIT] ID={record_id} | Status={cache_status} | Hospital={hospital[:40]} | Message={cache_msg}")
        return result, str(cached_payload.get("query", "")).strip(), False, status_code, observacao

    official_name = normalize_query_parts((original_row or {}).get("NOME_ESTABELECIMENTO", ""))
    official_address = build_official_address_query(original_row) if original_row else ""
    address_without_postcode = re.sub(r",\s*\d{5}-?\d{3},\s*Brasil\s*$", "", official_address, flags=re.IGNORECASE)
    structured_query = build_structured_query(original_row) if original_row else ""
    candidates = [
        build_street_postcode_query(original_row) if original_row else "",
        build_cep_number_query(original_row) if original_row else build_cep_query(endereco),
        structured_query,
        official_address,
        normalize_query_parts(official_name, address_without_postcode),
        address_without_postcode,
        build_query(hospital, endereco),
    ]

    unique_candidates: list[str] = []
    seen_candidates: set[str] = set()
    for candidate in candidates:
        normalized_candidate = normalize_query_parts(candidate)
        candidate_key = normalized_candidate.casefold()
        if normalized_candidate and candidate_key not in seen_candidates:
            seen_candidates.add(candidate_key)
            unique_candidates.append(normalized_candidate)

    for candidate in unique_candidates:
        if not candidate.strip():
            continue

        wait_for_delay()
        try:
            api_response = geocoder.search(candidate)
            if api_response is None:
                payload = {"status": "not_found", "query": candidate, "message": "Nenhum resultado retornado pelo Nominatim", "status_code": 0}
                write_cache(record_id, payload)
                logging.debug(f"[NOT_FOUND] ID={record_id} | Query={candidate}")
                continue
            
            result = api_response.get("result")
            status_code = api_response.get("status_code", 0)
            response_payload = api_response.get("response", [])
            success = api_response.get("success", False)
            
            if success and result is not None:
                # Sucesso: lat e lon encontrados
                payload = {
                    "status": "ok",
                    "query": candidate,
                    "lat": result.get("lat"),
                    "lon": result.get("lon"),
                    "result": result,
                    "status_code": status_code
                }
                write_cache(record_id, payload)
                logging.info(f"[SUCCESS] ID={record_id} | Query={candidate} | Lat={result.get('lat')}, Lon={result.get('lon')}")
                return result, candidate, False, status_code, ""
            else:
                # Falso positivo: status 200 mas sem coordenadas
                observacao = f"Status 200 OK mas sem lat/lon. Response: {json.dumps(response_payload, ensure_ascii=False)[:200]}"
                payload = {
                    "status": "false_positive",
                    "query": candidate,
                    "message": "Resposta 200 OK mas sem coordenadas",
                    "status_code": status_code,
                    "observacao": observacao,
                    "response": response_payload
                }
                write_cache(record_id, payload)
                logging.warning(f"[FALSE_POSITIVE] ID={record_id} | Query={candidate} | Status={status_code} | {observacao[:100]}")
                
        except Exception as e:
            error_msg = str(e)
            payload = {"status": "error", "query": candidate, "message": error_msg}
            write_cache(record_id, payload)
            logging.error(f"[API_ERROR] ID={record_id} | Query={candidate} | Error={error_msg}")
            return None, candidate, True, 0, f"Erro de conexão: {error_msg}"

    logging.warning(f"[FAILED] ID={record_id} | Hospital={hospital[:40]} | Nenhuma query retornou coordenadas")
    return None, "", False, 0, "Nenhuma das queries retornou coordenadas válidas"


def recuperar_latitude_longitude() -> int:
    """Geocodifica os hospitais, grava auditoria completa e cria arquivo limpo."""
    geocoder = OpenStreetMapGeocoder()
    original_rows = read_original_rows()

    with SOURCE_PATH.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file, delimiter=";")
        rows = list(reader)

    if not rows:
        return 0

    processed = 0
    output_rows: list[dict[str, str]] = []
    consecutive_errors = 0

    logging.info(f"Iniciando processamento de {len(rows)} hospitais...")

    # Cada registro pode tentar varias consultas, mas o cache evita repetir chamadas.
    for row_index, row in enumerate(rows, start=1):
        hospital = (row.get("hospital") or "").strip()
        endereco = (row.get("endereco") or "").strip()
        record_id = str(row.get("id", "")).strip()

        result, used_query, api_error, status_code, observacao = buscar_resultado_geografico(
            record_id,
            hospital,
            endereco,
            geocoder,
            original_rows.get(record_id),
        )

        if api_error:
            consecutive_errors += 1
            logging.error(f"Erro consecutivo #{consecutive_errors} detectado no ID={record_id}")
            if consecutive_errors >= 2:
                logging.critical("API DO NOMINATIM ESTÁ INDISPONÍVEL (2 erros consecutivos detectados)")
                logging.info(f"Encerrando processamento. {row_index - 1} de {len(rows)} registros foram processados.")
                break
        else:
            consecutive_errors = 0

        # O arquivo bruto preserva inclusive falhas para permitir revisao posterior.
        status = "ok" if result else "not_found"
        
        # Recupera mensagem de erro do cache se disponível
        error_message = ""
        cached_payload = read_cache(record_id)
        if cached_payload and cached_payload.get("status") != "ok":
            error_message = cached_payload.get("message", "")

        latitude = str(result.get("lat", "")).strip() if result else ""
        longitude = str(result.get("lon", "")).strip() if result else ""
        place_id = str(result.get("place_id", "")).strip() if result else ""
        osm_type = str(result.get("osm_type", "")).strip() if result else ""
        osm_id = str(result.get("osm_id", "")).strip() if result else ""
        display_name = str(result.get("display_name", "")).strip() if result else ""
        importance = str(result.get("importance", "")).strip() if result else ""
        feature_class = str(result.get("class", "")).strip() if result else ""
        feature_type = str(result.get("type", "")).strip() if result else ""

        address_fields = extract_address_fields(result)

        output_rows.append(
            {
                "id": record_id,
                "hospital": hospital,
                "endereco": endereco,
                "latitude": latitude,
                "longitude": longitude,
                "geocode_status": status,
                "geocode_provider": "nominatim",
                "geocode_accuracy": determine_accuracy(result),
                "geocode_error_message": error_message,
                "status_code": str(status_code),
                "observacao": observacao,
                "place_id": place_id,
                "osm_type": osm_type,
                "osm_id": osm_id,
                "display_name": display_name,
                "importance": importance,
                "feature_class": feature_class,
                "feature_type": feature_type,
                "address_city": address_fields["address_city"],
                "address_state": address_fields["address_state"],
                "address_country": address_fields["address_country"],
                "query_used": used_query,
                "api_response": json.dumps(result, ensure_ascii=False) if result else "",
            }
        )
        processed += 1

    fieldnames = [
        "id",
        "hospital",
        "endereco",
        "latitude",
        "longitude",
        "geocode_status",
        "geocode_provider",
        "geocode_accuracy",
        "geocode_error_message",
        "status_code",
        "observacao",
        "place_id",
        "osm_type",
        "osm_id",
        "display_name",
        "importance",
        "feature_class",
        "feature_type",
        "address_city",
        "address_state",
        "address_country",
        "query_used",
        "api_response",
    ]

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(output_rows)

    clean_rows = [
        row
        for row in output_rows
        if row["geocode_status"] == "ok"
        and row["latitude"]
        and row["longitude"]
    ]
    with CLEAN_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as clean_output_file:
        clean_writer = csv.DictWriter(clean_output_file, fieldnames=fieldnames, delimiter=";")
        clean_writer.writeheader()
        clean_writer.writerows(clean_rows)

    logging.info(f"Arquivo gerado: {OUTPUT_PATH}")
    logging.info(f"Arquivo limpo gerado: {CLEAN_OUTPUT_PATH}")
    logging.info(f"Registros processados: {processed}")
    logging.info(f"Registros válidos no arquivo limpo: {len(clean_rows)}")
    return processed


if __name__ == "__main__":
    total = recuperar_latitude_longitude()
    print(f"Arquivo gerado: {OUTPUT_PATH}")
    print(f"Registros processados: {total}")
