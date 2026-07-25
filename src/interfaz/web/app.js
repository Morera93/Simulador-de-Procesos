/* Panel del Simulador de Procesos.
   La vista no guarda estado propio del sistema: pinta la instantanea que
   entrega /api/estado y envia las acciones del usuario a la API. */

const PERIODO_ACTIVO = 250;
const PERIODO_OCULTO = 1500;
const MAXIMO_EVENTOS_VISIBLES = 300;
const VENTANA_GANTT = 120;

const estado = { ultimoEvento: 0, ultimoReloj: 0, metadatos: null };

const $ = (selector) => document.querySelector(selector);
const crear = (etiqueta, clase) => {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  return nodo;
};

/* Color estable por PID: el mismo proceso se reconoce en el mapa de memoria,
   el diagrama de Gantt y las colas sin necesidad de leer el numero. */
const colorProceso = (pid) => `hsl(${(pid * 47) % 360} 62% 58%)`;

async function peticion(url, opciones) {
  const respuesta = await fetch(url, opciones);
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(datos.error || `Error ${respuesta.status}`);
  return datos;
}

const enviar = (url, cuerpo) =>
  peticion(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cuerpo || {}),
  });

function mostrarAviso(mensaje, tono) {
  const aviso = $('#aviso');
  aviso.textContent = mensaje;
  aviso.dataset.tono = tono || 'error';
  aviso.hidden = false;
  clearTimeout(mostrarAviso.temporizador);
  mostrarAviso.temporizador = setTimeout(() => { aviso.hidden = true; }, 6000);
}

const conError = (accion) => accion().catch((error) => mostrarAviso(error.message));

/* ------------------------------------------------------------- formularios */

function campoParametro(descriptor) {
  const campo = crear('div', 'campo');
  const identificador = `parametro-${descriptor.nombre}`;
  const encabezado = crear('div', 'campo__etiqueta');
  const etiqueta = crear('label');
  etiqueta.htmlFor = identificador;
  etiqueta.textContent = descriptor.etiqueta;
  encabezado.append(etiqueta);

  let control;
  if (descriptor.opciones) {
    control = crear('select');
    for (const [valor, texto] of Object.entries(descriptor.opciones)) {
      control.add(new Option(texto, valor));
    }
  } else {
    control = crear('input');
    const esVelocidad = descriptor.nombre === 'ticks_por_segundo';
    control.type = esVelocidad ? 'range' : 'number';
    control.min = descriptor.minimo;
    control.max = descriptor.maximo;
    control.step = descriptor.tipo === 'float' ? 0.25 : 1;
    if (!esVelocidad) control.inputMode = 'numeric';
    if (esVelocidad) {
      const salida = crear('output', 'campo__valor');
      salida.id = `${identificador}-valor`;
      encabezado.append(salida);
    }
  }

  control.id = identificador;
  control.name = descriptor.nombre;
  control.dataset.parametro = descriptor.nombre;
  control.title = descriptor.ayuda;

  const ayuda = crear('span', 'campo__ayuda');
  ayuda.textContent = descriptor.ayuda;
  ayuda.id = `${identificador}-ayuda`;
  control.setAttribute('aria-describedby', ayuda.id);

  campo.append(encabezado, control, ayuda);
  return campo;
}

function construirParametros() {
  const formulario = $('#form-parametros');
  formulario.append(...estado.metadatos.parametros.map(campoParametro));

  formulario.addEventListener('change', (evento) => {
    const nombre = evento.target.dataset.parametro;
    if (nombre) aplicarParametro(nombre, evento.target.value);
  });
  // El deslizador de velocidad se refleja al instante, pero solo se envia al
  // soltarlo (evento change) para no saturar el servidor.
  formulario.addEventListener('input', (evento) => {
    if (evento.target.type === 'range') actualizarSalidaRango(evento.target);
  });
}

function actualizarSalidaRango(control) {
  const salida = document.getElementById(`${control.id}-valor`);
  if (salida) salida.textContent = `${control.value} ticks/s`;
}

function aplicarParametro(nombre, valor) {
  conError(async () => {
    await enviar('/api/parametros', { [nombre]: valor });
    await sondear();
  });
}

