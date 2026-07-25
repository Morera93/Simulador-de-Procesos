"""
Interfaz de usuario por consola.

Funciona en dos modos que se alternan con la tecla Enter: monitor (el tablero
se refresca solo, en tiempo real) y comando (el refresco se detiene para que se
pueda escribir sin que la pantalla se repinte encima).

No usa dependencias externas: las tablas y las barras se dibujan con caracteres
de bloque y secuencias ANSI.
"""

import os
import re
import shutil
import sys
import time

from ..config import PARAMETROS, POLITICAS_MEMORIA
from ..nucleo.simulador import EstadoSimulacion, Simulador

RESET = "\033[0m"
NEGRITA = "\033[1m"
LIMPIAR = "\033[2J\033[H"
INICIO = "\033[H"


def _color(codigo: int) -> str:
    return f"\033[38;5;{codigo}m"


VERDE, CIAN, VIOLETA, AMBAR, ROJO, GRIS = (
    _color(83), _color(45), _color(141), _color(214), _color(203), _color(245)
)

COLOR_ESTADO = {
    "nuevo": GRIS,
    "listo": CIAN,
    "ejecucion": VERDE,
    "bloqueado": VIOLETA,
    "terminado": GRIS,
}

COLOR_CATEGORIA = {
    "despacho": VERDE, "finalizacion": VERDE, "llegada": CIAN, "admision": CIAN,
    "bloqueo": VIOLETA, "desbloqueo": VIOLETA, "expropiacion": AMBAR,
    "parametro": AMBAR, "error": ROJO,
}

ALIAS = {
    "algoritmo": "algoritmo", "quantum": "quantum", "nucleos": "nucleos_cpu",
    "memoria": "memoria_total_kb", "politica": "politica_memoria",
    "dispositivos": "dispositivos_es", "contexto": "costo_cambio_contexto",
    "envejecimiento": "envejecimiento", "velocidad": "ticks_por_segundo",
}

AYUDA = f"""
{NEGRITA}COMANDOS{RESET}
  iniciar | i            arranca la simulacion
  pausar  | p            detiene el avance automatico
  paso    | s            avanza un solo tick
  reiniciar | r          vuelve al tick 0 con los mismos procesos
  exportar  | e          genera el reporte y la bitacora en reportes_generados/
  proceso <nombre> <cpu> [es] [prioridad] [kb]
                         agrega un proceso al sistema en caliente
  generar <cantidad> [semilla]
                         genera una carga de procesos aleatoria
  <parametro> <valor>    cambia un parametro en tiempo real
  ayuda   | h            muestra esta ayuda
  salir   | q            termina el simulador

{NEGRITA}PARAMETROS{RESET}
  {' · '.join(ALIAS)}
  algoritmos: {', '.join(PARAMETROS['algoritmo'].opciones)}
  politicas de memoria: {', '.join(POLITICAS_MEMORIA)}
"""


def _tecla_pendiente() -> bool:
    """Detecta si el usuario presiono una tecla sin bloquear el refresco."""
    if os.name == "nt":
        import msvcrt

        if not msvcrt.kbhit():
            return False
        while msvcrt.kbhit():
            msvcrt.getwch()
        return True

    import select

    return bool(select.select([sys.stdin], [], [], 0)[0])


def _barra(porcentaje: float, ancho: int, color: str = VERDE) -> str:
    llenos = round(porcentaje / 100 * ancho)
    return f"{color}{'█' * llenos}{GRIS}{'░' * (ancho - llenos)}{RESET}"


