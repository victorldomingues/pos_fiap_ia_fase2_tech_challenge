# -*- coding: utf-8 -*-
"""
Integracao com LLM para geracao de instrucoes de entrega, relatorios
operacionais e respostas em linguagem natural sobre as rotas otimizadas.

O projeto nao depende de nenhuma chave de API para funcionar. A ordem de
prioridade (ver `obter_cliente_llm`) sempre favorece a opcao mais simples e
gratuita antes de uma API paga:
1. Template (padrao): gerador de texto deterministico e reproduzivel, usado
   quando nenhuma LLM esta configurada;
2. OLLAMA_MODEL: usa um modelo local servido pelo Ollama (http://localhost:11434),
   sem necessidade de chave de API nem envio de dados para fora da maquina;
3. OPENAI_API_KEY: usa uma API compativel com o formato de chat da OpenAI
   (nuvem, paga), usada apenas se OLLAMA_MODEL nao estiver definida.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

import requests

from .models import Hospital, VrpSolution
from .vrp import calcular_posicao_media_entregas_criticas

OPENAI_BASE_URL_PADRAO = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL_PADRAO = "gpt-4o-mini"

OLLAMA_BASE_URL_PADRAO = "http://localhost:11434/api/chat"
OLLAMA_MODEL_PADRAO = "llama3.1"


class ClienteLLM(ABC):
    """Interface abstrata para um cliente de LLM capaz de gerar texto a partir de um prompt."""

    @abstractmethod
    def gerar_texto(self, prompt: str, contexto_sistema: str = "") -> str:
        """Gera uma resposta em texto livre a partir do prompt informado."""
        raise NotImplementedError


class ClienteLLMOpenAICompativel(ClienteLLM):
    """
    Cliente LLM que chama uma API compativel com o formato de chat da OpenAI,
    usando apenas `requests` (sem dependencia do SDK oficial). Requer a
    variavel de ambiente OPENAI_API_KEY.
    """

    def __init__(self, api_key: str, base_url: str = OPENAI_BASE_URL_PADRAO, modelo: str = OPENAI_MODEL_PADRAO):
        self.api_key = api_key
        self.base_url = base_url
        self.modelo = modelo

    def gerar_texto(self, prompt: str, contexto_sistema: str = "") -> str:
        """Envia o prompt para a API de chat e retorna o texto gerado pelo modelo."""
        cabecalhos = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        mensagens = []
        if contexto_sistema:
            mensagens.append({"role": "system", "content": contexto_sistema})
        mensagens.append({"role": "user", "content": prompt})

        corpo_requisicao = {"model": self.modelo, "messages": mensagens, "temperature": 0.3}
        resposta = requests.post(self.base_url, headers=cabecalhos, json=corpo_requisicao, timeout=30)
        resposta.raise_for_status()

        return resposta.json()["choices"][0]["message"]["content"].strip()


class ClienteLLMOllama(ClienteLLM):
    """
    Cliente LLM que chama um servidor Ollama local (`ollama serve`), via o
    endpoint /api/chat. Nao requer chave de API: basta ter o Ollama instalado,
    rodando e com o modelo desejado baixado (`ollama pull <modelo>`).
    """

    def __init__(self, base_url: str = OLLAMA_BASE_URL_PADRAO, modelo: str = OLLAMA_MODEL_PADRAO, timeout_segundos: int = 120):
        self.base_url = base_url
        self.modelo = modelo
        self.timeout_segundos = timeout_segundos

    def gerar_texto(self, prompt: str, contexto_sistema: str = "") -> str:
        """Envia o prompt ao Ollama e retorna o texto gerado pelo modelo local."""
        mensagens = []
        if contexto_sistema:
            mensagens.append({"role": "system", "content": contexto_sistema})
        mensagens.append({"role": "user", "content": prompt})

        # stream=False para receber a resposta completa em uma unica chamada, sem chunking
        corpo_requisicao = {"model": self.modelo, "messages": mensagens, "stream": False}
        resposta = requests.post(self.base_url, json=corpo_requisicao, timeout=self.timeout_segundos)
        resposta.raise_for_status()

        return resposta.json()["message"]["content"].strip()


def obter_cliente_llm() -> ClienteLLM | None:
    """
    Seleciona o cliente LLM conforme as variaveis de ambiente configuradas,
    priorizando sempre a opcao mais simples/gratuita antes de uma API paga:
    1. Template (padrao): usado quando nem OLLAMA_MODEL nem OPENAI_API_KEY estao definidas.
    2. OLLAMA_MODEL definida: usa Ollama local (gratuito, sem envio de dados para fora da maquina).
    3. OPENAI_API_KEY definida (e OLLAMA_MODEL ausente): usa a API paga da OpenAI, como ultimo recurso.
    """
    modelo_ollama = os.environ.get("OLLAMA_MODEL")
    if modelo_ollama:
        base_url = os.environ.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL_PADRAO)
        return ClienteLLMOllama(base_url=base_url, modelo=modelo_ollama)

    chave_api_openai = os.environ.get("OPENAI_API_KEY")
    if chave_api_openai:
        base_url = os.environ.get("OPENAI_BASE_URL", OPENAI_BASE_URL_PADRAO)
        modelo = os.environ.get("OPENAI_MODEL", OPENAI_MODEL_PADRAO)
        return ClienteLLMOpenAICompativel(api_key=chave_api_openai, base_url=base_url, modelo=modelo)

    return None


# ---------------------------------------------------------------------------
# Geracao de instrucoes para motoristas
# ---------------------------------------------------------------------------
def _montar_prompt_instrucoes_motorista(numero_rota: int, rota, hospitais_por_id: dict[int, Hospital]) -> str:
    """Monta o prompt textual descrevendo a rota, usado tanto pelo template quanto pela LLM."""
    paradas_texto = "\n".join(
        f"{posicao + 1}. {hospitais_por_id[hid].name} ({hospitais_por_id[hid].district}) "
        f"- prioridade {hospitais_por_id[hid].priority.name} - {hospitais_por_id[hid].demand_kg:.1f} kg"
        for posicao, hid in enumerate(rota.hospital_ids)
    )
    return (
        f"Rota {numero_rota}: veiculo {rota.vehicle.brand} {rota.vehicle.model} "
        f"(capacidade {rota.vehicle.capacity_kg:.0f} kg, autonomia {rota.vehicle.autonomy_km:.0f} km).\n"
        f"Distancia total: {rota.distance_km:.1f} km. Duracao estimada: {rota.duration_min:.1f} min.\n"
        f"Carga total: {rota.load_kg:.1f} kg.\n"
        f"Paradas em ordem de entrega:\n{paradas_texto}"
    )


def gerar_instrucoes_motorista_template(numero_rota: int, rota, hospitais_por_id: dict[int, Hospital]) -> str:
    """
    Gera instrucoes de entrega em linguagem natural sem depender de LLM externa.

    Formato pensado para leitura rapida por motoristas/equipe de entrega,
    destacando entregas criticas e a ordem correta de visitacao.
    """
    linhas = [
        f"## Instrucoes de entrega - Rota {numero_rota}",
        "",
        f"- **Veiculo:** {rota.vehicle.brand} {rota.vehicle.model} {rota.vehicle.version}",
        f"- **Carga total:** {rota.load_kg:.1f} kg de {rota.vehicle.capacity_kg:.0f} kg disponiveis",
        f"- **Distancia total prevista:** {rota.distance_km:.1f} km (autonomia do veiculo: {rota.vehicle.autonomy_km:.0f} km)",
        f"- **Tempo estimado de percurso:** {rota.duration_min:.1f} minutos",
        "",
        "### Ordem de entrega (parta e retorne ao Centro de Distribuicao)",
        "",
    ]

    for posicao, hospital_id in enumerate(rota.hospital_ids, start=1):
        hospital = hospitais_por_id[hospital_id]
        marcador = " **:rotating_light: ENTREGA CRITICA**" if hospital.priority.name == "CRITICAL" else ""
        linhas.append(
            f"{posicao}. {hospital.name} - bairro {hospital.district} - {hospital.demand_kg:.1f} kg{marcador}".rstrip()
        )

    linhas.append("")
    linhas.append("> **Atencao:** priorize entregas marcadas como criticas e confirme o recebimento em cada parada.")
    return "\n".join(linhas)


def gerar_instrucoes_motorista(
    numero_rota: int,
    rota,
    hospitais_por_id: dict[int, Hospital],
    cliente_llm: ClienteLLM | None = None,
) -> str:
    """
    Gera as instrucoes de entrega para uma rota, usando LLM real quando
    disponivel (cliente_llm informado) ou o gerador baseado em template.
    """
    if cliente_llm is None:
        return gerar_instrucoes_motorista_template(numero_rota, rota, hospitais_por_id)

    prompt = _montar_prompt_instrucoes_motorista(numero_rota, rota, hospitais_por_id)
    contexto_sistema = (
        "Voce e um assistente de logistica hospitalar. Gere instrucoes claras, objetivas e "
        "em portugues do Brasil para o motorista responsavel pela rota de entrega descrita, "
        "destacando entregas criticas e cuidados com medicamentos."
    )
    return cliente_llm.gerar_texto(prompt, contexto_sistema)


# ---------------------------------------------------------------------------
# Geracao de relatorios operacionais
# ---------------------------------------------------------------------------
def gerar_relatorio_operacional_template(
    solucao: VrpSolution,
    baseline: VrpSolution,
    hospitais_por_id: dict[int, Hospital],
) -> str:
    """
    Gera um relatorio operacional comparando a solucao otimizada pelo
    algoritmo genetico com a baseline (planejamento manual/sem otimizacao).
    """
    economia_distancia_km = baseline.total_distance_km - solucao.total_distance_km
    economia_percentual = (
        (economia_distancia_km / baseline.total_distance_km * 100) if baseline.total_distance_km else 0.0
    )

    posicao_critica_otimizado = calcular_posicao_media_entregas_criticas(solucao, hospitais_por_id)
    posicao_critica_baseline = calcular_posicao_media_entregas_criticas(baseline, hospitais_por_id)

    linhas = [
        "# Relatorio de eficiencia de rotas - Distribuicao hospitalar",
        "",
        "## Veiculos utilizados",
        "",
        f"- **Otimizado:** {solucao.vehicles_used}",
        f"- **Baseline:** {baseline.vehicles_used}",
        "",
        "## Distancia total",
        "",
        f"- **Otimizado:** {solucao.total_distance_km:.1f} km",
        f"- **Baseline:** {baseline.total_distance_km:.1f} km",
        f"- **Economia de distancia:** {economia_distancia_km:.1f} km ({economia_percentual:.1f}%)",
        "",
        "## Duracao total",
        "",
        f"- **Otimizado:** {solucao.total_duration_min:.1f} min",
        f"- **Baseline:** {baseline.total_duration_min:.1f} min",
        "",
        "## Entregas nao atendidas",
        "",
        f"- **Otimizado:** {len(solucao.unassigned_hospital_ids)}",
        f"- **Baseline:** {len(baseline.unassigned_hospital_ids)}",
        "",
        "## Priorizacao de entregas criticas",
        "",
        "_Posicao media na sequencia de despacho (menor = mais cedo)._",
        "",
        f"- **Otimizado:** {posicao_critica_otimizado:.1f}ª entrega em media" if posicao_critica_otimizado is not None else "- **Otimizado:** sem entregas criticas",
        f"- **Baseline:** {posicao_critica_baseline:.1f}ª entrega em media" if posicao_critica_baseline is not None else "- **Baseline:** sem entregas criticas",
        "",
        "## Detalhamento por rota (solucao otimizada)",
        "",
        "| Rota | Veiculo | Paradas | Criticas | Distancia (km) | Carga (kg) |",
        "|---|---|---|---|---|---|",
    ]

    for numero_rota, rota in enumerate(solucao.routes, start=1):
        if not rota.hospital_ids:
            continue
        qtd_criticas = sum(
            1 for hid in rota.hospital_ids if hospitais_por_id[hid].priority.name == "CRITICAL"
        )
        linhas.append(
            f"| {numero_rota} | {rota.vehicle.brand} {rota.vehicle.model} | "
            f"{len(rota.hospital_ids)} | {qtd_criticas} | "
            f"{rota.distance_km:.1f} | {rota.load_kg:.1f} |"
        )

    linhas.append("")
    linhas.append(
        "> **Sugestao de melhoria:** avaliar aumento da frota ou revisao de janelas de entrega "
        "caso o numero de entregas nao atendidas seja maior que zero."
        if solucao.unassigned_hospital_ids
        else "> Todas as entregas foram atendidas dentro das restricoes de capacidade e autonomia."
    )

    return "\n".join(linhas)


def gerar_relatorio_operacional(
    solucao: VrpSolution,
    baseline: VrpSolution,
    hospitais_por_id: dict[int, Hospital],
    cliente_llm: ClienteLLM | None = None,
) -> str:
    """
    Gera o relatorio operacional de eficiencia de rotas, usando LLM real
    quando disponivel para enriquecer a narrativa, ou o template padrao.
    """
    relatorio_base = gerar_relatorio_operacional_template(solucao, baseline, hospitais_por_id)

    if cliente_llm is None:
        return relatorio_base

    prompt = (
        f"Com base nos dados a seguir, escreva um relatorio operacional executivo, em portugues, "
        f"sobre a eficiencia das rotas de distribuicao de medicamentos hospitalares, destacando "
        f"ganhos de eficiencia e sugestoes de melhoria:\n\n{relatorio_base}"
    )
    contexto_sistema = "Voce e um analista de logistica hospitalar redigindo relatorios executivos em portugues do Brasil."
    return cliente_llm.gerar_texto(prompt, contexto_sistema)


# ---------------------------------------------------------------------------
# Perguntas e respostas em linguagem natural sobre as rotas
# ---------------------------------------------------------------------------
def responder_pergunta_template(pergunta: str, solucao: VrpSolution, hospitais_por_id: dict[int, Hospital]) -> str:
    """
    Responde perguntas simples sobre a solucao de rotas usando busca por
    palavras-chave (sem depender de LLM externa). Cobre as perguntas
    operacionais mais comuns: distancia total, veiculos usados, entregas
    criticas e localizacao de um hospital especifico na solucao.
    """
    pergunta_lower = pergunta.lower()

    if "distancia" in pergunta_lower or "km" in pergunta_lower:
        return f"A distancia total das rotas otimizadas e de {solucao.total_distance_km:.1f} km."

    if "veiculo" in pergunta_lower or "veículo" in pergunta_lower:
        return f"Sao utilizados {solucao.vehicles_used} veiculo(s) na solucao otimizada."

    if "critic" in pergunta_lower:
        criticas = [
            hospitais_por_id[hid].name
            for rota in solucao.routes
            for hid in rota.hospital_ids
            if hospitais_por_id[hid].priority.name == "CRITICAL"
        ]
        return f"Entregas criticas ({len(criticas)}): {', '.join(criticas) if criticas else 'nenhuma'}."

    if "atendid" in pergunta_lower:
        return f"Hospitais nao atendidos: {len(solucao.unassigned_hospital_ids)}."

    for hospital in hospitais_por_id.values():
        if hospital.name.lower() in pergunta_lower:
            for numero_rota, rota in enumerate(solucao.routes, start=1):
                if hospital.id in rota.hospital_ids:
                    return f"{hospital.name} esta na Rota {numero_rota}, atendida pelo veiculo {rota.vehicle.brand} {rota.vehicle.model}."
            return f"{hospital.name} nao foi atendido na solucao atual."

    return (
        "Nao foi possivel identificar a pergunta automaticamente. Tente perguntar sobre "
        "distancia total, quantidade de veiculos, entregas criticas ou um hospital especifico."
    )


def responder_pergunta(
    pergunta: str,
    solucao: VrpSolution,
    hospitais_por_id: dict[int, Hospital],
    cliente_llm: ClienteLLM | None = None,
) -> str:
    """Responde uma pergunta em linguagem natural sobre a solucao de rotas."""
    if cliente_llm is None:
        return responder_pergunta_template(pergunta, solucao, hospitais_por_id)

    resumo_solucao = gerar_relatorio_operacional_template(solucao, solucao, hospitais_por_id)
    prompt = f"Considerando os dados de rotas abaixo, responda a pergunta do usuario.\n\nDados:\n{resumo_solucao}\n\nPergunta: {pergunta}"
    contexto_sistema = "Voce e um assistente de logistica hospitalar respondendo perguntas em portugues do Brasil."
    return cliente_llm.gerar_texto(prompt, contexto_sistema)
