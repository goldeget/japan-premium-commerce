const offlinePage = (language) => {
  const requestedLanguage = (language || 'ja').split(',')[0].trim().toLowerCase();
  const locale = requestedLanguage.startsWith('ko') ? 'ko' : requestedLanguage.startsWith('en') ? 'en' : 'ja';
  const copyByLocale = {
    ja: {
      title: 'オーデノワ | ORDENOWA',
      brand: 'ORDENOWA / オーデノワ',
      heading: 'インターネットに接続できません',
      message: '接続を確認してから、もう一度お試しください。',
    },
    en: {
      title: 'ORDENOWA',
      brand: 'ORDENOWA',
      heading: 'You are offline',
      message: 'Reconnect to the internet and try again.',
    },
    ko: {
      title: '오데노와 | ORDENOWA',
      brand: '오데노와 / ORDENOWA',
      heading: '연결을 확인해 주세요',
      message: '인터넷에 연결되면 다시 시도해 주세요.',
    },
  };
  const copy = copyByLocale[locale];

  return `<!doctype html><html lang="${locale}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#10243a"><title>${copy.title}</title><body style="margin:0;background:#fff;color:#10243a;font:16px/1.8 sans-serif"><main style="max-width:38rem;margin:18vh auto;padding:2rem"><p style="letter-spacing:.16em">${copy.brand}</p><h1>${copy.heading}</h1><p>${copy.message}</p></main></body></html>`;
};

self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || request.mode !== 'navigate') {
    return;
  }

  event.respondWith(
    fetch(request).catch(() => new Response(offlinePage(request.headers.get('Accept-Language') || self.navigator.language || 'ja'), {
      status: 503,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    })),
  );
});
