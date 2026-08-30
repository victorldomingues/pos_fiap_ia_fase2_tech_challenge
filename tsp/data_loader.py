# -*- coding: utf-8 -*-
"""
Carregamento e normalizacao dos dados de entrada do projeto (hospitais,
matriz de distancias/duracoes e frota de veiculos), a partir da pasta
`tsp/bases`.

Como as bases fornecidas nao contem volume de demanda, prioridade de entrega,
capacidade de carga nem autonomia dos veiculos, este modulo tambem gera esses
atributos de forma deterministica (seed fixa) para viabilizar um cenario de
VRP realista. Cada premissa assumida esta documentada na funcao correspondente.
"""
from __future__ import annotations

import random

import pandas as pd

from . import config
from .models import DeliveryPriority, Hospital, Vehicle

COLUNAS_OBRIGATORIAS_MATRIZ = {
    "origin_id",
    "origin_hospital",
    "origin_bairro",
    "destination_id",
    "destination_hospital",
    "destination_bairro",
    "distance_km",
    "duration_minutes",
    "status",
}

COLUNAS_OBRIGATORIAS_COORDENADAS = {
    "origin_id",
    "origin_latitude",
    "origin_longitude",
}


def carregar_matriz_distancias(caminho=config.MATRIZ_DISTANCIAS_PATH) -> pd.DataFrame:
    """
    Carrega o CSV de distancias/duracoes entre hospitais e valida sua integridade.

    Parametros:
    - caminho: caminho para o arquivo matriz_distacias_hospitais.csv.

    Retorno:
    DataFrame somente com pares de status "ok", garantindo dados confiaveis
    para o calculo de custos das rotas.
    """
    df = pd.read_csv(caminho, sep=";")

    colunas_faltantes = COLUNAS_OBRIGATORIAS_MATRIZ - set(df.columns)
    if colunas_faltantes:
        raise ValueError(f"Colunas obrigatorias ausentes na matriz de distancias: {colunas_faltantes}")

    # Mantem apenas os pares com coleta de rota bem sucedida (status == "ok")
    df_valido = df[df["status"] == "ok"].copy()
    if df_valido.empty:
        raise ValueError("Nenhum par origem-destino com status 'ok' foi encontrado na matriz.")

    return df_valido


def construir_lista_hospitais_base(df_matriz: pd.DataFrame) -> pd.DataFrame:
    """
    Extrai a lista unica de hospitais (id, nome, bairro) a partir da matriz.

    Retorno:
    DataFrame ordenado por id, com uma linha por hospital.
    """
    hospitais = (
        df_matriz.drop_duplicates("origin_id")[["origin_id", "origin_hospital", "origin_bairro"]]
        .rename(columns={"origin_id": "id", "origin_hospital": "name", "origin_bairro": "district"})
        .sort_values("id")
        .reset_index(drop=True)
    )
    return hospitais


def carregar_coordenadas_hospitais(
    df_matriz: pd.DataFrame,
    hospital_ids: list[int],
) -> dict[int, tuple[float, float]]:
    """
    Extrai latitude/longitude reais dos hospitais a partir da matriz reduzida.

    Observacao: essas coordenadas devem estar em tsp/bases/matriz_distacias_hospitais.csv
    e sao usadas apenas para visualizacao no mapa OpenStreetMap. O custo das
    rotas continua sendo calculado pela matriz real de distancias e duracoes.
    """
    colunas_faltantes = COLUNAS_OBRIGATORIAS_COORDENADAS - set(df_matriz.columns)
    if colunas_faltantes:
        raise ValueError(
            "Colunas de latitude/longitude ausentes na matriz tsp/bases/matriz_distacias_hospitais.csv: "
            f"{colunas_faltantes}. Gere a matriz pelo caso de uso 6 atualizado e copie o CSV para tsp/bases/."
        )

    ids_necessarios = set(hospital_ids)
    df_valido = df_matriz[df_matriz["origin_id"].isin(ids_necessarios)].copy()
    coordenadas_por_id = {
        int(linha.origin_id): (float(linha.origin_latitude), float(linha.origin_longitude))
        for linha in df_valido.itertuples(index=False)
    }

    ids_faltantes = sorted(ids_necessarios - set(coordenadas_por_id))
    if ids_faltantes:
        raise ValueError(f"Hospitais sem coordenadas validas para mapa OpenStreetMap: {ids_faltantes}")

    return coordenadas_por_id


