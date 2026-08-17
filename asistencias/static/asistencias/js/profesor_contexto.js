(function () {
  'use strict';

  var raiz = document.documentElement;
  var opcionesTema = document.querySelectorAll('[data-theme-option]');
  var temaActual = raiz.dataset.theme || 'light';

  opcionesTema.forEach(function (opcion) {
    opcion.checked = opcion.value === temaActual;
    opcion.addEventListener('change', function () {
      if (!opcion.checked) return;
      raiz.dataset.theme = opcion.value;
      localStorage.setItem('profesor-theme', opcion.value);
    });
  });

  document.querySelectorAll('[data-contexto-form]').forEach(function (formulario) {
    var modo = formulario.querySelector('[data-periodo-modo]');
    var periodoTodos = formulario.querySelector('[data-periodo-todos]');
    var campos = formulario.querySelectorAll('[name="periodo_mes"], [name="periodo_anio"]');
    var estado = formulario.querySelector('[data-contexto-status]');
    var boton = formulario.querySelector('[data-contexto-submit]');

    function sincronizarPeriodo() {
      var esTodos = modo.value === 'todos';
      periodoTodos.disabled = !esTodos;
      campos.forEach(function (campo) { campo.disabled = esTodos; });
    }

    modo.addEventListener('change', sincronizarPeriodo);
    sincronizarPeriodo();

    formulario.addEventListener('submit', function () {
      sincronizarPeriodo();
      opcionesTema.forEach(function (opcion) { opcion.disabled = true; });
      boton.disabled = true;
      boton.setAttribute('aria-busy', 'true');
      estado.textContent = 'Aplicando contexto…';
    });
  });

  document.addEventListener('submit', function (evento) {
    var formulario = evento.target.closest('[data-sensitive-form]');
    if (!formulario) return;
    var mensaje = formulario.dataset.confirm || '¿Confirmas esta acción?';
    if (!window.confirm(mensaje)) {
      evento.preventDefault();
      return;
    }
    var boton = formulario.querySelector('button[type="submit"]');
    if (boton) {
      boton.disabled = true;
      boton.setAttribute('aria-busy', 'true');
    }
  });
})();
