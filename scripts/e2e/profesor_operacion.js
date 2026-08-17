/**
 * Recorrido móvil reutilizable del espacio Operación Profesor.
 *
 * Es de solo lectura por defecto. Para ejecutar altas, asistencia, pago y
 * liberación de sesión se debe definir ELEMENTAL_E2E_MUTACIONES=1 y usar una
 * base de desarrollo/QA con datos sintéticos preparados.
 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const baseUrl = (process.env.ELEMENTAL_E2E_BASE_URL || 'http://127.0.0.1:8010').replace(/\/$/, '');
const username = process.env.ELEMENTAL_E2E_USERNAME;
const password = process.env.ELEMENTAL_E2E_PASSWORD;
const sessionCookie = process.env.ELEMENTAL_E2E_SESSION_COOKIE;
const sessionCookieName = process.env.ELEMENTAL_E2E_SESSION_COOKIE_NAME || 'elemental_sessionid';
const userDataDir = process.env.ELEMENTAL_E2E_USER_DATA_DIR || '';
const browserUrl = process.env.ELEMENTAL_E2E_BROWSER_URL || '';
const organizacionId = process.env.ELEMENTAL_E2E_ORGANIZACION_ID;
const chromePath = process.env.ELEMENTAL_E2E_CHROME || '/usr/bin/google-chrome';
const runId = process.env.ELEMENTAL_E2E_RUN_ID || new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
const outputDir = path.resolve(
  process.env.ELEMENTAL_E2E_OUTPUT_DIR || `docs/evidencia/profesor-${runId}`,
);
const ejecutarMutaciones = process.env.ELEMENTAL_E2E_MUTACIONES === '1';
const ejecutarSelectorMasivo = process.env.ELEMENTAL_E2E_PAGO_MASIVO !== '0';
const conservarCapturas = process.env.ELEMENTAL_E2E_CAPTURAS !== '0';
const inspeccionarFormulario = process.env.ELEMENTAL_E2E_INSPECCIONAR_FORMULARIO || '';
const soloPagoPersonaId = process.env.ELEMENTAL_E2E_SOLO_PAGO_PERSONA_ID || '';
const tema = process.env.ELEMENTAL_E2E_THEME || '';
const periodoTodos = process.env.ELEMENTAL_E2E_PERIODO_TODOS === '1';
const periodoMes = process.env.ELEMENTAL_E2E_PERIODO_MES || '';
const periodoAnio = process.env.ELEMENTAL_E2E_PERIODO_ANIO || '';
const sanitizarCapturas = process.env.ELEMENTAL_E2E_SANITIZAR_CAPTURAS !== '0';

if ((!username || !password) && !sessionCookie && !userDataDir && !browserUrl) {
  console.error('Define usuario/clave, cookie de sesión, perfil de Chrome o ELEMENTAL_E2E_BROWSER_URL.');
  process.exit(2);
}
if (!organizacionId || (!/^\d+$/.test(organizacionId) && organizacionId !== 'todos')) {
  console.error('Define ELEMENTAL_E2E_ORGANIZACION_ID con un ID explícito o "todos".');
  process.exit(2);
}
if (soloPagoPersonaId && !/^\d+$/.test(soloPagoPersonaId)) {
  console.error('ELEMENTAL_E2E_SOLO_PAGO_PERSONA_ID debe ser un ID numérico.');
  process.exit(2);
}
if (tema && !['light', 'dark'].includes(tema)) {
  console.error('ELEMENTAL_E2E_THEME debe ser light o dark.');
  process.exit(2);
}
if (periodoTodos && (periodoMes || periodoAnio)) {
  console.error('No combines ELEMENTAL_E2E_PERIODO_TODOS con mes/año.');
  process.exit(2);
}
if (!periodoTodos && ((periodoMes && !periodoAnio) || (!periodoMes && periodoAnio))) {
  console.error('Define mes y año juntos.');
  process.exit(2);
}

fs.mkdirSync(outputDir, {recursive: true});

function fechaIso(dias = 0) {
  const fecha = new Date();
  fecha.setDate(fecha.getDate() + dias);
  return fecha.toISOString().slice(0, 10);
}

async function pausa(ms) {
  await new Promise(resolve => setTimeout(resolve, ms));
}

async function capturarPantalla(page, nombre) {
  if (!conservarCapturas) return;
  if (sanitizarCapturas) {
    await page.evaluate(() => {
      const ruta = window.location.pathname;
      const selectores = ['.context-person'];
      if (
        ruta === '/profesor/'
        || ruta.includes('/profesor/alumnos')
        || ruta.includes('/profesor/pagos')
      ) {
        selectores.push('.operational-row-title', '.operational-row-meta');
      }
      if (ruta.startsWith('/asistencias/sesiones/')) {
        selectores.push('#asistentes-mobile h3');
      }
      document.querySelectorAll(selectores.join(',')).forEach(elemento => {
        elemento.style.filter = 'blur(6px)';
        elemento.style.userSelect = 'none';
      });
    });
  }
  await page.screenshot({path: path.join(outputDir, nombre), fullPage: true});
}

async function seleccionarPrimeraOpcion(page, selector) {
  const valor = await page.$eval(`${selector} option:not([value=""])`, option => option.value);
  await page.select(selector, valor);
  return valor;
}

async function loginLocal(page) {
  if (sessionCookie) {
    await page.setCookie({
      name: sessionCookieName,
      value: sessionCookie,
      url: baseUrl,
      httpOnly: true,
      sameSite: 'Lax',
    });
    await page.goto(profesorRuta('/profesor/'), {waitUntil: 'domcontentloaded'});
    if (new URL(page.url()).pathname.startsWith('/accounts/login/')) {
      throw new Error('La sesión temporal no autenticó al profesor.');
    }
    return;
  }
  if ((userDataDir || browserUrl) && (!username || !password)) {
    await page.goto(profesorRuta('/profesor/'), {waitUntil: 'domcontentloaded'});
    if (new URL(page.url()).pathname.startsWith('/accounts/login/')) {
      throw new Error('El perfil temporal de Chrome no tiene una sesión Profesor vigente.');
    }
    return;
  }
  await page.goto(`${baseUrl}/accounts/login/`, {waitUntil: 'domcontentloaded'});
  await page.type('#id_username', username);
  await page.type('#id_password', password);
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('form[aria-label="Acceso local"] button[type=submit]'),
  ]);
}

function profesorRuta(ruta) {
  const url = new URL(ruta, baseUrl);
  url.searchParams.set('organizacion', organizacionId);
  if (periodoTodos) {
    url.searchParams.set('periodo', 'todos');
  } else if (periodoMes && periodoAnio) {
    url.searchParams.set('periodo_mes', periodoMes);
    url.searchParams.set('periodo_anio', periodoAnio);
  }
  return url.toString();
}

function urlEvidencia(valor) {
  if (!sanitizarCapturas) return valor;
  const url = new URL(valor);
  url.pathname = url.pathname.replace(/\/\d+(?=\/|$)/g, '/[id]');
  if (/^\d+$/.test(url.searchParams.get('organizacion') || '')) {
    url.searchParams.set('organizacion', '[id-autorizado]');
  }
  return url.toString();
}

async function capturar(page, ruta, nombre, resultado) {
  const response = await page.goto(profesorRuta(ruta), {waitUntil: 'domcontentloaded'});
  await pausa(300);
  resultado.paginas[nombre] = {
    status: response.status(),
    url: urlEvidencia(page.url()),
    title: await page.title(),
  };
  await capturarPantalla(page, `${nombre}.png`);
}

async function recorridoLectura(page, resultado) {
  await capturar(page, '/profesor/', '01-inicio-mobile', resultado);
  await page.click('[data-bs-target="#contextoProfesor"]');
  await page.waitForSelector('#contextoProfesor.show', {visible: true, timeout: 5000});
  resultado.controles.contextoTrabajo = {
    organizacionesDisponibles: await page.$$eval(
      '#contexto-organizacion option:not([value=""])',
      opciones => opciones.length,
    ),
    permiteTodasOrganizaciones: Boolean(await page.$('#contexto-organizacion option[value="todos"]')),
    permiteTodosPeriodos: Boolean(await page.$('[data-periodo-modo] option[value="todos"]')),
    temasDisponibles: await page.$$eval('[data-theme-option]', opciones => opciones.length),
    organizaciones: await page.$$eval(
      '#contexto-organizacion option:not([value=""]):not([value="todos"])',
      opciones => opciones.map(opcion => opcion.textContent.trim()),
    ),
  };
  await capturarPantalla(page, '01-contexto-trabajo-mobile.png');
  await page.click('#contextoProfesor .btn-close');
  await page.waitForSelector('#contextoProfesor.show', {hidden: true, timeout: 5000});
  resultado.controles.navegacionInferior = await page.$$eval('.profesor-bottom-nav a', links =>
    links.map(link => ({
      texto: link.textContent.trim(),
      alto: Math.round(link.getBoundingClientRect().height),
      ancho: Math.round(link.getBoundingClientRect().width),
    })),
  );
  resultado.controles.accionesRapidas = await page.$$eval('.quick-actions .btn', links =>
    links.map(link => ({
      texto: link.textContent.trim(),
      alto: Math.round(link.getBoundingClientRect().height),
    })),
  );

  await capturar(page, '/profesor/sesiones/', '02-sesiones-mobile', resultado);
  const detalleHref = await page.$eval(
    '.operational-list a.row-link[href^="/asistencias/sesiones/"]',
    enlace => enlace.getAttribute('href'),
  ).catch(() => '');
  if (detalleHref) {
    const response = await page.goto(new URL(detalleHref, baseUrl).toString(), {waitUntil: 'domcontentloaded'});
    await pausa(300);
    resultado.paginas.detalleSesion = {
      status: response.status(),
      url: urlEvidencia(page.url()),
      title: await page.title(),
    };
    await capturarPantalla(page, '03-detalle-sesion-mobile.png');
  }
  await capturar(page, '/profesor/alumnos/', '03-alumnos-mobile', resultado);
  await capturar(page, '/profesor/pagos/', '04-pagos-mobile', resultado);

  const contextoMutable = organizacionId !== 'todos' && !periodoTodos;
  if (contextoMutable) {
    await capturar(page, '/profesor/sesiones/crear/', '05-formulario-sesion-mobile', resultado);
    await capturar(page, '/profesor/alumnos/crear/', '06-formulario-alumno-mobile', resultado);
    await capturar(page, '/profesor/pagos/crear/', '07-formulario-pago-mobile', resultado);

    await page.goto(profesorRuta('/profesor/pagos/masivo/nuevo/'), {waitUntil: 'domcontentloaded'});
    const disciplinaDisponible = Boolean(await page.$('#id_disciplina option:not([value=""])'));
    if (disciplinaDisponible) await seleccionarPrimeraOpcion(page, '#id_disciplina');
    if (ejecutarSelectorMasivo && disciplinaDisponible) {
      for (let index = 0; index < 10; index += 1) {
        await page.click('#buscar-alumno');
        await page.$eval('#buscar-alumno', element => { element.value = ''; });
        await page.type('#buscar-alumno', process.env.ELEMENTAL_E2E_BUSQUEDA_ALUMNO || 'Alumno');
        await pausa(450);
        await page.keyboard.press('Enter');
      }
    }
    resultado.controles.selectorMasivo = {
      ejecutado: ejecutarSelectorMasivo && disciplinaDisponible,
      motivo: disciplinaDisponible ? '' : 'Sin disciplina operativa en el contexto',
      seleccionados: await page.$$eval('#seleccionados button', botones => botones.length),
      foco: await page.evaluate(() => document.activeElement && document.activeElement.id),
    };
    await capturarPantalla(page, '08-pago-masivo-selector-mobile.png');
  } else {
    resultado.controles.selectorMasivo = {ejecutado: false, motivo: 'Contexto de solo lectura'};
  }

  const gates = {
    finanzasGlobales: '/finanzas/',
    organizaciones: '/personas/organizaciones/',
    adminGlobal: '/admin/',
  };
  for (const [nombre, ruta] of Object.entries(gates)) {
    const response = await page.goto(`${baseUrl}${ruta}`, {waitUntil: 'domcontentloaded'});
    resultado.autorizacion[nombre] = {status: response.status(), urlFinal: urlEvidencia(page.url())};
  }
}

async function recorridoMutaciones(page, resultado) {
  await page.goto(profesorRuta('/profesor/'), {waitUntil: 'domcontentloaded'});
  const sesionHref = await page.$eval(
    'a[href^="/asistencias/sesiones/"]',
    enlace => enlace.getAttribute('href'),
  );
  await page.goto(new URL(sesionHref, baseUrl).toString(), {waitUntil: 'domcontentloaded'});
  await page.waitForSelector('.ts-control input', {timeout: 10000});
  resultado.controles.sesionProfesor = {
    puedeCrearPersonaDesdeSesion: Boolean(await page.$('button[name="crear_persona_estudiante"]')),
    puedeQuitarAsistente: Boolean(await page.$('button[name="eliminar_asistente"]')),
    puedeLiberarClaseAlumno: Boolean(await page.$('button[name="liberar_clase"]')),
  };
  const antes = Number(await page.$eval('#total-asistentes', element => element.textContent.trim()));
  await page.type('.ts-control input', process.env.ELEMENTAL_E2E_BUSQUEDA_ALUMNO || 'Alumno');
  await page.waitForSelector('.ts-dropdown .option', {visible: true, timeout: 10000});
  await page.keyboard.press('Enter');
  await page.waitForFunction(
    esperado => Number(document.querySelector('#total-asistentes').textContent.trim()) === esperado,
    {timeout: 10000},
    antes + 1,
  );
  await page.click('#asistentes-mobile article:first-child [data-estado="justificada"]');
  await page.waitForFunction(
    () => document.querySelector('#asistentes-mobile article:first-child [data-estado-status]')
      .textContent.includes('guardada'),
    {timeout: 10000},
  );
  await page.reload({waitUntil: 'domcontentloaded'});
  resultado.mutaciones.asistencia = {
    antes,
    despues: Number(await page.$eval('#total-asistentes', element => element.textContent.trim())),
  };
  await capturarPantalla(page, '06-asistencia-persistida-mobile.png');

  await page.goto(profesorRuta('/profesor/alumnos/crear/'), {waitUntil: 'domcontentloaded'});
  await seleccionarPrimeraOpcion(page, '#id_disciplina');
  await page.type('#id_nombres', `Alumno navegador ${runId}`);
  await page.type('#id_apellidos', 'E2E');
  await page.type('#id_email', `browser.alumno.${runId}@example.com`);
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('button[type=submit]'),
  ]);
  resultado.mutaciones.alumno = {url: urlEvidencia(page.url()), runId};

  await page.goto(profesorRuta('/profesor/pagos/crear/'), {waitUntil: 'domcontentloaded'});
  await seleccionarPrimeraOpcion(page, '#id_disciplina');
  await seleccionarPrimeraOpcion(page, '#id_persona');
  if (await page.$('#id_plan option:not([value=""])')) {
    await seleccionarPrimeraOpcion(page, '#id_plan');
  }
  await page.select('#id_metodo_pago', 'efectivo');
  await page.$eval('#id_fecha_pago', (element, valor) => { element.value = valor; }, fechaIso());
  await page.type('#id_monto', process.env.ELEMENTAL_E2E_MONTO || '15000');
  await page.$eval('#id_clases_asignadas', element => { element.value = '3'; });
  await page.type('#id_glosa', `Pago navegador E2E ${runId}`);
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('button[type=submit]'),
  ]);
  resultado.mutaciones.pago = {
    url: urlEvidencia(page.url()),
    transaccionVisible: (await page.content()).includes('Transacción #'),
    puedeEditar: Boolean(await page.$('a[href*="/editar/"]')),
    puedeEliminarORevertir: Boolean(await page.$('a[href*="/revertir/"]')),
  };
  await capturarPantalla(page, '07-pago-transaccion-mobile.png');

  await page.goto(profesorRuta('/profesor/sesiones/crear/'), {waitUntil: 'domcontentloaded'});
  await seleccionarPrimeraOpcion(page, '#id_disciplina');
  await page.$eval('#id_fecha', (element, valor) => { element.value = valor; }, fechaIso(10));
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('button[type=submit]'),
  ]);
  const urlCreada = urlEvidencia(page.url());
  await page.type('#motivo-liberar-sesion', `Liberación navegador E2E ${runId}`);
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('form[action*="/liberar/"] button[type=submit]'),
  ]);
  resultado.mutaciones.sesion = {urlCreada, liberada: (await page.content()).includes('Cancelada')};
  await capturarPantalla(page, '08-sesion-liberada-mobile.png');
}

async function recorridoPagoEspecifico(page, resultado) {
  await page.goto(profesorRuta('/profesor/pagos/crear/'), {waitUntil: 'domcontentloaded'});
  await seleccionarPrimeraOpcion(page, '#id_disciplina');
  const opcionExiste = await page.$(`#id_persona option[value="${soloPagoPersonaId}"]`);
  if (!opcionExiste) throw new Error('La persona indicada no está disponible en el pago Profesor.');
  await page.select('#id_persona', soloPagoPersonaId);
  await page.select('#id_metodo_pago', 'efectivo');
  await page.$eval('#id_fecha_pago', (element, valor) => { element.value = valor; }, fechaIso());
  await page.type('#id_monto', process.env.ELEMENTAL_E2E_MONTO || '12000');
  await page.$eval('#id_clases_asignadas', element => { element.value = '2'; });
  await page.type('#id_glosa', `Pago dirigido navegador E2E ${runId}`);
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('button[type=submit]'),
  ]);
  resultado.mutaciones.pagoDirigido = {
    url: urlEvidencia(page.url()),
    transaccionVisible: (await page.content()).includes('Transacción #'),
  };
}

async function main() {
  const browser = browserUrl
    ? await puppeteer.connect({browserURL: browserUrl})
    : await puppeteer.launch({
      headless: true,
      executablePath: chromePath,
      userDataDir: userDataDir || undefined,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
  const page = await browser.newPage();
  await page.setViewport({width: 390, height: 844, deviceScaleFactor: 1});
  if (tema) {
    await page.evaluateOnNewDocument(temaSeleccionado => {
      localStorage.setItem('profesor-theme', temaSeleccionado);
    }, tema);
  }
  const resultado = {
    runId,
    baseUrl,
    organizacionId: sanitizarCapturas && /^\d+$/.test(organizacionId)
      ? '[id-autorizado]'
      : organizacionId,
    periodo: periodoTodos ? 'todos' : (periodoMes && periodoAnio ? `${periodoMes}/${periodoAnio}` : 'predeterminado'),
    tema: tema || 'sistema',
    viewport: '390x844',
    mutacionesHabilitadas: ejecutarMutaciones,
    capturasConservadas: conservarCapturas,
    capturasSanitizadas: sanitizarCapturas,
    perfilChromeReutilizado: Boolean(userDataDir),
    navegadorAbiertoReutilizado: Boolean(browserUrl),
    paginas: {},
    controles: {},
    autorizacion: {},
    mutaciones: {},
    erroresConsola: [],
  };
  page.on('console', message => {
    if (message.type() === 'error') resultado.erroresConsola.push(message.text());
  });
  page.on('pageerror', error => resultado.erroresConsola.push(error.message));

  try {
    await loginLocal(page);
    if (soloPagoPersonaId) {
      await recorridoPagoEspecifico(page, resultado);
    } else if (inspeccionarFormulario) {
      await page.goto(`${baseUrl}${inspeccionarFormulario}`, {waitUntil: 'domcontentloaded'});
      resultado.formulario = await page.$$eval('input,select,textarea', elementos =>
        elementos.map(elemento => ({
          id: elemento.id,
          name: elemento.name,
          type: elemento.type,
          value: elemento.value,
        })),
      );
    } else {
      await recorridoLectura(page, resultado);
      if (ejecutarMutaciones) await recorridoMutaciones(page, resultado);
    }
  } finally {
    await page.close();
    if (browserUrl) browser.disconnect();
    else await browser.close();
  }

  const resultadoPath = path.join(outputDir, 'resultado.json');
  fs.writeFileSync(resultadoPath, `${JSON.stringify(resultado, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify(resultado));
}

main().catch(error => {
  console.error(error.stack || error.message);
  process.exit(1);
});
