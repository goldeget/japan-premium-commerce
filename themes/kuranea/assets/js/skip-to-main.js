(() => {
  document.addEventListener('click', event => {
    const link = event.target?.closest?.('a.skip-link[href="#main-content"]');
    if (!link) return;

    const target = document.getElementById('main-content');
    if (!target || typeof target.focus !== 'function') return;

    // Hummingbird's fragment is an empty div, which is not keyboard-focusable by default.
    target.setAttribute('tabindex', '-1');
    const focusTarget = () => target.focus({ preventScroll: true });
    if (typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(focusTarget);
    } else {
      focusTarget();
    }
  });
})();
