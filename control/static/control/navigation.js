/* Secciones nativas y accesibles; recordar solo preferencias visuales locales. */
document.querySelectorAll('[data-nav-group]').forEach(group => {
  const summary = group.querySelector('summary');
  const content = group.querySelector('.nav-group-links');
  const key = 'dret.menu.' + group.dataset.navGroup;
  let desired = group.open;
  let animation;
  try { if (!group.open && localStorage.getItem(key) === 'open') group.open = desired = true; } catch (_) {}
  summary.addEventListener('click', event => {
    event.preventDefault();
    const start = content.getBoundingClientRect().height;
    desired = !desired;
    if (animation) animation.cancel();
    try { localStorage.setItem(key, desired ? 'open' : 'closed'); } catch (_) {}
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced || !content.animate) { group.open = desired; delete group.dataset.expanded; animation = undefined; return; }
    group.open = true;
    group.dataset.expanded = String(desired);
    const current = content.animate([{height: start + 'px'}, {height: (desired ? content.scrollHeight : 0) + 'px'}],
      {duration: 190, easing: 'ease-out'});
    animation = current;
    current.finished.then(() => {
      if (animation !== current) return;
      group.open = desired;
      delete group.dataset.expanded;
      animation = undefined;
    }).catch(() => {});
  });
});