function construirCamposProceso() {
  const contenedor = $('#campos-proceso');
  for (const descriptor of estado.metadatos.campos_proceso) {
    const campo = crear('div', 'campo');
    const identificador = `proceso-${descriptor.nombre}`;
    const etiqueta = crear('label');
    etiqueta.htmlFor = identificador;
    etiqueta.textContent = descriptor.etiqueta;

    const control = crear('input');
    control.type = 'number';
    control.id = identificador;
    control.name = descriptor.nombre;
    control.min = descriptor.minimo;
    control.max = descriptor.maximo;
    control.inputMode = 'numeric';
    control.placeholder = descriptor.nombre === 'rafaga_cpu' ? '5' : '0';

    campo.append(etiqueta, control);
    contenedor.append(campo);
  }
}

function datosFormulario(formulario) {
  return Object.fromEntries(
    [...new FormData(formulario).entries()].filter(([, valor]) => valor !== '')
  );
}

/* ------------------------------------------------------------------ pintado */

function pintarBarra(datos) {
  $('#reloj').textContent = datos.reloj;
  $('#estado').dataset.estado = datos.estado;
  $('#estado-texto').textContent = datos.estado_etiqueta;
  $('#algoritmo-activo').textContent = datos.algoritmo_activo;

  const ejecutando = datos.estado === 'ejecutando';
  $('#icono-ejecutar').setAttribute('href', ejecutando ? '#i-pausar' : '#i-ejecutar');
  $('#btn-ejecutar-texto').textContent = ejecutando ? 'Pausar' : 'Iniciar';
  $('#btn-ejecutar').disabled = datos.estado === 'finalizada';
  $('#btn-paso').disabled = ejecutando || datos.estado === 'finalizada';
}

function pintarParametros(configuracion) {
  for (const [nombre, valor] of Object.entries(configuracion)) {
    const control = document.getElementById(`parametro-${nombre}`);
    if (!control || control === document.activeElement) continue;
    if (control.value !== String(valor)) control.value = valor;
    if (control.type === 'range') actualizarSalidaRango(control);
  }
}

function pintarCPU(datos) {
  const contenedor = $('#nucleos');
  contenedor.replaceChildren(...datos.cpu.nucleos.map((nucleo) => {
    const tarjeta = crear('div', 'nucleo');
    tarjeta.dataset.ocupado = nucleo.pid === null ? 'no' : 'si';
    tarjeta.dataset.conmutando = nucleo.conmutando ? 'si' : 'no';
    if (nucleo.pid !== null) tarjeta.style.setProperty('--proceso', colorProceso(nucleo.pid));

    const titulo = crear('div', 'nucleo__titulo');
    titulo.append(`Nucleo ${nucleo.indice}`);
    const marca = crear('span');
    marca.textContent = nucleo.conmutando ? 'conmutando' : nucleo.pid === null ? 'libre' : 'activo';
    titulo.append(marca);

    const proceso = crear('span', 'nucleo__proceso');
    if (nucleo.pid === null) {
      proceso.classList.add('nucleo__proceso--libre');
      proceso.textContent = 'Sin proceso';
    } else {
      proceso.textContent = `${nucleo.nombre}`;
    }

    const detalle = crear('div', 'nucleo__detalle');
    detalle.textContent = nucleo.pid === null
      ? `ocioso ${nucleo.ticks_ocioso} ticks`
      : `PID ${nucleo.pid} · CPU restante ${nucleo.cpu_restante} · turno ${nucleo.ticks_en_proceso}`;

    const barra = crear('div', 'barra-progreso');
    const relleno = crear('i');
    relleno.style.width = `${nucleo.pid === null ? 0 : nucleo.avance}%`;
    barra.append(relleno);

    tarjeta.append(titulo, proceso, detalle, barra);
    return tarjeta;
  }));

  $('#cpu-uso').textContent = `${datos.cpu.porcentaje_uso}%`;
  $('#cpu-util').textContent = `${datos.cpu.rendimiento_util}%`;
  $('#cpu-sobrecarga').textContent = datos.cpu.ticks_sobrecarga;
  $('#cpu-ocioso').textContent = datos.cpu.ticks_ocioso;
  $('#cpu-cambios').textContent = datos.metricas.cambios_contexto;
}

