# -*- coding: utf-8 -*-
"""
Ponto de entrada principal do projeto.

Por padrao, executa somente o VRP HOSPITALAR (tsp/vrp.py + tsp/optimizer.py):
multiplos veiculos, com capacidade de carga, autonomia e prioridade de
entrega, alem de geracao de mapa de rotas, grafico de convergencia,
instrucoes de motoristas e relatorio operacional (via LLM ou template).

Opcionalmente, e possivel tambem rodar antes o TSP BASE (tsp/tsp.py):
algoritmo genetico classico do caixeiro viajante, uma unica rota visitando
todos os hospitais, sem restricoes de frota, com visualizacao interativa em
Pygame. Isso e controlado pela variavel `config.EXECUTAR_TSP_BASE` (padrao
False) ou pelo parametro `executar_tsp_base` de `main()`.

Uso (a partir da raiz do repositorio ou de dentro da pasta tsp/):
    python tsp/run.py                  # roda somente o VRP (padrao)
    python -m tsp.run                  # idem, como modulo do pacote

Para tambem rodar o TSP base, defina `EXECUTAR_TSP_BASE = True` em
tsp/config.py, ou chame `main(executar_tsp_base=True)` programaticamente.
"""



from __future__ import annotations

import os
import sys
from pathlib import Path

# Garante que a raiz do repositorio esteja no sys.path, permitindo importar o
# pacote `tsp` mesmo quando este arquivo e executado diretamente (python tsp/run.py)
_RAIZ_REPOSITORIO = Path(__file__).resolve().parent.parent
if str(_RAIZ_REPOSITORIO) not in sys.path:
    sys.path.insert(0, str(_RAIZ_REPOSITORIO))


def _carregar_env(caminho: Path) -> None:
    """Carrega variaveis de ambiente do arquivo .env (sem sobrescrever as ja definidas)."""
    if not caminho.is_file():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(caminho, override=False)
        return
    except ImportError:
        pass
    # Fallback minimo caso python-dotenv nao esteja instalado.
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave, valor = chave.strip(), valor.strip().strip('"').strip("'")
        os.environ.setdefault(chave, valor)


_carregar_env(_RAIZ_REPOSITORIO / ".env")

from tsp import config
from tsp.data_loader import (
    carregar_coordenadas_hospitais,
    carregar_frota,
    carregar_matriz_distancias,
    construir_lista_hospitais_base,
    gerar_demandas_hospitais,
)
from tsp.distance_matrix import calcular_coordenadas_mds, construir_matriz_custos
from tsp.llm_integration import gerar_instrucoes_motorista, gerar_relatorio_operacional, obter_cliente_llm
from tsp.optimizer import calcular_solucao_baseline, executar_algoritmo_genetico_vrp
from tsp.tsp import calcular_fitness_hospitais, executar_tsp_hospitais
from tsp.visualization import plotar_convergencia, plotar_mapa_rotas, plotar_mapa_rotas_openstreetmap


