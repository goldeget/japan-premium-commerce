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
  '내-계정',
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

const LOGOUT_REDIRECT_TTL_MS = 10000;
const LOGOUT_REDIRECT_MAX_HOPS = 6;
const MAX_LOGOUT_REDIRECT_CLIENTS = 16;
const logoutRedirectClients = new Map();

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

const releaseLogoutRedirectClient = (clientId, marker) => {
  if (logoutRedirectClients.get(clientId) !== marker) return;
  logoutRedirectClients.delete(clientId);
  clearTimeout(marker.timerId);
  marker.resolveLifetime();
};

const beginLogoutRedirectClient = (event, clientId, resultingClientId) => {
  const previous = logoutRedirectClients.get(clientId);
  if (previous) releaseLogoutRedirectClient(clientId, previous);

  let resolveLifetime;
  const marker = {
    resultingClientId,
    expiresAt: Date.now() + LOGOUT_REDIRECT_TTL_MS,
    remainingHops: LOGOUT_REDIRECT_MAX_HOPS,
    resolveLifetime: () => {},
    timerId: 0,
  };
  const lifetime = new Promise((resolve) => {
    resolveLifetime = resolve;
  });
  marker.resolveLifetime = resolveLifetime;
  marker.timerId = setTimeout(() => releaseLogoutRedirectClient(clientId, marker), LOGOUT_REDIRECT_TTL_MS);
  logoutRedirectClients.set(clientId, marker);
  while (logoutRedirectClients.size > MAX_LOGOUT_REDIRECT_CLIENTS) {
    const oldestClientId = logoutRedirectClients.keys().next().value;
    if (typeof oldestClientId !== 'string') break;
    releaseLogoutRedirectClient(oldestClientId, logoutRedirectClients.get(oldestClientId));
  }
  event.waitUntil(lifetime);
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
  const isSameOriginGetNavigation = request.method === 'GET'
    && request.mode === 'navigate'
    && url.origin === self.location.origin;
  const clientId = typeof event.clientId === 'string' ? event.clientId : '';
  const resultingClientId = typeof event.resultingClientId === 'string' ? event.resultingClientId : '';

  for (const [markedClientId, marker] of logoutRedirectClients) {
    if (marker.expiresAt <= Date.now()) {
      releaseLogoutRedirectClient(markedClientId, marker);
      continue;
    }
    if (
      marker.resultingClientId
      && clientId === marker.resultingClientId
      && clientId !== markedClientId
    ) {
      // The destination document committed and is now the source of a later navigation.
      releaseLogoutRedirectClient(markedClientId, marker);
    }
  }

  if (isSameOriginGetNavigation && isLogoutAction && clientId) {
    beginLogoutRedirectClient(event, clientId, resultingClientId);
    return;
  }

  if (isSameOriginGetNavigation && clientId) {
    const marker = logoutRedirectClients.get(clientId);
    const resultClientMatches = !marker?.resultingClientId
      || !resultingClientId
      || marker.resultingClientId === resultingClientId;
    if (marker && resultClientMatches) {
      marker.remainingHops -= 1;
      if (marker.remainingHops <= 0) {
        releaseLogoutRedirectClient(clientId, marker);
      }
      return;
    }
  }

  const isPrivateCustomerNavigation = isPrivateReturnRoute(url.href);
  const isPrivateReturnNavigation = url.searchParams.getAll('back').some(isPrivateReturnRoute);
  // Let Chrome follow private-route redirects natively; navigation Request objects can use manual mode.
  if (
    request.method !== 'GET'
    || request.mode !== 'navigate'
    || isLogoutAction
    || isPrivateCustomerNavigation
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
