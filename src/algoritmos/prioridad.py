"""Planificacion por prioridad, con envejecimiento contra la inanicion."""

from .base import AlgoritmoPlanificacion
from ..modelos.proceso import Proceso


class PorPrioridad(AlgoritmoPlanificacion):
    """
    Menor numero de prioridad significa mayor urgencia.

    Con `envejecimiento > 0` la prioridad efectiva mejora un nivel por cada N
    ticks de espera acumulada, de forma que un proceso poco prioritario termina
    ganando la CPU en lugar de morir de inanicion.
    """

    nombre = "prioridad"
    etiqueta = "Prioridad"
    apropiativo = False

    def prioridad_efectiva(self, proceso: Proceso) -> int:
        ticks = self.configuracion.envejecimiento
        if ticks <= 0:
            return proceso.prioridad
        return proceso.prioridad - proceso.ticks_espera // ticks

    def clave_orden(self, proceso: Proceso, reloj: int) -> tuple:
        return (self.prioridad_efectiva(proceso), proceso.secuencia_listos)


class PorPrioridadApropiativa(PorPrioridad):
    nombre = "prioridad_apropiativa"
    etiqueta = "Prioridad apropiativa"
    apropiativo = True
