"""Modelos de datos del simulador."""

from .estados import EstadoProceso, transicion_permitida
from .proceso import Proceso

__all__ = ["EstadoProceso", "Proceso", "transicion_permitida"]
