# -*- coding: utf-8 -*-
"""
Construcao da matriz de custos (distancia/duracao) entre hospitais e de um
layout bidimensional para visualizacao das rotas em mapa.

Como a base tsp/bases nao possui latitude/longitude dos hospitais (apenas
distancias e duracoes rodoviarias entre pares), utilizamos escalonamento
multidimensional classico (MDS de Torgerson) para projetar os hospitais em
um plano 2D que preserva, o melhor possivel, as distancias reais da matriz.
Essa projecao e apenas para fins de visualizacao; o custo real das rotas
sempre usa a matriz original.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def construir_matriz_custos(
    df_matriz: pd.DataFrame,
    hospital_ids: list[int],
    metrica: str = "distance_km",
) -> np.ndarray:
    """
    Monta uma matriz de custos quadrada (numpy) alinhada a ordem de hospital_ids.

    Parametros:
    - df_matriz: DataFrame com colunas origin_id, destination_id e a metrica escolhida.
    - hospital_ids: lista ordenada de ids que define a ordem das linhas/colunas.
    - metrica: nome da coluna de custo a utilizar ("distance_km" ou "duration_minutes").

    Retorno:
    Matriz numpy (n x n) onde a celula [i, j] e o custo do hospital i ao hospital j.
    """
    indice_por_id = {hospital_id: posicao for posicao, hospital_id in enumerate(hospital_ids)}
    n = len(hospital_ids)
    matriz_custos = np.zeros((n, n), dtype=float)

    for linha in df_matriz.itertuples(index=False):
        origem = getattr(linha, "origin_id")
        destino = getattr(linha, "destination_id")
        if origem not in indice_por_id or destino not in indice_por_id:
            continue
        i = indice_por_id[origem]
        j = indice_por_id[destino]
        matriz_custos[i, j] = getattr(linha, metrica)

    return matriz_custos


def calcular_coordenadas_mds(matriz_distancias: np.ndarray) -> np.ndarray:
    """
    Projeta os hospitais em um plano 2D via MDS classico (Torgerson), a partir
    da matriz de distancias real, para permitir visualizacao das rotas em mapa.

    Parametros:
    - matriz_distancias: matriz quadrada (n x n) de distancias entre hospitais.

    Retorno:
    Array numpy (n x 2) com as coordenadas (x, y) estimadas de cada hospital.
    """
    n = matriz_distancias.shape[0]

    # Dupla centralizacao da matriz de distancias ao quadrado (algoritmo classico de Torgerson)
    distancias_ao_quadrado = matriz_distancias ** 2
    matriz_centralizadora = np.eye(n) - np.ones((n, n)) / n
    matriz_gram = -0.5 * matriz_centralizadora @ distancias_ao_quadrado @ matriz_centralizadora

    autovalores, autovetores = np.linalg.eigh(matriz_gram)

    # Ordena do maior para o menor autovalor e mantem apenas as 2 dimensoes principais
    ordem_decrescente = np.argsort(autovalores)[::-1]
    autovalores = autovalores[ordem_decrescente][:2]
    autovetores = autovetores[:, ordem_decrescente][:, :2]

    autovalores_positivos = np.clip(autovalores, a_min=0, a_max=None)
    coordenadas = autovetores * np.sqrt(autovalores_positivos)

    return coordenadas
