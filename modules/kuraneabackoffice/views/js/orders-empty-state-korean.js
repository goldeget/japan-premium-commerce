(function () {
  'use strict';

  const coreIllustrationPath = '/themes/new-theme/img/empty_state/order.svg';
  const scriptUrl = document.currentScript && document.currentScript.src;
  if (!scriptUrl) return;

  const localizedIllustrationUrl = new URL('../img/orders-empty-state-ko.svg', scriptUrl).href;

  function localizeOrdersEmptyState() {
    document.querySelectorAll('img[src]').forEach((image) => {
      let imagePath;
      try {
        imagePath = new URL(image.src, window.location.href).pathname;
      } catch (error) {
        return;
      }

      if (!imagePath.endsWith(coreIllustrationPath)) return;

      image.src = localizedIllustrationUrl;
      image.alt = '주문 목록 예시';
    });
  }

  localizeOrdersEmptyState();

  if (document.documentElement && 'MutationObserver' in window) {
    const observer = new MutationObserver(localizeOrdersEmptyState);
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
})();
