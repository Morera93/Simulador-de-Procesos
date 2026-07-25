"""
Interfaz grafica: panel web servido por la biblioteca estandar.

Se eligio un panel en el navegador en lugar de una GUI de escritorio porque no
agrega dependencias (`http.server` viene con Python), corre igual en cualquier
sistema operativo y permite una visualizacion en tiempo real mucho mas rica.

El servidor solo expone la fachada del simulador como JSON: toda la logica vive
en `src/nucleo`, y la vista se limita a pintar la instantanea que recibe.
"""

import json
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..config import ConfiguracionSimulacion
from ..nucleo.entrada import descriptores_proceso
from ..nucleo.simulador import Simulador
from ..reportes.registro import CATEGORIAS

DIRECTORIO_WEB = Path(__file__).parent / "web"

ARCHIVOS_ESTATICOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/estilos.css": ("estilos.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}

TAMANO_MAXIMO_PETICION = 64 * 1024


class ManejadorPanel(BaseHTTPRequestHandler):
    """Traduce peticiones HTTP a operaciones del simulador."""

    protocol_version = "HTTP/1.1"
    server_version = "SimuladorProcesos/1.0"

    def __init__(self, simulador: Simulador, *args, **kwargs):
        self.simulador = simulador
        super().__init__(*args, **kwargs)

    def log_message(self, formato, *args):
        """Silencia el registro por peticion para no ensuciar la terminal."""

    # ------------------------------------------------------------- respuestas

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _responder_json(self, datos: dict, codigo: int = 200) -> None:
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self._responder(codigo, cuerpo, "application/json; charset=utf-8")

    def _responder_error(self, mensaje: str, codigo: int = 400) -> None:
        self._responder_json({"error": mensaje}, codigo)

    def _leer_json(self) -> dict:
        longitud = int(self.headers.get("Content-Length") or 0)
        if longitud <= 0:
            return {}
        if longitud > TAMANO_MAXIMO_PETICION:
            raise ValueError("La peticion excede el tamano permitido.")
        try:
            return json.loads(self.rfile.read(longitud).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("El cuerpo de la peticion no es JSON valido.")

    # ------------------------------------------------------------------- GET

    def do_GET(self) -> None:
        ruta = urlparse(self.path)
        try:
            if ruta.path in ARCHIVOS_ESTATICOS:
                nombre, tipo = ARCHIVOS_ESTATICOS[ruta.path]
                self._responder(200, (DIRECTORIO_WEB / nombre).read_bytes(), tipo)
            elif ruta.path == "/api/estado":
                desde = int(parse_qs(ruta.query).get("desde", ["0"])[0])
                self._responder_json(self.simulador.instantanea(desde))
            elif ruta.path == "/api/metadatos":
                self._responder_json(self._metadatos())
            else:
                self._responder_error("Recurso no encontrado.", 404)
        except FileNotFoundError:
            self._responder_error("Falta un archivo de la interfaz web.", 500)
        except ValueError as error:
            self._responder_error(str(error))

    def _metadatos(self) -> dict:
        return {
            "parametros": ConfiguracionSimulacion.descriptores(),
            "campos_proceso": descriptores_proceso(),
            "categorias": CATEGORIAS,
        }

    # ------------------------------------------------------------------ POST

    def do_POST(self) -> None:
        ruta = urlparse(self.path).path
        acciones = {
            "/api/control": self._accion_control,
            "/api/parametros": self._accion_parametros,
            "/api/procesos": self._accion_proceso,
            "/api/procesos/aleatorios": self._accion_carga_aleatoria,
            "/api/exportar": self._accion_exportar,
        }
        manejador = acciones.get(ruta)
        if manejador is None:
            self._responder_error("Recurso no encontrado.", 404)
            return

        try:
            self._responder_json(manejador(self._leer_json()))
        except ValueError as error:
            self._responder_error(str(error))
        except OSError as error:
            self._responder_error(f"No se pudo escribir el reporte: {error}", 500)

    def _accion_control(self, datos: dict) -> dict:
        operaciones = {
            "iniciar": self.simulador.iniciar,
            "pausar": self.simulador.pausar,
            "alternar": self.simulador.alternar,
            "paso": self.simulador.paso,
            "reiniciar": self.simulador.reiniciar,
        }
        accion = str(datos.get("accion", "")).strip().lower()
        if accion not in operaciones:
            raise ValueError(f"Accion desconocida: '{accion}'.")
        operaciones[accion]()
        return {"estado": self.simulador.estado.value}

    def _accion_parametros(self, datos: dict) -> dict:
        return {"aplicados": self.simulador.aplicar_parametros(datos)}

    def _accion_proceso(self, datos: dict) -> dict:
        proceso = self.simulador.agregar_proceso(datos)
        return {"proceso": proceso.como_diccionario()}

    def _accion_carga_aleatoria(self, datos: dict) -> dict:
        semilla = datos.get("semilla")
        procesos = self.simulador.generar_procesos(
            datos.get("cantidad", 5), int(semilla) if semilla not in ("", None) else None
        )
        return {"generados": len(procesos)}

    def _accion_exportar(self, datos: dict) -> dict:
        return {"archivos": self.simulador.exportar()}


class ServidorPanel:
    """Arranca el panel web y mantiene el proceso vivo hasta Ctrl+C."""

    def __init__(self, simulador: Simulador, host: str = "127.0.0.1", puerto: int = 8765):
        self.simulador = simulador
        self.host = host
        self.puerto = puerto

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.puerto}/"

    def ejecutar(self, abrir_navegador: bool = True) -> None:
        manejador = partial(ManejadorPanel, self.simulador)
        try:
            servidor = ThreadingHTTPServer((self.host, self.puerto), manejador)
        except OSError as error:
            raise SystemExit(
                f"No se pudo abrir el puerto {self.puerto}: {error}. "
                f"Use --puerto para elegir otro."
            ) from error

        print(f"Panel del simulador disponible en {self.url}")
        print("Presione Ctrl+C para detener el servidor.")
        if abrir_navegador:
            webbrowser.open(self.url)

        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nDeteniendo el simulador...")
        finally:
            self.simulador.detener()
            servidor.server_close()
