import sys
import os
import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Ajustando path
sys.path.insert(0, os.getcwd())

# 1. Compilar/Importar servicos/open_route/service.py
print("Importando OpenRouteServiceClient...")
from servicos.open_route.service import OpenRouteServiceClient

# 2. Mockar requests.post
print("Configurando mock para requests.post...")
import requests

mock_post_called = False

def fake_post(url, json, headers, timeout):
    global mock_post_called
    mock_post_called = True
    print(f"Mock requests.post recebido: URL={url}")
    print(f"Headers: {headers}")
    print(f"JSON payload: {json}")
    
    # Validações solicitadas: URL, Authorization, coordenadas no formato [lng, lat], metrics distance/duration e units km
    assert url == "https://api.openrouteservice.org/v2/matrix/driving-car", f"URL incorreta: {url}"
    assert "Authorization" in headers, "Falta Header Authorization"
    assert headers["Authorization"] == "test_api_key", "Chave de autorização incorreta"
    
    # Validando formato do json
    assert "locations" in json, "Falta 'locations' no JSON"
    locations = json["locations"]
    for coord in locations:
        assert isinstance(coord, list) and len(coord) == 2, f"Coordenadas brutas ou malformadas: {coord}"
        assert isinstance(coord[0], (int, float)) and isinstance(coord[1], (int, float)), f"Coordenadas não numéricas: {coord}"
    
    assert json.get("metrics") == ["distance", "duration"], f"Métricas incorretas: {json.get('metrics')}"
    assert json.get("units") == "km", f"Unidades incorretas: {json.get('units')}"
    
    # Retornar distances=[[0, 1.2], [1.5, 0]] e durations=[[0, 60], [90, 0]]
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "distances": [[0, 1.2], [1.5, 0]],
        "durations": [[0, 60], [90, 0]]
    }
    mock_response.raise_for_status = MagicMock()
    return mock_response

requests.post = fake_post

# 3. Chamar matrix para confirmar o payload retornado
client = OpenRouteServiceClient()
h1 = {"id": "1", "hospital": "Hosp1", "bairro": "B1", "lat": -23.55, "lng": -46.63}
h2 = {"id": "2", "hospital": "Hosp2", "bairro": "B2", "lat": -23.56, "lng": -46.64}

returned_payload = client.matrix(origins=[h1], destinations=[h2], api_key="test_api_key")
print(f"Payload retornado do client.matrix confirmado: {returned_payload}")
assert returned_payload["distances"] == [[0, 1.2], [1.5, 0]]
assert returned_payload["durations"] == [[0, 60], [90, 0]]
assert mock_post_called, "O mock_post não foi chamado\!"

# 4. Importar o caso de uso via file path
print("Importando caso de uso...")
module_path = os.path.abspath("casos_de_uso/6-gerar_matriz_distancias.usecase.py")
spec = importlib.util.spec_from_file_location("gerar_matriz_usecase", module_path)
usecase = importlib.util.module_from_spec(spec)
sys.modules["gerar_matriz_usecase"] = usecase
spec.loader.exec_module(usecase)

# 5. Injete um fake client com `matrix`
class FakeOpenRouteServiceClient:
    def __init__(self):
        self.called = False

    def matrix(self, origins, destinations, api_key):
        self.called = True
        return {
            "distances": [[0, 1.2], [1.5, 0]],
            "durations": [[0, 60], [90, 0]]
        }

fake_client = FakeOpenRouteServiceClient()

# 6. Substitua `CACHE_DIR` por diretório temporário
temp_dir = tempfile.TemporaryDirectory()
print(f"CACHE_DIR original: {usecase.CACHE_DIR}")
usecase.CACHE_DIR = Path(temp_dir.name)
print(f"CACHE_DIR substituído por: {usecase.CACHE_DIR}")

# 7. Rode `gerar_matriz` com dois hospitais e batch_size=2
hospitais_test = [
    {"id": "H1", "hospital": "Hospital Um", "bairro": "Bairro Um", "lat": -23.55, "lng": -46.63},
    {"id": "H2", "hospital": "Hospital Dois", "bairro": "Bairro Dois", "lat": -23.56, "lng": -46.64}
]

rows = usecase.gerar_matriz(
    hospitais=hospitais_test,
    api_key="test_api_key_2",
    batch_size=2,
    service=fake_client
)

# 8. Confirme 4 relações e conversões 1200/1500 metros e 60/90 segundos
print(f"Total de relações geradas: {len(rows)}")
for r in rows:
    print(r)

assert len(rows) == 4, f"Esperava 4 relações, gerou {len(rows)}"

rel_h1_h1 = next(r for r in rows if r["origin_id"] == "H1" and r["destination_id"] == "H1")
rel_h1_h2 = next(r for r in rows if r["origin_id"] == "H1" and r["destination_id"] == "H2")
rel_h2_h1 = next(r for r in rows if r["origin_id"] == "H2" and r["destination_id"] == "H1")
rel_h2_h2 = next(r for r in rows if r["origin_id"] == "H2" and r["destination_id"] == "H2")

assert rel_h1_h1["distance_meters"] == 0, f"H1->H1 incorreto: {rel_h1_h1}"
assert rel_h1_h1["duration_seconds"] == 0, f"H1->H1 incorreto: {rel_h1_h1}"

assert rel_h1_h2["distance_meters"] == 1200, f"H1->H2 dist incorreta: {rel_h1_h2['distance_meters']}"
assert rel_h1_h2["duration_seconds"] == 60, f"H1->H2 dur incorreta: {rel_h1_h2['duration_seconds']}"

assert rel_h2_h1["distance_meters"] == 1500, f"H2->H1 dist incorreta: {rel_h2_h1['distance_meters']}"
assert rel_h2_h1["duration_seconds"] == 90, f"H2->H1 dur incorreta: {rel_h2_h1['duration_seconds']}"

assert rel_h2_h2["distance_meters"] == 0, f"H2->H2 incorreto: {rel_h2_h2}"
assert rel_h2_h2["duration_seconds"] == 0, f"H2->H2 incorreto: {rel_h2_h2}"

print("Todas as validações passaram com sucesso\!")
temp_dir.cleanup()
