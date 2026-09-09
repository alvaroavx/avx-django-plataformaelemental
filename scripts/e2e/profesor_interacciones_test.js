/** Pruebas aisladas de DOM con datos sintéticos: no servidor Django ni base de datos. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('puppeteer');
const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.ELEMENTAL_E2E_CHROME || '/usr/bin/google-chrome',
    headless: true, args: ['--no-sandbox'],
  });
  try {
    const page = await browser.newPage();
    // El script real debe conservar la acción del botón elegido, incluso al deshabilitarlo.
    await page.setContent('<form data-sensitive-form><button type="submit" name="quitar_asistente" value="quitar">Quitar</button><button type="submit" name="liberar_clase" value="liberar">Liberar</button></form>');
    await page.evaluate(() => { window.confirm = () => true; });
    await page.addScriptTag({content: read('asistencias/static/asistencias/js/profesor_contexto.js')});
    const actions = await page.evaluate(() => {
      const form = document.querySelector('form');
      const button = form.querySelector('[name="liberar_clase"]');
      form.dispatchEvent(new SubmitEvent('submit', {bubbles: true, cancelable: true, submitter: button}));
      const first = Array.from(new FormData(form));
      const retry = form.dispatchEvent(new SubmitEvent('submit', {bubbles: true, cancelable: true, submitter: button}));
      return {first, retry, hidden: form.querySelectorAll('input[type="hidden"]').length};
    });
    assert.deepEqual(actions, {first: [['liberar_clase', 'liberar']], retry: false, hidden: 1});

    // Ejecutar la inicialización real del selector con una selección recuperada del servidor.
    const name = '<img src=x onerror="window.nombreEjecutado=true"> Alumno sintético';
    await page.setContent('<form id="lote-form"><select id="id_disciplina"><option value="1">Clase</option></select><input id="buscar-alumno"><div id="resultados"></div><div id="buscar-alumno-status"></div><div id="lote-status"></div><input id="id_personas_seleccionadas"><div id="seleccionados"></div><input id="id_filas_json"></form><script type="application/json" id="alumnos-seleccionados-data"></script>');
    await page.evaluate(nombre => {
      document.getElementById('alumnos-seleccionados-data').textContent = JSON.stringify([{id: 7, nombre}, {id: 8, nombre: 'Otro alumno sintético'}]);
    }, name);
    const mass = read('asistencias/templates/asistencias/profesor/pago_masivo.html').split('<script>')[1].split('</script>')[0]
      .replace(/{%[\s\S]*?%}/g, '').replace(/{{[\s\S]*?}}/g, '');
    await page.addScriptTag({content: mass});
    const selected = await page.evaluate(() => ({
      value: document.getElementById('id_personas_seleccionadas').value,
      text: document.getElementById('seleccionados').textContent,
      images: document.querySelectorAll('#seleccionados img').length,
      executed: !!window.nombreEjecutado,
    }));
    assert.equal(selected.value, '7,8');
    assert.ok(selected.text.includes(name));
    assert.equal(selected.images, 0);
    assert.equal(selected.executed, false);
    await page.click('#seleccionados button');
    assert.equal(await page.$eval('#id_personas_seleccionadas', el => el.value), '8');

    // La función real consume el estado autoritativo del servidor sin asumir una transición.
    const detail = read('asistencias/templates/asistencias/sesion_detail.html');
    const stateFunction = detail.slice(detail.indexOf('  function actualizarEstadoSesion('), detail.indexOf('  function agregarAsistente('));
    await page.setContent('<span data-sesion-estado>Planificada</span>');
    await page.addScriptTag({content: stateFunction});
    await page.evaluate(() => actualizarEstadoSesion({estado: 'abierta', estado_label: 'Abierta'}));
    assert.equal(await page.$eval('[data-sesion-estado]', el => el.textContent), 'Abierta');
    assert.equal(await page.$eval('[data-sesion-estado] i', el => el.className), 'bi bi-play-circle');
    await page.evaluate(() => actualizarEstadoSesion({estado: 'completada', estado_label: 'Cerrada'}));
    assert.equal(await page.$eval('[data-sesion-estado]', el => el.textContent), 'Cerrada');
    console.log('OK: submitter preservado, doble envío bloqueado, nombres como texto, selección recuperada y estado autoritativo. Sin acceso a DB.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
