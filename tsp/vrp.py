# -*- coding: utf-8 -*-
"""
Logica especifica do problema de roteamento de veiculos (VRP) hospitalar:
decodificacao de uma rota gigante (permutacao de hospitais) em rotas por
veiculo respeitando capacidade de carga e autonomia, alem do calculo de
fitness usado pelo algoritmo genetico.

Representacao adotada: o cromossomo do algoritmo genetico e uma unica
permutacao ("rota gigante") com todos os hospitais a visitar. Essa
permutacao e decodificada de forma gulosa (procedimento de "split") em
rotas individuais por veiculo, respeitando capacidade e autonomia. Essa
abordagem permite reaproveitar diretamente os operadores geneticos ja
existentes em genetic_algorithm.py (order_crossover, mutate, etc.), que
funcionam sobre qualquer sequencia, sem a necessidade de reescreve-los.
"""
from __future__ import annotations

from .config import PESO_ATRASO_PRIORIDADE, PESO_DISTANCIA, PESO_ENTREGA_NAO_ATENDIDA
from .models import Hospital, Vehicle, VehicleRoute, VrpSolution


def _distancia_total_rota(
    paradas: list[int],
    deposito_id: int,
    indice_por_id: dict[int, int],
    matriz_custos: "np.ndarray",  # noqa: F821 - anotacao apenas informativa
) -> float:
    """Calcula o custo (distancia ou duracao) de uma rota partindo e retornando ao deposito."""
    if not paradas:
        return 0.0

    sequencia_completa = [deposito_id, *paradas, deposito_id]
    custo_total = 0.0
    for origem, destino in zip(sequencia_completa, sequencia_completa[1:]):
        custo_total += matriz_custos[indice_por_id[origem], indice_por_id[destino]]
    return custo_total


def _montar_rota_veiculo(
    veiculo: Vehicle,
    paradas: list[int],
    carga_kg: float,
    deposito_id: int,
    indice_por_id: dict[int, int],
    matriz_distancias_km,
    matriz_duracoes_min,
) -> VehicleRoute:
    """Cria o objeto VehicleRoute final calculando distancia e duracao totais da rota fechada."""
    distancia_km = _distancia_total_rota(paradas, deposito_id, indice_por_id, matriz_distancias_km)
    duracao_min = _distancia_total_rota(paradas, deposito_id, indice_por_id, matriz_duracoes_min)

    return VehicleRoute(
        vehicle=veiculo,
        hospital_ids=list(paradas),
        distance_km=distancia_km,
        duration_min=duracao_min,
        load_kg=carga_kg,
    )


def decodificar_rota_gigante(
    rota_gigante: tuple[int, ...],
    frota: list[Vehicle],
    hospitais_por_id: dict[int, Hospital],
    deposito_id: int,
    indice_por_id: dict[int, int],
    matriz_distancias_km,
    matriz_duracoes_min,
) -> VrpSolution:
    """
    Decodifica uma permutacao de hospitais (rota gigante) em rotas por veiculo.

    Estrategia gulosa ("split"): percorre a rota gigante na ordem informada,
    acumulando paradas no veiculo atual enquanto a capacidade de carga e a
    autonomia forem respeitadas. Ao violar uma restricao, a rota atual e
    fechada (retornando ao deposito) e a proxima parada e atribuida ao
    proximo veiculo da frota (com rotacao, permitindo que um mesmo veiculo
    realize multiplas viagens no dia).

    Parametros:
    - rota_gigante: permutacao (tupla) com os ids de todos os hospitais a visitar.
    - frota: lista de veiculos disponiveis para a operacao.
    - hospitais_por_id: dicionario id -> Hospital, com demanda e prioridade.
    - deposito_id: id do hospital usado como Centro de Distribuicao (CD).
    - indice_por_id: dicionario id -> indice na matriz de custos.
    - matriz_distancias_km / matriz_duracoes_min: matrizes de custo (numpy).

    Retorno:
    VrpSolution com as rotas por veiculo e a lista de hospitais nao atendidos
    (quando nenhum veiculo da frota consegue atender aquela demanda isoladamente).
    """
    if not frota:
        raise ValueError("A frota nao pode estar vazia para decodificar uma solucao VRP.")

    rotas: list[VehicleRoute] = []
    nao_atendidos: list[int] = []

    indice_veiculo_atual = 0
    veiculo_atual = frota[indice_veiculo_atual]
    paradas_atuais: list[int] = []
    carga_atual = 0.0

    for hospital_id in rota_gigante:
        hospital = hospitais_por_id[hospital_id]
        paradas_tentativa = paradas_atuais + [hospital_id]
        carga_tentativa = carga_atual + hospital.demand_kg
        distancia_tentativa = _distancia_total_rota(paradas_tentativa, deposito_id, indice_por_id, matriz_distancias_km)

        cabe_na_capacidade = carga_tentativa <= veiculo_atual.capacity_kg
        cabe_na_autonomia = distancia_tentativa <= veiculo_atual.autonomy_km

        if cabe_na_capacidade and cabe_na_autonomia:
            paradas_atuais = paradas_tentativa
            carga_atual = carga_tentativa
            continue

        # Fecha a rota atual (se ha paradas acumuladas) e avanca para o proximo veiculo da frota
        if paradas_atuais:
            rotas.append(
                _montar_rota_veiculo(
                    veiculo_atual, paradas_atuais, carga_atual, deposito_id,
                    indice_por_id, matriz_distancias_km, matriz_duracoes_min,
                )
            )

        indice_veiculo_atual = (indice_veiculo_atual + 1) % len(frota)
        veiculo_atual = frota[indice_veiculo_atual]
        paradas_atuais = []
        carga_atual = 0.0

        # Tenta encaixar o hospital sozinho no novo veiculo
        distancia_individual = _distancia_total_rota([hospital_id], deposito_id, indice_por_id, matriz_distancias_km)
        if hospital.demand_kg <= veiculo_atual.capacity_kg and distancia_individual <= veiculo_atual.autonomy_km:
            paradas_atuais = [hospital_id]
            carga_atual = hospital.demand_kg
        else:
            # Nenhum veiculo da frota consegue atender esse hospital isoladamente
            nao_atendidos.append(hospital_id)

    if paradas_atuais:
        rotas.append(
            _montar_rota_veiculo(
                veiculo_atual, paradas_atuais, carga_atual, deposito_id,
                indice_por_id, matriz_distancias_km, matriz_duracoes_min,
            )
        )

    return VrpSolution(routes=rotas, unassigned_hospital_ids=nao_atendidos)


