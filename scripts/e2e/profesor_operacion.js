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
const chromePath = process.env.ELEMENTAL_E2E_CHROME || '/usr/bin/google-chrome';
const runId = process.env.ELEMENTAL_E2E_RUN_ID || new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
const outputDir = path.resolve(
  process.env.ELEMENTAL_E2E_OUTPUT_DIR || `docs/evidencia/profesor-${runId}`,
);
const ejecutarMutaciones = process.env.ELEMENTAL_E2E_MUTACIONES === '1';
const inspeccionarFormulario = process.env.ELEMENTAL_E2E_INSPECCIONAR_FORMULARIO || '';

if (!username || !password) {
  console.error('Define ELEMENTAL_E2E_USERNAME y ELEMENTAL_E2E_PASSWORD.');
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

async function seleccionarPrimeraOpcion(page, selector) {
  const valor = await page.$eval(`${selector} option:not([value=""])`, option => option.value);
  await page.select(selector, valor);
  return valor;
}

async function loginLocal(page) {
  await page.goto(`${baseUrl}/accounts/login/`, {waitUntil: 'domcontentloaded'});
  await page.type('#id_username', username);
  await page.type('#id_password', password);
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('form[aria-label="Acceso local"] button[type=submit]'),
  ]);
}

async function capturar(page, ruta, nombre, resultado) {
  const response = await page.goto(`${baseUrl}${ruta}`, {waitUntil: 'domcontentloaded'});
  await pausa(300);
  resultado.paginas[nombre] = {
    status: response.status(),
    url: page.url(),
    title: await page.title(),
  };
  await page.screenshot({path: path.join(outputDir, `${nombre}.png`), fullPage: true});
}

async function recorridoLectura(page, resultado) {
  await capturar(page, '/profesor/', '01-inicio-mobile', resultado);
  resultado.controles.navegacionInferior = await page.$$eval('.profesor-bottom-nav a', links =>
    links.map(link => ({
      texto: link.textContent.trim(),
      alto: Math.round(link.getBoundingClientRect().height),
      ancho: Math.round(link.getBoundingClientRect().width),
    })),
  );
  resultado.controles.accionesRapidas = await page.$$eval('.acciones-rapidas .btn', links =>
    links.map(link => ({
      texto: link.textContent.trim(),
      alto: Math.round(link.getBoundingClientRect().height),
    })),
  );

  await capturar(page, '/profesor/sesiones/', '02-sesiones-mobile', resultado);
  await capturar(page, '/profesor/alumnos/', '03-alumnos-mobile', resultado);
  await capturar(page, '/profesor/pagos/', '04-pagos-mobile', resultado);

  await page.goto(`${baseUrl}/profesor/pagos/masivo/nuevo/`, {waitUntil: 'domcontentloaded'});
  await seleccionarPrimeraOpcion(page, '#id_disciplina');
  for (let index = 0; index < 10; index += 1) {
    await page.click('#buscar-alumno');
    await page.$eval('#buscar-alumno', element => { element.value = ''; });
    await page.type('#buscar-alumno', process.env.ELEMENTAL_E2E_BUSQUEDA_ALUMNO || 'Alumno');
    await pausa(450);
    await page.keyboard.press('Enter');
  }
  resultado.controles.selectorMasivo = {
    seleccionados: await page.$$eval('#seleccionados button', botones => botones.length),
    foco: await page.evaluate(() => document.activeElement && document.activeElement.id),
  };
  await page.screenshot({
    path: path.join(outputDir, '05-pago-masivo-selector-mobile.png'),
    fullPage: true,
  });

  const gates = {
    finanzasGlobales: '/finanzas/',
    organizaciones: '/personas/organizaciones/',
    adminGlobal: '/admin/',
  };
  for (const [nombre, ruta] of Object.entries(gates)) {
    const response = await page.goto(`${baseUrl}${ruta}`, {waitUntil: 'domcontentloaded'});
    resultado.autorizacion[nombre] = {status: response.status(), urlFinal: page.url()};
  }
}

async function recorridoMutaciones(page, resultado) {
  await page.goto(`${baseUrl}/profesor/`, {waitUntil: 'domcontentloaded'});
  const sesionHref = await page.$eval(
    'a[href^="/asistencias/sesiones/"]',
    enlace => enlace.getAttribute('href'),
  );
  await page.goto(`${baseUrl}${sesionHref}`, {waitUntil: 'domcontentloaded'});
  await page.waitForSelector('.ts-control input', {timeout: 10000});
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
  await page.screenshot({
    path: path.join(outputDir, '06-asistencia-persistida-mobile.png'),
    fullPage: true,
  });

  await page.goto(`${baseUrl}/profesor/alumnos/crear/`, {waitUntil: 'domcontentloaded'});
  await seleccionarPrimeraOpcion(page, '#id_disciplina');
  await page.type('#id_nombres', `Alumno navegador ${runId}`);
  await page.type('#id_apellidos', 'E2E');
  await page.type('#id_email', `browser.alumno.${runId}@example.com`);
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('button[type=submit]'),
  ]);
  resultado.mutaciones.alumno = {url: page.url(), runId};

  await page.goto(`${baseUrl}/profesor/pagos/crear/`, {waitUntil: 'domcontentloaded'});
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
    url: page.url(),
    transaccionVisible: (await page.content()).includes('Transacción #'),
  };
  await page.screenshot({path: path.join(outputDir, '07-pago-transaccion-mobile.png'), fullPage: true});

  await page.goto(`${baseUrl}/profesor/sesiones/crear/`, {waitUntil: 'domcontentloaded'});
  await seleccionarPrimeraOpcion(page, '#id_disciplina');
  await page.$eval('#id_fecha', (element, valor) => { element.value = valor; }, fechaIso(10));
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('button[type=submit]'),
  ]);
  const urlCreada = page.url();
  await page.type('#motivo-liberar-sesion', `Liberación navegador E2E ${runId}`);
  await Promise.all([
    page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    page.click('form[action$="/liberar/"] button[type=submit]'),
  ]);
  resultado.mutaciones.sesion = {urlCreada, liberada: (await page.content()).includes('Cancelada')};
  await page.screenshot({path: path.join(outputDir, '08-sesion-liberada-mobile.png'), fullPage: true});
}

async function main() {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: chromePath,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({width: 390, height: 844, deviceScaleFactor: 1});
  const resultado = {
    runId,
    baseUrl,
    viewport: '390x844',
    mutacionesHabilitadas: ejecutarMutaciones,
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
    if (inspeccionarFormulario) {
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
    await browser.close();
  }

  const resultadoPath = path.join(outputDir, 'resultado.json');
  fs.writeFileSync(resultadoPath, `${JSON.stringify(resultado, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify(resultado));
}

main().catch(error => {
  console.error(error.stack || error.message);
  process.exit(1);
});
