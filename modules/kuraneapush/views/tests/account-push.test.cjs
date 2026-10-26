'use strict';

// Entirely local DOM/PushManager doubles: these tests cannot reach a provider.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../js/account-push.js'), 'utf8');

function element(textContent = '') {
  return {
    textContent, disabled: false, checked: false, listeners: {},
    addEventListener(name, callback) { this.listeners[name] = callback; }
  };
}

function fixture(options = {}) {
  const calls = [];
  const nodes = {
    '[data-push-consent]': element(),
    '[data-push-status]': element(),
    '[data-push-enable]': element(),
    '[data-push-disable]': element(),
    '[data-push-notice]': options.noNotice ? null : element('Synthetic test notice')
  };
  const key = Buffer.alloc(65, 1);
  key[0] = 4;
  const root = {
    dataset: {
      subscriptionUrl: '/index.php?fc=module&module=kuraneapush&controller=subscription',
      statusUrl: '/index.php?fc=module&module=kuraneapush&controller=subscription&action=status',
      token: 'synthetic-token', locale: options.locale || 'en',
      pushNoticeVersion: options.noticeVersion === false ? '' : 'a'.repeat(64),
      canSubscribe: options.unavailable ? '0' : '1', active: options.active ? '1' : '0',
      revocable: options.revocable || options.active ? '1' : '0',
      applicationServerKey: options.key === false ? '' : key.toString('base64url')
    },
    querySelector(selector) { return nodes[selector]; },
    setAttribute() {}
  };
  if (options.crossOrigin) root.dataset.subscriptionUrl = 'https://untrusted.invalid/subscription';
  const subscription = {
    toJSON() { return { endpoint: 'https://synthetic.invalid/device', expirationTime: null, keys: { p256dh: 'synthetic', auth: 'synthetic' } }; },
    async unsubscribe() { calls.push('unsubscribe'); return !options.unsubscribeFails; }
  };
  const registration = {
    pushManager: {
      async getSubscription() { calls.push('getSubscription'); return options.existing ? subscription : null; },
      async subscribe() { calls.push('subscribe'); return subscription; }
    }
  };
  const notification = {
    permission: options.permission || 'default',
    async requestPermission() { calls.push('permission'); return options.permissionResult || 'granted'; }
  };
  const serviceWorker = {
    get ready() { calls.push('ready'); return Promise.resolve(registration); },
    async getRegistration() { calls.push('getRegistration'); return registration; }
  };
  const window = {
    location: { href: 'https://shop.invalid/account', origin: 'https://shop.invalid' },
    isSecureContext: true, Notification: notification, PushManager: function () {},
    atob(value) { return Buffer.from(value, 'base64').toString('binary'); },
    setTimeout, clearTimeout
  };
  vm.runInNewContext(source, {
    window, navigator: { serviceWorker }, Notification: notification, URL, Uint8Array,
    document: { readyState: 'complete', querySelectorAll() { return [root]; } },
    async fetch(url, init) {
      const payload = JSON.parse(init.body);
      calls.push({ url, init, payload });
      return { ok: !options.saveFails, async json() { return { ok: true }; } };
    }
  });
  return {
    calls, nodes, root,
    async enable() { await nodes['[data-push-enable]'].listeners.click(); },
    async revoke() { await nodes['[data-push-disable]'].listeners.click(); },
    consent() {
      nodes['[data-push-consent]'].checked = true;
      nodes['[data-push-consent]'].listeners.change();
    }
  };
}

test('initialization performs no permission, worker, subscription or API operation', () => {
  const f = fixture();
  assert.deepEqual(f.calls, []);
  assert.equal(f.nodes['[data-push-enable]'].disabled, true);
});

test('explicit enable without consent cannot ask browser permission', async () => {
  const f = fixture();
  await f.enable();
  assert.deepEqual(f.calls, []);
  assert.match(f.nodes['[data-push-status]'].textContent, /Agree to the notice/);
});

test('missing copy, notice version, public key and readiness off each keep enable disabled', async () => {
  for (const options of [{ noNotice: true }, { noticeVersion: false }, { key: false }, { unavailable: true }]) {
    const f = fixture(options);
    f.consent();
    assert.equal(f.nodes['[data-push-enable]'].disabled, true);
    await f.enable();
    assert.deepEqual(f.calls, []);
    assert.match(f.nodes['[data-push-status]'].textContent, /unavailable/);
  }
});

