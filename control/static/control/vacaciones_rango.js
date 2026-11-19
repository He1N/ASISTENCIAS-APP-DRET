(() => {
  const range = document.querySelector('[data-vac-rango]');
  if (!range) return;

  const start = range.querySelector('[name="inicio"]');
  const end = range.querySelector('[name="fin"]');
  const amount = range.closest('form').querySelector('[name="dias"]');
  const calendar = range.querySelector('.vac-calendario');
  const grid = calendar.querySelector('[data-calendario-dias]');
  const title = calendar.querySelector('[data-mes-titulo]');
  const help = calendar.querySelector('[data-calendario-ayuda]');
  const monthLabel = new Intl.DateTimeFormat('es-PE', { month: 'long', year: 'numeric', timeZone: 'UTC' });
  const dayLabel = new Intl.DateTimeFormat('es-PE', { dateStyle: 'full', timeZone: 'UTC' });
  const dateFromInput = value => new Date(value + 'T00:00:00Z');
  const today = new Date();
  let month = start.value ? dateFromInput(start.value) :
    new Date(Date.UTC(today.getFullYear(), today.getMonth(), 1));
  month.setUTCDate(1);
  let choosingEnd = Boolean(start.value && !end.value);

  function countDays() {
    if (!start.value || !end.value || end.value < start.value) return '';
    return String(1 + (dateFromInput(end.value) - dateFromInput(start.value)) / 86400000);
  }

  let manual = amount.value !== '' && Number(amount.value) !== Number(countDays());
  function updateAmount() {
    if (!manual) amount.value = countDays();
  }

  function render(focusDate) {
    title.textContent = monthLabel.format(month);
    help.textContent = choosingEnd
      ? 'Seleccione la fecha de fin. Puede elegir el mismo día.'
      : 'Seleccione la fecha de inicio.';
    const year = month.getUTCFullYear();
    const index = month.getUTCMonth();
    const offset = (month.getUTCDay() + 6) % 7;
    const count = new Date(Date.UTC(year, index + 1, 0)).getUTCDate();
    grid.replaceChildren();
    for (let i = 0; i < offset; i++) grid.append(document.createElement('span'));
    for (let day = 1; day <= count; day++) {
      const date = new Date(Date.UTC(year, index, day));
      const value = date.toISOString().slice(0, 10);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'secundario';
      button.textContent = day;
      button.setAttribute('aria-label', dayLabel.format(date));
      const selected = value === start.value ||
        Boolean(start.value && end.value && value >= start.value && value <= end.value);
      button.setAttribute('aria-pressed', String(selected));
      if (value === start.value || value === end.value) button.dataset.extremo = '';
      button.addEventListener('click', () => {
        if (choosingEnd && value >= start.value) {
          end.value = value;
          choosingEnd = false;
        } else {
          start.value = value;
          end.value = '';
          choosingEnd = true;
        }
        updateAmount();
        render(value);
      });
      grid.append(button);
      if (value === focusDate) button.focus();
    }
  }

  for (const field of [start, end]) {
    field.addEventListener('change', () => {
      if (field.value) {
        month = dateFromInput(field.value);
        month.setUTCDate(1);
      }
      choosingEnd = Boolean(start.value && !end.value);
      updateAmount();
      render();
    });
  }
  amount.addEventListener('input', () => { manual = amount.value !== '' || amount.validity.badInput; });
  amount.addEventListener('change', () => { if (!manual) updateAmount(); });
  for (const button of calendar.querySelectorAll('[data-mes]')) {
    button.addEventListener('click', () => {
      month.setUTCMonth(month.getUTCMonth() + Number(button.dataset.mes));
      render();
    });
  }
  updateAmount();
  render();
  calendar.hidden = false;
})();
