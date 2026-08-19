# -*- coding: utf-8 -*-
"""
Testes objetivos e leves do pipeline de otimizacao de rotas medicas (VRP).

Os testes validam: carregamento e integridade dos dados, respeito as
restricoes de capacidade/autonomia na decodificacao das rotas e melhoria do
fitness ao longo das geracoes do algoritmo genetico.
"""
from tsp import config
from tsp.data_loader import (
    carregar_frota,
    carregar_matriz_distancias,
    construir_lista_hospitais_base,
    gerar_demandas_hospitais,
)
from tsp.distance_matrix import calcular_coordenadas_mds, construir_matriz_custos
from tsp.models import Vehicle
from tsp.optimizer import calcular_solucao_baseline, executar_algoritmo_genetico_vrp
from tsp.vrp import calcular_fitness_vrp, decodificar_rota_gigante


def _carregar_cenario_teste():
    """Monta um cenario completo (hospitais, frota, matrizes) reaproveitado pelos testes."""
    df_matriz = carregar_matriz_distancias()
    df_hospitais_base = construir_lista_hospitais_base(df_matriz)
    hospitais = gerar_demandas_hospitais(df_hospitais_base)
    hospitais_por_id = {hospital.id: hospital for hospital in hospitais}
    hospital_ids = [hospital.id for hospital in hospitais]

    frota = carregar_frota()
    matriz_distancias_km = construir_matriz_custos(df_matriz, hospital_ids, metrica="distance_km")
    matriz_duracoes_min = construir_matriz_custos(df_matriz, hospital_ids, metrica="duration_minutes")
    indice_por_id = {hospital_id: posicao for posicao, hospital_id in enumerate(hospital_ids)}

    return df_matriz, hospitais, hospitais_por_id, hospital_ids, frota, matriz_distancias_km, matriz_duracoes_min, indice_por_id


def test_carregar_matriz_distancias_e_hospitais():
    """A matriz deve carregar somente pares com status ok e gerar hospitais unicos e validos."""
    df_matriz = carregar_matriz_distancias()
    assert (df_matriz["status"] == "ok").all()

    df_hospitais_base = construir_lista_hospitais_base(df_matriz)
    assert df_hospitais_base["id"].is_unique
    assert len(df_hospitais_base) > 0


def test_gerar_demandas_hospitais_e_deterministico():
    """A geracao de demanda/prioridade deve ser reproduzivel para a mesma seed."""
    df_matriz = carregar_matriz_distancias()
    df_hospitais_base = construir_lista_hospitais_base(df_matriz)

    hospitais_1 = gerar_demandas_hospitais(df_hospitais_base, seed=config.RANDOM_SEED)
    hospitais_2 = gerar_demandas_hospitais(df_hospitais_base, seed=config.RANDOM_SEED)

    assert [h.demand_kg for h in hospitais_1] == [h.demand_kg for h in hospitais_2]
    assert [h.priority for h in hospitais_1] == [h.priority for h in hospitais_2]
    assert all(config.DEMANDA_KG_MIN <= h.demand_kg <= config.DEMANDA_KG_MAX for h in hospitais_1)


def test_carregar_frota_calcula_autonomia_positiva():
    """Cada veiculo da frota deve ter autonomia e capacidade positivas."""
    frota = carregar_frota(tamanho_frota=config.TAMANHO_FROTA)
    assert len(frota) == config.TAMANHO_FROTA
    for veiculo in frota:
        assert veiculo.autonomy_km > 0
        assert veiculo.capacity_kg > 0


