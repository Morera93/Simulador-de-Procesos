"""
Planificador: coordina el ciclo de vida de los procesos en cada tick.

El estado de cada proceso es la unica fuente de verdad; las colas se derivan de
`self.procesos` filtrando por estado. Asi es imposible que una cola quede
desincronizada del PCB, que es el error clasico al mantener listas paralelas.
"""

from ..algoritmos import crear_algoritmo
from ..modelos.estados import EstadoProceso
from ..modelos.proceso import Proceso


class Planificador:
    def __init__(self, configuracion, cpu, memoria, dispositivos_es, registro):
        self.configuracion = configuracion
        self.cpu = cpu
        self.memoria = memoria
        self.dispositivos_es = dispositivos_es
        self.registro = registro

        self.procesos: list[Proceso] = []
        self.reloj = 0
        self.algoritmo = crear_algoritmo(configuracion.algoritmo, configuracion)
        self._secuencia = 0
        self._sin_memoria: set[int] = set()
        self._completados_es: list[Proceso] = []

    # ------------------------------------------------------------------ colas

    def _por_estado(self, estado: EstadoProceso) -> list[Proceso]:
        return [proceso for proceso in self.procesos if proceso.estado is estado]

    @property
    def programados(self) -> list[Proceso]:
        """Procesos definidos que todavia no han llegado al sistema."""
        return [p for p in self._por_estado(EstadoProceso.NUEVO) if p.tiempo_llegada > self.reloj]

    @property
    def nuevos(self) -> list[Proceso]:
        """Llegaron, pero esperan memoria para ser admitidos."""
        return [p for p in self._por_estado(EstadoProceso.NUEVO) if p.tiempo_llegada <= self.reloj]

    @property
    def listos(self) -> list[Proceso]:
        return sorted(self._por_estado(EstadoProceso.LISTO), key=lambda p: p.secuencia_listos)

    @property
    def en_ejecucion(self) -> list[Proceso]:
        return self._por_estado(EstadoProceso.EJECUCION)

    @property
    def bloqueados(self) -> list[Proceso]:
        return self._por_estado(EstadoProceso.BLOQUEADO)

    @property
    def terminados(self) -> list[Proceso]:
        return self._por_estado(EstadoProceso.TERMINADO)

    @property
    def finalizada(self) -> bool:
        return bool(self.procesos) and all(
            p.estado is EstadoProceso.TERMINADO for p in self.procesos
        )

    # ------------------------------------------------------------- operaciones

    def agregar(self, proceso: Proceso) -> None:
        self.procesos.append(proceso)
        # Un proceso con llegada futura lo anuncia el tick correspondiente; solo
        # se avisa aqui si se incorpora con la llegada ya vencida.
        if proceso.tiempo_llegada < self.reloj:
            self._anunciar_llegada(proceso)

    def sincronizar_algoritmo(self) -> None:
        if self.algoritmo.nombre != self.configuracion.algoritmo:
            self.algoritmo = crear_algoritmo(self.configuracion.algoritmo, self.configuracion)

    def reencolar(self, proceso: Proceso) -> None:
        """Devuelve un proceso al final de la cola de listos."""
        self._secuencia += 1
        proceso.secuencia_listos = self._secuencia
        proceso.cambiar_estado(EstadoProceso.LISTO, self.reloj)

    def tick(self, reloj: int) -> None:
        self.reloj = reloj
        self.sincronizar_algoritmo()

        self._anunciar_llegadas()
        self._admitir()
        self._expropiar()
        self._despachar()
        self._ejecutar()
        self._contabilizar_espera()
        self._resolver_salidas()

    # --------------------------------------------------------------- etapas

    def _anunciar_llegada(self, proceso: Proceso) -> None:
        self.registro.registrar(
            self.reloj,
            "llegada",
            f"Llego {proceso.nombre} (rafaga CPU {proceso.rafaga_cpu}, "
            f"E/S {proceso.rafaga_es}, {proceso.memoria_kb} KB)",
            proceso.pid,
        )

    def _anunciar_llegadas(self) -> None:
        for proceso in self.procesos:
            if proceso.estado is EstadoProceso.NUEVO and proceso.tiempo_llegada == self.reloj:
                self._anunciar_llegada(proceso)

    def _admitir(self) -> None:
        """Planificador a largo plazo: NUEVO -> LISTO cuando hay memoria libre."""
        for proceso in sorted(self.nuevos, key=lambda p: (p.tiempo_llegada, p.pid)):
            if self.memoria.asignar(proceso):
                proceso.tick_admision = self.reloj
                self._sin_memoria.discard(proceso.pid)
                self.reencolar(proceso)
                self.registro.registrar(
                    self.reloj,
                    "memoria",
                    f"{proceso.nombre} admitido: {proceso.memoria_kb} KB en la "
                    f"direccion {proceso.direccion_memoria}",
                    proceso.pid,
                )
            elif proceso.pid not in self._sin_memoria:
                # Se avisa una sola vez por proceso para no inundar la bitacora.
                self._sin_memoria.add(proceso.pid)
                self.registro.registrar(
                    self.reloj,
                    "error",
                    f"{proceso.nombre} en espera: requiere {proceso.memoria_kb} KB y el "
                    f"mayor hueco libre es de {self.memoria.mayor_hueco_kb} KB",
                    proceso.pid,
                )

    def _expropiar(self) -> None:
        """
        Libera nucleos cuando el algoritmo lo exige (quantum agotado o candidato
        mas urgente). Se expropian como maximo tantos nucleos como candidatos
        haya en espera, para no provocar cambios de contexto inutiles.
        """
        candidatos = self.listos
        if not candidatos:
            return

        activos = [n for n in self.cpu.nucleos if not n.libre and not n.conmutando]
        activos.sort(key=lambda n: self.algoritmo.orden_expropiacion(n, self.reloj), reverse=True)

        reservados = 0
        for nucleo in activos:
            if reservados >= len(candidatos):
                break
            candidato = candidatos[reservados]
            proceso = nucleo.proceso
            if not self.algoritmo.debe_expropiar(
                proceso, [candidato], nucleo.ticks_en_proceso, self.reloj
            ):
                continue

            turno = nucleo.ticks_en_proceso
            self.cpu.liberar(nucleo, self.reloj)
            self.reencolar(proceso)
            reservados += 1
            self.registro.registrar(
                self.reloj,
                "expropiacion",
                f"{proceso.nombre} deja el nucleo {nucleo.indice} tras {turno} ticks; "
                f"entra {candidato.nombre}",
                proceso.pid,
            )

    def _despachar(self) -> None:
        for nucleo in self.cpu.nucleos_libres:
            proceso = self.algoritmo.seleccionar(self.listos, self.reloj)
            if proceso is None:
                return

            proceso.cambiar_estado(EstadoProceso.EJECUCION, self.reloj)
            if proceso.tick_primer_despacho is None:
                proceso.tick_primer_despacho = self.reloj
            self.cpu.asignar(
                nucleo, proceso, self.reloj, self.configuracion.costo_cambio_contexto
            )
            self.registro.registrar(
                self.reloj,
                "despacho",
                f"{proceso.nombre} ocupa el nucleo {nucleo.indice} "
                f"({proceso.cpu_restante} ticks de CPU pendientes)",
                proceso.pid,
            )

    def _ejecutar(self) -> None:
        self.cpu.ejecutar_tick()
        self.dispositivos_es.asignar_pendientes()
        self._completados_es = self.dispositivos_es.ejecutar_tick()

    def _contabilizar_espera(self) -> None:
        """La espera se mide sobre el estado que el proceso tuvo durante el tick."""
        for proceso in self.procesos:
            if proceso.estado is EstadoProceso.LISTO:
                proceso.ticks_espera += 1
            elif proceso.estado is EstadoProceso.BLOQUEADO:
                proceso.ticks_bloqueado += 1

    def _resolver_salidas(self) -> None:
        for proceso in self._completados_es:
            self.reencolar(proceso)
            self.registro.registrar(
                self.reloj, "desbloqueo", f"{proceso.nombre} completo su operacion de E/S",
                proceso.pid,
            )
        self._completados_es = []

        for nucleo in list(self.cpu.nucleos):
            proceso = nucleo.proceso
            if proceso is None or nucleo.conmutando:
                continue
            if proceso.finalizo:
                self._finalizar(nucleo, proceso)
            elif proceso.solicita_es:
                self._bloquear(nucleo, proceso)

    def _finalizar(self, nucleo, proceso: Proceso) -> None:
        self.cpu.liberar(nucleo, self.reloj + 1)
        proceso.cambiar_estado(EstadoProceso.TERMINADO, self.reloj + 1)
        proceso.tick_finalizacion = self.reloj + 1
        self.memoria.liberar(proceso)
        self.registro.registrar(
            self.reloj + 1,
            "finalizacion",
            f"{proceso.nombre} termino: retorno {proceso.tiempo_retorno} ticks, "
            f"espera {proceso.ticks_espera} ticks",
            proceso.pid,
        )

    def _bloquear(self, nucleo, proceso: Proceso) -> None:
        self.cpu.liberar(nucleo, self.reloj + 1)
        proceso.cambiar_estado(EstadoProceso.BLOQUEADO, self.reloj + 1)
        proceso.operaciones_es += 1
        proceso.es_restante = proceso.rafaga_es
        self.dispositivos_es.solicitar(proceso)
        self.registro.registrar(
            self.reloj + 1,
            "bloqueo",
            f"{proceso.nombre} solicita E/S por {proceso.rafaga_es} ticks",
            proceso.pid,
        )

    # ------------------------------------------------- cambios en los recursos

    def aplicar_cambio_nucleos(self, cantidad: int) -> None:
        for proceso in self.cpu.redimensionar(cantidad, self.reloj):
            self.reencolar(proceso)

    def colas_como_diccionario(self) -> dict:
        return {
            "programados": [p.como_diccionario() for p in self.programados],
            "nuevos": [p.como_diccionario() for p in self.nuevos],
            "listos": [p.como_diccionario() for p in self.listos],
            "ejecucion": [p.como_diccionario() for p in self.en_ejecucion],
            "bloqueados": [p.como_diccionario() for p in self.bloqueados],
            "terminados": [p.como_diccionario() for p in self.terminados],
        }
