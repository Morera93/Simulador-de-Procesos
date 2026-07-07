# Simulador-de-Procesos

Proyecto Final — Curso Sistemas Operativos I
Bachillerato en Ingenieria de Sistemas — UACA

Simulador de procesos de un sistema operativo: planificacion de procesos,
gestion y visualizacion de recursos (CPU, memoria, E/S), modificacion de
parametros en tiempo real y registro de actividad.

## Estado del proyecto

- [x] **Fase 1 — Estructura del proyecto** (actual): carpetas, paquetes y
      archivos listos, cada uno documentado con su responsabilidad. Sin logica.
- [ ] Fase 2 — Modelos y nucleo (Proceso/PCB, estados, reloj de simulacion).
- [ ] Fase 3 — Algoritmos de planificacion (FCFS, SJF, Round Robin, Prioridad).
- [ ] Fase 4 — Recursos y metricas (CPU, memoria, E/S, reportes).
- [ ] Fase 5 — Interfaz (consola o grafica) y visualizacion en tiempo real.
- [ ] Fase 6 — Documentacion y presentacion final.

## Estructura

```
Simulador-de-Procesos/
├── main.py                     # Punto de entrada
├── requirements.txt            # Dependencias
├── .gitignore
├── data/
│   └── procesos_ejemplo.csv    # Entrada de datos de ejemplo
├── docs/                       # Entregables de documentacion tecnica
│   ├── diseno_sistema.md
│   ├── manual_usuario.md
│   └── analisis_recursos.md
├── src/
│   ├── config.py               # Parametros de la simulacion
│   ├── modelos/                # Proceso (PCB) y estados
│   │   ├── proceso.py
│   │   └── estados.py
│   ├── nucleo/                 # Reloj/bucle y planificador
│   │   ├── simulador.py
│   │   └── planificador.py
│   ├── algoritmos/             # Algoritmos de planificacion
│   │   ├── base.py
│   │   ├── fcfs.py
│   │   ├── sjf.py
│   │   ├── round_robin.py
│   │   └── prioridad.py
│   ├── recursos/               # CPU, memoria y dispositivos de E/S
│   │   ├── cpu.py
│   │   ├── memoria.py
│   │   └── dispositivos_es.py
│   ├── interfaz/               # Interfaz de usuario
│   │   ├── consola.py
│   │   └── grafica.py
│   └── reportes/               # Metricas y registro de actividad
│       ├── metricas.py
│       └── registro.py
└── tests/                      # Pruebas
    ├── test_algoritmos.py
    ├── test_planificador.py
    └── test_recursos.py
```

## Puesta en marcha (Fase 2 en adelante)

> Nota: aun no hay Python instalado en este equipo (solo los accesos del
> Microsoft Store). Instalar Python 3 desde https://www.python.org/downloads/
> y marcar "Add python.exe to PATH".

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
python main.py
```
