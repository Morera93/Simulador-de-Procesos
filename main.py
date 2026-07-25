"""
Punto de entrada del Simulador de Procesos.

Ejemplos:
    python main.py                                  panel web con el CSV de ejemplo
    python main.py --interfaz consola --iniciar     tablero de terminal, ya corriendo
    python main.py --generar 12 --algoritmo srtf    carga aleatoria y SJF apropiativo
"""

import argparse
import sys
from pathlib import Path

from src.config import PARAMETROS, ConfiguracionSimulacion
from src.interfaz.consola import InterfazConsola
from src.interfaz.grafica import ServidorPanel
from src.nucleo.entrada import cargar_csv, generar_aleatorios
from src.nucleo.simulador import Simulador

ARCHIVO_POR_DEFECTO = Path(__file__).parent / "data" / "procesos_ejemplo.csv"

# Cada opcion de linea de comandos apunta al parametro que modifica, para que la
# validacion sea exactamente la misma que usan las interfaces en tiempo real.
OPCIONES_PARAMETRO = {
    "algoritmo": "algoritmo",
    "quantum": "quantum",
    "nucleos": "nucleos_cpu",
    "memoria": "memoria_total_kb",
    "politica": "politica_memoria",
    "dispositivos": "dispositivos_es",
    "contexto": "costo_cambio_contexto",
    "envejecimiento": "envejecimiento",
    "velocidad": "ticks_por_segundo",
}


def construir_analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(
        prog="simulador",
        description="Simulador de procesos de un sistema operativo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analizador.add_argument(
        "--interfaz", choices=("grafica", "consola"), default="grafica",
        help="panel web en el navegador (por defecto) o tablero de terminal",
    )
    analizador.add_argument(
        "--archivo", type=Path, default=ARCHIVO_POR_DEFECTO,
        help="CSV con los procesos de entrada",
    )
    analizador.add_argument(
        "--generar", type=int, metavar="N",
        help="genera N procesos aleatorios en lugar de leer el archivo",
    )
    analizador.add_argument("--semilla", type=int, help="semilla para la carga aleatoria")
    analizador.add_argument(
        "--iniciar", action="store_true", help="arranca la simulacion de inmediato"
    )
    analizador.add_argument("--host", default="127.0.0.1", help="direccion del panel web")
    analizador.add_argument("--puerto", type=int, default=8765, help="puerto del panel web")
    analizador.add_argument(
        "--sin-navegador", action="store_true", help="no abre el navegador automaticamente"
    )

    grupo = analizador.add_argument_group("parametros iniciales de la simulacion")
    for opcion, parametro in OPCIONES_PARAMETRO.items():
        descriptor = PARAMETROS[parametro]
        limites = (
            f"opciones: {', '.join(descriptor.opciones)}" if descriptor.opciones
            else f"entre {descriptor.minimo} y {descriptor.maximo}{descriptor.unidad}"
        )
        grupo.add_argument(f"--{opcion}", help=f"{descriptor.ayuda} ({limites})")
    return analizador


def construir_configuracion(argumentos: argparse.Namespace) -> ConfiguracionSimulacion:
    configuracion = ConfiguracionSimulacion()
    cambios = {
        parametro: getattr(argumentos, opcion)
        for opcion, parametro in OPCIONES_PARAMETRO.items()
        if getattr(argumentos, opcion) is not None
    }
    configuracion.aplicar(cambios)
    return configuracion


def cargar_procesos(argumentos: argparse.Namespace):
    if argumentos.generar is not None:
        return generar_aleatorios(argumentos.generar, semilla=argumentos.semilla)
    return cargar_csv(argumentos.archivo)


def main(argv: list[str] | None = None) -> int:
    argumentos = construir_analizador().parse_args(argv)
    try:
        configuracion = construir_configuracion(argumentos)
        procesos = cargar_procesos(argumentos)
    except ValueError as error:
        print(f"Error de configuracion: {error}", file=sys.stderr)
        return 2

    simulador = Simulador(configuracion, procesos)
    print(
        f"Cargados {len(procesos)} procesos · algoritmo "
        f"{simulador.planificador.algoritmo.etiqueta}"
    )
    if argumentos.iniciar:
        simulador.iniciar()

    if argumentos.interfaz == "consola":
        InterfazConsola(simulador).ejecutar()
    else:
        ServidorPanel(simulador, argumentos.host, argumentos.puerto).ejecutar(
            abrir_navegador=not argumentos.sin_navegador
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
