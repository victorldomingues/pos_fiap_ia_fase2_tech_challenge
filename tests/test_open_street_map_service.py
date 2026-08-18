import unittest
from unittest.mock import patch

from servicos.open_street_map.service import OpenStreetMapGeocoder


class OpenStreetMapGeocoderTest(unittest.TestCase):
    """Testes para OpenStreetMapGeocoder com mocks completos."""

    @patch("servicos.open_street_map.service.urllib.request.urlopen")
    def test_search_raises_timeout_on_request_fails(self, mock_urlopen):
        """Simula timeout sem fazer requisição real."""
        geocoder = OpenStreetMapGeocoder()
        mock_urlopen.side_effect = TimeoutError("timeout")

        with self.assertRaises(TimeoutError):
            geocoder.search("Hospital Teste, São Paulo, SP")

    @patch("servicos.open_street_map.service.urllib.request.urlopen")
    def test_search_returns_result_with_status_code_when_api_succeeds(self, mock_urlopen):
        """Simula resposta sucesso sem fazer requisição real."""
        from unittest.mock import MagicMock
        
        geocoder = OpenStreetMapGeocoder()

        # Mock da resposta HTTP
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = (
            '[{"lat":"-23.5","lon":"-46.6","display_name":"Hospital Teste, São Paulo, SP"}]'
        ).encode("utf-8")
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda self, *args: False

        mock_urlopen.return_value = mock_response

        result = geocoder.search("Hospital Teste, São Paulo, SP")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["status_code"], 200)
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["result"])
        self.assertEqual(result["result"]["lat"], "-23.5")
        
        # Garante que urlopen foi chamado
        mock_urlopen.assert_called_once()

    def test_search_returns_none_for_empty_query(self):
        """Query vazia retorna None sem fazer requisição."""
        geocoder = OpenStreetMapGeocoder()
        result = geocoder.search("   ")
        self.assertIsNone(result)

    @patch("servicos.open_street_map.service.urllib.request.urlopen")
    def test_search_raises_connection_error_on_http_403(self, mock_urlopen):
        """Simula erro OSError sem fazer requisição real."""
        geocoder = OpenStreetMapGeocoder()
        mock_urlopen.side_effect = OSError("blocked")

        with self.assertRaises(ConnectionError) as context:
            geocoder.search("Hospital Teste, São Paulo, SP")
        
        self.assertIn("Erro de sistema", str(context.exception))
        mock_urlopen.assert_called_once()

    @patch("servicos.open_street_map.service.urllib.request.urlopen")
    def test_search_handles_false_positive_status_200_without_coordinates(self, mock_urlopen):
        """Simula falso positivo (200 sem lat/lon) sem requisição real."""
        from unittest.mock import MagicMock
        
        geocoder = OpenStreetMapGeocoder()

        # Mock da resposta HTTP
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = (
            '[{"place_id": 123, "display_name":"Sem coordenadas"}]'
        ).encode("utf-8")
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda self, *args: False

        mock_urlopen.return_value = mock_response

        result = geocoder.search("Query sem coordenadas")

        self.assertIsNotNone(result)
        self.assertEqual(result["status_code"], 200)
        self.assertFalse(result["success"])
        self.assertIsNone(result["result"].get("lat"))
        mock_urlopen.assert_called_once()

    @patch("servicos.open_street_map.service.urllib.request.urlopen")
    def test_search_handles_http_429_rate_limit(self, mock_urlopen):
        """Simula erro HTTP 429 (rate limit) sem requisição real."""
        import urllib.error
        
        geocoder = OpenStreetMapGeocoder()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "url", 429, "Too Many Requests", {}, None
        )

        with self.assertRaises(ConnectionError) as context:
            geocoder.search("Hospital Teste")
        
        self.assertIn("429", str(context.exception))
        mock_urlopen.assert_called_once()

    @patch("servicos.open_street_map.service.urllib.request.urlopen")
    def test_search_handles_empty_response(self, mock_urlopen):
        """Simula resposta vazia sem fazer requisição real."""
        from unittest.mock import MagicMock
        
        geocoder = OpenStreetMapGeocoder()

        # Mock da resposta HTTP vazia
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = '[]'.encode("utf-8")
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda self, *args: False

        mock_urlopen.return_value = mock_response

        result = geocoder.search("Hospital inexistente")

        self.assertIsNotNone(result)
        self.assertEqual(result["status_code"], 200)
        self.assertFalse(result["success"])
        self.assertIsNone(result["result"])
        mock_urlopen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
