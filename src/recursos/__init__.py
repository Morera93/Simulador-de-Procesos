"""Recursos del sistema simulado: CPU, memoria y dispositivos de E/S."""

from .cpu import CPU, Nucleo
from .dispositivos_es import DispositivoES, SubsistemaES
from .memoria import GestorMemoria, Particion

__all__ = ["CPU", "Nucleo", "DispositivoES", "SubsistemaES", "GestorMemoria", "Particion"]
