/* Preferencia visual local; claro por defecto. Aplicar antes de pintar. */
(() => {
  const root = document.documentElement;
  let theme = 'light';
  try { if (localStorage.getItem('dret.theme') === 'dark') theme = 'dark'; } catch (_) {}
  root.dataset.theme = theme;
  document.addEventListener('DOMContentLoaded', () => {
    const button = document.querySelector('.theme-toggle');
    if (!button) return;
    const update = () => {
      const dark = root.dataset.theme === 'dark';
      const label = dark ? 'Activar modo claro' : 'Activar modo oscuro';
      button.setAttribute('aria-label', label);
      button.title = label;
      button.setAttribute('aria-pressed', String(dark));
    };
    button.addEventListener('click', () => {
      root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('dret.theme', root.dataset.theme); } catch (_) {}
      update();
    });
    update();
  });
})();
