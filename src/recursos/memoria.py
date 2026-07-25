"""Gestion de memoria principal por particiones dinamicas contiguas."""

from dataclasses import dataclass

from ..modelos.proceso import Proceso


@dataclass
class Particion:
    """Bloque contiguo de memoria; `pid` en None significa hueco libre."""

    inicio: int
    tamano: int
    pid: int | None = None

    @property
    def libre(self) -> bool:
        return self.pid is None

    @property
    def fin(self) -> int:
        return self.inicio + self.tamano


class GestorMemoria:
    """
    Asignacion contigua con particiones dinamicas y tres politicas clasicas
    (primer, mejor y peor ajuste). Al liberar un bloque se fusiona con sus
    vecinos libres para combatir la fragmentacion externa, que ademas se mide y
    se expone a la interfaz.
    """

    POLITICAS = ("primer_ajuste", "mejor_ajuste", "peor_ajuste")

    def __init__(self, total_kb: int, politica: str = "primer_ajuste"):
        self.total_kb = total_kb
        self.politica = self._validar_politica(politica)
        self.particiones = [Particion(0, total_kb)]
        self.asignaciones_fallidas = 0

    @staticmethod
    def _validar_politica(politica: str) -> str:
        if politica not in GestorMemoria.POLITICAS:
            validas = ", ".join(GestorMemoria.POLITICAS)
            raise ValueError(f"Politica de memoria invalida: '{politica}'. Validas: {validas}.")
        return politica

    @property
    def usados_kb(self) -> int:
        return sum(p.tamano for p in self.particiones if not p.libre)

    @property
    def libres_kb(self) -> int:
        return self.total_kb - self.usados_kb

    @property
    def mayor_hueco_kb(self) -> int:
        huecos = [p.tamano for p in self.particiones if p.libre]
        return max(huecos, default=0)

    @property
    def porcentaje_uso(self) -> float:
        if self.total_kb == 0:
            return 0.0
        return round(self.usados_kb / self.total_kb * 100, 1)

    @property
    def fragmentacion_externa(self) -> float:
        """Porcentaje de memoria libre que no cabe en un solo hueco."""
        if self.libres_kb == 0:
            return 0.0
        return round((self.libres_kb - self.mayor_hueco_kb) / self.libres_kb * 100, 1)

    def cambiar_politica(self, politica: str) -> None:
        self.politica = self._validar_politica(politica)

    def asignar(self, proceso: Proceso) -> bool:
        """Reserva memoria para el proceso. Devuelve False si no hay hueco suficiente."""
        candidatas = [p for p in self.particiones if p.libre and p.tamano >= proceso.memoria_kb]
        if not candidatas:
            self.asignaciones_fallidas += 1
            return False

        elegida = self._elegir(candidatas)
        indice = self.particiones.index(elegida)
        sobrante = elegida.tamano - proceso.memoria_kb

        elegida.tamano = proceso.memoria_kb
        elegida.pid = proceso.pid
        if sobrante > 0:
            self.particiones.insert(indice + 1, Particion(elegida.fin, sobrante))

        proceso.direccion_memoria = elegida.inicio
        return True

    def _elegir(self, candidatas: list[Particion]) -> Particion:
        if self.politica == "mejor_ajuste":
            return min(candidatas, key=lambda p: p.tamano)
        if self.politica == "peor_ajuste":
            return max(candidatas, key=lambda p: p.tamano)
        return candidatas[0]

    def liberar(self, proceso: Proceso) -> None:
        for particion in self.particiones:
            if particion.pid == proceso.pid:
                particion.pid = None
                break
        proceso.direccion_memoria = None
        self._fusionar_huecos()

    def _fusionar_huecos(self) -> None:
        fusionadas: list[Particion] = []
        for particion in self.particiones:
            anterior = fusionadas[-1] if fusionadas else None
            if anterior is not None and anterior.libre and particion.libre:
                anterior.tamano += particion.tamano
            else:
                fusionadas.append(particion)
        self.particiones = fusionadas

    def redimensionar(self, total_kb: int) -> None:
        """
        Cambia el tamano de la memoria fisica en caliente. Solo se puede reducir
        hasta donde llega el ultimo proceso cargado, para no invalidar memoria
        que alguien esta usando.
        """
        if total_kb == self.total_kb:
            return

        ocupadas = [p for p in self.particiones if not p.libre]
        limite_ocupado = max((p.fin for p in ocupadas), default=0)
        if total_kb < limite_ocupado:
            raise ValueError(
                f"Memoria total: no se puede reducir a {total_kb} KB, hay procesos "
                f"cargados hasta la direccion {limite_ocupado} KB."
            )

        if total_kb > self.total_kb:
            extra = total_kb - self.total_kb
            ultima = self.particiones[-1]
            if ultima.libre:
                ultima.tamano += extra
            else:
                self.particiones.append(Particion(ultima.fin, extra))
        else:
            self.particiones = [p for p in self.particiones if p.inicio < total_kb]
            ultima = self.particiones[-1]
            ultima.tamano = total_kb - ultima.inicio

        self.total_kb = total_kb
        self._fusionar_huecos()

    def mapa(self) -> list[dict]:
        return [
            {"inicio": p.inicio, "tamano": p.tamano, "pid": p.pid, "libre": p.libre}
            for p in self.particiones
        ]

    def como_diccionario(self) -> dict:
        return {
            "total_kb": self.total_kb,
            "usados_kb": self.usados_kb,
            "libres_kb": self.libres_kb,
            "porcentaje_uso": self.porcentaje_uso,
            "mayor_hueco_kb": self.mayor_hueco_kb,
            "fragmentacion_externa": self.fragmentacion_externa,
            "asignaciones_fallidas": self.asignaciones_fallidas,
            "politica": self.politica,
            "particiones": self.mapa(),
        }
