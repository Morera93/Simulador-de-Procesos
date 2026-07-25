"""Contrato comun de los algoritmos de planificacion (patron Estrategia)."""

from abc import ABC

from ..modelos.proceso import Proceso


class AlgoritmoPlanificacion(ABC):
    """
    Cada algoritmo solo define como ordenar la cola de listos mediante
    `clave_orden`; la seleccion y la logica de expropiacion son comunes.

    La clave siempre termina en el numero de secuencia de encolado para que los
    empates se resuelvan por orden de llegada a la cola y la simulacion sea
    reproducible.
    """

    nombre = "base"
    etiqueta = "Base"
    apropiativo = False

    def __init__(self, configuracion):
        self.configuracion = configuracion

    def clave_orden(self, proceso: Proceso, reloj: int) -> tuple:
        return (proceso.secuencia_listos,)

    def seleccionar(self, cola_listos: list[Proceso], reloj: int) -> Proceso | None:
        if not cola_listos:
            return None
        return min(cola_listos, key=lambda proceso: self.clave_orden(proceso, reloj))

    def debe_expropiar(
        self,
        en_ejecucion: Proceso,
        cola_listos: list[Proceso],
        ticks_en_nucleo: int,
        reloj: int,
    ) -> bool:
        if not self.apropiativo or not cola_listos:
            return False
        candidato = self.seleccionar(cola_listos, reloj)
        return self.clave_orden(candidato, reloj) < self.clave_orden(en_ejecucion, reloj)

    def orden_expropiacion(self, nucleo, reloj: int) -> tuple:
        """
        Criterio para decidir a que nucleo se expropia primero cuando hay menos
        candidatos que nucleos. El planificador ordena de mayor a menor, asi que
        la clave mas alta corresponde al proceso menos merecedor de la CPU.
        """
        return self.clave_orden(nucleo.proceso, reloj)
