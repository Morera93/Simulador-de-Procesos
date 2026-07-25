"""Round Robin: turnos de CPU acotados por un quantum configurable."""

from .base import AlgoritmoPlanificacion
from ..modelos.proceso import Proceso


class RoundRobin(AlgoritmoPlanificacion):
    """
    Selecciona en orden FIFO (igual que FCFS) pero expropia al agotarse el
    quantum. El quantum se lee de la configuracion en cada evaluacion, de modo
    que cambiarlo durante la simulacion afecta al turno en curso.
    """

    nombre = "round_robin"
    etiqueta = "Round Robin (por quantum)"
    apropiativo = True

    def debe_expropiar(
        self,
        en_ejecucion: Proceso,
        cola_listos: list[Proceso],
        ticks_en_nucleo: int,
        reloj: int,
    ) -> bool:
        if not cola_listos:
            return False
        return ticks_en_nucleo >= self.configuracion.quantum

    def orden_expropiacion(self, nucleo, reloj: int) -> tuple:
        """Se expropia primero al nucleo que lleva mas tiempo sin ceder el turno."""
        return (nucleo.ticks_en_proceso,)
