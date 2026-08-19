# -*- coding: utf-8 -*-
"""
Configuracoes centrais do projeto de otimizacao de rotas medicas (TSP/VRP).

Todas as constantes usadas pelos demais modulos do pacote `tsp` ficam
concentradas aqui para facilitar rastreabilidade e ajuste de parametros.
"""
from __future__ import annotations

from pathlib import Path

# Caminhos base do projeto (contexto restrito a pasta tsp/, conforme escopo do projeto)
BASE_DIR = Path(__file__).resolve().parent
BASES_DIR = BASE_DIR / "bases"
OUTPUT_DIR = BASE_DIR / "output"

MATRIZ_DISTANCIAS_PATH = BASES_DIR / "matriz_distacias_hospitais.csv"
VEICULOS_PATH = BASES_DIR / "veiculos.csv"

# Semente fixa para reprodutibilidade de todo o pipeline (sorteios de demanda,
# prioridade, frota e populacao inicial do algoritmo genetico).
RANDOM_SEED = 42

# Id do hospital utilizado como Centro de Distribuicao (CD) / deposito.
# Assumimos o primeiro hospital da matriz como CD, pois a base nao possui
# um deposito explicito separado dos hospitais.
DEPOT_HOSPITAL_ID = 1

# ---------------------------------------------------------------------------
# Parametros da frota (veiculos.csv traz apenas dados de consumo do PBE e nao
# possui capacidade de carga nem tanque de combustivel). Os valores abaixo sao
# premissas documentadas, necessarias para tornar o problema um VRP realista.
# ---------------------------------------------------------------------------
TAMANHO_FROTA = 5
TANQUE_LITROS_PADRAO = 50.0

# Capacidade de carga (kg) estimada por segmento do veiculo, com base em
# palavras-chave do modelo. Valor default usado quando nenhuma palavra-chave
# for encontrada.
CAPACIDADE_KG_POR_SEGMENTO = {
    "HR-V": 450.0,
    "CITY": 400.0,
    "CRONOS": 400.0,
    "ONIX": 380.0,
    "HB20": 360.0,
    "208": 350.0,
    "ARGO": 340.0,
    "MOBI": 300.0,
}
CAPACIDADE_KG_PADRAO = 350.0

# ---------------------------------------------------------------------------
# Parametros de demanda/prioridade sinteticos dos hospitais (a base tsp/bases
# nao possui volume de entrega nem criticidade por hospital).
# ---------------------------------------------------------------------------
DEMANDA_KG_MIN = 10.0
DEMANDA_KG_MAX = 120.0
PROBABILIDADE_ENTREGA_CRITICA = 0.3

# ---------------------------------------------------------------------------
# Controle de execucao do tsp/run.py: por padrao, roda somente o VRP
# hospitalar (fim-a-fim, sem interacao do usuario). O TSP base (Pygame,
# interativo) fica desligado por padrao e pode ser habilitado via parametro.
# ---------------------------------------------------------------------------
EXECUTAR_TSP_BASE = False

# ---------------------------------------------------------------------------
# Parametros do algoritmo genetico
# ---------------------------------------------------------------------------
POPULATION_SIZE = 120
N_GENERATIONS = 200
MUTATION_PROBABILITY = 0.35
ELITE_SIZE = 2

# Pesos da funcao de fitness do VRP (quanto maior, mais penalizado)
PESO_DISTANCIA = 1.0
PESO_ATRASO_PRIORIDADE = 25.0
PESO_ENTREGA_NAO_ATENDIDA = 5000.0
