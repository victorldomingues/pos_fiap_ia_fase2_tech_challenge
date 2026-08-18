from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "bases" / "hospitais_publicos_sao_paulo_sp.csv"
OUTPUT_PATH = ROOT / "bases" / "normaliza_hospitais_publicos_sao_paulo_sp.csv"


def normalize_text(value: object) -> str:
    """Converte um valor para texto limpo e remove espacos redundantes."""
    if value is None:
        return ""

    text = str(value).strip()
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\uFFFD", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_key(value: object) -> str:
    """Normaliza um valor para comparacoes de filtros sem diferenca de caixa."""
    return normalize_text(value).upper()


def build_endereco(row: dict[str, str]) -> str:
    """Monta um endereco legivel a partir dos campos oficiais da linha."""
    logradouro = normalize_text(row.get("NO_LOGRADOURO", ""))
    numero = normalize_text(row.get("NU_ENDERECO", ""))
    complemento = normalize_text(row.get("NO_COMPLEMENTO", ""))
    bairro = normalize_text(row.get("NO_BAIRRO", ""))
    cidade = normalize_text(row.get("MUNICIPIO", ""))
    uf = normalize_text(row.get("UF", ""))

    partes_endereco = [p for p in [logradouro, numero, complemento] if p]
    prefixo = ", ".join(partes_endereco)

    partes_localidade = [p for p in [bairro, cidade, uf] if p]
    sufixo = ", ".join(partes_localidade)

    if prefixo and sufixo:
        return f"{prefixo} - {sufixo}"
    if prefixo:
        return prefixo
    if sufixo:
        return sufixo
    return ""


def is_hospital_publico(row: dict[str, str]) -> bool:
    """Indica se a natureza juridica identifica um hospital publico."""
    natureza = normalize_key(row.get("DESC_NATUREZA_JURIDICA", ""))
    return natureza in {"HOSPITAL_PUBLICO", "HOSPITAL_PÚBLICO", "HOSPITAL PÚBLICO", "HOSPITAL_P\u00daBLICO"}


def normalizar_base() -> int:
    """Filtra a base oficial e grava a versao normalizada do recorte."""
    total = 0

    # A base oficial usa Latin-1 e ponto e virgula; ambos precisam ser
    # informados explicitamente para preservar os caracteres e as colunas.
    with SOURCE_PATH.open("r", encoding="latin-1", newline="") as source_file:
        reader = csv.DictReader(source_file, delimiter=";")

        rows: list[dict[str, str]] = []
        for row in reader:
            if not row:
                continue

            # O recorte academico considera somente Sao Paulo, SP e hospitais publicos.
            if normalize_key(row.get("UF", "")) != "SP":
                continue

            if normalize_key(row.get("MUNICIPIO", "")) != "SAO PAULO":
                continue

            if not is_hospital_publico(row):
                continue

            id_original = normalize_text(row.get("ID", ""))
            hospital = normalize_text(row.get("NOME_ESTABELECIMENTO", ""))
            endereco = build_endereco(row)

            if not hospital:
                continue

            rows.append(
                {
                    "id": id_original,
                    "hospital": hospital,
                    "endereco": endereco,
                }
            )
            total += 1

    # O arquivo de saida contem apenas o contrato minimo consumido pelas etapas seguintes.
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=["id", "hospital", "endereco"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    return total


if __name__ == "__main__":
    total = normalizar_base()
    print(f"Arquivo gerado: {OUTPUT_PATH}")
    print(f"Registros normalizados: {total}")