function pintarIndicadores(datos) {
  const m = datos.metricas;
  const filas = [
    ['Procesos terminados', `${m.procesos_terminados}/${m.procesos_totales}`, ''],
    ['Espera promedio', m.promedio_espera, 'ticks'],
    ['Retorno promedio', m.promedio_retorno, 'ticks'],
    ['Respuesta promedio', m.promedio_respuesta, 'ticks'],
    ['Bloqueo promedio', m.promedio_bloqueo, 'ticks'],
    ['Rendimiento', m.rendimiento, 'proc/tick'],
    ['Operaciones de E/S', m.operaciones_es, ''],
  ];
  $('#indicadores').replaceChildren(...filas.map(([titulo, valor, unidad]) => {
    const fila = crear('li');
    const texto = crear('span');
    texto.textContent = titulo;
    const numero = crear('b');
    numero.append(String(valor));
    if (unidad) {
      const sufijo = crear('small');
      sufijo.textContent = unidad;
      numero.append(sufijo);
    }
    fila.append(texto, numero);
    return fila;
  }));
}

function pintarMemoria(datos) {
  const memoria = datos.memoria;
  const mapa = $('#mapa-memoria');
  mapa.replaceChildren(...memoria.particiones.map((particion) => {
    const bloque = crear('div', particion.libre ? 'bloque bloque--libre' : 'bloque');
    bloque.style.flex = `${particion.tamano} 1 0`;
    if (!particion.libre) bloque.style.setProperty('--proceso', colorProceso(particion.pid));
    const porcentaje = (particion.tamano / memoria.total_kb) * 100;
    if (porcentaje > 7) bloque.textContent = particion.libre ? `${particion.tamano} KB` : `P${particion.pid}`;
    bloque.title = particion.libre
      ? `Hueco libre de ${particion.tamano} KB en la direccion ${particion.inicio}`
      : `PID ${particion.pid}: ${particion.tamano} KB desde la direccion ${particion.inicio}`;
    return bloque;
  }));

  const ocupadas = memoria.particiones.filter((p) => !p.libre);
  $('#leyenda-memoria').replaceChildren(...ocupadas.map((particion) => {
    const item = crear('li');
    const muestra = crear('i');
    muestra.style.setProperty('--proceso', colorProceso(particion.pid));
    item.append(muestra, `PID ${particion.pid} · ${particion.tamano} KB`);
    return item;
  }));

  $('#memoria-uso').textContent = `${memoria.porcentaje_uso}%`;
  $('#memoria-usada').textContent = `${memoria.usados_kb} KB`;
  $('#memoria-libre').textContent = `${memoria.libres_kb} KB`;
  $('#memoria-hueco').textContent = `${memoria.mayor_hueco_kb} KB`;
  $('#memoria-fragmentacion').textContent = `${memoria.fragmentacion_externa}%`;
}

function pintarES(datos) {
  const subsistema = datos.dispositivos_es;
  $('#dispositivos').replaceChildren(...subsistema.dispositivos.map((dispositivo) => {
    const tarjeta = crear('div', 'dispositivo');
    tarjeta.dataset.ocupado = dispositivo.pid === null ? 'no' : 'si';

    const titulo = crear('div', 'dispositivo__titulo');
    titulo.textContent = `Dispositivo ${dispositivo.indice}`;

    const proceso = crear('div', 'dispositivo__proceso');
    if (dispositivo.pid === null) {
      proceso.classList.add('dispositivo__proceso--libre');
      proceso.textContent = 'Inactivo';
    } else {
      proceso.textContent = dispositivo.nombre;
    }

    const detalle = crear('div', 'dispositivo__detalle');
    detalle.textContent = dispositivo.pid === null
      ? `${dispositivo.operaciones_atendidas} operaciones`
      : `restan ${dispositivo.es_restante} ticks`;

    tarjeta.append(titulo, proceso, detalle);
    return tarjeta;
  }));

  $('#es-uso').textContent = `${subsistema.porcentaje_uso}%`;
  pintarFichas($('#cola-es'), subsistema.cola_espera, (p) => `${p.es_restante}t`);
}

