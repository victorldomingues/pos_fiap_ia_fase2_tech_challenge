from __future__ import annotations

from typing import Any

import requests


class OpenRouteServiceClient:
    """Cliente HTTP fino para a Matrix API do OpenRouteService."""

    def __init__(
        self,
        base_url: str = "https://api.openrouteservice.org/v2/matrix/driving-car",
        timeout_seconds: int = 120,
    ) -> None:
        """Configura endpoint da Matrix API e timeout da requisicao."""
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def matrix(
        self,
        origins: list[dict[str, Any]],
        destinations: list[dict[str, Any]],
        api_key: str,
    ) -> dict[str, Any]:
        """Consulta distancias e duracoes direcionadas entre dois conjuntos de pontos."""
        # O ORS usa longitude, latitude; as listas de indices separam fontes e destinos.
        locations = [
            [hospital["lng"], hospital["lat"]]
            for hospital in origins + destinations
        ]
        origin_indices = list(range(len(origins)))
        destination_indices = list(
            range(len(origins), len(origins) + len(destinations))
        )
        request_body = {
            "locations": locations,
            "sources": origin_indices,
            "destinations": destination_indices,
            "metrics": ["distance", "duration"],
            "units": "km",
        }
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }

        # Falhas de rede e respostas fora do contrato sao convertidas em erros claros.
        try:
            response = requests.post(
                self.base_url,
                json=request_body,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as error:
            raise ConnectionError(f"Erro ao consultar OpenRouteService: {error}") from error
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(
                f"Resposta inesperada da OpenRouteService: {type(payload).__name__}"
            )
        if not isinstance(payload.get("distances"), list):
            raise ValueError("OpenRouteService não retornou distances")
        if not isinstance(payload.get("durations"), list):
            raise ValueError("OpenRouteService não retornou durations")
        return payload
