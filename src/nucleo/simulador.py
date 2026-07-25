"""
Nucleo del simulador: reloj, bucle de ejecucion y fachada para las interfaces.

Toda mutacion pasa por un unico cerrojo reentrante, de modo que el hilo del
reloj y las peticiones de la interfaz (consola o web) nunca ven un estado a
medio actualizar.
"""

import threading
from datetime import datetime
from enum import Enum
from pathlib import Path

from ..config import PARAMETROS, ConfiguracionSimulacion
from ..modelos.proceso import Proceso
from ..recursos.cpu import CPU
from ..recursos.dispositivos_es import SubsistemaES
from ..recursos.memoria import GestorMemoria
from ..reportes.metricas import CalculadoraMetricas
from ..reportes.registro import RegistroActividades
from .entrada import crear_proceso, generar_aleatorios
from .planificador import Planificador

DIRECTORIO_REPORTES = Path("reportes_generados")


class EstadoSimulacion(Enum):
    DETENIDA = "detenida"
    EJECUTANDO = "ejecutando"
    PAUSADA = "pausada"
    FINALIZADA = "finalizada"

    @property
    def etiqueta(self) -> str:
        return {
            EstadoSimulacion.DETENIDA: "Detenida",
            EstadoSimulacion.EJECUTANDO: "En ejecucion",
            EstadoSimulacion.PAUSADA: "Pausada",
            EstadoSimulacion.FINALIZADA: "Finalizada",
        }[self]


def _definicion(proceso: Proceso) -> dict:
    return {
        "pid": proceso.pid,
        "nombre": proceso.nombre,
        "tiempo_llegada": proceso.tiempo_llegada,
        "rafaga_cpu": proceso.rafaga_cpu,
        "rafaga_es": proceso.rafaga_es,
        "prioridad": proceso.prioridad,
        "memoria_kb": proceso.memoria_kb,
    }


