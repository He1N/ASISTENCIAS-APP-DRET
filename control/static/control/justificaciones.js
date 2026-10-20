/* Mejora progresiva: selección explícita por ID y controles nativos de teclado. */
(() => {
  const reglas = new Map();
  const initial = document.getElementById('operacion-inicial');
  if (initial) {
    const op = JSON.parse(initial.textContent);
    if (op) reglas.set(String(op.id), op.requiere_fecha_final);
  }
  const operacion = document.getElementById('id_tipo_operacion');
  const final = document.getElementById('id_fecha_final');
  function mostrarRegla() {
    if (!final || !operacion) return;
    const regla = reglas.get(operacion.value);
    final.required = regla === true;
    document.getElementById('regla-fecha-final').textContent = !operacion.value
      ? 'Seleccione una operación para revisar su regla de fecha final.'
      : regla === true ? 'Esta operación requiere fecha final; puede ser igual al inicio.'
      : regla === false ? 'La fecha final es opcional para esta operación.'
      : 'Regla de fecha final pendiente de revisión. No se admite el alta manual hasta definirla.';
  }
  operacion?.addEventListener('change', mostrarRegla);
  mostrarRegla();
  document.querySelectorAll('[data-autocompletado]').forEach(container => {
    const input = container.querySelector('input');
    const select = container.querySelector('select');
    const status = container.querySelector('[aria-live]');
    let timer, controller;
    let revision = 0;
    async function buscar() {
      const currentRevision = ++revision;
      controller?.abort();
      controller = new AbortController();
      status.textContent = 'Buscando…';
      try {
        const url = new URL(container.dataset.endpoint, window.location.origin);
        url.searchParams.set('q', input.value);
        url.searchParams.set('modo', container.dataset.modo);
        const response = await fetch(url, {signal: controller.signal, headers: {'Accept': 'application/json'}});
        if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('respuesta');
        const {results} = await response.json();
        if (currentRevision !== revision) return;
        const selected = select.value;
        const option = selected ? select.selectedOptions[0]?.cloneNode(true) : null;
        select.replaceChildren(new Option('Seleccione…', ''));
        // Conservar la selección existente; nunca elegir la primera coincidencia.
        if (option && !results.some(obj => String(obj.id) === selected)) select.append(option);
        for (const obj of results) {
          select.add(new Option(obj.label, obj.id));
          if ('requiere_fecha_final' in obj) reglas.set(String(obj.id), obj.requiere_fecha_final);
        }
        select.value = selected;
        status.textContent = results.length ? `${results.length} coincidencias (máximo 20). Seleccione la ficha.` : 'Sin coincidencias. Pruebe otro fragmento.';
        mostrarRegla();
      } catch (error) {
        if (error.name !== 'AbortError' && currentRevision === revision) status.textContent = 'No se pudo consultar. Revise la sesión o inténtelo nuevamente.';
      }
    }
    input.addEventListener('input', () => {
      clearTimeout(timer);
      // Invalidar la consulta anterior antes del siguiente debounce.
      revision++;
      controller?.abort();
      timer = setTimeout(buscar, 250);
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        clearTimeout(timer);
        buscar();
      }
    });
    if (select === operacion) buscar();
  });
  const periodo = document.getElementById('id_periodo');
  const estados = document.getElementById('estados-periodos');
  if (periodo && estados) {
    const periodos = JSON.parse(estados.textContent);
    function mostrarPeriodo() {
      const p = periodos.find(obj => String(obj.id) === periodo.value);
      const avisos = document.getElementById('avisos-periodo');
      avisos.replaceChildren();
      if (p && p.estado !== 'ABIERTO') {
        const text = document.createElement('p');
        text.className = 'mensaje';
        text.textContent = `Este periodo está ${p.estado === 'CERRADO' ? 'cerrado' : 'procesado'}. El registro se añadirá al historial.`;
        avisos.append(text);
      }
    }
    periodo.addEventListener('change', mostrarPeriodo);
    mostrarPeriodo();
  }
})();
