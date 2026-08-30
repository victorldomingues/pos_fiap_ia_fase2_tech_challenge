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

import html
import json

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
    indice_por_id: dict[int, int],
    matriz_distancias_km: np.ndarray,
    matriz_duracoes_min: np.ndarray,
) -> str:
    """
    Gera um HTML Leaflet com tiles OpenStreetMap e toggle de rotas.

    O Leaflet e usado aqui porque renderiza tooltips permanentes de vertices e
    arestas de forma mais confiavel que o texto sobre Scattermapbox/Plotly.
    """
    rotas_payload = []

    # Prepara dados serializaveis para cada camada de rota no mapa Leaflet.
    for numero_rota, rota in enumerate(solucao.routes):
        if not rota.hospital_ids:
            continue

        sequencia_ids = [deposito_id, *rota.hospital_ids, deposito_id]
        cor = CORES_ROTAS[numero_rota % len(CORES_ROTAS)]
        pontos = []
        for indice_trecho, (origem_id, destino_id) in enumerate(zip(sequencia_ids, sequencia_ids[1:]), start=1):
            if indice_trecho == 1:
                hospital_origem = hospitais_por_id[origem_id]
                lat_origem, lon_origem = coordenadas_geo_por_id[origem_id]
                pontos.append(
                    {
                        "lat": lat_origem,
                        "lon": lon_origem,
                        "label": "CD",
                        "popup": f"{hospital_origem.name}<br>Bairro: {hospital_origem.district}<br>Prioridade: {hospital_origem.priority.name}",
                    }
                )

            hospital_destino = hospitais_por_id[destino_id]
            lat_destino, lon_destino = coordenadas_geo_por_id[destino_id]
            label_destino = "CD" if destino_id == deposito_id else f"{indice_trecho}. {hospital_destino.name[:28]}"
            pontos.append(
                {
                    "lat": lat_destino,
                    "lon": lon_destino,
                    "label": label_destino,
                    "popup": f"{hospital_destino.name}<br>Bairro: {hospital_destino.district}<br>Prioridade: {hospital_destino.priority.name}",
                }
            )

        arestas = []
        for indice_trecho, (origem_id, destino_id) in enumerate(zip(sequencia_ids, sequencia_ids[1:]), start=1):
            distancia_km = matriz_distancias_km[indice_por_id[origem_id], indice_por_id[destino_id]]
            duracao_min = matriz_duracoes_min[indice_por_id[origem_id], indice_por_id[destino_id]]
            lat_origem, lon_origem = coordenadas_geo_por_id[origem_id]
            lat_destino, lon_destino = coordenadas_geo_por_id[destino_id]
            arestas.append(
                {
                    "lat": (lat_origem + lat_destino) / 2,
                    "lon": (lon_origem + lon_destino) / 2,
                    "label": f"{indice_trecho}: {distancia_km:.1f} km | {duracao_min:.0f} min",
                    "popup": (
                        f"Trecho {indice_trecho}: {hospitais_por_id[origem_id].name} -> {hospitais_por_id[destino_id].name}<br>"
                        f"Distancia: {distancia_km:.1f} km<br>Duracao: {duracao_min:.0f} min"
                    ),
                }
            )

        rotas_payload.append(
            {
                "name": f"Rota {numero_rota + 1} - {rota.vehicle.brand} {rota.vehicle.model}",
                "color": cor,
                "points": pontos,
                "edges": arestas,
            }
        )

    latitude_deposito, longitude_deposito = coordenadas_geo_por_id[deposito_id]
    latitudes_todas = [coordenada[0] for coordenada in coordenadas_geo_por_id.values()]
    longitudes_todas = [coordenada[1] for coordenada in coordenadas_geo_por_id.values()]
    mapa_payload = {
        "center": {"lat": float(np.mean(latitudes_todas)), "lon": float(np.mean(longitudes_todas))},
        "deposit": {
            "lat": latitude_deposito,
            "lon": longitude_deposito,
            "label": "CD",
            "popup": hospitais_por_id[deposito_id].name,
        },
        "routes": rotas_payload,
        "unassigned": [
            {
                "lat": coordenadas_geo_por_id[hospital_id][0],
                "lon": coordenadas_geo_por_id[hospital_id][1],
                "label": hospitais_por_id[hospital_id].name,
            }
            for hospital_id in solucao.unassigned_hospital_ids
        ],
    }
    dados_json = json.dumps(mapa_payload, ensure_ascii=False)
    titulo = html.escape("Rotas otimizadas no OpenStreetMap")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{titulo}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        html, body, #mapa {{ height: 100%; width: 100%; margin: 0; }}
        .painel-controles {{
            background: white;
            border: 1px solid #999;
            border-radius: 4px;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.35);
            font: 14px Arial, sans-serif;
            padding: 8px;
        }}
        .painel-controles button {{
            display: block;
            margin: 4px 0;
            min-width: 120px;
            padding: 6px 8px;
            font-weight: 700;
            cursor: pointer;
        }}
        .leaflet-control-layers, .leaflet-control-layers label {{
            font: 14px Arial, sans-serif;
            font-weight: 700;
        }}
        .rotulo-no, .rotulo-aresta {{
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(0, 0, 0, 0.25);
            border-radius: 3px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
            color: #111;
            font: 700 13px Arial, sans-serif;
            padding: 2px 4px;
            white-space: nowrap;
        }}
        .rotulo-aresta {{ font-size: 12px; }}
    </style>
