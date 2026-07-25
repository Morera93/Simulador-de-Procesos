"""
Parametros de la simulacion y su validacion.

Los descriptores de `PARAMETROS` son la unica fuente de verdad: validan los
cambios y ademas alimentan los controles de las interfaces (consola y web), de
modo que agregar un parametro nuevo no obliga a tocar las vistas.
"""

from dataclasses import dataclass, field, fields

from .algoritmos import NOMBRES_ALGORITMOS

POLITICAS_MEMORIA = {
    "primer_ajuste": "Primer ajuste",
    "mejor_ajuste": "Mejor ajuste",
    "peor_ajuste": "Peor ajuste",
}


@dataclass(frozen=True)
class Parametro:
    """Descriptor de un parametro modificable en tiempo real."""

    nombre: str
    etiqueta: str
    tipo: type
    minimo: float | None = None
    maximo: float | None = None
    opciones: dict[str, str] | None = None
    unidad: str = ""
    ayuda: str = ""

    def convertir(self, valor):
        """Normaliza y valida un valor entrante. Lanza ValueError en espanol."""
        if self.opciones is not None:
            texto = str(valor).strip().lower()
            if texto not in self.opciones:
                validos = ", ".join(self.opciones)
                raise ValueError(
                    f"{self.etiqueta}: '{valor}' no es valido. Opciones: {validos}."
                )
            return texto

        try:
            convertido = self.tipo(valor)
        except (TypeError, ValueError):
            esperado = "un numero entero" if self.tipo is int else "un numero"
            raise ValueError(f"{self.etiqueta}: se esperaba {esperado}, se recibio '{valor}'.")

        if self.minimo is not None and convertido < self.minimo:
            raise ValueError(f"{self.etiqueta}: el minimo permitido es {self.minimo}{self.unidad}.")
        if self.maximo is not None and convertido > self.maximo:
            raise ValueError(f"{self.etiqueta}: el maximo permitido es {self.maximo}{self.unidad}.")
        return convertido

    def como_diccionario(self) -> dict:
        return {
            "nombre": self.nombre,
            "etiqueta": self.etiqueta,
            "tipo": "opcion" if self.opciones else self.tipo.__name__,
            "minimo": self.minimo,
            "maximo": self.maximo,
            "opciones": self.opciones,
            "unidad": self.unidad,
            "ayuda": self.ayuda,
        }


PARAMETROS: dict[str, Parametro] = {
    p.nombre: p
    for p in (
        Parametro(
            "algoritmo",
            "Algoritmo de planificacion",
            str,
            opciones=NOMBRES_ALGORITMOS,
            ayuda="Politica que decide cual proceso listo ocupa la CPU.",
        ),
        Parametro(
            "quantum",
            "Quantum",
            int,
            minimo=1,
            maximo=50,
            unidad=" ticks",
            ayuda="Turno maximo de CPU antes de expropiar (solo Round Robin).",
        ),
        Parametro(
            "nucleos_cpu",
            "Nucleos de CPU",
            int,
            minimo=1,
            maximo=8,
            ayuda="Procesos que pueden ejecutarse en paralelo.",
        ),
        Parametro(
            "memoria_total_kb",
            "Memoria total",
            int,
            minimo=64,
            maximo=16384,
            unidad=" KB",
            ayuda="Memoria fisica disponible para admitir procesos.",
        ),
        Parametro(
            "politica_memoria",
            "Politica de memoria",
            str,
            opciones=POLITICAS_MEMORIA,
            ayuda="Criterio para elegir el hueco libre donde cargar un proceso.",
        ),
        Parametro(
            "dispositivos_es",
            "Dispositivos de E/S",
            int,
            minimo=1,
            maximo=8,
            ayuda="Operaciones de entrada/salida atendidas en simultaneo.",
        ),
        Parametro(
            "costo_cambio_contexto",
            "Costo de cambio de contexto",
            int,
            minimo=0,
            maximo=5,
            unidad=" ticks",
            ayuda="Sobrecarga que el nucleo gasta al conmutar de proceso.",
        ),
        Parametro(
            "envejecimiento",
            "Envejecimiento",
            int,
            minimo=0,
            maximo=50,
            unidad=" ticks",
            ayuda="Ticks de espera que suben un nivel de prioridad (0 lo desactiva).",
        ),
        Parametro(
            "ticks_por_segundo",
            "Velocidad",
            float,
            minimo=0.25,
            maximo=60,
            unidad=" ticks/s",
            ayuda="Ritmo del reloj de la simulacion.",
        ),
    )
}


@dataclass
class ConfiguracionSimulacion:
    """
    Estado mutable de los parametros. El simulador la lee en cada tick, por lo
    que cualquier cambio aplicado desde una interfaz surte efecto de inmediato.
    """

    algoritmo: str = "fcfs"
    quantum: int = 3
    nucleos_cpu: int = 2
    memoria_total_kb: int = 1024
    politica_memoria: str = "primer_ajuste"
    dispositivos_es: int = 2
    costo_cambio_contexto: int = 1
    envejecimiento: int = 0
    ticks_por_segundo: float = 4.0

    escuchadores: list = field(default_factory=list, repr=False, compare=False)

    def __post_init__(self) -> None:
        for parametro in PARAMETROS.values():
            setattr(self, parametro.nombre, parametro.convertir(getattr(self, parametro.nombre)))

    def aplicar(self, cambios: dict) -> dict:
        """
        Valida y aplica un lote de cambios. Es todo o nada: si algun valor es
        invalido no se modifica ninguno, para no dejar la simulacion a medias.
        """
        desconocidos = set(cambios) - set(PARAMETROS)
        if desconocidos:
            raise ValueError(f"Parametros desconocidos: {', '.join(sorted(desconocidos))}.")

        validados = {
            nombre: PARAMETROS[nombre].convertir(valor) for nombre, valor in cambios.items()
        }
        aplicados = {
            nombre: valor
            for nombre, valor in validados.items()
            if getattr(self, nombre) != valor
        }
        for nombre, valor in aplicados.items():
            setattr(self, nombre, valor)
        for escuchador in self.escuchadores:
            escuchador(aplicados)
        return aplicados

    def como_diccionario(self) -> dict:
        return {
            campo.name: getattr(self, campo.name)
            for campo in fields(self)
            if campo.name != "escuchadores"
        }

    @staticmethod
    def descriptores() -> list[dict]:
        return [parametro.como_diccionario() for parametro in PARAMETROS.values()]
