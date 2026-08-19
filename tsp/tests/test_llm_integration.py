# -*- coding: utf-8 -*-
"""
Testes da integracao com LLM: selecao do cliente conforme variaveis de
ambiente e chamadas HTTP dos clientes OpenAI-compativel e Ollama, usando
`monkeypatch` para simular as respostas da API (sem depender de rede real
nem de um servidor Ollama em execucao).
"""
import requests

from tsp.llm_integration import (
    ClienteLLMOllama,
    ClienteLLMOpenAICompativel,
    obter_cliente_llm,
)


class _RespostaFalsa:
    """Simula um objeto Response do `requests` para os testes."""

    def __init__(self, corpo_json: dict):
        self._corpo_json = corpo_json

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._corpo_json


def test_obter_cliente_llm_retorna_none_sem_variaveis_de_ambiente(monkeypatch):
    """Sem OPENAI_API_KEY nem OLLAMA_MODEL, o sistema deve usar o template (None)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    assert obter_cliente_llm() is None


def test_obter_cliente_llm_prioriza_ollama_quando_ambas_configuradas(monkeypatch):
    """Se OPENAI_API_KEY e OLLAMA_MODEL estiverem definidas, o Ollama (local/gratuito) tem prioridade."""
    monkeypatch.setenv("OPENAI_API_KEY", "chave-teste")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1")

    cliente = obter_cliente_llm()
    assert isinstance(cliente, ClienteLLMOllama)


def test_obter_cliente_llm_usa_openai_quando_apenas_openai_configurado(monkeypatch):
    """Com apenas OPENAI_API_KEY definida (sem OLLAMA_MODEL), o cliente OpenAI deve ser selecionado."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "chave-teste")

    cliente = obter_cliente_llm()
    assert isinstance(cliente, ClienteLLMOpenAICompativel)


def test_obter_cliente_llm_usa_ollama_quando_apenas_ollama_configurado(monkeypatch):
    """Com apenas OLLAMA_MODEL definida, o cliente Ollama local deve ser selecionado."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1")

    cliente = obter_cliente_llm()
    assert isinstance(cliente, ClienteLLMOllama)
    assert cliente.modelo == "llama3.1"


def test_cliente_llm_ollama_gera_texto(monkeypatch):
    """O cliente Ollama deve montar a requisicao no formato /api/chat e extrair o texto da resposta."""
    requisicoes_capturadas = []

    def post_falso(url, json, timeout):
        requisicoes_capturadas.append({"url": url, "json": json, "timeout": timeout})
        return _RespostaFalsa({"message": {"role": "assistant", "content": "Resposta do modelo local."}})

    monkeypatch.setattr(requests, "post", post_falso)

    cliente = ClienteLLMOllama(modelo="llama3.1")
    resultado = cliente.gerar_texto("Gere instrucoes de entrega.", contexto_sistema="Voce e um assistente de logistica.")

    assert resultado == "Resposta do modelo local."
    assert requisicoes_capturadas[0]["json"]["model"] == "llama3.1"
    assert requisicoes_capturadas[0]["json"]["stream"] is False
    assert requisicoes_capturadas[0]["json"]["messages"][0]["role"] == "system"


def test_cliente_llm_openai_compativel_gera_texto(monkeypatch):
    """O cliente OpenAI-compativel deve montar a requisicao com Authorization e extrair o texto da resposta."""
    def post_falso(url, headers, json, timeout):
        assert headers["Authorization"] == "Bearer chave-teste"
        return _RespostaFalsa({"choices": [{"message": {"content": "Relatorio gerado."}}]})

    monkeypatch.setattr(requests, "post", post_falso)

    cliente = ClienteLLMOpenAICompativel(api_key="chave-teste")
    resultado = cliente.gerar_texto("Gere um relatorio.")

    assert resultado == "Relatorio gerado."
