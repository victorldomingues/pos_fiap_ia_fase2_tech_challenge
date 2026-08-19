# -*- coding: utf-8 -*-
"""
Ponto de entrada principal do projeto: executa, em sequencia, os dois
algoritmos construidos sobre a matriz real de hospitais e apresenta os
resultados de ambos.

1. TSP BASE (tsp/tsp.py): algoritmo genetico classico do caixeiro viajante,
   uma unica rota visitando todos os hospitais, sem restricoes de frota.
   Visualizacao interativa em Pygame (feche a janela ou pressione Q para
   avancar para a etapa seguinte).
2. VRP HOSPITALAR (tsp/vrp.py + tsp/optimizer.py): multiplos veiculos, com
   capacidade de carga, autonomia e prioridade de entrega, alem de geracao
   de mapa de rotas, grafico de convergencia, instrucoes de motoristas e
   relatorio operacional (via LLM ou template).

Uso (a partir da raiz do repositorio ou de dentro da pasta tsp/):
    python tsp/run.py
    # ou, como modulo do pacote:
    python -m tsp.run
"""
from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do repositorio esteja no sys.path, permitindo importar o
# pacote `tsp` mesmo quando este arquivo e executado diretamente (python tsp/run.py)
_RAIZ_REPOSITORIO = str(Path(__file__).resolve().parent.parent)
if _RAIZ_REPOSITORIO not in sys.path:
    sys.path.insert(0, _RAIZ_REPOSITORIO)

from tsp import config
from tsp.data_loader import (
    carregar_frota,
    carregar_matriz_distancias,
    construir_lista_hospitais_base,
    gerar_demandas_hospitais,
)
from tsp.distance_matrix import calcular_coordenadas_mds, construir_matriz_custos
from tsp.llm_integration import gerar_instrucoes_motorista, gerar_relatorio_operacional, obter_cliente_llm
from tsp.optimizer import calcular_solucao_baseline, executar_algoritmo_genetico_vrp
from tsp.tsp import calcular_fitness_hospitais, executar_tsp_hospitais
from tsp.visualization import plotar_convergencia, plotar_mapa_rotas


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
    figura_convergencia = plotar_convergencia(historico_fitness)
    # Usa o Plotly via CDN (em vez de embutir a biblioteca inteira) para manter os arquivos HTML leves
    figura_mapa.write_html(config.OUTPUT_DIR / "mapa_rotas_otimizadas.html", include_plotlyjs="cdn")
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
        linhas_instrucoes.append("\n" + "-" * 60 + "\n")

    relatorio = gerar_relatorio_operacional(melhor_solucao, solucao_baseline, hospitais_por_id, cliente_llm)

    (config.OUTPUT_DIR / "instrucoes_motoristas.txt").write_text("\n".join(linhas_instrucoes), encoding="utf-8")
    (config.OUTPUT_DIR / "relatorio_operacional.txt").write_text(relatorio, encoding="utf-8")

    print(f"Arquivos gerados em: {config.OUTPUT_DIR}")

    return melhor_solucao, solucao_baseline


def main() -> None:
    """Executa as duas etapas (TSP base e VRP hospitalar) e resume os resultados de ambas."""
    print("=" * 70)
    print("ETAPA 1/2 - TSP BASE (algoritmo genetico classico, sem restricoes de frota)")
    print("Feche a janela do Pygame (ou pressione Q) para avancar para o VRP.")
    print("=" * 70)
    melhor_rota_tsp = executar_tsp_hospitais()
    distancia_tsp = None
    if melhor_rota_tsp:
        df_matriz = carregar_matriz_distancias()
        df_hospitais_base = construir_lista_hospitais_base(df_matriz)
        hospital_ids = df_hospitais_base["id"].tolist()
        matriz_distancias_km = construir_matriz_custos(df_matriz, hospital_ids, metrica="distance_km")
        indice_por_id = {hospital_id: posicao for posicao, hospital_id in enumerate(hospital_ids)}
        distancia_tsp = calcular_fitness_hospitais(melhor_rota_tsp, indice_por_id, matriz_distancias_km)

    print()
    print("=" * 70)
    print("ETAPA 2/2 - VRP HOSPITALAR (multiplos veiculos, restricoes e relatorios via LLM)")
    print("=" * 70)
    melhor_solucao_vrp, solucao_baseline_vrp = executar_pipeline_vrp()

    print()
    print("=" * 70)
    print("RESUMO COMPARATIVO DOS DOIS ALGORITMOS")
    print("=" * 70)
    if distancia_tsp is not None:
        print(f"TSP base (1 veiculo, sem restricoes):        {distancia_tsp:.1f} km")
    print(f"VRP otimizado ({melhor_solucao_vrp.vehicles_used} veiculos, com restricoes): {melhor_solucao_vrp.total_distance_km:.1f} km")
    print(f"VRP baseline ({solucao_baseline_vrp.vehicles_used} veiculos, ordem de cadastro):  {solucao_baseline_vrp.total_distance_km:.1f} km")
    print(f"Relatorios, instrucoes e visualizacoes disponiveis em: {config.OUTPUT_DIR}")


if __name__ == "__main__":
    main()
