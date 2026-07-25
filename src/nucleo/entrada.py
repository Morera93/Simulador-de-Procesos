"""
Entrada de datos al sistema simulado.

Tres origenes comparten la misma validacion: archivo CSV, generador de carga
aleatoria y alta manual desde la interfaz.
"""

import csv
import random
from pathlib import Path

from ..config import Parametro
from ..modelos.proceso import Proceso

LONGITUD_MAXIMA_NOMBRE = 20

CAMPOS_PROCESO = {
    p.nombre: p
    for p in (
        Parametro("tiempo_llegada", "Tiempo de llegada", int, minimo=0, maximo=9999),
        Parametro("rafaga_cpu", "Rafaga de CPU", int, minimo=1, maximo=999),
        Parametro("rafaga_es", "Rafaga de E/S", int, minimo=0, maximo=999),
        Parametro("prioridad", "Prioridad", int, minimo=1, maximo=9),
        Parametro("memoria_kb", "Memoria requerida", int, minimo=1, maximo=16384),
    )
}

VALORES_POR_DEFECTO = {
    "tiempo_llegada": 0,
    "rafaga_cpu": 5,
    "rafaga_es": 0,
    "prioridad": 3,
    "memoria_kb": 64,
}

NOMBRES_SUGERIDOS = (
    "navegador", "compilador", "respaldo", "antivirus", "indexador", "editor",
    "servidor_web", "base_datos", "reproductor", "actualizador", "impresion",
    "monitor_red",
)


def _validar_nombre(valor, pid: int) -> str:
    nombre = str(valor).strip() if valor is not None else ""
    if not nombre:
        return f"P{pid}"
    if len(nombre) > LONGITUD_MAXIMA_NOMBRE:
        raise ValueError(
            f"Nombre del proceso: no puede superar {LONGITUD_MAXIMA_NOMBRE} caracteres."
        )
    return nombre


def crear_proceso(datos: dict, pid: int) -> Proceso:
    """Valida un diccionario de entrada y construye el PCB correspondiente."""
    desconocidos = set(datos) - set(CAMPOS_PROCESO) - {"nombre", "pid"}
    if desconocidos:
        raise ValueError(f"Campos desconocidos: {', '.join(sorted(desconocidos))}.")

    valores = {}
    for nombre, campo in CAMPOS_PROCESO.items():
        entrada = datos.get(nombre, "")
        if entrada in ("", None):
            valores[nombre] = VALORES_POR_DEFECTO[nombre]
        else:
            valores[nombre] = campo.convertir(entrada)

    return Proceso(pid=pid, nombre=_validar_nombre(datos.get("nombre"), pid), **valores)


def cargar_csv(ruta: str | Path) -> list[Proceso]:
    """
    Carga procesos desde un CSV con encabezado. El PID del archivo se ignora y
    se reasigna de forma correlativa para garantizar que sea unico.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ValueError(f"No se encontro el archivo de procesos: {ruta}")

    procesos: list[Proceso] = []
    with ruta.open(newline="", encoding="utf-8-sig") as archivo:
        lector = csv.DictReader(archivo)
        if not lector.fieldnames:
            raise ValueError(f"El archivo {ruta.name} esta vacio o no tiene encabezado.")

        faltantes = {"rafaga_cpu"} - set(lector.fieldnames)
        if faltantes:
            raise ValueError(
                f"El archivo {ruta.name} debe incluir la columna 'rafaga_cpu'."
            )

        for numero, fila in enumerate(lector, start=2):
            if not any((valor or "").strip() for valor in fila.values()):
                continue
            datos = {clave: valor for clave, valor in fila.items() if clave in CAMPOS_PROCESO}
            datos["nombre"] = fila.get("nombre")
            try:
                procesos.append(crear_proceso(datos, pid=len(procesos) + 1))
            except ValueError as error:
                raise ValueError(f"{ruta.name}, linea {numero}: {error}") from error

    if not procesos:
        raise ValueError(f"El archivo {ruta.name} no contiene procesos validos.")
    return procesos


def generar_aleatorios(
    cantidad: int,
    pid_inicial: int = 1,
    tick_inicial: int = 0,
    semilla: int | None = None,
) -> list[Proceso]:
    """
    Genera una carga de trabajo sintetica para simular la entrada continua de
    procesos al sistema. Con `semilla` fija el resultado es reproducible, algo
    util para comparar algoritmos sobre la misma carga.
    """
    cantidad = Parametro("cantidad", "Cantidad de procesos", int, minimo=1, maximo=50).convertir(
        cantidad
    )
    azar = random.Random(semilla)

    procesos = []
    for desplazamiento in range(cantidad):
        pid = pid_inicial + desplazamiento
        rafaga_es = azar.choice([0, 0, azar.randint(1, 6)])
        procesos.append(
            Proceso(
                pid=pid,
                nombre=f"{azar.choice(NOMBRES_SUGERIDOS)}_{pid}",
                tiempo_llegada=tick_inicial + azar.randint(0, max(1, cantidad // 2)),
                rafaga_cpu=azar.randint(2, 12),
                rafaga_es=rafaga_es,
                prioridad=azar.randint(1, 5),
                memoria_kb=azar.choice([32, 64, 96, 128, 192, 256]),
            )
        )
    return procesos


def descriptores_proceso() -> list[dict]:
    """Metadatos de los campos de un proceso, para construir formularios."""
    return [campo.como_diccionario() for campo in CAMPOS_PROCESO.values()]