class InterfazConsola:
    """Vista de terminal: solo lee instantaneas y traduce comandos."""

    def __init__(self, simulador: Simulador):
        self.simulador = simulador
        self.mensaje = "Enter para escribir un comando · 'ayuda' para ver la lista"
        self.ancho = 100

    def ejecutar(self) -> None:
        if os.name == "nt":
            os.system("")  # habilita las secuencias ANSI en la consola de Windows
        # Si la salida se redirige a un archivo con una codificacion limitada,
        # los caracteres de bloque se sustituyen en vez de abortar el programa.
        sys.stdout.reconfigure(errors="replace")
        print(LIMPIAR, end="")
        try:
            while True:
                self.ancho = max(80, min(shutil.get_terminal_size((110, 30)).columns - 1, 130))
                self._pintar(self.simulador.instantanea())
                if _tecla_pendiente() and not self._leer_comando():
                    break
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            self.simulador.detener()
            print(f"\n{GRIS}Simulador detenido.{RESET}")

    # ------------------------------------------------------------- comandos

    def _leer_comando(self) -> bool:
        """Devuelve False cuando el usuario pide salir."""
        print(f"\n{VERDE}>{RESET} ", end="", flush=True)
        try:
            partes = input().strip().split()
        except EOFError:
            return False
        print(LIMPIAR, end="")
        if not partes:
            self.mensaje = "Modo monitor reanudado."
            return True

        orden, argumentos = partes[0].lower(), partes[1:]
        try:
            return self._ejecutar_comando(orden, argumentos)
        except ValueError as error:
            self.mensaje = f"{ROJO}{error}{RESET}"
        except IndexError:
            self.mensaje = f"{ROJO}Faltan argumentos. Escriba 'ayuda'.{RESET}"
        return True

    def _ejecutar_comando(self, orden: str, argumentos: list[str]) -> bool:
        simples = {
            "iniciar": self.simulador.iniciar, "i": self.simulador.iniciar,
            "pausar": self.simulador.pausar, "p": self.simulador.pausar,
            "paso": self.simulador.paso, "s": self.simulador.paso,
            "reiniciar": self.simulador.reiniciar, "r": self.simulador.reiniciar,
        }

        if orden in ("salir", "q"):
            return False
        if orden in simples:
            simples[orden]()
            self.mensaje = f"Orden '{orden}' aplicada."
        elif orden in ("ayuda", "h"):
            self.mensaje = AYUDA
        elif orden in ("exportar", "e"):
            rutas = self.simulador.exportar()
            self.mensaje = f"{VERDE}Reporte generado: {rutas['reporte']}{RESET}"
        elif orden == "proceso":
            self._agregar_proceso(argumentos)
        elif orden == "generar":
            semilla = int(argumentos[1]) if len(argumentos) > 1 else None
            procesos = self.simulador.generar_procesos(int(argumentos[0]), semilla)
            self.mensaje = f"{VERDE}Se generaron {len(procesos)} procesos.{RESET}"
        elif orden in ALIAS:
            aplicados = self.simulador.aplicar_parametros({ALIAS[orden]: argumentos[0]})
            self.mensaje = (
                f"{VERDE}Parametro actualizado: {aplicados}{RESET}" if aplicados
                else "El parametro ya tenia ese valor."
            )
        else:
            self.mensaje = f"{ROJO}Comando desconocido: '{orden}'. Escriba 'ayuda'.{RESET}"
        return True

    def _agregar_proceso(self, argumentos: list[str]) -> None:
        campos = ("nombre", "rafaga_cpu", "rafaga_es", "prioridad", "memoria_kb")
        datos = dict(zip(campos, argumentos))
        if "rafaga_cpu" not in datos:
            raise ValueError("Uso: proceso <nombre> <cpu> [es] [prioridad] [kb]")
        proceso = self.simulador.agregar_proceso(datos)
        self.mensaje = f"{VERDE}Proceso {proceso.nombre} (PID {proceso.pid}) agregado.{RESET}"

    # -------------------------------------------------------------- pintado

    def _regla(self, titulo: str = "") -> str:
        if not titulo:
            return f"{GRIS}{'─' * self.ancho}{RESET}"
        relleno = "─" * max(0, self.ancho - len(titulo) - 3)
        return f"{GRIS}──{RESET} {NEGRITA}{titulo}{RESET} {GRIS}{relleno}{RESET}"

    def _pintar(self, datos: dict) -> None:
        secciones = [
            self._encabezado(datos),
            self._seccion_cpu(datos),
            self._seccion_memoria(datos),
            self._seccion_es(datos),
            self._seccion_colas(datos),
            self._seccion_metricas(datos),
            self._seccion_bitacora(datos),
            self._regla(),
            f" {self.mensaje}",
        ]
        # Se escribe todo de una vez para evitar parpadeo entre secciones.
        salida = "\n".join(secciones)
        print(f"{INICIO}\033[0J{salida}", end="", flush=True)

    def _encabezado(self, datos: dict) -> str:
        color = {
            EstadoSimulacion.EJECUTANDO.value: VERDE,
            EstadoSimulacion.PAUSADA.value: AMBAR,
            EstadoSimulacion.FINALIZADA.value: CIAN,
        }.get(datos["estado"], GRIS)
        configuracion = datos["configuracion"]
        izquierda = (
            f" {NEGRITA}SIMULADOR DE PROCESOS{RESET}  {GRIS}tick{RESET} "
            f"{VERDE}{NEGRITA}{datos['reloj']:>5}{RESET}  "
            f"{color}● {datos['estado_etiqueta']}{RESET}"
        )
        derecha = (
            f"{GRIS}{datos['algoritmo_activo']} · q={configuracion['quantum']} · "
            f"{configuracion['ticks_por_segundo']} ticks/s{RESET} "
        )
        visible = len(self._sin_color(izquierda)) + len(self._sin_color(derecha))
        return izquierda + " " * max(1, self.ancho - visible) + derecha

    @staticmethod
    def _sin_color(texto: str) -> str:
        return re.sub(r"\033\[[0-9;]*m", "", texto)

    def _seccion_cpu(self, datos: dict) -> str:
        cpu = datos["cpu"]
        lineas = [self._regla(f"CPU  {cpu['porcentaje_uso']}% ocupacion · "
                             f"{cpu['rendimiento_util']}% trabajo util")]
        for nucleo in cpu["nucleos"]:
            if nucleo["pid"] is None:
                detalle = f"{GRIS}libre{RESET}"
                avance = 0.0
            else:
                marca = f"{AMBAR}conmutando{RESET}" if nucleo["conmutando"] else f"{VERDE}activo{RESET}"
                detalle = (
                    f"{nucleo['nombre'][:14]:<14} {GRIS}PID{RESET} {nucleo['pid']:<3} "
                    f"{GRIS}restan{RESET} {nucleo['cpu_restante']:<3} {marca}"
                )
                avance = nucleo["avance"]
            lineas.append(
                f"  {CIAN}N{nucleo['indice']}{RESET} {_barra(avance, 22)} {detalle}"
            )
        return "\n".join(lineas)

    def _seccion_memoria(self, datos: dict) -> str:
        memoria = datos["memoria"]
        mapa = ""
        ancho_mapa = self.ancho - 8
        for particion in memoria["particiones"]:
            celdas = max(1, round(particion["tamano"] / memoria["total_kb"] * ancho_mapa))
            mapa += f"{GRIS}·{RESET}" * celdas if particion["libre"] else f"{VERDE}█{RESET}" * celdas
        return "\n".join([
            self._regla(
                f"MEMORIA  {memoria['usados_kb']}/{memoria['total_kb']} KB · "
                f"{memoria['porcentaje_uso']}% · fragmentacion {memoria['fragmentacion_externa']}% · "
                f"{memoria['politica']}"
            ),
            f"  {mapa}",
        ])

    def _seccion_es(self, datos: dict) -> str:
        subsistema = datos["dispositivos_es"]
        lineas = [self._regla(f"ENTRADA/SALIDA  {subsistema['porcentaje_uso']}% ocupacion · "
                              f"{subsistema['operaciones_atendidas']} operaciones")]
        for dispositivo in subsistema["dispositivos"]:
            if dispositivo["pid"] is None:
                estado = f"{GRIS}inactivo{RESET}"
            else:
                estado = (
                    f"{VIOLETA}{dispositivo['nombre'][:14]:<14}{RESET} "
                    f"{GRIS}restan{RESET} {dispositivo['es_restante']} ticks"
                )
            lineas.append(f"  {VIOLETA}E{dispositivo['indice']}{RESET} {estado}")
        cola = subsistema["cola_espera"]
        espera = ", ".join(f"{p['nombre']}({p['pid']})" for p in cola) or f"{GRIS}vacia{RESET}"
        lineas.append(f"  {GRIS}cola de peticiones:{RESET} {espera}")
        return "\n".join(lineas)

    def _seccion_colas(self, datos: dict) -> str:
        colas = datos["colas"]
        etiquetas = [
            ("programados", "Programados"), ("nuevos", "Sin memoria"), ("listos", "Listos"),
            ("ejecucion", "Ejecucion"), ("bloqueados", "Bloqueados"), ("terminados", "Terminados"),
        ]
        lineas = [self._regla("COLAS DE PROCESOS")]
        for clave, titulo in etiquetas:
            procesos = colas[clave]
            contenido = " ".join(
                f"{COLOR_ESTADO.get(p['estado'], GRIS)}[{p['pid']}:{p['nombre'][:10]}]{RESET}"
                for p in procesos[:8]
            )
            if len(procesos) > 8:
                contenido += f" {GRIS}+{len(procesos) - 8}{RESET}"
            lineas.append(f"  {titulo:<12}{GRIS}({len(procesos):>2}){RESET} {contenido}")
        return "\n".join(lineas)

    def _seccion_metricas(self, datos: dict) -> str:
        m = datos["metricas"]
        return "\n".join([
            self._regla("INDICADORES"),
            f"  {GRIS}terminados{RESET} {m['procesos_terminados']}/{m['procesos_totales']}   "
            f"{GRIS}espera{RESET} {m['promedio_espera']}   "
            f"{GRIS}retorno{RESET} {m['promedio_retorno']}   "
            f"{GRIS}respuesta{RESET} {m['promedio_respuesta']}   "
            f"{GRIS}rendimiento{RESET} {m['rendimiento']}   "
            f"{GRIS}cambios de contexto{RESET} {m['cambios_contexto']}",
        ])

    def _seccion_bitacora(self, datos: dict) -> str:
        eventos = self.simulador.registro.ultimos(6)
        lineas = [self._regla("BITACORA")]
        for evento in eventos:
            color = COLOR_CATEGORIA.get(evento["categoria"], GRIS)
            lineas.append(
                f"  {GRIS}t{evento['tick']:<4}{RESET} {color}{evento['categoria_etiqueta']:<13}{RESET}"
                f" {evento['mensaje'][:self.ancho - 24]}"
            )
        return "\n".join(lineas)
