"""Recurso CPU: nucleos, cambio de contexto y traza de ocupacion."""

from dataclasses import dataclass, field

from ..modelos.proceso import Proceso

MAXIMO_SEGMENTOS = 600


@dataclass
class Nucleo:
    """Un nucleo fisico: ejecuta a lo sumo un proceso por tick."""

    indice: int
    proceso: Proceso | None = None
    ticks_en_proceso: int = 0
    cambio_pendiente: int = 0
    ticks_utiles: int = 0
    ticks_sobrecarga: int = 0
    ticks_ocioso: int = 0
    ultimo_pid: int | None = None
    segmento: dict | None = field(default=None, repr=False)

    @property
    def libre(self) -> bool:
        return self.proceso is None

    @property
    def conmutando(self) -> bool:
        return self.cambio_pendiente > 0

    def como_diccionario(self) -> dict:
        return {
            "indice": self.indice,
            "pid": self.proceso.pid if self.proceso else None,
            "nombre": self.proceso.nombre if self.proceso else None,
            "cpu_restante": self.proceso.cpu_restante if self.proceso else None,
            "avance": self.proceso.porcentaje_avance if self.proceso else 0,
            "ticks_en_proceso": self.ticks_en_proceso,
            "conmutando": self.conmutando,
            "ticks_utiles": self.ticks_utiles,
            "ticks_sobrecarga": self.ticks_sobrecarga,
            "ticks_ocioso": self.ticks_ocioso,
        }


class CPU:
    """
    Agrupa los nucleos y contabiliza en que se gasta cada tick: trabajo util,
    sobrecarga por cambio de contexto o tiempo ocioso. Esa separacion es la que
    permite medir el costo real de cada politica de planificacion.
    """

    def __init__(self, cantidad_nucleos: int = 1):
        self.nucleos = [Nucleo(indice) for indice in range(cantidad_nucleos)]
        self.segmentos: list[dict] = []

    @property
    def cantidad_nucleos(self) -> int:
        return len(self.nucleos)

    @property
    def nucleos_libres(self) -> list[Nucleo]:
        return [nucleo for nucleo in self.nucleos if nucleo.libre]

    @property
    def nucleos_ocupados(self) -> int:
        return sum(1 for nucleo in self.nucleos if not nucleo.libre)

    @property
    def porcentaje_uso(self) -> float:
        return round(self.nucleos_ocupados / self.cantidad_nucleos * 100, 1)

    @property
    def ticks_utiles(self) -> int:
        return sum(nucleo.ticks_utiles for nucleo in self.nucleos)

    @property
    def ticks_sobrecarga(self) -> int:
        return sum(nucleo.ticks_sobrecarga for nucleo in self.nucleos)

    @property
    def ticks_ocioso(self) -> int:
        return sum(nucleo.ticks_ocioso for nucleo in self.nucleos)

    @property
    def rendimiento_util(self) -> float:
        """Porcentaje de los ticks de nucleo dedicados a trabajo real."""
        total = self.ticks_utiles + self.ticks_sobrecarga + self.ticks_ocioso
        if total == 0:
            return 0.0
        return round(self.ticks_utiles / total * 100, 1)

    def asignar(self, nucleo: Nucleo, proceso: Proceso, tick: int, costo_cambio: int) -> None:
        # Optimizacion: si el nucleo vuelve a recibir el proceso que acaba de
        # dejar, su contexto sigue cargado y no hay conmutacion que pagar.
        reanuda = nucleo.ultimo_pid == proceso.pid
        nucleo.proceso = proceso
        nucleo.ticks_en_proceso = 0
        nucleo.cambio_pendiente = 0 if reanuda else costo_cambio
        proceso.nucleo_asignado = nucleo.indice
        if not reanuda:
            proceso.cambios_contexto += 1
        nucleo.segmento = {
            "pid": proceso.pid,
            "nucleo": nucleo.indice,
            "inicio": tick,
            "fin": None,
        }
        self.segmentos.append(nucleo.segmento)
        del self.segmentos[:-MAXIMO_SEGMENTOS]

    def liberar(self, nucleo: Nucleo, tick: int) -> Proceso | None:
        proceso = nucleo.proceso
        if nucleo.segmento is not None:
            nucleo.segmento["fin"] = tick
        nucleo.proceso = None
        nucleo.segmento = None
        nucleo.ticks_en_proceso = 0
        nucleo.cambio_pendiente = 0
        if proceso is not None:
            nucleo.ultimo_pid = proceso.pid
            proceso.nucleo_asignado = None
        return proceso

    def ejecutar_tick(self) -> None:
        """Avanza un tick en cada nucleo, separando sobrecarga de trabajo util."""
        for nucleo in self.nucleos:
            if nucleo.libre:
                nucleo.ticks_ocioso += 1
            elif nucleo.conmutando:
                nucleo.cambio_pendiente -= 1
                nucleo.ticks_sobrecarga += 1
            else:
                nucleo.proceso.consumir_cpu()
                nucleo.ticks_en_proceso += 1
                nucleo.ticks_utiles += 1

    def redimensionar(self, cantidad: int, tick: int) -> list[Proceso]:
        """
        Ajusta el numero de nucleos en caliente. Al reducir, los procesos de los
        nucleos eliminados se devuelven para que el planificador los reencole.
        """
        if cantidad == self.cantidad_nucleos:
            return []
        if cantidad > self.cantidad_nucleos:
            self.nucleos.extend(
                Nucleo(indice) for indice in range(self.cantidad_nucleos, cantidad)
            )
            return []

        desalojados = []
        for nucleo in self.nucleos[cantidad:]:
            proceso = self.liberar(nucleo, tick)
            if proceso is not None:
                desalojados.append(proceso)
        del self.nucleos[cantidad:]
        return desalojados

    def linea_tiempo(self, tick: int, ventana: int = 120) -> list[dict]:
        """
        Segmentos del diagrama de Gantt dentro de los ultimos `ventana` ticks.
        Los segmentos abiertos se cierran en el tick actual para dibujarlos.
        """
        desde = max(0, tick - ventana)
        return [
            {**segmento, "fin": tick if segmento["fin"] is None else segmento["fin"]}
            for segmento in self.segmentos
            if segmento["fin"] is None or segmento["fin"] > desde
        ]

    def como_diccionario(self) -> dict:
        return {
            "nucleos": [nucleo.como_diccionario() for nucleo in self.nucleos],
            "porcentaje_uso": self.porcentaje_uso,
            "ticks_utiles": self.ticks_utiles,
            "ticks_sobrecarga": self.ticks_sobrecarga,
            "ticks_ocioso": self.ticks_ocioso,
            "rendimiento_util": self.rendimiento_util,
        }
