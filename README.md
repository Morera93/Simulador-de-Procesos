# Simulador de Procesos

Proyecto Final — Sistemas Operativos I
Bachillerato en Ingenieria de Sistemas — UACA

Simulador de los procesos de un sistema operativo: planificacion, gestion y
visualizacion de recursos (CPU, memoria y E/S), modificacion de parametros en
tiempo real y registro de actividad.

**Sin dependencias externas.** Solo requiere Python 3.10 o superior.

---

## Puesta en marcha

```bash
python main.py
```

Abre el panel en <http://127.0.0.1:8765/> con los procesos de
`data/procesos_ejemplo.csv`. Para el tablero de terminal:

```bash
python main.py --interfaz consola
```

Otros ejemplos:

```bash
python main.py --generar 12 --semilla 7 --algoritmo srtf --nucleos 4
```

`python main.py --help` lista todas las opciones y sus rangos validos.

---

## Que hace

**Entrada de datos.** Carga desde CSV, generador de carga sintetica reproducible
por semilla y alta manual de procesos con la simulacion en marcha. Toda entrada
pasa por la misma validacion, con mensajes en espanol que indican archivo, linea
y campo.

**Recursos visibles en tiempo real.**

- *CPU multinucleo* con costo de cambio de contexto configurable. Cada tick de
  nucleo se clasifica en trabajo util, sobrecarga u ocioso.
- *Memoria* por particiones dinamicas contiguas con primer, mejor y peor ajuste,
  fusion de huecos y medicion de fragmentacion externa.
- *Dispositivos de E/S* con cola de peticiones.

**Seis politicas de planificacion:** FCFS, SJF, SRTF, Round Robin, Prioridad y
Prioridad apropiativa, esta ultima con envejecimiento contra la inanicion.

**Parametros modificables en caliente:** algoritmo, quantum, nucleos, memoria
total, politica de memoria, dispositivos de E/S, costo de cambio de contexto,
envejecimiento y velocidad del reloj. Ninguno requiere reiniciar la simulacion.

**Registro y reportes.** Bitacora de eventos clasificada por categoria y
exportacion a `reportes_generados/`: reporte de la corrida, detalle de procesos
en CSV y bitacora completa en CSV.

**Dos interfaces.** Panel web (retícula bento, tema oscuro, diagrama de Gantt,
mapa de memoria, series de uso) y tablero de consola con ANSI. Ambas consumen la
misma instantanea del simulador.

---

## Estructura

```
Simulador-de-Procesos/
├── main.py                     # Punto de entrada y linea de comandos
├── requirements.txt            # (sin dependencias)
├── data/
│   └── procesos_ejemplo.csv    # Entrada de datos de ejemplo
└── src/
    ├── config.py               # Parametros y su validacion
    ├── modelos/                # PCB y maquina de estados
    │   ├── proceso.py
    │   └── estados.py
    ├── nucleo/                 # Entrada de datos, planificador y reloj
    │   ├── entrada.py
    │   ├── planificador.py
    │   └── simulador.py
    ├── algoritmos/             # Politicas de planificacion
    │   ├── base.py
    │   ├── fcfs.py
    │   ├── sjf.py
    │   ├── round_robin.py
    │   └── prioridad.py
    ├── recursos/               # CPU, memoria y dispositivos de E/S
    │   ├── cpu.py
    │   ├── memoria.py
    │   └── dispositivos_es.py
    ├── reportes/               # Bitacora y metricas
    │   ├── registro.py
    │   └── metricas.py
    └── interfaz/               # Panel web (+ web/) y consola
        ├── grafica.py
        ├── consola.py
        └── web/
```

---

## Arquitectura

Patron **Modelo - Vista - Controlador**, con una regla que se cumple sin
excepciones: **las vistas no calculan nada**. Consumen una instantanea
(`Simulador.instantanea()`) y envian ordenes; toda la logica vive en el nucleo.

| Capa | Modulos |
|---|---|
| Vistas | `interfaz/grafica.py` (panel web), `interfaz/consola.py` (terminal) |
| Controladores | `nucleo/simulador.py`, `nucleo/planificador.py`, `nucleo/entrada.py`, `algoritmos/` |
| Modelos | `modelos/`, `recursos/`, `reportes/`, `config.py` |

Las dependencias apuntan siempre hacia adentro: `interfaz` conoce a `nucleo`;
`nucleo` conoce a `modelos`, `recursos` y `algoritmos`; los modelos no conocen a
nadie.

### Decisiones tecnicas

**Las colas se derivan del estado.** `Planificador` guarda una sola lista de
procesos y expone `listos`, `bloqueados`, etc. como propiedades que filtran por
estado. Mantener listas paralelas es la fuente clasica de desincronizacion entre
la cola y el PCB. El orden FIFO se conserva con `secuencia_listos`.

**Los algoritmos solo definen un criterio de orden.** La seleccion y la
expropiacion se implementan una sola vez en `AlgoritmoPlanificacion`; cada
politica sobrescribe `clave_orden()`. FCFS y Round Robin heredan el orden FIFO
por defecto.

**Un solo descriptor por parametro.** `PARAMETROS` define etiqueta, tipo,
limites, unidad y ayuda. El mismo diccionario valida los cambios, genera las
opciones de la linea de comandos y construye los controles de las dos interfaces.

**Un unico cerrojo reentrante.** El reloj corre en un hilo aparte mientras el
panel web atiende peticiones; todas las mutaciones pasan por `Simulador._bloqueo`.
La espera entre ticks ocurre fuera del cerrojo para no bloquear a la interfaz.

**Cambios de parametros con reversion.** Si un recurso rechaza el cambio (por
ejemplo, reducir la memoria por debajo de lo que ocupan los procesos cargados),
la configuracion vuelve a su valor anterior.

---

## Cumplimiento de los requisitos

| Requisito del enunciado | Donde vive |
|---|---|
| Simulacion de la entrada de datos | [entrada.py](src/nucleo/entrada.py), [procesos_ejemplo.csv](data/procesos_ejemplo.csv) |
| Consumo de CPU, memoria y E/S | [cpu.py](src/recursos/cpu.py), [memoria.py](src/recursos/memoria.py), [dispositivos_es.py](src/recursos/dispositivos_es.py) |
| Parametros modificables en tiempo real | [config.py](src/config.py), [simulador.py](src/nucleo/simulador.py) |
| Registro y reporte de actividades | [registro.py](src/reportes/registro.py), [metricas.py](src/reportes/metricas.py) |
| Interfaz grafica o de consola | [grafica.py](src/interfaz/grafica.py), [consola.py](src/interfaz/consola.py) |