function pintarFichas(contenedor, procesos, extra) {
  if (!procesos.length) {
    const vacio = crear('span', 'fichas--vacia');
    vacio.textContent = 'sin procesos';
    contenedor.replaceChildren(vacio);
    return;
  }
  contenedor.replaceChildren(...procesos.map((proceso) => {
    const ficha = crear('span', 'ficha');
    const pid = crear('span', 'ficha__pid');
    pid.style.setProperty('--proceso', colorProceso(proceso.pid));
    pid.textContent = proceso.pid;
    const nombre = crear('span', 'ficha__nombre');
    nombre.textContent = proceso.nombre;
    ficha.append(pid, nombre);
    if (extra) {
      const dato = crear('span', 'ficha__extra');
      dato.textContent = extra(proceso);
      ficha.append(dato);
    }
    return ficha;
  }));
}

const COLUMNAS_COLAS = [
  ['programados', 'Programados', (p) => `t${p.tiempo_llegada}`],
  ['nuevos', 'Esperando memoria', (p) => `${p.memoria_kb}KB`],
  ['listos', 'Listos', (p) => `${p.cpu_restante}t`],
  ['ejecucion', 'En ejecucion', (p) => `N${p.nucleo}`],
  ['bloqueados', 'Bloqueados', (p) => `${p.es_restante}t`],
  ['terminados', 'Terminados', (p) => `r${p.retorno}`],
];

function pintarColas(datos) {
  $('#colas').replaceChildren(...COLUMNAS_COLAS.map(([clave, titulo, extra]) => {
    const columna = crear('div', 'cola');
    const encabezado = crear('div', 'cola__titulo');
    encabezado.append(titulo);
    const conteo = crear('span', 'cola__conteo');
    conteo.textContent = datos.colas[clave].length;
    encabezado.append(conteo);

    const fichas = crear('div', 'fichas');
    pintarFichas(fichas, datos.colas[clave], extra);
    columna.append(encabezado, fichas);
    return columna;
  }));
}

function pintarTabla(datos) {
  $('#tabla-procesos').replaceChildren(...datos.procesos.map((proceso) => {
    const fila = crear('tr');
    const celdas = [
      proceso.pid, proceso.nombre, null,
      `${proceso.cpu_restante}/${proceso.rafaga_cpu}`, proceso.prioridad, proceso.memoria_kb,
      proceso.espera, proceso.retorno ?? '—', proceso.respuesta ?? '—',
    ];
    celdas.forEach((valor, indice) => {
      const celda = crear('td');
      if (indice === 0) {
        const marca = crear('span', 'marca-pid');
        marca.style.setProperty('--proceso', colorProceso(proceso.pid));
        celda.append(marca, String(valor));
      } else if (indice === 2) {
        const etiqueta = crear('span', 'etiqueta-estado');
        etiqueta.dataset.valor = proceso.estado;
        etiqueta.textContent = proceso.estado_etiqueta;
        celda.append(etiqueta);
      } else {
        celda.textContent = valor;
      }
      fila.append(celda);
    });
    return fila;
  }));
}

function pintarBitacora(eventos) {
  if (!eventos.length) return;
  const lista = $('#bitacora');
  for (const evento of eventos) {
    const fila = crear('li');
    fila.dataset.categoria = evento.categoria;

    const tick = crear('span', 'bitacora__tick');
    tick.textContent = `t${evento.tick}`;
    const categoria = crear('span', 'bitacora__categoria');
    categoria.textContent = evento.categoria_etiqueta;
    const mensaje = crear('span', 'bitacora__mensaje');
    mensaje.textContent = evento.mensaje;

    fila.append(tick, categoria, mensaje);
    lista.append(fila);
  }
  while (lista.childElementCount > MAXIMO_EVENTOS_VISIBLES) lista.firstElementChild.remove();
  if ($('#auto-desplazar').checked) lista.scrollTop = lista.scrollHeight;
}

/* -------------------------------------------------------------- graficos */

function prepararLienzo(lienzo) {
  const escala = window.devicePixelRatio || 1;
  const ancho = lienzo.clientWidth;
  const alto = lienzo.clientHeight || Number(lienzo.getAttribute('height'));
  if (lienzo.width !== ancho * escala || lienzo.height !== alto * escala) {
    lienzo.width = ancho * escala;
    lienzo.height = alto * escala;
  }
  const contexto = lienzo.getContext('2d');
  contexto.setTransform(escala, 0, 0, escala, 0, 0);
  contexto.clearRect(0, 0, ancho, alto);
  return { contexto, ancho, alto };
}