def calcular_fitness_vrp(
    solucao: VrpSolution,
    hospitais_por_id: dict[int, Hospital],
    peso_distancia: float = PESO_DISTANCIA,
    peso_atraso_prioridade: float = PESO_ATRASO_PRIORIDADE,
    peso_entrega_nao_atendida: float = PESO_ENTREGA_NAO_ATENDIDA,
) -> float:
    """
    Calcula o fitness (quanto menor, melhor) de uma solucao VRP.

    A funcao combina tres componentes:
    - custo operacional: distancia total percorrida por todas as rotas;
    - penalidade de prioridade: entregas criticas atendidas tardiamente
      (posicao global na sequencia de despacho) sao mais penalizadas que
      entregas regulares, pois assume-se que as rotas sao despachadas na
      ordem em que aparecem na solucao;
    - penalidade de entregas nao atendidas: hospitais que nenhum veiculo
      da frota conseguiu atender por restricao de capacidade/autonomia.

    Retorno:
    Valor float representando o custo total da solucao (fitness a minimizar).
    """
    custo_distancia = solucao.total_distance_km * peso_distancia

    penalidade_prioridade = 0.0
    posicao_global = 0
    for rota in solucao.routes:
        for hospital_id in rota.hospital_ids:
            hospital = hospitais_por_id[hospital_id]
            penalidade_prioridade += hospital.priority.penalty_weight * posicao_global
            posicao_global += 1
    penalidade_prioridade *= peso_atraso_prioridade

    penalidade_nao_atendidas = len(solucao.unassigned_hospital_ids) * peso_entrega_nao_atendida

    return custo_distancia + penalidade_prioridade + penalidade_nao_atendidas


def calcular_posicao_media_entregas_criticas(
    solucao: VrpSolution,
    hospitais_por_id: dict[int, Hospital],
) -> float | None:
    """
    Calcula a posicao media (na sequencia global de despacho) em que as
    entregas criticas sao atendidas. Quanto menor esse valor, mais cedo, em
    media, os medicamentos criticos chegam aos hospitais - metrica usada no
    relatorio operacional para evidenciar o ganho de priorizacao do GA
    (independente do efeito na distancia total percorrida).

    Retorno:
    Media das posicoes (0 = primeira entrega do dia) das entregas criticas,
    ou None se a solucao nao tiver nenhuma entrega critica.
    """
    posicoes_criticas: list[int] = []
    posicao_global = 0
    for rota in solucao.routes:
        for hospital_id in rota.hospital_ids:
            if hospitais_por_id[hospital_id].priority.name == "CRITICAL":
                posicoes_criticas.append(posicao_global)
            posicao_global += 1

    if not posicoes_criticas:
        return None
    return sum(posicoes_criticas) / len(posicoes_criticas)
