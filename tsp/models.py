# -*- coding: utf-8 -*-
"""
Estruturas de dados (dataclasses) do dominio de otimizacao de rotas medicas.

Nomenclatura de classes e atributos em ingles; comentarios e docstrings em
portugues do Brasil, conforme convencao do projeto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class DeliveryPriority(IntEnum):
    """Prioridade de entrega dos insumos/medicamentos para um hospital."""

    REGULAR = 1
    CRITICAL = 2

    @property
    def penalty_weight(self) -> float:
        """Peso multiplicador de penalidade por atraso, maior para entregas criticas."""
        return 3.0 if self is DeliveryPriority.CRITICAL else 1.0


@dataclass(frozen=True)
class Hospital:
    """Representa um ponto de entrega (hospital/unidade) na rede logistica."""

    id: int
    name: str
    district: str
    demand_kg: float
    priority: DeliveryPriority


@dataclass(frozen=True)
class Vehicle:
    """Representa um veiculo da frota disponivel para as entregas."""

    id: int
    brand: str
    model: str
    version: str
    fuel_type: str
    consumption_city_km_l: float
    consumption_road_km_l: float
    tank_liters: float
    capacity_kg: float

    @property
    def autonomy_km(self) -> float:
        """Autonomia estimada (km) usando o consumo urbano e o tanque cheio."""
        return self.tank_liters * self.consumption_city_km_l


@dataclass
class VehicleRoute:
    """Rota unica atribuida a um veiculo, partindo e retornando ao deposito."""

    vehicle: Vehicle
    hospital_ids: list[int] = field(default_factory=list)
    distance_km: float = 0.0
    duration_min: float = 0.0
    load_kg: float = 0.0

    @property
    def is_within_capacity(self) -> bool:
        """Indica se a carga da rota respeita a capacidade do veiculo."""
        return self.load_kg <= self.vehicle.capacity_kg

    @property
    def is_within_autonomy(self) -> bool:
        """Indica se a distancia da rota respeita a autonomia do veiculo."""
        return self.distance_km <= self.vehicle.autonomy_km


@dataclass
class VrpSolution:
    """Solucao completa do problema de roteamento de veiculos (VRP)."""

    routes: list[VehicleRoute] = field(default_factory=list)
    unassigned_hospital_ids: list[int] = field(default_factory=list)
    fitness: float = 0.0

    @property
    def total_distance_km(self) -> float:
        """Soma da distancia percorrida por todas as rotas da solucao."""
        return sum(route.distance_km for route in self.routes)

    @property
    def total_duration_min(self) -> float:
        """Soma da duracao estimada de todas as rotas da solucao."""
        return sum(route.duration_min for route in self.routes)

    @property
    def vehicles_used(self) -> int:
        """Quantidade de veiculos efetivamente utilizados (rotas nao vazias)."""
        return sum(1 for route in self.routes if route.hospital_ids)
