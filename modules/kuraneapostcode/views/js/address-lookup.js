(function () {
  'use strict';

  var config = window.kuraneaPostcodeConfig;
  if (!config || !config.endpoint || !config.strings) return;

  var strings = config.strings;

  function normalizePostcode(value) {
    var text = String(value || '').trim()
      .replace(/[０-９]/g, function (digit) { return String.fromCharCode(digit.charCodeAt(0) - 0xFEE0); })
      .replace(/[‐‑‒–—−－]/g, '-');
    var digits = text.replace(/-/g, '');
    if (/^[0-9]{7}$/.test(digits) && (/^[0-9]{7}$/.test(text) || /^[0-9]{3}-[0-9]{4}$/.test(text))) {
      return digits.slice(0, 3) + '-' + digits.slice(3);
    }
    return null;
  }

  function emitChange(field) {
    field.dispatchEvent(new Event('input', { bubbles: true }));
    field.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function japaneseCountrySelected(form) {
    var country = form.querySelector('[name="id_country"]');
    if (!country) return Number(config.japanCountryId) > 0;
    return Number(country.value) === Number(config.japanCountryId);
  }

  function initForm(form) {
    if (form.dataset.kuraneapostcodeBound === '1') return;

    var postcode = form.querySelector('[name="postcode"]');
    var searchInput = form.querySelector('[name="kuraneapostcode_search"]');
    var city = form.querySelector('[name="city"]');
    var address1 = form.querySelector('[name="address1"]');
    var state = form.querySelector('[name="id_state"]');
    if (!postcode || !searchInput || !city || !address1) return;

    form.dataset.kuraneapostcodeBound = '1';
    var searchGroup = searchInput.closest('.mb-3') || searchInput.parentElement;
    var postcodeGroup = postcode.closest('.mb-3') || postcode.parentElement;
    if (searchGroup && postcodeGroup) postcodeGroup.insertAdjacentElement('afterend', searchGroup);
    var sequence = 0;

    searchInput.placeholder = strings.search_placeholder || '';
    searchInput.setAttribute('autocomplete', 'off');
    searchInput.setAttribute('aria-autocomplete', 'list');

    var controls = document.createElement('div');
    controls.className = 'kuraneapostcode-controls mt-2';
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-outline-secondary';
    button.textContent = strings.search_button || 'Search';
    controls.appendChild(button);

    var status = document.createElement('div');
    status.className = 'form-text mt-2';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    var results = document.createElement('div');
    results.className = 'list-group mt-2';
    results.setAttribute('role', 'listbox');
    results.setAttribute('aria-label', strings.search_label || 'Address candidates');

    searchGroup.appendChild(controls);
    searchGroup.appendChild(status);
    searchGroup.appendChild(results);

    function updateVisibility() {
      searchGroup.hidden = !japaneseCountrySelected(form);
      if (searchGroup.hidden) {
        sequence += 1;
        results.replaceChildren();
        status.textContent = '';
      }
    }

    function applyCandidate(candidate) {
      sequence += 1;
      postcode.value = candidate.postcode || '';
      city.value = candidate.municipality || '';
      address1.value = candidate.town || '';
      if (state && candidate.state_id) state.value = String(candidate.state_id);
      emitChange(postcode);
      emitChange(city);
      emitChange(address1);
      if (state && candidate.state_id) emitChange(state);
      searchInput.value = [candidate.prefecture, candidate.municipality, candidate.town].filter(Boolean).join('');
      results.replaceChildren();
      status.textContent = strings.choose_hint || '';
      searchInput.focus();
    }

    async function search(value, requestId) {
      var query = String(value || '').trim();
      if (requestId === undefined) requestId = ++sequence;
      status.textContent = '';
      results.replaceChildren();
      if (!query || !japaneseCountrySelected(form)) return;

      try {
        var url = new URL(config.endpoint, window.location.href);
        url.searchParams.set('q', query);
        var response = await fetch(url.toString(), {
          method: 'GET',
          credentials: 'same-origin',
          headers: { Accept: 'application/json' }
        });
        if (!response.ok) throw new Error('lookup unavailable');
        var payload = await response.json();
        if (requestId !== sequence) return;

        var candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
        candidates.forEach(function (candidate) {
          var option = document.createElement('button');
          option.type = 'button';
          option.className = 'list-group-item list-group-item-action text-start';
          option.setAttribute('role', 'option');
          option.textContent = [candidate.prefecture, candidate.municipality, candidate.town].filter(Boolean).join('');
          option.addEventListener('click', function () { applyCandidate(candidate); });
          results.appendChild(option);
        });
        if (candidates.length === 0) status.textContent = strings.no_results || '';
      } catch (error) {
        if (requestId === sequence) status.textContent = strings.no_results || '';
      }
    }

    var timer;
    function scheduleSearch(value) {
      window.clearTimeout(timer);
      var requestId = ++sequence;
      timer = window.setTimeout(function () { search(value, requestId); }, 250);
    }

    searchInput.addEventListener('input', function () { scheduleSearch(searchInput.value); });
    postcode.addEventListener('input', function () {
      var normalized = normalizePostcode(postcode.value);
      if (normalized) postcode.value = normalized;
      scheduleSearch(normalized || '');
    });
    postcode.addEventListener('blur', function () {
      var normalized = normalizePostcode(postcode.value);
      if (normalized) postcode.value = normalized;
    });
    button.addEventListener('click', function () {
      var query = searchInput.value.trim() || normalizePostcode(postcode.value) || postcode.value;
      search(query);
    });

    var country = form.querySelector('[name="id_country"]');
    if (country) country.addEventListener('change', updateVisibility);
    form.addEventListener('submit', function () {
      var normalized = normalizePostcode(postcode.value);
      if (normalized) postcode.value = normalized;
    });
    updateVisibility();
  }

  function scan(root) {
    if (root.matches && root.matches('.js-address-form form')) initForm(root);
    if (root.querySelectorAll) root.querySelectorAll('.js-address-form form').forEach(initForm);
  }

  function start() {
    scan(document);
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        mutation.addedNodes.forEach(function (node) {
          if (node.nodeType === 1) scan(node);
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
