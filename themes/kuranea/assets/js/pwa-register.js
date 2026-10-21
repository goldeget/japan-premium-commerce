(() => {
  const script = document.currentScript;
  const workerUrl = script?.dataset.serviceWorker;
  const scopeUrl = script?.dataset.scope;

  if (!workerUrl || !scopeUrl || !('serviceWorker' in navigator)) {
    return;
  }

  const worker = new URL(workerUrl, document.baseURI);
  const scope = new URL(scopeUrl, document.baseURI);
  if (worker.origin !== window.location.origin || scope.origin !== window.location.origin) {
    return;
  }

  window.addEventListener('load', () => {
    navigator.serviceWorker.register(worker.href, { scope: scope.pathname }).catch(() => {});
  });
})();
