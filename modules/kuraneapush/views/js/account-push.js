(function () {
  'use strict';

  // Functional copy never comes from a response or a push payload.
  var messages = {
    ja: {
      unavailable: '現在、新しい通知の登録は利用できません。',
      saved: 'このアカウントには通知の登録が保存されています。',
      ready: '案内を確認して同意すると、通知を登録できます。',
      consent: '通知を有効にするには、案内への同意が必要です。',
      denied: 'ブラウザーで通知が許可されていません。ブラウザーの設定をご確認ください。',
      working: '通知の設定を更新しています。',
      enabled: 'この端末の通知登録を保存しました。',
      revoked: 'すべての端末の通知登録を取り消しました。',
      failed: '設定を更新できませんでした。もう一度お試しください。',
      localFailed: 'アカウントの通知登録を取り消しました。この端末の解除を完了するには、もう一度お試しください。'
    },
    en: {
      unavailable: 'New notification subscriptions are currently unavailable.',
      saved: 'A notification subscription is saved for this account.',
      ready: 'Read and agree to the notice to register for notifications.',
      consent: 'Agree to the notice before enabling notifications.',
      denied: 'Notifications are not allowed in this browser. Check your browser settings.',
      working: 'Updating notification settings.',
      enabled: 'The notification subscription for this device has been saved.',
      revoked: 'Notification subscriptions have been revoked on all devices.',
      failed: 'The settings could not be updated. Please try again.',
      localFailed: 'Account subscriptions have been revoked. Try again to finish unsubscribing this device.'
    },
    ko: {
      unavailable: '현재 새 알림 구독을 사용할 수 없습니다.',
      saved: '이 계정에 저장된 알림 구독이 있습니다.',
      ready: '안내를 확인하고 동의하면 알림을 등록할 수 있습니다.',
      consent: '알림을 사용하려면 안내에 동의해야 합니다.',
      denied: '이 브라우저에서 알림이 허용되지 않았습니다. 브라우저 설정을 확인해 주세요.',
      working: '알림 설정을 변경하고 있습니다.',
      enabled: '이 기기의 알림 구독을 저장했습니다.',
      revoked: '모든 기기의 알림 구독을 철회했습니다.',
      failed: '설정을 변경하지 못했습니다. 다시 시도해 주세요.',
      localFailed: '계정의 알림 구독을 철회했습니다. 이 기기의 구독 해제를 완료하려면 다시 시도해 주세요.'
    }
  };

  function moduleUrl(value) {
    try {
      var url = new URL(value, window.location.href);
      if (!value || url.origin !== window.location.origin || url.username || url.password || url.hash) return null;
      // The URL is issued by the authenticated module hook. Never construct a
      // provider URL, append an action, or follow a redirect with the token.
      return url.href;
    } catch (error) {
      return null;
    }
  }

  function applicationKey(value) {
    try {
      if (!/^[A-Za-z0-9_-]{87}=?$/.test(value || '')) return null;
      var encoded = value.replace(/-/g, '+').replace(/_/g, '/');
      while (encoded.length % 4) encoded += '=';
      var decoded = window.atob(encoded);
      if (decoded.length !== 65 || decoded.charCodeAt(0) !== 4) return null;
      return Uint8Array.from(decoded, function (character) { return character.charCodeAt(0); });
    } catch (error) {
      return null;
    }
  }

  function init(root) {
    if (root.dataset.pushBound === '1') return;
    var consent = root.querySelector('[data-push-consent]');
    var status = root.querySelector('[data-push-status]');
    var enable = root.querySelector('[data-push-enable]');
    var disable = root.querySelector('[data-push-disable]');
    if (!consent || !status || !enable || !disable) return;
    root.dataset.pushBound = '1';

    var locale = Object.prototype.hasOwnProperty.call(messages, root.dataset.locale) ? root.dataset.locale : 'ja';
    var copy = messages[locale];
    var endpoint = moduleUrl(root.dataset.subscriptionUrl);
    var key = applicationKey(root.dataset.applicationServerKey);
    var notice = root.querySelector('[data-push-notice]');
    var active = root.dataset.active === '1';
    var localRevokePending = false;
    var busy = false;
    var supported = Boolean(window.isSecureContext && 'Notification' in window && 'PushManager' in window && 'serviceWorker' in navigator);
    var available = Boolean(endpoint && root.dataset.token && root.dataset.canSubscribe === '1' && key && notice && notice.textContent.trim() && supported);

    function render() {
      consent.disabled = busy || !available;
      enable.disabled = busy || !available || !consent.checked;
      // Revocation depends only on authentication, never subscription readiness.
      disable.disabled = busy || !(active || localRevokePending) || !endpoint || !root.dataset.token;
      root.setAttribute('aria-busy', busy ? 'true' : 'false');
    }

    function say(name) { status.textContent = copy[name]; }

    async function post(payload) {
      if (!endpoint) throw new Error('Unavailable');
      var response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        redirect: 'error',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error('Request failed');
      var result = await response.json();
      if (!result || result.ok === false || result.success === false || result.error) throw new Error('Request failed');
      return result;
    }

    function workerReady() {
      // Called only by enable. An unregistered/blocked worker must not leave
      // controls indefinitely busy.
      return new Promise(function (resolve, reject) {
        var timer = window.setTimeout(function () { reject(new Error('Unavailable')); }, 10000);
        navigator.serviceWorker.ready.then(function (registration) {
          window.clearTimeout(timer);
          resolve(registration);
        }, function () {
          window.clearTimeout(timer);
          reject(new Error('Unavailable'));
        });
      });
    }

    consent.addEventListener('change', render);
    enable.addEventListener('click', async function () {
      if (busy) return;
      if (!consent.checked) { say('consent'); return; }
      if (!available) { say('unavailable'); return; }
      busy = true;
      render();
      say('working');
      var created = null;
      try {
        // Keep requestPermission directly in this click handler, before any
        // awaited worker/network operation, to preserve the user gesture.
        var permission = Notification.permission;
        if (permission === 'default') permission = await Notification.requestPermission();
        if (permission !== 'granted') { say('denied'); return; }
        var registration = await workerReady();
        if (!key || !registration.pushManager) throw new Error('Unavailable');
        var subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
          subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
          created = subscription;
        }
        await post({ action: 'subscribe', token: root.dataset.token, consent: true, locale: locale, subscription: subscription.toJSON() });
        created = null;
        active = true;
        say('enabled');
      } catch (error) {
        if (created) {
          try {
            if (!await created.unsubscribe()) localRevokePending = true;
          } catch (cleanupError) { localRevokePending = true; }
        }
        say('failed');
      } finally {
        busy = false;
        render();
      }
    });

    disable.addEventListener('click', async function () {
      if (busy || !(active || localRevokePending)) return;
      busy = true;
      render();
      say('working');
      var serverRevoked = false;
      var localRevoked = true;
      try {
        await post({ action: 'revoke', token: root.dataset.token });
        serverRevoked = true;
        active = false;
      } catch (error) { /* Always attempt current-device removal as well. */ }
      try {
        if ('serviceWorker' in navigator) {
          var registration = await navigator.serviceWorker.getRegistration();
          if (registration && registration.pushManager) {
            var subscription = await registration.pushManager.getSubscription();
            if (subscription) localRevoked = await subscription.unsubscribe();
          }
        }
      } catch (error) { localRevoked = false; }
      localRevokePending = !localRevoked;
      consent.checked = false;
      say(!serverRevoked ? 'failed' : (localRevoked ? 'revoked' : 'localFailed'));
      busy = false;
      render();
    });

    // No permission, service-worker readiness, browser subscription or network
    // operation takes place during initialization.
    status.textContent = (active ? copy.saved + ' ' : '') + (available ? copy.ready : copy.unavailable);
    render();
  }

  function initAll() { document.querySelectorAll('[data-ordenowa-push]').forEach(init); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll);
  else initAll();
}());