class Simulador:
    def __init__(
        self,
        configuracion: ConfiguracionSimulacion | None = None,
        procesos: list[Proceso] | None = None,
    ):
        self.configuracion = configuracion or ConfiguracionSimulacion()
        self.definiciones = [_definicion(proceso) for proceso in procesos or []]
        self._bloqueo = threading.RLock()
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None
        self._construir()

    # ------------------------------------------------------------ construccion

    def _construir(self) -> None:
        """Crea el sistema completo desde cero a partir de la configuracion."""
        self.reloj = 0
        self.estado = EstadoSimulacion.DETENIDA
        self.registro = RegistroActividades()
        self.cpu = CPU(self.configuracion.nucleos_cpu)
        self.memoria = GestorMemoria(
            self.configuracion.memoria_total_kb, self.configuracion.politica_memoria
        )
        self.dispositivos_es = SubsistemaES(self.configuracion.dispositivos_es)
        self.metricas = CalculadoraMetricas(self.cpu, self.memoria, self.dispositivos_es)
        self.planificador = Planificador(
            self.configuracion, self.cpu, self.memoria, self.dispositivos_es, self.registro
        )
        self.registro.registrar(
            0,
            "sistema",
            f"Sistema iniciado con {len(self.definiciones)} procesos, "
            f"{self.configuracion.nucleos_cpu} nucleos, "
            f"{self.configuracion.memoria_total_kb} KB de memoria y "
            f"{self.configuracion.dispositivos_es} dispositivos de E/S",
        )
        for definicion in self.definiciones:
            self.planificador.agregar(Proceso(**definicion))

    @property
    def siguiente_pid(self) -> int:
        return max((d["pid"] for d in self.definiciones), default=0) + 1

    # ------------------------------------------------------- entrada de datos

    def cargar(self, procesos: list[Proceso]) -> None:
        with self._bloqueo:
            self.definiciones = [_definicion(proceso) for proceso in procesos]
            self._construir()

    def agregar_proceso(self, datos: dict) -> Proceso:
        """Alta manual de un proceso, incluso con la simulacion en marcha."""
        with self._bloqueo:
            proceso = crear_proceso(datos, pid=self.siguiente_pid)
            if proceso.tiempo_llegada < self.reloj:
                proceso.tiempo_llegada = self.reloj
            self.definiciones.append(_definicion(proceso))
            self.planificador.agregar(proceso)
            if self.estado is EstadoSimulacion.FINALIZADA:
                self.estado = EstadoSimulacion.PAUSADA
            return proceso

    def generar_procesos(self, cantidad: int, semilla: int | None = None) -> list[Proceso]:
        with self._bloqueo:
            procesos = generar_aleatorios(
                cantidad, pid_inicial=self.siguiente_pid, tick_inicial=self.reloj, semilla=semilla
            )
            for proceso in procesos:
                self.definiciones.append(_definicion(proceso))
                self.planificador.agregar(proceso)
            self.registro.registrar(
                self.reloj, "llegada", f"Se genero una carga de {len(procesos)} procesos"
            )
            if self.estado is EstadoSimulacion.FINALIZADA:
                self.estado = EstadoSimulacion.PAUSADA
            return procesos

    # --------------------------------------------------------------- control

    def avanzar(self) -> None:
        """Ejecuta un tick completo de la simulacion."""
        with self._bloqueo:
            self.planificador.tick(self.reloj)
            self.reloj += 1
            self.metricas.muestrear(self.reloj, self.planificador.procesos)
            if self.planificador.finalizada:
                self.estado = EstadoSimulacion.FINALIZADA
                self.registro.registrar(
                    self.reloj, "sistema", f"Simulacion finalizada en {self.reloj} ticks"
                )

    def paso(self) -> None:
        with self._bloqueo:
            if self.estado is EstadoSimulacion.FINALIZADA:
                return
            self.estado = EstadoSimulacion.PAUSADA
            self.avanzar()

    def iniciar(self) -> None:
        with self._bloqueo:
            if self.estado is EstadoSimulacion.FINALIZADA:
                return
            self.estado = EstadoSimulacion.EJECUTANDO
            if self._hilo is not None and self._hilo.is_alive():
                return
            self._detener.clear()
            self._hilo = threading.Thread(target=self._bucle, name="reloj", daemon=True)
            self._hilo.start()

    def pausar(self) -> None:
        with self._bloqueo:
            if self.estado is EstadoSimulacion.EJECUTANDO:
                self.estado = EstadoSimulacion.PAUSADA

    def alternar(self) -> None:
        if self.estado is EstadoSimulacion.EJECUTANDO:
            self.pausar()
        else:
            self.iniciar()

    def detener(self) -> None:
        self._detener.set()
        hilo = self._hilo
        if hilo is not None and hilo.is_alive():
            hilo.join(timeout=2)
        self._hilo = None
        with self._bloqueo:
            if self.estado is EstadoSimulacion.EJECUTANDO:
                self.estado = EstadoSimulacion.PAUSADA

    def reiniciar(self) -> None:
        """Vuelve al tick 0 conservando la definicion de los procesos."""
        self.detener()
        with self._bloqueo:
            self._construir()

    def _bucle(self) -> None:
        while not self._detener.is_set():
            with self._bloqueo:
                if self.estado is EstadoSimulacion.EJECUTANDO:
                    self.avanzar()
                intervalo = 1 / self.configuracion.ticks_por_segundo
            # La espera queda fuera del cerrojo para no bloquear a la interfaz.
            self._detener.wait(intervalo)

    # ------------------------------------------------ parametros en caliente

    def aplicar_parametros(self, cambios: dict) -> dict:
        """
        Valida y aplica cambios de parametros sin detener la simulacion. Si un
        recurso rechaza el cambio, la configuracion vuelve a su valor anterior
        para que nunca quede describiendo un sistema que no existe.
        """
        with self._bloqueo:
            previos = {
                clave: getattr(self.configuracion, clave)
                for clave in cambios
                if clave in PARAMETROS
            }
            aplicados = self.configuracion.aplicar(cambios)
            try:
                self._sincronizar_recursos(aplicados)
            except ValueError:
                self.configuracion.aplicar({clave: previos[clave] for clave in aplicados})
                raise

            for clave, valor in aplicados.items():
                self.registro.registrar(
                    self.reloj, "parametro", f"{PARAMETROS[clave].etiqueta} = {valor}"
                )
            return aplicados

    def _sincronizar_recursos(self, aplicados: dict) -> None:
        # La memoria va primero: es el unico recurso que puede rechazar el
        # cambio, y asi el resto no queda a medio aplicar.
        if "memoria_total_kb" in aplicados:
            self.memoria.redimensionar(aplicados["memoria_total_kb"])
        if "politica_memoria" in aplicados:
            self.memoria.cambiar_politica(aplicados["politica_memoria"])
        if "algoritmo" in aplicados:
            self.planificador.sincronizar_algoritmo()
        if "nucleos_cpu" in aplicados:
            self.planificador.aplicar_cambio_nucleos(aplicados["nucleos_cpu"])
        if "dispositivos_es" in aplicados:
            self.dispositivos_es.redimensionar(aplicados["dispositivos_es"])

    # ------------------------------------------------------------ proyeccion

    def instantanea(self, desde_evento: int = 0) -> dict:
        """Fotografia completa del sistema; es lo unico que consumen las vistas."""
        with self._bloqueo:
            procesos = self.planificador.procesos
            return {
                "reloj": self.reloj,
                "estado": self.estado.value,
                "estado_etiqueta": self.estado.etiqueta,
                "algoritmo_activo": self.planificador.algoritmo.etiqueta,
                "configuracion": self.configuracion.como_diccionario(),
                "cpu": self.cpu.como_diccionario(),
                "memoria": self.memoria.como_diccionario(),
                "dispositivos_es": self.dispositivos_es.como_diccionario(),
                "colas": self.planificador.colas_como_diccionario(),
                "procesos": [proceso.como_diccionario() for proceso in procesos],
                "metricas": self.metricas.resumen(procesos, self.reloj),
                "series": self.metricas.series_como_diccionario(),
                "gantt": self.cpu.linea_tiempo(self.reloj),
                "eventos": self.registro.desde(desde_evento),
                "ultimo_evento": self.registro.total_eventos,
            }

    def exportar(self, directorio: str | Path = DIRECTORIO_REPORTES) -> dict[str, str]:
        """Genera el reporte de la corrida: resumen, detalle de procesos y bitacora."""
        with self._bloqueo:
            marca = datetime.now().strftime("%Y%m%d_%H%M%S")
            destino = Path(directorio)
            rutas = {
                "reporte": self.metricas.exportar_reporte(
                    destino / f"reporte_{marca}.txt",
                    self.planificador.procesos,
                    self.reloj,
                    self.configuracion.como_diccionario(),
                    self.registro.resumen_por_categoria(),
                ),
                "procesos": self.metricas.exportar_procesos_csv(
                    destino / f"procesos_{marca}.csv", self.planificador.procesos
                ),
                "bitacora": self.registro.exportar_csv(destino / f"bitacora_{marca}.csv"),
            }
            self.registro.registrar(
                self.reloj, "sistema", f"Reporte exportado a {destino.resolve()}"
            )
            return {clave: str(ruta) for clave, ruta in rutas.items()}
