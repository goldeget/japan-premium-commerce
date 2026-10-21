const offlinePage = (language) => {
  const copy = language.startsWith('ko')
    ? ['연결을 확인해 주세요', '인터넷에 연결되면 다시 시도해 주세요.']
    : language.startsWith('en')
      ? ['You are offline', 'Reconnect to the internet and try again.']
      : ['インターネットに接続できません', '接続を確認してから、もう一度お試しください。'];

  return `<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0b1b30"><title>KURANEA</title><body style="margin:0;background:#faf8f3;color:#172638;font:16px/1.8 sans-serif"><main style="max-width:38rem;margin:18vh auto;padding:2rem"><p style="color:#b49a61;letter-spacing:.16em">KURANEA / クラネア</p><h1>${copy[0]}</h1><p>${copy[1]}</p></main></body></html>`;
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
    fetch(request).catch(() => new Response(offlinePage(self.navigator.language || 'ja'), {
      status: 503,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    })),
  );
});
