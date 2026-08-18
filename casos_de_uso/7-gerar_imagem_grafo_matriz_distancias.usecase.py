from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

BASE_DIR = Path(__file__).resolve().parents[1]
HOSPITALS_PATH = BASE_DIR / "bases" / "por_bairro_hospitais_publicos_sao_paulo_sp.csv"
MATRIX_PATH = BASE_DIR / "bases" / "matriz_distacias.csv"
OUTPUT_DIR = BASE_DIR / "bases" / "graficos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_EDGES_PER_ORIGIN = 3


def write_responsive_html(figure: go.Figure, html_path: Path) -> None:
    """Exporta uma figura Plotly para HTML responsivo e sem redimensionamento fixo."""
    html_figure = go.Figure(figure)
    html_figure.update_layout(autosize=True, width=None, height=None)
    html_figure.write_html(
        html_path,
        include_plotlyjs="cdn",
        config={"responsive": True, "displaylogo": False},
        default_width="100vw",
        default_height="100vh",
    )


def load_graph_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carrega coordenadas e matriz, descartando pesos incompletos ou invalidos."""
    matrix = pd.read_csv(MATRIX_PATH, sep=";", encoding="utf-8-sig")
    hospitals = pd.read_csv(HOSPITALS_PATH, sep=";", encoding="utf-8-sig")

    hospitals["id"] = hospitals["id"].astype(str).str.strip()
    hospitals["latitude"] = pd.to_numeric(hospitals["latitude"], errors="coerce")
    hospitals["longitude"] = pd.to_numeric(hospitals["longitude"], errors="coerce")
    hospitals = hospitals.dropna(subset=["latitude", "longitude"])

    for column in ("origin_id", "destination_id"):
        matrix[column] = matrix[column].astype(str).str.strip()
    for column in ("distance_km", "duration_minutes"):
        matrix[column] = pd.to_numeric(matrix[column], errors="coerce")

    matrix = matrix[matrix["status"].eq("ok")].dropna(
        subset=["distance_km", "duration_minutes"]
    )
    matrix_node_ids = set(matrix["origin_id"]) | set(matrix["destination_id"])
    hospitals = hospitals[hospitals["id"].isin(matrix_node_ids)].reset_index(drop=True)
    if hospitals.empty or matrix.empty:
        raise ValueError("Nao foram encontrados hospitais ou pesos validos na matriz.")
    return hospitals, matrix


def select_edges(matrix: pd.DataFrame, weight_column: str) -> pd.DataFrame:
    """Seleciona as menores arestas de cada origem para manter o grafico legivel."""
    non_diagonal = matrix[matrix["origin_id"] != matrix["destination_id"]].copy()
    return (
        non_diagonal.sort_values(["origin_id", weight_column])
        .groupby("origin_id", as_index=False, group_keys=False)
        .head(MAX_EDGES_PER_ORIGIN)
        .reset_index(drop=True)
    )


def build_edge_trace(
    hospitals: pd.DataFrame,
    edges: pd.DataFrame,
    weight_column: str,
    unit: str,
) -> go.Scatter:
    """Monta a camada de linhas entre as coordenadas das arestas selecionadas."""
    coordinates = hospitals.set_index("id")[["longitude", "latitude"]].to_dict("index")
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []

    for edge in edges.itertuples(index=False):
        origin = coordinates.get(edge.origin_id)
        destination = coordinates.get(edge.destination_id)
        if origin is None or destination is None:
            continue
        edge_x.extend([origin["longitude"], destination["longitude"], None])
        edge_y.extend([origin["latitude"], destination["latitude"], None])

    return go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(color="#C1C0C0", width=1),
        hoverinfo='skip',
        showlegend=False,
    )


def build_edge_label_trace(
    hospitals: pd.DataFrame,
    edges: pd.DataFrame,
    metric: str,
) -> go.Scatter:
    """Monta os rotulos de distancia ou duracao no ponto medio das arestas."""
    coordinates = hospitals.set_index("id")[['longitude', 'latitude']].to_dict('index')
    label_x: list[float] = []
    label_y: list[float] = []
    labels: list[str] = []

    for edge in edges.itertuples(index=False):
        origin = coordinates.get(edge.origin_id)
        destination = coordinates.get(edge.destination_id)
        if origin is None or destination is None:
            continue

        label_x.append((origin['longitude'] + destination['longitude']) / 2)
        label_y.append((origin['latitude'] + destination['latitude']) / 2)
        if metric == "distance":
            labels.append(f"{edge.distance_km:.2f} km")
        else:
            labels.append(f"{edge.duration_minutes:.1f} min")

    return go.Scatter(
        x=label_x,
        y=label_y,
        mode='text',
        text=labels,
        textposition='middle center',
        textfont=dict(size=8, color='#335CA3'),
        hoverinfo='skip',
        showlegend=False,
    )


def render_graph(
    hospitals: pd.DataFrame,
    matrix: pd.DataFrame,
    weight_column: str,
    unit: str,
    title: str,
    filename: str,
) -> None:
    """Renderiza o grafo cartesiano ponderado e suas alternativas de metrica."""
    edges = select_edges(matrix, weight_column)
    node_customdata = hospitals[["hospital", "bairro", "id"]].to_numpy()

    figure = go.Figure()
    figure.add_trace(build_edge_trace(hospitals, edges, weight_column, unit))
    figure.add_trace(build_edge_label_trace(hospitals, edges, "distance"))
    duration_label_trace = build_edge_label_trace(hospitals, edges, "duration")
    duration_label_trace.visible = False
    figure.add_trace(duration_label_trace)
    figure.add_trace(
        go.Scatter(
            x=hospitals["longitude"],
            y=hospitals["latitude"],
            mode="markers+text",
            marker=dict(size=8, color="#333333", line=dict(color="white", width=1)),
            text=hospitals["hospital"],
            textposition="top center",
            textfont=dict(size=8, color="#000000"),
            customdata=node_customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Bairro: %{customdata[1]}<br>"
                "ID: %{customdata[2]}<br>"
                "Latitude: %{y:.5f}<br>Longitude: %{x:.5f}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    figure.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=0.02,
                y=1.08,
                buttons=[
                    dict(
                        label="Distancia",
                        method="restyle",
                        args=[{"visible": [True, True, False, True]}],
                    ),
                    dict(
                        label="Duracao",
                        method="restyle",
                        args=[{"visible": [True, False, True, True]}],
                    ),
                ],
            )
        ],
    )

    x_min, x_max = hospitals["longitude"].min(), hospitals["longitude"].max()
    y_min, y_max = hospitals["latitude"].min(), hospitals["latitude"].max()
    x_pad = (x_max - x_min) * 0.08 if x_max != x_min else 0.01
    y_pad = (y_max - y_min) * 0.08 if y_max != y_min else 0.01
    figure.update_layout(
        title=f"{title} | {len(hospitals)} hospitais | {len(edges)} arestas",
        title_x=0.5,
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        xaxis=dict(range=[x_min - x_pad, x_max + x_pad], zeroline=False),
        yaxis=dict(range=[y_min - y_pad, y_max + y_pad], zeroline=False),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=50, r=20, t=70, b=50),
        width=1400,
        height=950,
    )

    html_path = OUTPUT_DIR / filename
    write_responsive_html(figure, html_path)
    try:
        png_figure = go.Figure()
        png_figure.add_trace(
            go.Scatter(
                x=figure.data[0].x,
                y=figure.data[0].y,
                mode="lines",
                line=dict(color="#C1C0C0", width=1),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        png_figure.add_trace(
            go.Scatter(
                x=hospitals["longitude"],
                y=hospitals["latitude"],
                mode="markers+text",
                marker=dict(size=8, color="#333333", line=dict(color="white", width=1)),
                text=hospitals["hospital"],
                textposition="top center",
                textfont=dict(size=8, color="#000000"),
                showlegend=False,
            )
        )
        png_figure.update_layout(
            title=title,
            xaxis_title="Longitude",
            yaxis_title="Latitude",
            width=1400,
            height=950,
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        png_figure.write_image(html_path.with_suffix(".png"), width=1400, height=950, scale=2)
        print(f"PNG gerado: {html_path.with_suffix('.png')}")
    except Exception as error:
        print(
            f"Aviso: PNG nao gerado ({error.__class__.__name__}: {error}). "
            "O HTML foi gerado normalmente."
        )
    print(f"Grafico gerado: {html_path}")


def render_map(
    hospitals: pd.DataFrame,
    matrix: pd.DataFrame,
    weight_column: str,
    title: str,
    filename: str,
) -> None:
    """Renderiza no mapa as arestas selecionadas e seus pesos."""
    edges = select_edges(matrix, weight_column)
    coordinates = hospitals.set_index("id")[["longitude", "latitude"]].to_dict("index")

    edge_lat: list[float | None] = []
    edge_lon: list[float | None] = []
    label_lat: list[float] = []
    label_lon: list[float] = []
    distance_labels: list[str] = []
    duration_labels: list[str] = []

    for edge in edges.itertuples(index=False):
        origin = coordinates.get(edge.origin_id)
        destination = coordinates.get(edge.destination_id)
        if origin is None or destination is None:
            continue
        edge_lat.extend([origin["latitude"], destination["latitude"], None])
        edge_lon.extend([origin["longitude"], destination["longitude"], None])
        label_lat.append((origin["latitude"] + destination["latitude"]) / 2)
        label_lon.append((origin["longitude"] + destination["longitude"]) / 2)
        distance_labels.append(f"{edge.distance_km:.2f} km")
        duration_labels.append(f"{edge.duration_minutes:.1f} min")

    figure = go.Figure()
    figure.add_trace(
        go.Scattermap(
            lat=edge_lat,
            lon=edge_lon,
            mode="lines",
            line=dict(color="#C0392B", width=1),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scattermap(
            lat=label_lat,
            lon=label_lon,
            mode="text",
            text=distance_labels,
            textfont=dict(size=9, color="#335CA3"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scattermap(
            lat=label_lat,
            lon=label_lon,
            mode="text",
            text=duration_labels,
            textfont=dict(size=9, color="#335CA3"),
            hoverinfo="skip",
            visible=False,
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scattermap(
            lat=hospitals["latitude"].tolist(),
            lon=hospitals["longitude"].tolist(),
            mode="markers+text",
            marker=dict(size=8, color="#333333"),
            text=hospitals["hospital"].tolist(),
            textposition="top center",
            textfont=dict(size=8, color="#000000"),
            customdata=hospitals[["hospital", "bairro", "id"]].to_numpy(),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Bairro: %{customdata[1]}<br>"
                "ID: %{customdata[2]}<br>"
                "Lat: %{lat:.5f}<br>Lon: %{lon:.5f}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    figure.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=0.02,
                y=1.08,
                buttons=[
                    dict(
                        label="Distancia",
                        method="restyle",
                        args=[{"visible": [True, True, False, True]}],
                    ),
                    dict(
                        label="Duracao",
                        method="restyle",
                        args=[{"visible": [True, False, True, True]}],
                    ),
                ],
            )
        ],
    )

    figure.update_layout(
        title=f"{title} | {len(hospitals)} hospitais | {len(edges)} arestas",
        title_x=0.5,
        margin=dict(l=0, r=0, t=55, b=0),
        map=dict(
            style="open-street-map",
            center=dict(
                lat=float(hospitals["latitude"].mean()),
                lon=float(hospitals["longitude"].mean()),
            ),
            zoom=10.4,
        ),
        width=1400,
        height=950,
    )

    html_path = OUTPUT_DIR / filename
    write_responsive_html(figure, html_path)

    try:
        figure.write_image(html_path.with_suffix(".png"), width=1400, height=950, scale=2)
        print(f"PNG mapa gerado: {html_path.with_suffix('.png')}")
    except Exception as error:
        print(f"Aviso: PNG mapa nao gerado ({error.__class__.__name__}: {error}).")
    print(f"Mapa gerado: {html_path}")


def main() -> None:
    """Gera grafos e mapas para distancia e duracao rodoviarias."""
    hospitals, matrix = load_graph_data()
    render_graph(
        hospitals,
        matrix,
        "distance_km",
        "km",
        "Grafo de hospitais ponderado por distancia",
        "grafo_hospitais_distancia_matriz.html",
    )
    render_graph(
        hospitals,
        matrix,
        "duration_minutes",
        "min",
        "Grafo de hospitais ponderado por duracao",
        "grafo_hospitais_duracao_matriz.html",
    )
    render_map(
        hospitals,
        matrix,
        "distance_km",
        "Mapa de hospitais ponderado por distancia",
        "mapa_hospitais_distancia_matriz.html",
    )
    render_map(
        hospitals,
        matrix,
        "duration_minutes",
        "Mapa de hospitais ponderado por duracao",
        "mapa_hospitais_duracao_matriz.html",
    )
    print(f"Hospitais carregados: {len(hospitals)}")
    print(f"Relacoes validas: {len(matrix)}")


if __name__ == "__main__":
    main()
