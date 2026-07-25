"""Subsistema de entrada/salida: dispositivos y cola de peticiones."""

from dataclasses import dataclass

from ..modelos.proceso import Proceso


@dataclass
class DispositivoES:
    """Dispositivo que atiende una peticion de E/S a la vez."""

    indice: int
    proceso: Proceso | None = None
    ticks_ocupado: int = 0
    ticks_ocioso: int = 0
    operaciones_atendidas: int = 0

    @property
    def libre(self) -> bool:
        return self.proceso is None

    def como_diccionario(self) -> dict:
        return {
            "indice": self.indice,
            "pid": self.proceso.pid if self.proceso else None,
            "nombre": self.proceso.nombre if self.proceso else None,
            "es_restante": self.proceso.es_restante if self.proceso else None,
            "ticks_ocupado": self.ticks_ocupado,
            "ticks_ocioso": self.ticks_ocioso,
            "operaciones_atendidas": self.operaciones_atendidas,
        }


class SubsistemaES:
    """
    Modela el cuello de botella tipico de la E/S: hay menos dispositivos que
    procesos, asi que las peticiones que no encuentran dispositivo libre esperan
    en una cola FIFO. El tiempo en esa cola se contabiliza como bloqueo.
    """

    def __init__(self, cantidad_dispositivos: int = 1):
        self.dispositivos = [DispositivoES(indice) for indice in range(cantidad_dispositivos)]
        self.cola_espera: list[Proceso] = []

    @property
    def cantidad_dispositivos(self) -> int:
        return len(self.dispositivos)

    @property
    def dispositivos_ocupados(self) -> int:
        return sum(1 for dispositivo in self.dispositivos if not dispositivo.libre)

    @property
    def porcentaje_uso(self) -> float:
        return round(self.dispositivos_ocupados / self.cantidad_dispositivos * 100, 1)

    @property
    def operaciones_atendidas(self) -> int:
        return sum(dispositivo.operaciones_atendidas for dispositivo in self.dispositivos)

    def solicitar(self, proceso: Proceso) -> None:
        self.cola_espera.append(proceso)

    def asignar_pendientes(self) -> list[tuple[Proceso, int]]:
        """Entrega la cola de espera a los dispositivos libres, en orden FIFO."""
        asignados = []
        for dispositivo in self.dispositivos:
            if not self.cola_espera:
                break
            if dispositivo.libre:
                proceso = self.cola_espera.pop(0)
                dispositivo.proceso = proceso
                asignados.append((proceso, dispositivo.indice))
        return asignados

    def ejecutar_tick(self) -> list[Proceso]:
        """Avanza un tick de E/S y devuelve los procesos cuya operacion termino."""
        completados = []
        for dispositivo in self.dispositivos:
            if dispositivo.libre:
                dispositivo.ticks_ocioso += 1
                continue

            dispositivo.proceso.consumir_es()
            dispositivo.ticks_ocupado += 1
            if dispositivo.proceso.es_restante <= 0:
                dispositivo.operaciones_atendidas += 1
                completados.append(dispositivo.proceso)
                dispositivo.proceso = None
        return completados

    def redimensionar(self, cantidad: int) -> None:
        """
        Ajusta el numero de dispositivos en caliente. Al reducir, los procesos
        que estaban siendo atendidos vuelven al frente de la cola de espera sin
        perder el progreso de su operacion.
        """
        if cantidad >= self.cantidad_dispositivos:
            self.dispositivos.extend(
                DispositivoES(indice)
                for indice in range(self.cantidad_dispositivos, cantidad)
            )
            return

        devueltos = [
            dispositivo.proceso
            for dispositivo in self.dispositivos[cantidad:]
            if not dispositivo.libre
        ]
        del self.dispositivos[cantidad:]
        self.cola_espera[:0] = devueltos

    def como_diccionario(self) -> dict:
        return {
            "dispositivos": [d.como_diccionario() for d in self.dispositivos],
            "porcentaje_uso": self.porcentaje_uso,
            "operaciones_atendidas": self.operaciones_atendidas,
            "cola_espera": [
                {"pid": p.pid, "nombre": p.nombre, "es_restante": p.es_restante}
                for p in self.cola_espera
            ],
        }
