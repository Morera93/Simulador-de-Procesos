"""SJF (Shortest Job First) y su variante apropiativa SRTF."""

from .base import AlgoritmoPlanificacion
from ..modelos.proceso import Proceso


class TrabajoMasCorto(AlgoritmoPlanificacion):
    """
    Prioriza la rafaga de CPU restante mas corta. En modo apropiativo (SRTF) un
    proceso recien llegado con menos trabajo pendiente desaloja al que ocupa la
    CPU, lo que baja el tiempo de espera promedio a costa de mas cambios de
    contexto.
    """

    nombre = "sjf"
    etiqueta = "SJF (trabajo mas corto)"
    apropiativo = False

    def clave_orden(self, proceso: Proceso, reloj: int) -> tuple:
        return (proceso.cpu_restante, proceso.secuencia_listos)


class TrabajoMasCortoApropiativo(TrabajoMasCorto):
    nombre = "srtf"
    etiqueta = "SRTF (SJF apropiativo)"
    apropiativo = True
