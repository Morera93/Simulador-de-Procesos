"""Bitacora de actividades del sistema simulado."""

import csv
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path

CATEGORIAS = {
    "sistema": "Sistema",
    "llegada": "Llegada",
    "admision": "Admision",
    "despacho": "Despacho",
    "expropiacion": "Expropiacion",
    "bloqueo": "Bloqueo E/S",
    "desbloqueo": "Fin de E/S",
    "finalizacion": "Finalizacion",
    "memoria": "Memoria",
    "parametro": "Parametro",
    "error": "Error",
}


@dataclass(frozen=True)
class Evento:
    identificador: int
    tick: int
    categoria: str
    mensaje: str
    pid: int | None = None

    def como_diccionario(self) -> dict:
        return {
            "id": self.identificador,
            "tick": self.tick,
            "categoria": self.categoria,
            "categoria_etiqueta": CATEGORIAS.get(self.categoria, self.categoria),
            "mensaje": self.mensaje,
            "pid": self.pid,
        }


class RegistroActividades:
    """
    Guarda los ultimos eventos en memoria con un tope fijo para que una
    simulacion larga no crezca sin control. Cada evento lleva un identificador
    incremental, de modo que la interfaz solo pide los eventos nuevos en lugar
    de recargar la bitacora completa en cada refresco.
    """

    def __init__(self, capacidad: int = 2000):
        self.capacidad = capacidad
        self.eventos: deque[Evento] = deque(maxlen=capacidad)
        self.contadores: Counter = Counter()
        self._siguiente_id = 1

    @property
    def total_eventos(self) -> int:
        return self._siguiente_id - 1

    def registrar(self, tick: int, categoria: str, mensaje: str, pid: int | None = None) -> Evento:
        evento = Evento(self._siguiente_id, tick, categoria, mensaje, pid)
        self._siguiente_id += 1
        self.eventos.append(evento)
        self.contadores[categoria] += 1
        return evento

    def desde(self, identificador: int, maximo: int = 200) -> list[dict]:
        """Eventos posteriores al identificador dado, para refrescos incrementales."""
        nuevos = [e for e in self.eventos if e.identificador > identificador]
        return [e.como_diccionario() for e in nuevos[-maximo:]]

    def ultimos(self, cantidad: int = 50) -> list[dict]:
        return [e.como_diccionario() for e in list(self.eventos)[-cantidad:]]

    def limpiar(self) -> None:
        self.eventos.clear()
        self.contadores.clear()
        self._siguiente_id = 1

    def exportar_csv(self, ruta: str | Path) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", newline="", encoding="utf-8") as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(["tick", "categoria", "pid", "mensaje"])
            for evento in self.eventos:
                escritor.writerow(
                    [evento.tick, CATEGORIAS.get(evento.categoria, evento.categoria),
                     evento.pid if evento.pid is not None else "", evento.mensaje]
                )
        return ruta

    def resumen_por_categoria(self) -> dict[str, int]:
        return {CATEGORIAS.get(clave, clave): total for clave, total in self.contadores.items()}