</head>
<body>
    <div id="mapa"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const dadosMapa = {dados_json};
        const mapa = L.map('mapa', {{ zoomControl: true }}).setView([dadosMapa.center.lat, dadosMapa.center.lon], 10);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(mapa);

        const gruposRotas = [];
        const overlays = {{}};

        for (const rota of dadosMapa.routes) {{
            const grupo = L.layerGroup();
            const coordenadas = rota.points.map((ponto) => [ponto.lat, ponto.lon]);
            L.polyline(coordenadas, {{ color: rota.color, weight: 4, opacity: 0.85 }}).addTo(grupo);

            for (const ponto of rota.points) {{
                const marcadorPonto = L.circleMarker([ponto.lat, ponto.lon], {{
                    radius: ponto.label === 'CD' ? 7 : 5,
                    color: rota.color,
                    fillColor: ponto.label === 'CD' ? '#111111' : rota.color,
                    fillOpacity: 0.9,
                    weight: 2,
                }});
                marcadorPonto
                    .bindPopup(ponto.popup, {{ closeButton: false, autoPan: false }})
                    .bindTooltip(ponto.label, {{ permanent: true, direction: 'top', className: 'rotulo-no' }})
                    .on('mouseover', function() {{ this.openPopup(); }})
                    .on('mouseout', function() {{ this.closePopup(); }})
                    .addTo(grupo);
            }}

            for (const aresta of rota.edges) {{
                const marcadorAresta = L.marker([aresta.lat, aresta.lon], {{
                    icon: L.divIcon({{ className: 'rotulo-aresta', html: aresta.label }})
                }});
                marcadorAresta
                    .bindPopup(aresta.popup, {{ closeButton: false, autoPan: false }})
                    .on('mouseover', function() {{ this.openPopup(); }})
                    .on('mouseout', function() {{ this.closePopup(); }})
                    .addTo(grupo);
            }}

            grupo.addTo(mapa);
            gruposRotas.push(grupo);
            overlays[rota.name] = grupo;
        }}

        const deposito = L.circleMarker([dadosMapa.deposit.lat, dadosMapa.deposit.lon], {{
            radius: 9,
            color: '#111111',
            fillColor: '#111111',
            fillOpacity: 1,
            weight: 2,
        }})
            .bindPopup(dadosMapa.deposit.popup, {{ closeButton: false, autoPan: false }})
            .bindTooltip(dadosMapa.deposit.label, {{ permanent: true, direction: 'top', className: 'rotulo-no' }})
            .on('mouseover', function() {{ this.openPopup(); }})
            .on('mouseout', function() {{ this.closePopup(); }})
            .addTo(mapa);

        if (dadosMapa.unassigned.length > 0) {{
            const naoAtendidos = L.layerGroup();
            for (const ponto of dadosMapa.unassigned) {{
                const marcadorNaoAtendido = L.circleMarker([ponto.lat, ponto.lon], {{ radius: 7, color: '#d62728', fillColor: '#d62728', fillOpacity: 1 }});
                marcadorNaoAtendido
                    .bindPopup(ponto.label, {{ closeButton: false, autoPan: false }})
                    .bindTooltip(ponto.label, {{ permanent: true, direction: 'top', className: 'rotulo-no' }})
                    .on('mouseover', function() {{ this.openPopup(); }})
                    .on('mouseout', function() {{ this.closePopup(); }})
                    .addTo(naoAtendidos);
            }}
            naoAtendidos.addTo(mapa);
            overlays['Nao atendidos'] = naoAtendidos;
        }}

        L.control.layers(null, overlays, {{ collapsed: false }}).addTo(mapa);

        const controleBotoes = L.control({{ position: 'topright' }});
        controleBotoes.onAdd = function() {{
            const div = L.DomUtil.create('div', 'painel-controles');
            div.innerHTML = `
                <button type="button" data-action="mostrar">Mostrar rotas</button>
                <button type="button" data-action="ocultar">Ocultar rotas</button>
                <button type="button" data-zoom="9">Zoom geral</button>
                <button type="button" data-zoom="10">Zoom cidade</button>
                <button type="button" data-zoom="12">Zoom detalhe</button>
            `;
            L.DomEvent.disableClickPropagation(div);
            return div;
        }};
        controleBotoes.addTo(mapa);

        document.querySelector('[data-action="mostrar"]').addEventListener('click', () => {{
            for (const grupo of gruposRotas) mapa.addLayer(grupo);
        }});
        document.querySelector('[data-action="ocultar"]').addEventListener('click', () => {{
            for (const grupo of gruposRotas) mapa.removeLayer(grupo);
            if (!mapa.hasLayer(deposito)) mapa.addLayer(deposito);
        }});
        for (const botao of document.querySelectorAll('[data-zoom]')) {{
            botao.addEventListener('click', () => mapa.setZoom(Number(botao.dataset.zoom)));
        }}
    </script>
</body>
</html>
"""


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
