"""FCFS (First Come, First Served): orden de llegada, sin expropiacion."""

from .base import AlgoritmoPlanificacion


class PrimeroEnLlegar(AlgoritmoPlanificacion):
    """
    Usa el orden de encolado heredado de la clase base: el proceso que lleva mas
    tiempo en la cola de listos es el siguiente en ocupar la CPU. Un proceso que
    regresa de E/S se reincorpora al final, igual que en un sistema real.
    """

    nombre = "fcfs"
    etiqueta = "FCFS (primero en llegar)"
    apropiativo = False