def executar_pipeline_vrp():
    """Executa o pipeline completo do VRP hospitalar e geracao de relatorios.

    Retorno:
    Tupla (melhor_solucao, solucao_baseline) com as solucoes VRP obtidas.
    """
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1-2. Carrega dados e gera demandas/prioridades sinteticas dos hospitais
    df_matriz = carregar_matriz_distancias()
    df_hospitais_base = construir_lista_hospitais_base(df_matriz)
    hospitais = gerar_demandas_hospitais(df_hospitais_base)
    hospitais_por_id = {hospital.id: hospital for hospital in hospitais}
    hospital_ids = [hospital.id for hospital in hospitais]

    frota = carregar_frota()
    print(f"Hospitais carregados: {len(hospitais)} | Veiculos na frota: {len(frota)}")

    # 3. Matrizes de custo (distancia e duracao) e projecao 2D para visualizacao
    matriz_distancias_km = construir_matriz_custos(df_matriz, hospital_ids, metrica="distance_km")
    matriz_duracoes_min = construir_matriz_custos(df_matriz, hospital_ids, metrica="duration_minutes")
    indice_por_id = {hospital_id: posicao for posicao, hospital_id in enumerate(hospital_ids)}
    coordenadas_mds = calcular_coordenadas_mds(matriz_distancias_km)
    coordenadas_geo_por_id = carregar_coordenadas_hospitais(df_matriz, hospital_ids)

    # 4. Algoritmo genetico e baseline
    print("Executando algoritmo genetico para o VRP hospitalar...")
    melhor_solucao, historico_fitness = executar_algoritmo_genetico_vrp(
        hospital_ids, hospitais_por_id, frota, config.DEPOT_HOSPITAL_ID,
        indice_por_id, matriz_distancias_km, matriz_duracoes_min,
    )
    solucao_baseline = calcular_solucao_baseline(
        hospital_ids, hospitais_por_id, frota, config.DEPOT_HOSPITAL_ID,
        indice_por_id, matriz_distancias_km, matriz_duracoes_min,
    )

    print(f"Fitness final (otimizado): {melhor_solucao.fitness:.1f} | Fitness baseline: {solucao_baseline.fitness:.1f}")
    print(f"Distancia total (otimizado): {melhor_solucao.total_distance_km:.1f} km | Baseline: {solucao_baseline.total_distance_km:.1f} km")

    # 5. Visualizacoes
    figura_mapa = plotar_mapa_rotas(melhor_solucao, coordenadas_mds, hospital_ids, hospitais_por_id, config.DEPOT_HOSPITAL_ID)
    html_mapa_openstreetmap = plotar_mapa_rotas_openstreetmap(
        melhor_solucao, coordenadas_geo_por_id, hospitais_por_id, config.DEPOT_HOSPITAL_ID,
        indice_por_id, matriz_distancias_km, matriz_duracoes_min,
    )
    figura_convergencia = plotar_convergencia(historico_fitness)
    # Usa o Plotly via CDN (em vez de embutir a biblioteca inteira) para manter os arquivos HTML leves
    figura_mapa.write_html(config.OUTPUT_DIR / "mapa_rotas_otimizadas.html", include_plotlyjs="cdn")
    (config.OUTPUT_DIR / "mapa_rotas_openstreetmap.html").write_text(html_mapa_openstreetmap, encoding="utf-8")
    figura_convergencia.write_html(config.OUTPUT_DIR / "convergencia_algoritmo_genetico.html", include_plotlyjs="cdn")

    # 6. Instrucoes de entrega e relatorio operacional (LLM opcional)
    cliente_llm = obter_cliente_llm()
    if cliente_llm is None:
        print("Nenhuma LLM configurada (OLLAMA_MODEL/OPENAI_API_KEY): usando gerador de texto baseado em template.")

    linhas_instrucoes = []
    for numero_rota, rota in enumerate(melhor_solucao.routes, start=1):
        if not rota.hospital_ids:
            continue
        linhas_instrucoes.append(gerar_instrucoes_motorista(numero_rota, rota, hospitais_por_id, cliente_llm))
        linhas_instrucoes.append("\n---\n")

    relatorio = gerar_relatorio_operacional(melhor_solucao, solucao_baseline, hospitais_por_id, cliente_llm)

    (config.OUTPUT_DIR / "instrucoes_motoristas.md").write_text("\n".join(linhas_instrucoes), encoding="utf-8")
    (config.OUTPUT_DIR / "relatorio_operacional.md").write_text(relatorio, encoding="utf-8")

    print(f"Arquivos gerados em: {config.OUTPUT_DIR}")

    return melhor_solucao, solucao_baseline


def main(executar_tsp_base: bool = config.EXECUTAR_TSP_BASE) -> None:
    """
    Executa o pipeline do VRP hospitalar e, opcionalmente, o TSP base antes dele.

    Parametros:
    - executar_tsp_base: se True, roda antes o TSP classico (Pygame,
      interativo) e inclui sua distancia no resumo comparativo. Por padrao
      (config.EXECUTAR_TSP_BASE = False), somente o VRP e executado.
    """
    distancia_tsp = None

    if executar_tsp_base:
        print("=" * 70)
        print("ETAPA 1/2 - TSP BASE (algoritmo genetico classico, sem restricoes de frota)")
        print("Feche a janela do Pygame (ou pressione Q) para avancar para o VRP.")
        print("=" * 70)
        melhor_rota_tsp = executar_tsp_hospitais()
        if melhor_rota_tsp:
            df_matriz = carregar_matriz_distancias()
            df_hospitais_base = construir_lista_hospitais_base(df_matriz)
            hospital_ids = df_hospitais_base["id"].tolist()
            matriz_distancias_km = construir_matriz_custos(df_matriz, hospital_ids, metrica="distance_km")
            indice_por_id = {hospital_id: posicao for posicao, hospital_id in enumerate(hospital_ids)}
            distancia_tsp = calcular_fitness_hospitais(melhor_rota_tsp, indice_por_id, matriz_distancias_km)
        print()

    print("=" * 70)
    print("VRP HOSPITALAR (multiplos veiculos, restricoes e relatorios via LLM)")
    print("=" * 70)
    melhor_solucao_vrp, solucao_baseline_vrp = executar_pipeline_vrp()

    print()
    print("=" * 70)
    print("RESUMO COMPARATIVO DOS DOIS ALGORITMOS" if executar_tsp_base else "RESUMO DA SOLUCAO VRP")
    print("=" * 70)
    if distancia_tsp is not None:
        print(f"TSP base (1 veiculo, sem restricoes):        {distancia_tsp:.1f} km")
    print(f"VRP otimizado ({melhor_solucao_vrp.vehicles_used} veiculos, com restricoes): {melhor_solucao_vrp.total_distance_km:.1f} km")
    print(f"VRP baseline ({solucao_baseline_vrp.vehicles_used} veiculos, ordem de cadastro):  {solucao_baseline_vrp.total_distance_km:.1f} km")
    print(f"Relatorios, instrucoes e visualizacoes disponiveis em: {config.OUTPUT_DIR}")


if __name__ == "__main__":
    main()