def gerar_demandas_hospitais(
    df_hospitais: pd.DataFrame,
    seed: int = config.RANDOM_SEED,
) -> list[Hospital]:
    """
    Gera demanda (kg) e prioridade de entrega para cada hospital.

    Observacao importante: a base tsp/bases nao possui informacoes reais de
    volume de insumos nem criticidade por hospital. Para viabilizar o
    problema de VRP, sorteamos esses valores de forma deterministica (seed
    fixa), simulando um cenario tipico de distribuicao hospitalar. Em um
    ambiente produtivo, esses dados viriam de um sistema de pedidos real.

    Parametros:
    - df_hospitais: DataFrame com colunas id, name, district.
    - seed: semente do gerador aleatorio, garante reprodutibilidade.

    Retorno:
    Lista de objetos Hospital com demanda e prioridade atribuidas.
    """
    gerador = random.Random(seed)

    hospitais: list[Hospital] = []
    for linha in df_hospitais.itertuples(index=False):
        demanda_kg = round(gerador.uniform(config.DEMANDA_KG_MIN, config.DEMANDA_KG_MAX), 1)
        eh_critico = gerador.random() < config.PROBABILIDADE_ENTREGA_CRITICA
        prioridade = DeliveryPriority.CRITICAL if eh_critico else DeliveryPriority.REGULAR

        hospitais.append(
            Hospital(
                id=int(linha.id),
                name=str(linha.name),
                district=str(linha.district),
                demand_kg=demanda_kg,
                priority=prioridade,
            )
        )

    return hospitais


def _estimar_capacidade_kg(modelo: str) -> float:
    """Estima a capacidade de carga (kg) do veiculo a partir de palavras-chave do modelo."""
    modelo_upper = modelo.upper()
    for palavra_chave, capacidade in config.CAPACIDADE_KG_POR_SEGMENTO.items():
        if palavra_chave in modelo_upper:
            return capacidade
    return config.CAPACIDADE_KG_PADRAO


def carregar_frota(
    caminho=config.VEICULOS_PATH,
    tamanho_frota: int = config.TAMANHO_FROTA,
    seed: int = config.RANDOM_SEED,
) -> list[Vehicle]:
    """
    Carrega a frota de veiculos disponiveis para as entregas.

    A base veiculos.csv traz dados reais de consumo do PBE (Programa
    Brasileiro de Etiquetagem), mas nao possui capacidade de carga nem
    tanque de combustivel. Por isso:
    - o tanque e assumido como constante (TANQUE_LITROS_PADRAO);
    - a capacidade de carga e estimada por segmento do veiculo (heuristica
      documentada em config.CAPACIDADE_KG_POR_SEGMENTO);
    - a autonomia (km) e calculada a partir do consumo urbano real
      (km/l) multiplicado pelo tanque assumido.

    Parametros:
    - caminho: caminho para o arquivo veiculos.csv.
    - tamanho_frota: quantidade de veiculos a selecionar para o cenario.
    - seed: semente do sorteio da amostra de veiculos, garante reprodutibilidade.

    Retorno:
    Lista de objetos Vehicle representando a frota disponivel no dia da operacao.
    """
    df = pd.read_csv(caminho, sep=";")

    # Remove versoes duplicadas (mesma marca/modelo/versao) para nao repetir o veiculo na frota
    df_unico = df.drop_duplicates(subset=["marca", "modelo", "versao"]).reset_index(drop=True)

    gerador = random.Random(seed)
    indices_sorteados = gerador.sample(range(len(df_unico)), k=min(tamanho_frota, len(df_unico)))

    frota: list[Vehicle] = []
    for veiculo_id, indice in enumerate(indices_sorteados, start=1):
        linha = df_unico.iloc[indice]
        frota.append(
            Vehicle(
                id=veiculo_id,
                brand=str(linha["marca"]),
                model=str(linha["modelo"]),
                version=str(linha["versao"]),
                fuel_type=str(linha["combustivel"]),
                consumption_city_km_l=float(linha["consumo_cidade"]),
                consumption_road_km_l=float(linha["consumo_estrada"]),
                tank_liters=config.TANQUE_LITROS_PADRAO,
                capacity_kg=_estimar_capacidade_kg(str(linha["modelo"])),
            )
        )

    return frota
