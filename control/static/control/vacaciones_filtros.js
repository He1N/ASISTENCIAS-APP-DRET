const yearPicker = document.querySelector('.vac-year-picker');
if (yearPicker) {
  const all = yearPicker.querySelector('[data-all-years]');
  const years = [...yearPicker.querySelectorAll('[name=anio]')];
  const summary = yearPicker.querySelector('summary');
  const update = () => {
    const selected = years.filter(input => input.checked);
    all.checked = selected.length === 0;
    summary.textContent = selected.length ? selected.map(input => input.parentElement.textContent.trim()).join(', ') : 'Todos los años';
  };
  all.addEventListener('change', () => { years.forEach(input => { input.checked = false; }); update(); });
  years.forEach(input => input.addEventListener('change', update));
}
