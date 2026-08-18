from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

try:
    import networkx as nx  # type: ignore
except Exception:  # pragma: no cover
    nx = None

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "bases" / "por_bairro_hospitais_publicos_sao_paulo_sp.csv"


def load_hospitais() -> pd.DataFrame:
    """Carrega hospitais com coordenadas e remove registros sem geocoding valido."""
    df = pd.read_csv(DATASET_PATH, sep=';')
    df = df.copy()
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df = df.dropna(subset=['latitude', 'longitude']).reset_index(drop=True)
    df = df[df['geocode_status'].fillna('not_found').eq('ok')].reset_index(drop=True)
    return df


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distancia geodesica aproximada entre duas coordenadas em km."""
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def build_adjacency(df: pd.DataFrame, max_neighbors: int = 6, max_distance_km: float = 25.0) -> dict[int, list[int]]:
    """Cria um grafo nao direcionado limitado a vizinhos proximos."""
    adjacency: dict[int, list[int]] = {idx: [] for idx in range(len(df))}
    candidates: list[tuple[float, int, int]] = []

    # Primeiro calcula candidatos; depois aplica os limites de distancia e grau.
    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            dist = haversine_km(
                float(df.iloc[i]['latitude']),
                float(df.iloc[i]['longitude']),
                float(df.iloc[j]['latitude']),
                float(df.iloc[j]['longitude']),
            )
            if dist <= max_distance_km:
                candidates.append((dist, i, j))

    for _, i, j in sorted(candidates, key=lambda item: item[0]):
        if len(adjacency[i]) < max_neighbors and len(adjacency[j]) < max_neighbors:
            adjacency[i].append(j)
            adjacency[j].append(i)

    for node in adjacency:
        adjacency[node] = sorted(adjacency[node])

    return adjacency


def count_simple_paths_limit(adjacency: dict[int, list[int]], max_depth: int = 4) -> int:
    """Conta caminhos simples unicos ate uma profundidade fixa via DFS."""
    unique_paths: set[tuple[int, ...]] = set()

    for source in adjacency:
        stack: list[tuple[int, list[int], set[int]]] = [(source, [source], {source})]

        while stack:
            node, path, seen = stack.pop()
            if len(path) - 1 >= max_depth:
                candidate = tuple(path)
                reversed_candidate = tuple(reversed(candidate))
                if candidate <= reversed_candidate:
                    unique_paths.add(candidate)
                else:
                    unique_paths.add(reversed_candidate)
                continue

            for neighbor in adjacency.get(node, []):
                if neighbor in seen:
                    continue
                stack.append((neighbor, path + [neighbor], seen | {neighbor}))

    return len(unique_paths)


def count_paths_with_networkx(df: pd.DataFrame, max_depth: int = 4) -> tuple[int, int, int]:
    """Conta nos, arestas e caminhos usando NetworkX quando instalado."""
    if nx is None:
        raise RuntimeError('networkx nao esta instalado')

    g = nx.Graph()
    for idx, row in df.iterrows():
        g.add_node(idx, hospital=row['hospital'])

    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            dist = haversine_km(
                float(df.iloc[i]['latitude']),
                float(df.iloc[i]['longitude']),
                float(df.iloc[j]['latitude']),
                float(df.iloc[j]['longitude']),
            )
            if dist <= 25.0:
                g.add_edge(i, j, weight=dist)

    nodes = g.number_of_nodes()
    edges = g.number_of_edges()
    paths = 0
    seen_paths: set[tuple[int, ...]] = set()

    for source in g.nodes:
        for target in g.nodes:
            if source == target:
                continue
            for path in nx.all_simple_paths(g, source, target, cutoff=max_depth):
                key = tuple(path)
                reverse_key = tuple(reversed(path))
                norm = key if key <= reverse_key else reverse_key
                seen_paths.add(norm)

    paths = len(seen_paths)
    return nodes, edges, paths


def main() -> None:
    """Executa a contagem limitada e imprime um resumo do grafo."""
    df = load_hospitais()
    if df.empty:
        raise ValueError('Nenhum hospital com coordenadas validas foi encontrado.')

    adjacency = build_adjacency(df, max_neighbors=6, max_distance_km=25.0)
    total_paths = count_simple_paths_limit(adjacency, max_depth=4)

    print('=== CONTAGEM DE CAMINHOS POSSIVEIS ===')
    print(f'Hospitais carregados: {len(df)}')
    print(f'Nos no grafo: {len(adjacency)}')
    print(f'Edges no grafo de vizinhos proximos: {sum(len(v) for v in adjacency.values()) // 2}')
    print(f'Profundidade maxima considerada: 4 passos')
    print(f'Caminhos simples unicos possiveis (modelo local): {total_paths}')
    print('Observacao: o numero total de rotas em um grafo completo explodiria combinatoriamente; por isso esta contagem usa um grafo de vizinhos proximos e uma profundidade limitada para manter o problema tratavel e reproduzivel.')


if __name__ == '__main__':
    main()
