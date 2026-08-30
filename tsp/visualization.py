# -*- coding: utf-8 -*-
"""
Visualizacoes interativas (Plotly) das rotas otimizadas e da convergencia
do algoritmo genetico.

Como a base tsp/bases nao possui latitude/longitude, o "mapa" de rotas usa
as coordenadas 2D estimadas por MDS (tsp/distance_matrix.py), preservando as
distancias relativas reais entre hospitais. Isso mantem a visualizacao
totalmente dentro do escopo de dados da pasta tsp.
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from .models import Hospital, VrpSolution

CORES_ROTAS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


def plotar_mapa_rotas(
    solucao: VrpSolution,
    coordenadas: np.ndarray,
    hospital_ids: list[int],
    hospitais_por_id: dict[int, Hospital],
    deposito_id: int,
) -> go.Figure:
    """
    Gera um mapa (Plotly) com as rotas otimizadas, uma cor por veiculo.

    Parametros:
    - solucao: solucao VRP (rotas por veiculo) a ser desenhada.
    - coordenadas: array (n x 2) com as coordenadas 2D de cada hospital (MDS).
    - hospital_ids: lista de ids na mesma ordem das coordenadas.
    - hospitais_por_id: dicionario id -> Hospital, para rotulos e prioridade.
    - deposito_id: id do hospital usado como Centro de Distribuicao (CD).

    Retorno:
    Figura Plotly pronta para exibicao (fig.show()) ou exportacao para HTML/PNG.
    """
    indice_por_id = {hospital_id: posicao for posicao, hospital_id in enumerate(hospital_ids)}
    figura = go.Figure()

    # Desenha uma linha (rota) por veiculo, partindo e retornando ao deposito
    for numero_rota, rota in enumerate(solucao.routes):
        if not rota.hospital_ids:
            continue

        sequencia_ids = [deposito_id, *rota.hospital_ids, deposito_id]
        xs = [coordenadas[indice_por_id[hospital_id], 0] for hospital_id in sequencia_ids]
        ys = [coordenadas[indice_por_id[hospital_id], 1] for hospital_id in sequencia_ids]
        cor = CORES_ROTAS[numero_rota % len(CORES_ROTAS)]

        figura.add_trace(
            go.Scatter(
                x=xs, y=ys, mode="lines+markers",
                line=dict(color=cor, width=2),
                marker=dict(size=6, color=cor),
                name=f"Rota {numero_rota + 1} - {rota.vehicle.brand} {rota.vehicle.model}",
                hovertext=[
                    f"{hospitais_por_id[hid].name} ({hospitais_por_id[hid].district})"
                    for hid in sequencia_ids
                ],
                hoverinfo="text",
            )
        )

    # Destaca o deposito (Centro de Distribuicao) com um marcador proprio
    x_deposito = coordenadas[indice_por_id[deposito_id], 0]
    y_deposito = coordenadas[indice_por_id[deposito_id], 1]
    figura.add_trace(
        go.Scatter(
            x=[x_deposito], y=[y_deposito], mode="markers+text",
            marker=dict(size=16, color="black", symbol="star"),
            text=["CD"], textposition="top center",
            name="Centro de Distribuicao",
        )
    )

    # Marca hospitais nao atendidos, se houver
    if solucao.unassigned_hospital_ids:
        xs_nao_atendidos = [coordenadas[indice_por_id[hid], 0] for hid in solucao.unassigned_hospital_ids]
        ys_nao_atendidos = [coordenadas[indice_por_id[hid], 1] for hid in solucao.unassigned_hospital_ids]
        figura.add_trace(
            go.Scatter(
                x=xs_nao_atendidos, y=ys_nao_atendidos, mode="markers",
                marker=dict(size=12, color="red", symbol="x"),
                name="Nao atendidos",
            )
        )

    figura.update_layout(
        title="Rotas otimizadas de distribuicao de medicamentos e insumos",
        xaxis_title="Coordenada estimada X (MDS)",
        yaxis_title="Coordenada estimada Y (MDS)",
        legend_title="Legenda",
        template="plotly_white",
    )
    return figura


def plotar_mapa_rotas_openstreetmap(
    solucao: VrpSolution,
    coordenadas_geo_por_id: dict[int, tuple[float, float]],
    hospitais_por_id: dict[int, Hospital],
    deposito_id: int,
) -> go.Figure:
    """
    Gera um mapa geografico com tiles OpenStreetMap e toggle de rotas na legenda.

    Cada rota e uma trace independente no Plotly. Assim, clicar na legenda
    permite mostrar/ocultar uma rota especifica sem alterar a solucao calculada.
    Tambem inclui botoes para mostrar/ocultar todas as rotas e ajustar o zoom.
    """
    figura = go.Figure()

    # Desenha cada rota como uma camada independente para habilitar o toggle pela legenda.
    for numero_rota, rota in enumerate(solucao.routes):
        if not rota.hospital_ids:
            continue

        sequencia_ids = [deposito_id, *rota.hospital_ids, deposito_id]
        latitudes = [coordenadas_geo_por_id[hospital_id][0] for hospital_id in sequencia_ids]
        longitudes = [coordenadas_geo_por_id[hospital_id][1] for hospital_id in sequencia_ids]
        cor = CORES_ROTAS[numero_rota % len(CORES_ROTAS)]

        figura.add_trace(
            go.Scattermapbox(
                lat=latitudes,
                lon=longitudes,
                mode="lines+markers",
                line=dict(color=cor, width=3),
                marker=dict(size=8, color=cor),
                name=f"Rota {numero_rota + 1} - {rota.vehicle.brand} {rota.vehicle.model}",
                hovertext=[
                    (
                        f"{hospitais_por_id[hospital_id].name}<br>"
                        f"Bairro: {hospitais_por_id[hospital_id].district}<br>"
                        f"Prioridade: {hospitais_por_id[hospital_id].priority.name}"
                    )
                    for hospital_id in sequencia_ids
                ],
                hoverinfo="text",
            )
        )

    quantidade_tracos_rotas = len(figura.data)

    latitude_deposito, longitude_deposito = coordenadas_geo_por_id[deposito_id]
    figura.add_trace(
        go.Scattermapbox(
            lat=[latitude_deposito],
            lon=[longitude_deposito],
            mode="markers+text",
            marker=dict(size=16, color="black"),
            text=["CD"],
            textposition="top center",
            name="Centro de Distribuicao",
            hovertext=[hospitais_por_id[deposito_id].name],
            hoverinfo="text",
        )
    )

    if solucao.unassigned_hospital_ids:
        figura.add_trace(
            go.Scattermapbox(
                lat=[coordenadas_geo_por_id[hospital_id][0] for hospital_id in solucao.unassigned_hospital_ids],
                lon=[coordenadas_geo_por_id[hospital_id][1] for hospital_id in solucao.unassigned_hospital_ids],
                mode="markers",
                marker=dict(size=12, color="red"),
                name="Nao atendidos",
            )
        )

    latitudes_todas = [coordenada[0] for coordenada in coordenadas_geo_por_id.values()]
    longitudes_todas = [coordenada[1] for coordenada in coordenadas_geo_por_id.values()]
    visibilidade_todas = [True] * len(figura.data)
    visibilidade_sem_rotas = [False] * quantidade_tracos_rotas + [True] * (len(figura.data) - quantidade_tracos_rotas)
    figura.update_layout(
        title="Rotas otimizadas no OpenStreetMap (clique na legenda para ligar/desligar rotas)",
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=float(np.mean(latitudes_todas)), lon=float(np.mean(longitudes_todas))),
            zoom=10,
        ),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=0.01,
                y=1.08,
                xanchor="left",
                yanchor="top",
                buttons=[
                    dict(label="Mostrar rotas", method="update", args=[{"visible": visibilidade_todas}]),
                    dict(label="Ocultar rotas", method="update", args=[{"visible": visibilidade_sem_rotas}]),
                ],
            ),
            dict(
                type="buttons",
                direction="right",
                x=0.01,
                y=1.01,
                xanchor="left",
                yanchor="top",
                buttons=[
                    dict(label="Zoom geral", method="relayout", args=[{"mapbox.zoom": 9}]),
                    dict(label="Zoom cidade", method="relayout", args=[{"mapbox.zoom": 10}]),
                    dict(label="Zoom detalhe", method="relayout", args=[{"mapbox.zoom": 12}]),
                ],
            ),
        ],
        legend_title="Rotas",
        margin=dict(l=0, r=0, t=90, b=0),
        dragmode="zoom",
    )
    return figura


def plotar_convergencia(historico_fitness: list[float]) -> go.Figure:
    """
    Gera o grafico de convergencia do algoritmo genetico (melhor fitness por geracao).

    Parametros:
    - historico_fitness: lista com o melhor fitness de cada geracao.

    Retorno:
    Figura Plotly com a curva de convergencia.
    """
    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=list(range(1, len(historico_fitness) + 1)),
            y=historico_fitness,
            mode="lines",
            line=dict(color="#2ca02c", width=2),
            name="Melhor fitness",
        )
    )
    figura.update_layout(
        title="Convergencia do algoritmo genetico (VRP hospitalar)",
        xaxis_title="Geracao",
        yaxis_title="Fitness (custo, quanto menor melhor)",
        template="plotly_white",
    )
    return figura
