from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASES_DIR = ROOT / "bases"
TSP_BASES_DIR = ROOT / "tsp" / "bases"

ARQUIVOS_PARA_COPIAR = {
    BASES_DIR / "matriz_distacias.csv": TSP_BASES_DIR / "matriz_distacias_hospitais.csv",
    BASES_DIR / "veiculos.csv": TSP_BASES_DIR / "veiculos.csv",
}


def validar_arquivo_origem(caminho_origem: Path) -> None:
    """Valida se o arquivo de origem existe antes da copia."""
    if not caminho_origem.is_file():
        raise FileNotFoundError(f"Arquivo de origem nao encontrado: {caminho_origem}")


def copiar_bases_para_tsp() -> None:
    """Copia as bases finais da raiz para o pacote tsp."""
    # Garante que o diretorio de destino existe antes da copia.
    TSP_BASES_DIR.mkdir(parents=True, exist_ok=True)

    for caminho_origem, caminho_destino in ARQUIVOS_PARA_COPIAR.items():
        validar_arquivo_origem(caminho_origem)
        shutil.copy2(caminho_origem, caminho_destino)
        print(f"Copiado: {caminho_origem.relative_to(ROOT)} -> {caminho_destino.relative_to(ROOT)}")


def main() -> None:
    """Executa a copia das bases usadas pelo projeto tsp."""
    copiar_bases_para_tsp()
    print("Bases copiadas com sucesso para tsp/bases.")


if __name__ == "__main__":
    main()
