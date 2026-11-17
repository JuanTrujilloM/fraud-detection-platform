const FILTROS = ['mes', 'categoria', 'ciudad', 'canal'];
const ESTADOS = ['PENDIENTE', 'CONFIRMADA_FRAUDE', 'DESCARTADA'];

const numero = new Intl.NumberFormat('es-CO');
const moneda = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

let autorizaciones = [];
let alertas = [];
const graficos = {};

function leerCsv(texto) {
  const lineas = texto.trim().split('\n');
  const columnas = partirLinea(lineas[0]);
  const filas = [];
  for (let i = 1; i < lineas.length; i++) {
    const valores = partirLinea(lineas[i]);
    const fila = {};
    for (let j = 0; j < columnas.length; j++) {
      fila[columnas[j]] = valores[j];
    }
    fila.mes_anio = fila.anio + '-' + fila.mes.padStart(2, '0');
    filas.push(fila);
  }
  return filas;
}

function partirLinea(linea) {
  return linea.trim().slice(1, -1).split('","');
}

function valoresUnicos(filas, campo) {
  const valores = [];
  for (let i = 0; i < filas.length; i++) {
    if (!valores.includes(filas[i][campo])) {
      valores.push(filas[i][campo]);
    }
  }
  return valores.sort();
}

function llenarFiltro(campo, valores) {
  const select = document.getElementById('filtro-' + campo);
  for (let i = 0; i < valores.length; i++) {
    select.add(new Option(valores[i], valores[i]));
  }
  select.addEventListener('change', actualizar);
}

function filtrar(filas, campos) {
  const resultado = [];
  for (let i = 0; i < filas.length; i++) {
    let incluir = true;
    for (let j = 0; j < campos.length; j++) {
      const elegido = document.getElementById('filtro-' + campos[j]).value;
      const campo = campos[j] === 'mes' ? 'mes_anio' : campos[j];
      if (elegido !== '' && filas[i][campo] !== elegido) {
        incluir = false;
      }
    }
    if (incluir) {
      resultado.push(filas[i]);
    }
  }
  return resultado;
}

function sumar(filas, campo) {
  let total = 0;
  for (let i = 0; i < filas.length; i++) {
    total += Number(filas[i][campo]);
  }
  return total;
}

function sumarPor(filas, clave, campo) {
  const totales = {};
  for (let i = 0; i < filas.length; i++) {
    const valor = filas[i][clave];
    totales[valor] = (totales[valor] || 0) + Number(filas[i][campo]);
  }
  return totales;
}

function porcentaje(parte, total) {
  if (total === 0) {
    return '—';
  }
  return ((parte / total) * 100).toFixed(1) + ' %';
}

function dibujar(id, titulo, totales, etiquetas, tipo) {
  const valores = [];
  for (let i = 0; i < etiquetas.length; i++) {
    valores.push(totales[etiquetas[i]] || 0);
  }
  if (graficos[id]) {
    graficos[id].destroy();
  }
  graficos[id] = new Chart(document.getElementById(id), {
    type: tipo,
    data: { labels: etiquetas, datasets: [{ label: 'Fraudes', data: valores, backgroundColor: '#c0392b', borderColor: '#c0392b' }] },
    options: { plugins: { title: { display: true, text: titulo }, legend: { display: false } } },
  });
}

function ordenarPorValor(totales) {
  const etiquetas = Object.keys(totales);
  etiquetas.sort(function (a, b) {
    return totales[b] - totales[a];
  });
  return etiquetas;
}

function actualizar() {
  const filas = filtrar(autorizaciones, FILTROS);
  const total = sumar(filas, 'autorizaciones');
  const fraudes = sumar(filas, 'fraudes');

  document.getElementById('ind-autorizaciones').textContent = numero.format(total);
  document.getElementById('ind-aprobacion').textContent = porcentaje(sumar(filas, 'aprobadas'), total);
  document.getElementById('ind-fraudes').textContent = numero.format(fraudes);
  document.getElementById('ind-tasa-fraude').textContent = porcentaje(fraudes, total);
  document.getElementById('ind-monto-fraude').textContent = moneda.format(sumar(filas, 'monto_fraude'));

  const porCategoria = sumarPor(filas, 'categoria', 'fraudes');
  const porCiudad = sumarPor(filas, 'ciudad', 'fraudes');
  const porMes = sumarPor(filas, 'mes_anio', 'fraudes');
  const porHora = sumarPor(filas, 'hora', 'fraudes');
  const porCanal = sumarPor(filas, 'canal', 'fraudes');
  const horas = [];
  for (let h = 0; h < 24; h++) {
    horas.push(String(h));
  }

  dibujar('grafico-categoria', 'Fraudes por categoría', porCategoria, ordenarPorValor(porCategoria), 'bar');
  dibujar('grafico-ciudad', 'Fraudes por ciudad', porCiudad, ordenarPorValor(porCiudad), 'bar');
  dibujar('grafico-mes', 'Fraudes por mes', porMes, Object.keys(porMes).sort(), 'line');
  dibujar('grafico-hora', 'Fraudes por hora', porHora, horas, 'bar');
  dibujar('grafico-canal', 'Fraudes por canal', porCanal, ordenarPorValor(porCanal), 'bar');

  actualizarAlertas(filtrar(alertas, ['mes', 'categoria']));
}

function actualizarAlertas(filas) {
  const porEstado = sumarPor(filas, 'estado', 'alertas');
  const confirmadas = porEstado.CONFIRMADA_FRAUDE || 0;
  const resueltas = confirmadas + (porEstado.DESCARTADA || 0);

  document.getElementById('ind-confirmadas').textContent = porcentaje(confirmadas, resueltas);
  document.getElementById('ind-pendientes').textContent = numero.format(porEstado.PENDIENTE || 0);
  document.getElementById('ind-promedio').textContent =
    resueltas === 0 ? '—' : numero.format(Math.round(sumar(filas, 'minutos_resolucion') / resueltas)) + ' min';

  const tabla = document.getElementById('tabla-alertas');
  tabla.innerHTML = '';
  const tipos = valoresUnicos(filas, 'tipo');
  for (let i = 0; i < tipos.length; i++) {
    const fila = tabla.insertRow();
    fila.insertCell().textContent = tipos[i];
    for (let j = 0; j < ESTADOS.length; j++) {
      let cantidad = 0;
      for (let k = 0; k < filas.length; k++) {
        if (filas[k].tipo === tipos[i] && filas[k].estado === ESTADOS[j]) {
          cantidad += Number(filas[k].alertas);
        }
      }
      fila.insertCell().textContent = numero.format(cantidad);
    }
  }
}

async function iniciar() {
  const respuestas = await Promise.all([fetch('data/cubo_autorizaciones.csv'), fetch('data/cubo_alertas.csv')]);
  autorizaciones = leerCsv(await respuestas[0].text());
  alertas = leerCsv(await respuestas[1].text());
  llenarFiltro('mes', valoresUnicos(autorizaciones, 'mes_anio'));
  for (let i = 1; i < FILTROS.length; i++) {
    llenarFiltro(FILTROS[i], valoresUnicos(autorizaciones, FILTROS[i]));
  }
  actualizar();
}

iniciar();
