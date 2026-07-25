"""Registro de algoritmos de planificacion disponibles."""

from .base import AlgoritmoPlanificacion
from .fcfs import PrimeroEnLlegar
from .prioridad import PorPrioridad, PorPrioridadApropiativa
from .round_robin import RoundRobin
from .sjf import TrabajoMasCorto, TrabajoMasCortoApropiativo

ALGORITMOS: dict[str, type[AlgoritmoPlanificacion]] = {
    clase.nombre: clase
    for clase in (
        PrimeroEnLlegar,
        TrabajoMasCorto,
        TrabajoMasCortoApropiativo,
        RoundRobin,
        PorPrioridad,
        PorPrioridadApropiativa,
    )
}

NOMBRES_ALGORITMOS: dict[str, str] = {
    nombre: clase.etiqueta for nombre, clase in ALGORITMOS.items()
}


def crear_algoritmo(nombre: str, configuracion) -> AlgoritmoPlanificacion:
    clase = ALGORITMOS.get(nombre)
    if clase is None:
        raise ValueError(
            f"Algoritmo desconocido: '{nombre}'. Disponibles: {', '.join(ALGORITMOS)}."
        )
    return clase(configuracion)


__all__ = ["ALGORITMOS", "NOMBRES_ALGORITMOS", "AlgoritmoPlanificacion", "crear_algoritmo"]
