(() => {
  const script = document.currentScript;
  const workerUrl = script?.dataset.serviceWorker;
  const scopeUrl = script?.dataset.scope;

  if (!workerUrl || !scopeUrl || !('serviceWorker' in navigator)) return;

  const worker = new URL(workerUrl, document.baseURI);
  const scope = new URL(scopeUrl, document.baseURI);
  if (worker.origin !== window.location.origin || scope.origin !== window.location.origin) return;

  const platform = document.querySelector('meta[name="ordenowa-platform"]')?.content === 'procurement';
  if (platform) worker.searchParams.set('platform', 'procurement');

  let deferredInstall = null;
  let guide = null;
  let installButton = null;
  if (platform) {
    window.addEventListener('beforeinstallprompt', (event) => {
      event.preventDefault();
      deferredInstall = event;
      if (installButton) installButton.hidden = false;
    });
    window.addEventListener('appinstalled', () => {
      deferredInstall = null;
      if (guide) guide.hidden = true;
    });
  }

  window.addEventListener('load', () => {
    navigator.serviceWorker.register(worker.href, {scope: scope.pathname}).catch(() => {});
    if (!platform || navigator.standalone === true || window.matchMedia?.('(display-mode: standalone)').matches) return;

    const requested = (document.documentElement.lang || navigator.language || 'ja').toLowerCase();
    const locale = requested.startsWith('ko') ? 'ko' : requested.startsWith('en') ? 'en' : 'ja';
    const copy = {
      ja: {
        title: 'ORDENOWAをホーム画面に追加', button: 'アプリをインストール',
        ios: 'Safariの共有ボタンを開き、「ホーム画面に追加」を選択してください。',
        browser: 'ブラウザのメニューから「アプリをインストール」または「ホーム画面に追加」を選択できます。',
        retry: 'ブラウザのメニューからも追加できます。',
      },
      en: {
        title: 'Add ORDENOWA to your home screen', button: 'Install app',
        ios: 'In Safari, open Share and select Add to Home Screen.',
        browser: 'From your browser menu, select Install app or Add to Home Screen.',
        retry: 'You can also add the app from your browser menu.',
      },
      ko: {
        title: 'ORDENOWA를 홈 화면에 추가', button: '앱 설치',
        ios: 'Safari의 공유 버튼을 열고 홈 화면에 추가를 선택해 주세요.',
        browser: '브라우저 메뉴에서 앱 설치 또는 홈 화면에 추가를 선택할 수 있습니다.',
        retry: '브라우저 메뉴에서도 앱을 추가할 수 있습니다.',
      },
    }[locale];
    const ios = /iPad|iPhone|iPod/.test(navigator.userAgent || '')
      || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    guide = document.createElement('aside');
    guide.setAttribute('data-ordenowa-install', '');
    guide.setAttribute('aria-label', copy.title);
    guide.style.maxWidth = '56rem';
    guide.style.margin = '1rem auto';
    guide.style.padding = '0 1rem';
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = copy.title;
    const instruction = document.createElement('p');
    instruction.textContent = ios ? copy.ios : copy.browser;
    installButton = document.createElement('button');
    installButton.type = 'button';
    installButton.className = 'btn btn-outline-primary';
    installButton.textContent = copy.button;
    installButton.hidden = !deferredInstall || ios;
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    installButton.addEventListener('click', async () => {
      if (!deferredInstall) return;
      const prompt = deferredInstall;
      deferredInstall = null;
      installButton.disabled = true;
      try {
        await prompt.prompt();
        await prompt.userChoice;
        installButton.hidden = true;
      } catch (_error) {
        status.textContent = copy.retry;
        installButton.hidden = true;
      } finally {
        installButton.disabled = false;
      }
    });
    details.append(summary, instruction, installButton, status);
    guide.appendChild(details);
    document.body.appendChild(guide);
  });
})();
