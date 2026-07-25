"""Registro de actividades y metricas de desempeno."""

from .metricas import CalculadoraMetricas
from .registro import CATEGORIAS, Evento, RegistroActividades

__all__ = ["CalculadoraMetricas", "RegistroActividades", "Evento", "CATEGORIAS"]
