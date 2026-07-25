"""Bloque de Control de Proceso (PCB): el modelo central del simulador."""

from dataclasses import dataclass, field

from .estados import EstadoProceso, transicion_permitida


@dataclass
class Proceso:
    """
    Representa un proceso y toda la informacion que el sistema operativo
    necesita para administrarlo.

    El modelo de ejecucion es CPU -> E/S -> CPU: el proceso consume CPU, a mitad
    de su rafaga solicita una operacion de entrada/salida que lo bloquea y
    despues vuelve a competir por el procesador. Se modela una sola operacion de
    E/S por proceso para mantener la traza legible durante la demostracion.
    """

    pid: int
    nombre: str
    tiempo_llegada: int
    rafaga_cpu: int
    rafaga_es: int = 0
    prioridad: int = 3
    memoria_kb: int = 64

    estado: EstadoProceso = EstadoProceso.NUEVO
    cpu_restante: int = field(init=False)
    es_restante: int = field(init=False)
    cpu_consumida: int = 0
    operaciones_es: int = 0

    tick_admision: int | None = None
    tick_primer_despacho: int | None = None
    tick_finalizacion: int | None = None

    ticks_espera: int = 0
    ticks_bloqueado: int = 0
    cambios_contexto: int = 0
    secuencia_listos: int = 0
    direccion_memoria: int | None = None
    nucleo_asignado: int | None = None
    historial: list[tuple[int, EstadoProceso]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cpu_restante = self.rafaga_cpu
        self.es_restante = self.rafaga_es

    @property
    def punto_solicitud_es(self) -> int:
        """Ticks de CPU que consume antes de pedir E/S (mitad de su rafaga)."""
        return max(1, self.rafaga_cpu // 2)

    @property
    def solicita_es(self) -> bool:
        return (
            self.rafaga_es > 0
            and self.operaciones_es == 0
            and self.cpu_consumida >= self.punto_solicitud_es
        )

    @property
    def finalizo(self) -> bool:
        return self.cpu_restante <= 0

    @property
    def tiempo_retorno(self) -> int | None:
        if self.tick_finalizacion is None:
            return None
        return self.tick_finalizacion - self.tiempo_llegada

    @property
    def tiempo_respuesta(self) -> int | None:
        if self.tick_primer_despacho is None:
            return None
        return self.tick_primer_despacho - self.tiempo_llegada

    @property
    def porcentaje_avance(self) -> float:
        if self.rafaga_cpu == 0:
            return 100.0
        return round(self.cpu_consumida / self.rafaga_cpu * 100, 1)

    def cambiar_estado(self, nuevo: EstadoProceso, tick: int) -> None:
        if nuevo is self.estado:
            return
        if not transicion_permitida(self.estado, nuevo):
            raise ValueError(
                f"Transicion invalida para el proceso {self.pid}: "
                f"{self.estado.etiqueta} -> {nuevo.etiqueta}"
            )
        self.estado = nuevo
        self.historial.append((tick, nuevo))

    def consumir_cpu(self, ticks: int = 1) -> None:
        self.cpu_restante = max(0, self.cpu_restante - ticks)
        self.cpu_consumida += ticks

    def consumir_es(self, ticks: int = 1) -> None:
        self.es_restante = max(0, self.es_restante - ticks)

    def como_diccionario(self) -> dict:
        """Proyeccion plana del PCB para las vistas (consola y web)."""
        return {
            "pid": self.pid,
            "nombre": self.nombre,
            "estado": self.estado.value,
            "estado_etiqueta": self.estado.etiqueta,
            "tiempo_llegada": self.tiempo_llegada,
            "rafaga_cpu": self.rafaga_cpu,
            "rafaga_es": self.rafaga_es,
            "prioridad": self.prioridad,
            "memoria_kb": self.memoria_kb,
            "cpu_restante": self.cpu_restante,
            "es_restante": self.es_restante,
            "avance": self.porcentaje_avance,
            "espera": self.ticks_espera,
            "bloqueado": self.ticks_bloqueado,
            "retorno": self.tiempo_retorno,
            "respuesta": self.tiempo_respuesta,
            "cambios_contexto": self.cambios_contexto,
            "direccion_memoria": self.direccion_memoria,
            "nucleo": self.nucleo_asignado,
        }
