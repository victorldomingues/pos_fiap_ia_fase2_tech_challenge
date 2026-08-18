from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class OpenStreetMapGeocoder:
    """Cliente HTTP simples para consulta de coordenadas no Nominatim."""

    def __init__(self, base_url: str = "https://nominatim.openstreetmap.org/search", timeout_seconds: int = 30) -> None:
        """Configura endpoint e limite de espera das requisicoes HTTP."""
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def search(self, query: str) -> dict[str, Any] | None:
        """Busca um endereço no Nominatim.
        
        Retorna:
            dict: {
                "result": dict,           # primeiro resultado do Nominatim
                "status_code": int,       # código HTTP da resposta
                "response": list,         # payload completo da API
                "success": bool           # se lat/lon foram extraídos
            }
            None: nenhum resultado encontrado
        
        Lança:
            ConnectionError: erro de conexão com a API
            TimeoutError: timeout na requisição
        """
        # A consulta vazia e tratada localmente para evitar chamada desnecessaria.
        normalized_query = (query or "").strip()
        if not normalized_query:
            return None

        params = {
            "q": normalized_query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 1,
            "countrycodes": "br",
            "email": "",
        }
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; OpenStreetMapGeocoder/1.0; +https://example.com)",
                "Accept": "application/json",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            },
        )

        # O cliente traduz erros de transporte para excecoes estaveis do dominio.
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status_code = response.status
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 403):
                raise ConnectionError(f"API rate-limited ou bloqueada (HTTP {e.code}): {e.reason}")
            raise ConnectionError(f"Erro HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Erro de rede: {str(e)}")
        except TimeoutError:
            raise TimeoutError("Timeout ao conectar ao Nominatim")
        except OSError as e:
            raise ConnectionError(f"Erro de sistema: {str(e)}")
        except ValueError as e:
            raise ConnectionError(f"Erro ao decodificar resposta JSON: {str(e)}")

        if isinstance(payload, list) and len(payload) > 0:
            result = payload[0]
            return {
                "result": result,
                "status_code": status_code,
                "response": payload,
                "success": result.get("lat") is not None and result.get("lon") is not None
            }
        
        return {
            "result": None,
            "status_code": status_code,
            "response": payload,
            "success": False
        }
