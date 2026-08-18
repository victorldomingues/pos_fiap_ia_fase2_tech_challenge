from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

BASE_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = BASE_DIR / "bases" / "por_bairro_hospitais_publicos_sao_paulo_sp.csv"
OUTPUT_DIR = BASE_DIR / "bases" / "graficos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_hospitais() -> pd.DataFrame:
    """Carrega hospitais e mantém somente coordenadas com geocoding confirmado."""
    df = pd.read_csv(CSV_PATH, sep=';')
    df = df.copy()
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df = df.dropna(subset=['latitude', 'longitude']).reset_index(drop=True)
    df = df[df['geocode_status'].fillna('not_found').eq('ok')].reset_index(drop=True)
    return df


def build_graph_edges(n: int, max_neighbors: int = 3) -> list[tuple[int, int]]:
    """Cria arestas circulares para uma representacao abstrata do conjunto."""
    edges: list[tuple[int, int]] = []
    if n <= 1:
        return edges

    for i in range(n):
        for offset in range(1, max_neighbors + 1):
            j = (i + offset) % n
            if i != j and (j, i) not in edges:
                edges.append((i, j))

    return edges


def render_abstract_graph(df: pd.DataFrame) -> None:
    """Gera o grafo cartesiano com ligacoes aos vizinhos geograficos mais proximos."""
    if df.empty:
        raise ValueError('DataFrame vazio para renderizacao do grafo.')

    x = df['longitude'].astype(float).to_numpy()
    y = df['latitude'].astype(float).to_numpy()

    k = min(3, max(1, len(df) - 1))
    edge_x: list[float] = []
    edge_y: list[float] = []
    seen_edges: set[tuple[int, int]] = set()

    for i in range(len(df)):
        distances = []
        for j in range(len(df)):
            if i == j:
                continue
            dist = (x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2
            distances.append((dist, j))

        for _, j in sorted(distances)[:k]:
            a, b = sorted((i, j))
            if a == b or (a, b) in seen_edges:
                continue
            seen_edges.add((a, b))
            edge_x.extend([x[a], x[b], None])
            edge_y.extend([y[a], y[b], None])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode='lines',
            line=dict(color="#C1C0C0", width=1),
            hoverinfo='skip',
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode='markers+text',
            marker=dict(size=8, color='#333333', line=dict(color='white', width=1)),
            text=df['hospital'],
            textposition='top center',
            textfont=dict(size=9, color='#000000'),
            hovertemplate='<b>%{customdata[0]}</b><br>X: %{x:.5f}<br>Y: %{y:.5f}<extra></extra>',
            customdata=df[['hospital']].to_numpy(),
            showlegend=False,
        )
    )

    x_min, x_max = float(x.min()), float(x.max())
    y_min, y_max = float(y.min()), float(y.max())
    x_pad = (x_max - x_min) * 0.08 if x_max != x_min else 0.01
    y_pad = (y_max - y_min) * 0.08 if y_max != y_min else 0.01

    fig.update_layout(
        title='Distribuição dos hospitais em plano cartesiano (X = longitude, Y = latitude)',
        title_x=0.5,
        xaxis_title='Longitude (X)',
        yaxis_title='Latitude (Y)',
        xaxis=dict(showgrid=True, zeroline=False, range=[x_min - x_pad, x_max + x_pad]),
        yaxis=dict(showgrid=True, zeroline=False, range=[y_min - y_pad, y_max + y_pad]),
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(l=50, r=20, t=60, b=50),
        width=1200,
        height=900,
    )

    html_path = OUTPUT_DIR / 'grafo_hospitais_publicos_sao_paulo.html'
    png_path = OUTPUT_DIR / 'grafo_hospitais_publicos_sao_paulo.png'
    fig.write_html(html_path, include_plotlyjs='cdn')
    try:
        fig.write_image(png_path, width=1200, height=900, scale=2)
        print(f'  PNG grafo: {png_path}')
    except Exception as exc:
        print(f'  Aviso: PNG do grafo não foi gerado neste ambiente ({exc.__class__.__name__}: {exc}).')
    print(f'  HTML grafo: {html_path}')


def render_map(df: pd.DataFrame) -> None:
    """Gera um mapa OSM com os hospitais e uma sequencia visual de ligacoes."""
    if df.empty:
        raise ValueError('DataFrame vazio para renderizacao do mapa.')

    center_lat = float(df['latitude'].mean()) 
    center_lon = float(df['longitude'].mean())

    edge_lat: list[float] = []
    edge_lon: list[float] = []
    for i in range(len(df) - 1):
        edge_lat.extend([float(df.iloc[i]['latitude']), float(df.iloc[i + 1]['latitude']), None])
        edge_lon.extend([float(df.iloc[i]['longitude']), float(df.iloc[i + 1]['longitude']), None])

    fig = go.Figure()
    fig.add_trace(
        go.Scattermap(
            lat=edge_lat,
            lon=edge_lon,
            mode='lines',
            line=dict(color='#C0392B', width=1),
            hoverinfo='skip',
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scattermap(
            lat=df['latitude'].tolist(),
            lon=df['longitude'].tolist(),
            mode='markers+text',
            marker=dict(size=8, color="#333333"),
            text=df['hospital'].tolist(),
            textposition='top center',
            textfont=dict(size=8, color='#000000'),
            customdata=df[['latitude', 'longitude']].to_numpy(),
            hovertemplate='<b>%{customdata[0]}</b><br>Lat: %{customdata[1]:.5f}<br>Lon: %{customdata[2]:.5f}<extra></extra>',
            showlegend=False,
        )
    )

    fig.update_layout(
        title='Mapa dos hospitais públicos de São Paulo',
        title_x=0.5,
        margin=dict(l=0, r=0, t=50, b=0),
        map=dict(
            style='open-street-map',
            center=dict(lat=center_lat - 0.06 , lon=center_lon),
            zoom=10.4,
        ),
        width=1400,
        height=900,
    )

    html_path = OUTPUT_DIR / 'mapa_hospitais_publicos_sao_paulo.html'
    png_path = OUTPUT_DIR / 'mapa_hospitais_publicos_sao_paulo.png'
    fig.write_html(html_path, include_plotlyjs='cdn')
    try:
        fig.write_image(png_path, width=1400, height=900, scale=2)
        print(f'  PNG mapa: {png_path}')
    except Exception as exc:
        print(f'  Aviso: PNG do mapa não foi gerado neste ambiente ({exc.__class__.__name__}: {exc}).')
    print(f'  HTML mapa: {html_path}')


def main() -> None:
    """Executa as renderizacoes do grafo abstrato e do mapa."""
    df = load_hospitais()
    if df.empty:
        raise ValueError('Nenhum hospital com coordenadas validas foi encontrado.')

    render_abstract_graph(df)
    render_map(df)

    print(f'Arquivo carregado: {len(df)} hospitais com coordenadas validas.')
    print(f'Arquivos criados em: {OUTPUT_DIR}')
    for name in [
        'grafo_hospitais_publicos_sao_paulo.html',
        'mapa_hospitais_publicos_sao_paulo.html',
        'grafo_hospitais_publicos_sao_paulo.png',
        'mapa_hospitais_publicos_sao_paulo.png',
    ]:
        print(f'- {OUTPUT_DIR / name}')


if __name__ == '__main__':
    main()
