# -*- coding: utf-8 -*-
"""
Aplicacao do algoritmo genetico BASE de TSP (Caixeiro Viajante classico) ao
problema hospitalar: uma unica rota que visita todos os hospitais uma vez e
retorna ao ponto de partida, minimizando a distancia real percorrida (usando
tsp/bases/matriz_distacias_hospitais.csv), sem restricoes adicionais.

Este arquivo evoluiu da demo original de TSP com Pygame (cidades aleatorias):
mantem a mesma estrutura de jogo/visualizacao, mas troca as coordenadas
aleatorias pelos hospitais reais e a distancia euclidiana pela distancia
real da matriz. Nao ha frota, capacidade, autonomia nem prioridade aqui -
essas restricoes (VRP) estao em tsp/vrp.py e tsp/optimizer.py, orquestradas
junto com esta demo em tsp/run.py.

Uso:
    python tsp/tsp.py
"""
from __future__ import annotations

import itertools
import random
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import pygame

# Garante que a raiz do repositorio esteja no sys.path, permitindo importar o
# pacote `tsp` mesmo quando este arquivo e executado diretamente (python tsp/tsp.py)
_RAIZ_REPOSITORIO = str(Path(__file__).resolve().parent.parent)
if _RAIZ_REPOSITORIO not in sys.path:
    sys.path.insert(0, _RAIZ_REPOSITORIO)

from tsp.data_loader import carregar_matriz_distancias, construir_lista_hospitais_base
from tsp.distance_matrix import calcular_coordenadas_mds, construir_matriz_custos
from tsp.draw_functions import draw_cities, draw_paths, draw_plot
from tsp.genetic_algorithm import generate_random_population, mutate, order_crossover, sort_population

# Define constant values (pygame)
WIDTH, HEIGHT = 1000, 600
NODE_RADIUS = 8
FPS = 30
PLOT_X_OFFSET = 450

# GA
POPULATION_SIZE = 100
MUTATION_PROBABILITY = 0.5

# Define colors
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
CINZA = (128, 128, 128)


def _escalar_coordenadas_para_tela(coordenadas_mds: np.ndarray) -> np.ndarray:
    """
    Converte as coordenadas 2D estimadas por MDS (tsp/distance_matrix.py) em
    coordenadas de pixel dentro da area disponivel da janela Pygame (a area
    a esquerda de PLOT_X_OFFSET fica reservada para o grafico de convergencia).
    """
    minimo = coordenadas_mds.min(axis=0)
    maximo = coordenadas_mds.max(axis=0)
    amplitude = np.where(maximo - minimo == 0, 1, maximo - minimo)

    area_util_x = WIDTH - PLOT_X_OFFSET - 2 * NODE_RADIUS
    area_util_y = HEIGHT - 2 * NODE_RADIUS

    coordenadas_normalizadas = (coordenadas_mds - minimo) / amplitude
    pixels_x = coordenadas_normalizadas[:, 0] * area_util_x + PLOT_X_OFFSET + NODE_RADIUS
    pixels_y = coordenadas_normalizadas[:, 1] * area_util_y + NODE_RADIUS
    return np.column_stack([pixels_x, pixels_y])


def calcular_fitness_hospitais(rota: Sequence[int], indice_por_id: dict[int, int], matriz_distancias_km: np.ndarray) -> float:
    """
    Calcula o fitness (distancia total, em km) de uma rota fechada de TSP
    puro, usando a matriz REAL de distancias entre hospitais (em vez da
    distancia euclidiana de pixels do exemplo original).
    """
    distancia_total = 0.0
    n = len(rota)
    for posicao in range(n):
        origem = rota[posicao]
        destino = rota[(posicao + 1) % n]
        distancia_total += matriz_distancias_km[indice_por_id[origem], indice_por_id[destino]]
    return distancia_total


def executar_tsp_hospitais(n_generations: int | None = None) -> list[int]:
    """
    Executa o algoritmo genetico base de TSP sobre os hospitais reais, com
    visualizacao interativa em Pygame (janela de rotas + grafico de
    convergencia), ate o usuario fechar a janela (ou pressionar Q).

    Parametros:
    - n_generations: numero maximo de geracoes. Se None (padrao, igual ao
      comportamento do exemplo original), roda indefinidamente ate o usuario
      encerrar a janela.

    Retorno:
    A melhor rota (lista de ids de hospitais) encontrada ate o encerramento.
    """
    # 1. Carrega os hospitais e a matriz real de distancias (tsp/bases)
    df_matriz = carregar_matriz_distancias()
    df_hospitais_base = construir_lista_hospitais_base(df_matriz)
    hospital_ids = df_hospitais_base["id"].tolist()

    matriz_distancias_km = construir_matriz_custos(df_matriz, hospital_ids, metrica="distance_km")
    indice_por_id = {hospital_id: posicao for posicao, hospital_id in enumerate(hospital_ids)}

    # 2. Projeta os hospitais em 2D (MDS) e escala para pixels da janela Pygame
    coordenadas_mds = calcular_coordenadas_mds(matriz_distancias_km)
    coordenadas_tela = _escalar_coordenadas_para_tela(coordenadas_mds)
    posicao_pixel_por_id = {
        hospital_id: (int(coordenadas_tela[indice, 0]), int(coordenadas_tela[indice, 1]))
        for hospital_id, indice in indice_por_id.items()
    }

    # Initialize Pygame
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("TSP Hospitalar - Algoritmo Genetico Base (Caixeiro Viajante)")
    clock = pygame.time.Clock()
    generation_counter = itertools.count(start=1)  # Start the counter at 1

    # Create Initial Population
    population = generate_random_population(hospital_ids, POPULATION_SIZE)
    best_fitness_values: list[float] = []
    melhor_rota_global = list(population[0])

    # Main game loop
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False

        generation = next(generation_counter)

        screen.fill(WHITE)

        population_fitness = [calcular_fitness_hospitais(individual, indice_por_id, matriz_distancias_km) for individual in population]

        population, population_fitness = sort_population(population, population_fitness)

        best_fitness = population_fitness[0]
        best_solution = population[0]
        melhor_rota_global = list(best_solution)

        best_fitness_values.append(best_fitness)

        draw_plot(screen, list(range(len(best_fitness_values))),
                  best_fitness_values, y_label="Fitness - Distancia (km)")

        draw_cities(screen, list(posicao_pixel_por_id.values()), RED, NODE_RADIUS)
        draw_paths(screen, [posicao_pixel_por_id[hid] for hid in best_solution], BLUE, width=3)
        draw_paths(screen, [posicao_pixel_por_id[hid] for hid in population[1]], rgb_color=CINZA, width=1)

        print(f"Geracao {generation}: melhor distancia = {round(best_fitness, 2)} km")

        new_population = [list(population[0])]  # Keep the best individual: ELITISM

        while len(new_population) < POPULATION_SIZE:

            # selection: solucao baseada na probabilidade pelo inverso do fitness
            probability = 1 / np.array(population_fitness)
            parent1, parent2 = random.choices(population, weights=probability, k=2)

            child1 = order_crossover(list(parent1), list(parent2))
            child1 = mutate(child1, MUTATION_PROBABILITY)

            new_population.append(child1)

        population = new_population

        pygame.display.flip()
        clock.tick(FPS)

        if n_generations is not None and generation >= n_generations:
            running = False

    pygame.quit()
    return melhor_rota_global


if __name__ == "__main__":
    executar_tsp_hospitais()

