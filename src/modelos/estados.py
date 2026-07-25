"""Estados del ciclo de vida de un proceso."""

from enum import Enum


class EstadoProceso(Enum):
    """
    Ciclo de vida modelado por el simulador:

        NUEVO -> LISTO -> EJECUCION -> TERMINADO
                   ^          |
                   |          v
                   +----- BLOQUEADO   (solicitud de E/S)

    NUEVO es la cola de admision: el proceso ya llego al sistema pero todavia no
    tiene memoria asignada, asi que el planificador a largo plazo aun no lo deja
    competir por la CPU.
    """

    NUEVO = "nuevo"
    LISTO = "listo"
    EJECUCION = "ejecucion"
    BLOQUEADO = "bloqueado"
    TERMINADO = "terminado"

    @property
    def etiqueta(self) -> str:
        return _ETIQUETAS[self]


_ETIQUETAS = {
    EstadoProceso.NUEVO: "Nuevo",
    EstadoProceso.LISTO: "Listo",
    EstadoProceso.EJECUCION: "En ejecucion",
    EstadoProceso.BLOQUEADO: "Bloqueado (E/S)",
    EstadoProceso.TERMINADO: "Terminado",
}

TRANSICIONES_VALIDAS = {
    EstadoProceso.NUEVO: {EstadoProceso.LISTO},
    EstadoProceso.LISTO: {EstadoProceso.EJECUCION},
    EstadoProceso.EJECUCION: {
        EstadoProceso.LISTO,
        EstadoProceso.BLOQUEADO,
        EstadoProceso.TERMINADO,
    },
    EstadoProceso.BLOQUEADO: {EstadoProceso.LISTO},
    EstadoProceso.TERMINADO: set(),
}


def transicion_permitida(origen: EstadoProceso, destino: EstadoProceso) -> bool:
    return destino in TRANSICIONES_VALIDAS[origen]
