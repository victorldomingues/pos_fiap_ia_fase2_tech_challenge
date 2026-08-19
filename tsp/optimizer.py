# -*- coding: utf-8 -*-
"""
Orquestracao do algoritmo genetico para o VRP hospitalar.

Reaproveita os operadores geneticos genericos definidos em
tsp/genetic_algorithm.py (geracao de populacao, crossover de ordem, mutacao
e selecao), aplicando-os sobre uma "rota gigante" (permutacao de ids de
hospitais) que e decodificada em rotas por veiculo via tsp/vrp.py.
"""
from __future__ import annotations

import copy

from . import config
from .genetic_algorithm import (
    generate_random_population,
    mutate,
    order_crossover,
    select_parents_by_fitness,
)
from .models import Hospital, Vehicle, VrpSolution
from .vrp import calcular_fitness_vrp, decodificar_rota_gigante


def _avaliar_populacao(
    populacao: list[list[int]],
    frota: list[Vehicle],
    hospitais_por_id: dict[int, Hospital],
    deposito_id: int,
    indice_por_id: dict[int, int],
    matriz_distancias_km,
    matriz_duracoes_min,
) -> tuple[list[VrpSolution], list[float]]:
    """Decodifica cada individuo da populacao e calcula seu fitness (custo)."""
    solucoes = [
        decodificar_rota_gigante(
            tuple(individuo), frota, hospitais_por_id, deposito_id,
            indice_por_id, matriz_distancias_km, matriz_duracoes_min,
        )
        for individuo in populacao
    ]
    fitness_valores = [calcular_fitness_vrp(solucao, hospitais_por_id) for solucao in solucoes]

    for solucao, fitness in zip(solucoes, fitness_valores):
        solucao.fitness = fitness

    return solucoes, fitness_valores


def executar_algoritmo_genetico_vrp(
    hospital_ids: list[int],
    hospitais_por_id: dict[int, Hospital],
    frota: list[Vehicle],
    deposito_id: int,
    indice_por_id: dict[int, int],
    matriz_distancias_km,
    matriz_duracoes_min,
    population_size: int = config.POPULATION_SIZE,
    n_generations: int = config.N_GENERATIONS,
    mutation_probability: float = config.MUTATION_PROBABILITY,
    elite_size: int = config.ELITE_SIZE,
    seed: int = config.RANDOM_SEED,
) -> tuple[VrpSolution, list[float]]:
    """
    Executa o algoritmo genetico completo (populacao inicial, avaliacao,
    selecao, crossover, mutacao e elitismo) para o problema de roteamento
    de veiculos hospitalar.

    Parametros:
    - hospital_ids: lista de todos os ids de hospitais (inclui o deposito).
    - hospitais_por_id: dicionario id -> Hospital com demanda e prioridade.
    - frota: lista de veiculos disponiveis para a operacao.
    - deposito_id: id do hospital usado como Centro de Distribuicao (CD).
    - indice_por_id: dicionario id -> indice na matriz de custos.
    - matriz_distancias_km / matriz_duracoes_min: matrizes de custo (numpy).
    - population_size, n_generations, mutation_probability, elite_size: hiperparametros do GA.
    - seed: semente para reprodutibilidade da populacao inicial.

    Retorno:
    Tupla (melhor_solucao, historico_fitness) com a melhor solucao encontrada
    e a evolucao do fitness (melhor de cada geracao), util para o grafico de
    convergencia.
    """
    import random
    random.seed(seed)

    # Genes da rota gigante: todos os hospitais, exceto o deposito (que e ponto fixo de partida/chegada)
    genes = [hospital_id for hospital_id in hospital_ids if hospital_id != deposito_id]
    populacao = generate_random_population(genes, population_size)

    historico_fitness: list[float] = []
    melhor_solucao_global: VrpSolution | None = None
    melhor_fitness_global = float("inf")

    for _geracao in range(n_generations):
        solucoes, fitness_valores = _avaliar_populacao(
            populacao, frota, hospitais_por_id, deposito_id,
            indice_por_id, matriz_distancias_km, matriz_duracoes_min,
        )

        # Ordena populacao, fitness e solucoes juntos, do menor (melhor) para o maior custo
        combinados = sorted(zip(fitness_valores, populacao, solucoes), key=lambda item: item[0])
        fitness_valores = [item[0] for item in combinados]
        populacao = [item[1] for item in combinados]
        solucoes = [item[2] for item in combinados]

        melhor_fitness_geracao = fitness_valores[0]
        historico_fitness.append(melhor_fitness_geracao)

        if melhor_fitness_geracao < melhor_fitness_global:
            melhor_fitness_global = melhor_fitness_geracao
            melhor_solucao_global = copy.deepcopy(solucoes[0])

        # ELITISMO: mantem os melhores individuos intactos na proxima geracao
        nova_populacao = [list(individuo) for individuo in populacao[:elite_size]]

        while len(nova_populacao) < population_size:
            pai1 = select_parents_by_fitness(populacao, fitness_valores, k=1)[0]
            pai2 = select_parents_by_fitness(populacao, fitness_valores, k=1)[0]

            filho = order_crossover(list(pai1), list(pai2))
            filho = mutate(filho, mutation_probability)

            nova_populacao.append(filho)

        populacao = nova_populacao

    assert melhor_solucao_global is not None
    return melhor_solucao_global, historico_fitness


def calcular_solucao_baseline(
    hospital_ids: list[int],
    hospitais_por_id: dict[int, Hospital],
    frota: list[Vehicle],
    deposito_id: int,
    indice_por_id: dict[int, int],
    matriz_distancias_km,
    matriz_duracoes_min,
) -> VrpSolution:
    """
    Gera uma solucao baseline (sem otimizacao) para comparar o ganho do GA.

    A baseline segue a ordem natural dos ids de hospitais (ordem de cadastro
    na base), simulando a forma tradicional de planejamento manual de rotas,
    sem considerar distancia, prioridade ou restricoes de otimizacao.
    """
    genes_em_ordem = [hospital_id for hospital_id in sorted(hospital_ids) if hospital_id != deposito_id]

    solucao_baseline = decodificar_rota_gigante(
        tuple(genes_em_ordem), frota, hospitais_por_id, deposito_id,
        indice_por_id, matriz_distancias_km, matriz_duracoes_min,
    )
    solucao_baseline.fitness = calcular_fitness_vrp(solucao_baseline, hospitais_por_id)

    return solucao_baseline
