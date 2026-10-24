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

const PRIVATE_RETURN_ROUTES = new Set([
  'address',
  'addresses',
  'cart',
  'discount',
  'getfile',
  'guest-tracking',
  'history',
  'identity',
  'my-account',
  'order',
  'order-confirmation',
  'order-detail',
  'order-follow',
  'order-opc',
  'order-return',
  'order-slip',
  'pdf-invoice',
  'pdf-order-return',
  'pdf-order-slip',
]);

const isPrivateReturnRoute = (value) => {
  if (typeof value !== 'string' || !value.trim()) return false;
  const route = value.trim().toLowerCase();
  if (PRIVATE_RETURN_ROUTES.has(route)) return true;

  try {
    const target = new URL(value, self.location.origin);
    if (target.origin !== self.location.origin) return false;
    const controllers = target.searchParams.getAll('controller');
    if (controllers.some((controller) => PRIVATE_RETURN_ROUTES.has(controller.trim().toLowerCase()))) {
      return true;
    }
    return target.pathname.split('/').some((segment) => {
      try {
        return PRIVATE_RETURN_ROUTES.has(decodeURIComponent(segment).trim().toLowerCase());
      } catch (_error) {
        return PRIVATE_RETURN_ROUTES.has(segment.trim().toLowerCase());
      }
    });
  } catch (_error) {
    return false;
  }
};

self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  const isLogoutAction = url.searchParams.has('mylogout');
  const isPrivateReturnNavigation = url.searchParams.getAll('back').some(isPrivateReturnRoute);
  // Let Chrome follow private-route redirects natively; navigation Request objects can use manual mode.
  if (
    request.method !== 'GET'
    || request.mode !== 'navigate'
    || isLogoutAction
    || isPrivateReturnNavigation
  ) {
    return;
  }

  event.respondWith(
    fetch(request, {
      referrer: request.referrer,
      referrerPolicy: request.referrerPolicy,
    }).catch(() => new Response(offlinePage(request.headers.get('Accept-Language') || self.navigator.language || 'ja'), {
      status: 503,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    })),
  );
});