test('consented enable requests permission before waiting for worker and saving', async () => {
  const f = fixture();
  f.consent();
  assert.equal(f.nodes['[data-push-enable]'].disabled, false);
  await f.enable();
  assert.deepEqual(f.calls.slice(0, 4), ['permission', 'ready', 'getSubscription', 'subscribe']);
  const request = f.calls[4];
  assert.equal(request.url, 'https://shop.invalid/index.php?fc=module&module=kuraneapush&controller=subscription');
  assert.equal(request.init.method, 'POST');
  assert.equal(request.init.credentials, 'same-origin');
  assert.equal(request.init.cache, 'no-store');
  assert.equal(request.init.redirect, 'error');
  assert.equal(request.payload.action, 'subscribe');
  assert.equal(request.payload.consent, true);
  assert.equal(request.payload.notice_version, 'a'.repeat(64));
  assert.equal(request.payload.token, 'synthetic-token');
  assert.equal(request.payload.locale, 'en');
  assert.equal(f.nodes['[data-push-disable]'].disabled, false);
  assert.doesNotMatch(f.nodes['[data-push-status]'].textContent, /synthetic|https:/);
});

test('denied browser permission prevents worker, subscribe and save', async () => {
  const f = fixture({ permission: 'denied' });
  f.consent();
  await f.enable();
  assert.deepEqual(f.calls, []);
  assert.match(f.nodes['[data-push-status]'].textContent, /not allowed/);
});

test('standard browser subscription JSON is normalized to the strict API schema', async () => {
  const f = fixture();
  f.consent();
  await f.enable();
  const request = f.calls.find(call => typeof call === 'object');
  assert.deepEqual(request.payload.subscription, {
    endpoint: 'https://synthetic.invalid/device',
    keys: { p256dh: 'synthetic', auth: 'synthetic' }
  });
});

test('failed save unsubscribes the newly created browser subscription', async () => {
  const f = fixture({ saveFails: true });
  f.consent();
  await f.enable();
  assert.equal(f.calls.at(-1), 'unsubscribe');
  assert.match(f.nodes['[data-push-status]'].textContent, /could not be updated/);
  assert.doesNotMatch(f.nodes['[data-push-status]'].textContent, /synthetic|https:/);
});

test('failed save preserves a preexisting browser subscription', async () => {
  const f = fixture({ saveFails: true, existing: true });
  f.consent();
  await f.enable();
  assert.equal(f.calls.includes('subscribe'), false);
  assert.equal(f.calls.includes('unsubscribe'), false);
});

test('active subscription stays revocable with blank copy, no key and readiness off', async () => {
  const f = fixture({ active: true, noNotice: true, key: false, unavailable: true, existing: true });
  assert.equal(f.nodes['[data-push-enable]'].disabled, true);
  assert.equal(f.nodes['[data-push-disable]'].disabled, false);
  await f.revoke();
  assert.equal(f.calls[0].payload.action, 'revoke');
  assert.deepEqual(Object.keys(f.calls[0].payload).sort(), ['action', 'token']);
  assert.deepEqual(f.calls.slice(1), ['getRegistration', 'getSubscription', 'unsubscribe']);
  assert.equal(f.nodes['[data-push-disable]'].disabled, true);
  assert.match(f.nodes['[data-push-status]'].textContent, /all devices/);
});

test('legacy stored subscription stays revocable without counting as consented or active', async () => {
  const f = fixture({ revocable: true, existing: true });
  assert.equal(f.root.dataset.active, '0');
  assert.equal(f.nodes['[data-push-disable]'].disabled, false);
  assert.match(f.nodes['[data-push-status]'].textContent, /previous notification registration/i);
  await f.revoke();
  assert.equal(f.calls[0].payload.action, 'revoke');
  assert.equal(f.nodes['[data-push-disable]'].disabled, true);
});

test('server revoke failure still unsubscribes locally and retains retry', async () => {
  const f = fixture({ active: true, existing: true, saveFails: true });
  await f.revoke();
  assert.equal(f.calls.at(-1), 'unsubscribe');
  assert.equal(f.nodes['[data-push-disable]'].disabled, false);
  assert.match(f.nodes['[data-push-status]'].textContent, /could not be updated/);
});

test('local revoke failure retains a retry after server success', async () => {
  const f = fixture({ active: true, existing: true, unsubscribeFails: true });
  await f.revoke();
  assert.equal(f.nodes['[data-push-disable]'].disabled, false);
  assert.match(f.nodes['[data-push-status]'].textContent, /finish unsubscribing/);
});

test('cross-origin template URLs cannot receive the token', async () => {
  const f = fixture({ crossOrigin: true, active: true });
  f.consent();
  await f.enable();
  await f.revoke();
  assert.equal(f.calls.some(call => typeof call === 'object'), false);
});

test('all three locales supply functional status copy without response content', () => {
  const expected = { en: /unavailable/, ja: /利用できません/, ko: /사용할 수 없습니다/ };
  for (const locale of ['ja', 'en', 'ko']) {
    const f = fixture({ locale, key: false });
    assert.match(f.nodes['[data-push-status]'].textContent, expected[locale]);
    assert.deepEqual(f.calls, []);
  }
});