const estiloCSS = (nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();

function dibujarGantt(datos) {
  const lienzo = $('#gantt');
  const filas = datos.cpu.nucleos.length;
  lienzo.style.height = `${Math.max(110, filas * 32 + 22)}px`;
  const { contexto, ancho, alto } = prepararLienzo(lienzo);
  const margenIzquierdo = 46;
  const margenInferior = 18;
  const desde = Math.max(0, datos.reloj - VENTANA_GANTT);
  const hasta = Math.max(datos.reloj, desde + 1);
  const escalaX = (ancho - margenIzquierdo - 8) / (hasta - desde);
  const altoFila = (alto - margenInferior) / filas;

  contexto.font = '11px ui-monospace, Consolas, monospace';
  contexto.textBaseline = 'middle';

  for (let fila = 0; fila < filas; fila += 1) {
    contexto.fillStyle = fila % 2 ? 'rgba(22,35,60,0.55)' : 'rgba(16,26,46,0.55)';
    contexto.fillRect(margenIzquierdo, fila * altoFila, ancho - margenIzquierdo - 8, altoFila - 3);
    contexto.fillStyle = estiloCSS('--texto-tenue');
    contexto.textAlign = 'left';
    contexto.fillText(`N${fila}`, 6, fila * altoFila + altoFila / 2 - 1);
  }

  const paso = Math.max(5, Math.ceil((hasta - desde) / 12 / 5) * 5);
  contexto.textAlign = 'center';
  for (let tick = Math.ceil(desde / paso) * paso; tick <= hasta; tick += paso) {
    const x = margenIzquierdo + (tick - desde) * escalaX;
    contexto.strokeStyle = 'rgba(53,72,110,0.5)';
    contexto.lineWidth = 1;
    contexto.beginPath();
    contexto.moveTo(x, 0);
    contexto.lineTo(x, alto - margenInferior);
    contexto.stroke();
    contexto.fillStyle = estiloCSS('--texto-tenue');
    contexto.fillText(tick, x, alto - margenInferior / 2);
  }

  for (const segmento of datos.gantt) {
    const inicio = Math.max(segmento.inicio, desde);
    if (segmento.fin <= desde || segmento.nucleo >= filas) continue;
    const x = margenIzquierdo + (inicio - desde) * escalaX;
    const anchoBloque = Math.max(2, (segmento.fin - inicio) * escalaX - 1);
    const y = segmento.nucleo * altoFila;
    contexto.fillStyle = colorProceso(segmento.pid);
    contexto.beginPath();
    contexto.roundRect(x, y + 3, anchoBloque, altoFila - 9, 3);
    contexto.fill();
    if (anchoBloque > 22) {
      contexto.fillStyle = '#06140b';
      contexto.textAlign = 'center';
      contexto.fillText(`P${segmento.pid}`, x + anchoBloque / 2, y + altoFila / 2 - 1);
    }
  }
}

const SERIES = [
  ['cpu', '--acento', []],
  ['memoria', '--info', [5, 3]],
  ['es', '--violeta', [2, 3]],
];

function dibujarSeries(datos) {
  const pico = (clave) => Math.max(0, ...datos.series[clave]);
  $('#pico-cpu').textContent = `${pico('cpu')}%`;
  $('#pico-memoria').textContent = `${pico('memoria')}%`;
  $('#pico-es').textContent = `${pico('es')}%`;
  $('#pico-listos').textContent = pico('listos');

  const { contexto, ancho, alto } = prepararLienzo($('#series'));
  const margen = 26;
  const util = ancho - margen - 6;
  const muestras = datos.series.cpu.length;

  contexto.font = '10px ui-monospace, Consolas, monospace';
  contexto.textBaseline = 'middle';
  contexto.textAlign = 'right';
  for (const nivel of [0, 50, 100]) {
    const y = alto - 12 - (nivel / 100) * (alto - 24);
    contexto.strokeStyle = 'rgba(53,72,110,0.45)';
    contexto.setLineDash([2, 3]);
    contexto.beginPath();
    contexto.moveTo(margen, y);
    contexto.lineTo(ancho - 6, y);
    contexto.stroke();
    contexto.setLineDash([]);
    contexto.fillStyle = estiloCSS('--texto-tenue');
    contexto.fillText(`${nivel}`, margen - 5, y);
  }

  if (muestras < 2) return;
  const escalaX = util / (muestras - 1);
  for (const [clave, color, patron] of SERIES) {
    contexto.strokeStyle = estiloCSS(color);
    contexto.lineWidth = 1.8;
    contexto.setLineDash(patron);
    contexto.beginPath();
    datos.series[clave].forEach((valor, indice) => {
      const x = margen + indice * escalaX;
      const y = alto - 12 - (valor / 100) * (alto - 24);
      if (indice === 0) contexto.moveTo(x, y);
      else contexto.lineTo(x, y);
    });
    contexto.stroke();
  }
  contexto.setLineDash([]);
}

/* ------------------------------------------------------------------- ciclo */

function pintar(datos) {
  if (datos.reloj < estado.ultimoReloj) {
    $('#bitacora').replaceChildren();
    estado.ultimoEvento = 0;
  }
  estado.ultimoReloj = datos.reloj;

  pintarBarra(datos);
  pintarParametros(datos.configuracion);
  pintarCPU(datos);
  pintarIndicadores(datos);
  pintarMemoria(datos);
  pintarES(datos);
  pintarColas(datos);
  pintarTabla(datos);
  pintarBitacora(datos.eventos);
  dibujarGantt(datos);
  dibujarSeries(datos);
}

async function sondear() {
  const datos = await peticion(`/api/estado?desde=${estado.ultimoEvento}`);
  pintar(datos);
  estado.ultimoEvento = datos.ultimo_evento;
  return datos;
}

function programarSondeo() {
  sondear()
    .catch((error) => mostrarAviso(`Sin conexion con el simulador: ${error.message}`))
    .finally(() => {
      setTimeout(programarSondeo, document.hidden ? PERIODO_OCULTO : PERIODO_ACTIVO);
    });
}

/* ----------------------------------------------------------------- eventos */

const control = (accion) => conError(async () => {
  await enviar('/api/control', { accion });
  if (accion === 'reiniciar') {
    estado.ultimoEvento = 0;
    estado.ultimoReloj = 0;
    $('#bitacora').replaceChildren();
  }
  await sondear();
});

function exportar() {
  conError(async () => {
    const { archivos } = await enviar('/api/exportar');
    mostrarAviso(`Reporte generado: ${Object.values(archivos).join(' · ')}`, 'exito');
  });
}

function registrarEventos() {
  $('#btn-ejecutar').addEventListener('click', () => control('alternar'));
  $('#btn-paso').addEventListener('click', () => control('paso'));
  $('#btn-reiniciar').addEventListener('click', () => control('reiniciar'));
  $('#btn-exportar').addEventListener('click', exportar);

  $('#form-proceso').addEventListener('submit', (evento) => {
    evento.preventDefault();
    const formulario = evento.target;
    conError(async () => {
      const { proceso } = await enviar('/api/procesos', datosFormulario(formulario));
      mostrarAviso(`Proceso ${proceso.nombre} (PID ${proceso.pid}) agregado al sistema.`, 'exito');
      formulario.reset();
      await sondear();
    });
  });

  $('#form-carga').addEventListener('submit', (evento) => {
    evento.preventDefault();
    const datos = datosFormulario(evento.target);
    conError(async () => {
      const { generados } = await enviar('/api/procesos/aleatorios', datos);
      mostrarAviso(`Se generaron ${generados} procesos.`, 'exito');
      await sondear();
    });
  });

  const ATAJOS = { ' ': 'alternar', s: 'paso', r: 'reiniciar' };
  document.addEventListener('keydown', (evento) => {
    if (evento.target.matches('input, select, textarea') || evento.ctrlKey || evento.altKey) return;
    const tecla = evento.key.toLowerCase();
    if (tecla === 'e') { evento.preventDefault(); exportar(); return; }
    const accion = ATAJOS[tecla];
    if (accion) {
      evento.preventDefault();
      control(accion);
    }
  });

  window.addEventListener('resize', () => conError(sondear));
}

(async function iniciar() {
  try {
    estado.metadatos = await peticion('/api/metadatos');
  } catch (error) {
    mostrarAviso(`No se pudo cargar la configuracion: ${error.message}`);
    return;
  }
  construirParametros();
  construirCamposProceso();
  registrarEventos();
  programarSondeo();
})();