def test_decodificar_rota_gigante_respeita_capacidade_e_autonomia():
    """As rotas decodificadas nunca devem ultrapassar a capacidade ou autonomia do veiculo."""
    (_df_matriz, _hospitais, hospitais_por_id, hospital_ids, _frota,
     matriz_distancias_km, matriz_duracoes_min, indice_por_id) = _carregar_cenario_teste()

    # Frota pequena e com capacidade reduzida para forcar a divisao em multiplas rotas
    frota_reduzida = [
        Vehicle(id=1, brand="TESTE", model="A", version="1", fuel_type="F",
                consumption_city_km_l=10.0, consumption_road_km_l=12.0,
                tank_liters=20.0, capacity_kg=80.0),
        Vehicle(id=2, brand="TESTE", model="B", version="1", fuel_type="F",
                consumption_city_km_l=10.0, consumption_road_km_l=12.0,
                tank_liters=20.0, capacity_kg=80.0),
    ]

    genes = [hid for hid in hospital_ids if hid != config.DEPOT_HOSPITAL_ID]
    solucao = decodificar_rota_gigante(
        tuple(genes), frota_reduzida, hospitais_por_id, config.DEPOT_HOSPITAL_ID,
        indice_por_id, matriz_distancias_km, matriz_duracoes_min,
    )

    for rota in solucao.routes:
        assert rota.load_kg <= rota.vehicle.capacity_kg + 1e-6
        assert rota.distance_km <= rota.vehicle.autonomy_km + 1e-6


def test_algoritmo_genetico_melhora_fitness_em_relacao_a_baseline():
    """O GA (mesmo com poucas geracoes) deve encontrar uma solucao pelo menos tao boa quanto a baseline."""
    (_df_matriz, _hospitais, hospitais_por_id, hospital_ids, frota,
     matriz_distancias_km, matriz_duracoes_min, indice_por_id) = _carregar_cenario_teste()

    baseline = calcular_solucao_baseline(
        hospital_ids, hospitais_por_id, frota, config.DEPOT_HOSPITAL_ID,
        indice_por_id, matriz_distancias_km, matriz_duracoes_min,
    )

    melhor_solucao, historico_fitness = executar_algoritmo_genetico_vrp(
        hospital_ids, hospitais_por_id, frota, config.DEPOT_HOSPITAL_ID,
        indice_por_id, matriz_distancias_km, matriz_duracoes_min,
        population_size=30, n_generations=25, mutation_probability=0.4, elite_size=2,
    )

    assert len(historico_fitness) == 25
    # Fitness deve ser nao-crescente ao longo das geracoes (elitismo garante isso)
    assert all(historico_fitness[i] >= historico_fitness[i + 1] - 1e-9 for i in range(len(historico_fitness) - 1))
    assert melhor_solucao.fitness <= baseline.fitness


def test_calcular_coordenadas_mds_preserva_dimensoes():
    """A projecao MDS deve retornar uma coordenada 2D por hospital."""
    (_df_matriz, _hospitais, _hospitais_por_id, hospital_ids, _frota,
     matriz_distancias_km, _matriz_duracoes_min, _indice_por_id) = _carregar_cenario_teste()

    coordenadas = calcular_coordenadas_mds(matriz_distancias_km)
    assert coordenadas.shape == (len(hospital_ids), 2)


def test_fitness_penaliza_entregas_nao_atendidas():
    """Uma solucao com hospitais nao atendidos deve ter fitness maior que uma sem pendencias."""
    (_df_matriz, _hospitais, hospitais_por_id, _hospital_ids, _frota,
     _matriz_distancias_km, _matriz_duracoes_min, _indice_por_id) = _carregar_cenario_teste()

    from tsp.models import VehicleRoute, VrpSolution

    veiculo_generico = Vehicle(id=1, brand="TESTE", model="A", version="1", fuel_type="F",
                                consumption_city_km_l=10.0, consumption_road_km_l=12.0,
                                tank_liters=20.0, capacity_kg=1000.0)
    algum_id = next(iter(hospitais_por_id))

    solucao_sem_pendencia = VrpSolution(
        routes=[VehicleRoute(vehicle=veiculo_generico, hospital_ids=[algum_id], distance_km=10.0, duration_min=10.0, load_kg=10.0)],
        unassigned_hospital_ids=[],
    )
    solucao_com_pendencia = VrpSolution(
        routes=[VehicleRoute(vehicle=veiculo_generico, hospital_ids=[algum_id], distance_km=10.0, duration_min=10.0, load_kg=10.0)],
        unassigned_hospital_ids=[algum_id],
    )

    fitness_sem_pendencia = calcular_fitness_vrp(solucao_sem_pendencia, hospitais_por_id)
    fitness_com_pendencia = calcular_fitness_vrp(solucao_com_pendencia, hospitais_por_id)

    assert fitness_com_pendencia > fitness_sem_pendencia
