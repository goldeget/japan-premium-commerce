#!/usr/bin/env python3
"""Native-session acceptance. Artifacts contain fixed stage labels/booleans only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import subprocess
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait

BASE = os.environ['SHOP_BASE_URL'].rstrip('/')
# Native canonical links and auth cookies use PS_DOMAIN. The HTTP readiness
# probe may use the loopback IP, while browser sessions use this same hostname.
if BASE == 'http://127.0.0.1:18081' and os.environ.get('PS_DOMAIN') == 'localhost:18081':
    BASE = 'http://localhost:18081'
RUN = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
IDENTITY = json.loads(Path(os.environ['PROCUREMENT_IDENTITY_FILE']).read_text())
DEST = Path(os.environ['QA_ARTIFACT_DIR'])
DEST.mkdir(parents=True, exist_ok=True)
STAGE = 'isolation_guard'
RESULTS: dict[str, bool] = {}


def check(value: bool) -> None:
    if not value:
        raise AssertionError(STAGE)


def visible(driver, selector):
    return WebDriverWait(driver, 30).until(lambda d: next((x for x in d.find_elements(By.CSS_SELECTOR, selector) if x.is_displayed()), False))


def workspace(driver, query=''):
    driver.get(BASE + '/index.php?fc=module&module=ordenowaprocurement&controller=workspace' + query)


def fill(form, name, value):
    element = form.find_element(By.CSS_SELECTOR, '[name="' + name + '"]')
    if element.get_attribute('type') == 'hidden':
        check(element.get_attribute('value') == str(value))
    elif element.tag_name == 'select':
        Select(element).select_by_value(str(value))
    else:
        element.clear()
        element.send_keys(str(value))


def login_customer(driver, side):
    driver.get(BASE + '/index.php?controller=authentication')
    visible(driver, 'input[name="email"]').send_keys(IDENTITY['customers'][side]['email'])
    visible(driver, 'input[name="password"],input[name="passwd"]').send_keys(IDENTITY['password'])
    visible(driver, 'button[data-link-action="sign-in"],button[name="submitLogin"]').click()
    workspace(driver)
    visible(driver, '[data-testid="assignment-list"], [data-testid="workspace"], [data-testid="assignments"], main')
    check(not driver.find_elements(By.CSS_SELECTOR, 'form#login-form'))


def login_admin(driver, email, password):
    driver.get(BASE + '/admin-kuranea/')
    visible(driver, '#login_form input[name="email"],input[type="email"]').send_keys(email)
    visible(driver, '#login_form input[name="passwd"],#login_form input[name="password"],input[type="password"]').send_keys(password + Keys.ENTER)
    WebDriverWait(driver, 30).until(lambda d: bool(d.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminOrdenowaProcurement"]')))


def denied_admin_action(driver, controller, action, fields):
    admin_page(driver, controller)
    check(not driver.find_elements(By.CSS_SELECTOR, '[data-testid="procurement-' + action + '"]'))
    token = parse_qs(urlparse(driver.current_url).query).get('token', [''])[0]
    check(bool(token))
    response = fetch(driver, driver.current_url, dict(fields, procurement_action=action, token=token))
    check(response['status'] == 403 and response['private'])


def admin_page(driver, controller):
    # Native menu links carry the correct per-controller native CSRF token.
    links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller=' + controller + '"]')
    check(bool(links))
    href = links[0].get_attribute('href')
    check(urlparse(href).netloc == urlparse(BASE).netloc)
    driver.get(href)
    visible(driver, 'main, #content')


def admin_form(driver, action, fields):
    form = visible(driver, '[data-testid="procurement-' + action + '"]')
    check(form.tag_name == 'form')
    for name, value in fields.items():
        fill(form, name, value)
    form.find_element(By.CSS_SELECTOR, '[name="procurement_action"][value="' + action + '"]').click()
    WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
    check(not driver.find_elements(By.CSS_SELECTOR, '.alert-danger'))


def viewport(driver, width):
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': width < 768,
    })
    check(driver.execute_script('return window.innerWidth') == width)


def safe_capture(driver, name):
    # No live HTML, input values, customer identities, point values, URLs,
    # cookies, browser logs or unredacted screenshots leave this process.
    driver.execute_script("""
        for (const e of document.querySelectorAll('input,textarea,select')) {e.value='';e.disabled=true;}
        for (const e of document.querySelectorAll('img')) {e.removeAttribute('src');e.removeAttribute('srcset');e.removeAttribute('alt');}
        for (const e of document.querySelectorAll('a')) {e.removeAttribute('href');}
        const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
        let n;while(n=w.nextNode()){if(n.textContent.trim())n.textContent='[synthetic acceptance]';}
        for(const e of document.querySelectorAll('[title],[aria-label]')) {e.removeAttribute('title');e.removeAttribute('aria-label');}
    """)
    driver.save_screenshot(str(DEST / (name + '.png')))


def fetch(driver, url, data=None):
    return driver.execute_async_script("""
        const [url,data,done]=arguments;
        fetch(url,{method:data?'POST':'GET',credentials:'same-origin',
          headers:data?{'Content-Type':'application/x-www-form-urlencoded'}:{},
          body:data?new URLSearchParams(data).toString():undefined})
        .then(async r=>{const t=await r.text();done({status:r.status,
          private:r.headers.get('cache-control')?.includes('no-store')||false,
          noindex:(r.headers.get('x-robots-tag')||'').includes('noindex')||/name=["']robots["'][^>]+noindex/.test(t)});})
        .catch(()=>done({status:0}));
    """, url, data)


def main():
    global STAGE
    parsed = urlparse(BASE)
    check(parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost') and parsed.port == 18081)
    check(os.environ.get('CI') == 'true' and os.environ.get('KURANEA_ISOLATED_CI') == '1')
    check(bool(re.fullmatch(r'[0-9]+-[0-9]+', RUN)))
    check(os.environ['CI_COMPOSE_PROJECT_NAME'] == 'ordenowa-procurement-ci-' + RUN and IDENTITY['run'] == RUN)
    options = Options()
    for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,1000'):
        options.add_argument(flag)
    if os.environ.get('CHROME_BIN'):
        options.binary_location = os.environ['CHROME_BIN']
    browsers = []
    try:
        admin, a, b = (webdriver.Chrome(options=options) for _ in range(3))
        browsers.extend((admin, a, b))
        STAGE = 'admin_native_login'
        login_admin(admin, os.environ['ADMIN_MAIL'], os.environ['ADMIN_PASSWD'])
        STAGE = 'admin_assign_product'
        admin_page(admin, 'AdminOrdenowaProcurement')
        admin_form(admin, 'assign', {'id_customer': IDENTITY['customers']['a']['id'], 'id_product': IDENTITY['product_id'], 'id_product_attribute': IDENTITY.get('product_attribute_id', 0),
                                    'default_quantity': 1, 'max_quantity': 3, 'instructions': 'Synthetic acceptance instruction'})
        RESULTS[STAGE] = True
        STAGE = 'customer_a_confirm_submit'
        login_customer(a, 'a')
        card = visible(a, '[data-testid="assignment-card"]')
        assignment_id = int(card.get_attribute('data-assignment-id'))
        workspace(a, '&view=assignment&id_assignment=' + str(assignment_id))
        detail = visible(a, '[data-testid="assignment-detail"]')
        fill(detail, 'quantity', 2)
        visible(a, '[data-testid="review-request"]').send_keys(Keys.ENTER)
        confirmation = visible(a, '[data-testid="confirm-request"]')
        version = confirmation.find_element(By.CSS_SELECTOR, '[name="version"]').get_attribute('value')
        visible(a, '[data-testid="submit-request"]').send_keys(Keys.ENTER)
        visible(a, '[data-testid="request-detail"]')
        workspace(a, '&view=requests')
        request_id = int(visible(a, '[data-testid="request-row"]').get_attribute('data-request-id'))
        RESULTS[STAGE] = True
        STAGE = 'customer_b_owner_denials'
        login_customer(b, 'b')
        workspace(b, '&view=points')
        check(visible(b, '[data-testid="points-balance"]').get_attribute('data-balance') == '0')
        token = b.execute_script("return document.querySelector('input[name=token]')?.value || document.querySelector('[data-csrf-token]')?.dataset.csrfToken || ''")
        # Workspace renders a CSRF token on all views so even a non-owner can
        # exercise the owner guard using their own valid native session token.
        if not token:
            workspace(b)
            token = b.execute_script("return document.querySelector('input[name=token]')?.value || document.querySelector('[data-csrf-token]')?.dataset.csrfToken || ''")
        check(bool(token))
        endpoint = BASE + '/index.php?fc=module&module=ordenowaprocurement&controller=workspace'
        for query in ('&view=assignment&id_assignment=' + str(assignment_id), '&view=request&id_request=' + str(request_id)):
            response = fetch(b, endpoint + query)
            check(response['status'] == 404 and response['private'])
        response = fetch(b, endpoint, {'action': 'submit', 'token': token, 'id_assignment': assignment_id, 'version': version,
                                       'quantity': 2, 'idempotency_key': 'b' * 64})
        check(response['status'] == 404)
        response = fetch(b, endpoint + '&view=points&id_customer=' + str(IDENTITY['customers']['a']['id']))
        check(response['status'] == 404)
        workspace(b, '&view=points')
        check(visible(b, '[data-testid="points-balance"]').get_attribute('data-balance') == '0')
        check(not b.find_elements(By.CSS_SELECTOR, '[data-testid="ledger-entry"]'))
        RESULTS[STAGE] = True
        STAGE = 'native_readonly_review_denial'
        reader = webdriver.Chrome(options=options)
        browsers.append(reader)
        login_admin(reader, IDENTITY['reader']['email'], IDENTITY['password'])
        denied_admin_action(reader, 'AdminOrdenowaProcurementReviews', 'review',
                            {'id_request': request_id, 'version': 1, 'decision': 'APPROVED', 'reason': 'Synthetic unauthorized review'})
        workspace(a, '&view=request&id_request=' + str(request_id))
        check(visible(a, '[data-testid="request-detail"] [data-status]').get_attribute('data-status') == 'SUBMITTED')
        RESULTS[STAGE] = True
        STAGE = 'admin_manual_review'
        admin_page(admin, 'AdminOrdenowaProcurementReviews')
        admin_form(admin, 'review', {'id_request': request_id, 'version': 1, 'decision': 'APPROVED', 'reason': 'Synthetic approval'})
        workspace(a, '&view=points')
        check(visible(a, '[data-testid="points-balance"]').get_attribute('data-balance') == '0')
        RESULTS[STAGE] = True
        STAGE = 'native_readonly_award_denial'
        denied_admin_action(reader, 'AdminOrdenowaProcurementPoints', 'award',
                            {'id_request': request_id, 'amount': 100, 'reason': 'Synthetic unauthorized award', 'idempotency_key': 'd' * 64})
        workspace(a, '&view=points')
        check(visible(a, '[data-testid="points-balance"]').get_attribute('data-balance') == '0')
        RESULTS[STAGE] = True
        STAGE = 'admin_explicit_award'
        admin_page(admin, 'AdminOrdenowaProcurementPoints')
        admin_form(admin, 'award', {'id_request': request_id, 'amount': 100, 'reason': 'Synthetic manual allowance'})
        RESULTS[STAGE] = True
        STAGE = 'customer_fresh_login_award'
        a.quit()
        browsers.remove(a)
        a = webdriver.Chrome(options=options)
        browsers.append(a)
        login_customer(a, 'a')
        workspace(a, '&view=points')
        check(visible(a, '[data-testid="points-balance"]').get_attribute('data-balance') == '100')
        check(len(a.find_elements(By.CSS_SELECTOR, '[data-testid="ledger-entry"]')) == 1)
        RESULTS[STAGE] = True
        STAGE = 'admin_linked_correction'
        admin_page(admin, 'AdminOrdenowaProcurementPoints')
        form = visible(admin, '[data-testid="procurement-correct"]')
        award_field = form.find_element(By.CSS_SELECTOR, '[name="id_award"]')
        if award_field.get_attribute('type') == 'hidden':
            award_id = award_field.get_attribute('value')
            check(bool(award_id) and award_id.isdigit())
        elif award_field.tag_name == 'select':
            candidates = [x.get_attribute('value') for x in Select(award_field).options if (x.get_attribute('value') or '').isdigit() and int(x.get_attribute('value')) > 0]
            check(len(candidates) == 1)
            award_id = candidates[0]
        else:
            # Exactly one award exists in this fresh run. Read its actual row ID.
            rows = admin.find_elements(By.CSS_SELECTOR, '[data-award-id]')
            check(len(rows) == 1)
            award_id = rows[0].get_attribute('data-award-id')
        STAGE = 'native_readonly_correction_denial'
        denied_admin_action(reader, 'AdminOrdenowaProcurementPoints', 'correct',
                            {'id_award': award_id, 'delta': -20, 'reason': 'Synthetic unauthorized correction', 'idempotency_key': 'e' * 64})
        RESULTS[STAGE] = True
        STAGE = 'admin_linked_correction'
        admin_form(admin, 'correct', {'id_award': award_id, 'delta': -20, 'reason': 'Synthetic correction'})
        workspace(a, '&view=points')
        check(visible(a, '[data-testid="points-balance"]').get_attribute('data-balance') == '80')
        deltas = [int(x.get_attribute('data-delta')) for x in a.find_elements(By.CSS_SELECTOR, '[data-testid="ledger-entry"]')]
        check(sorted(deltas) == [-20, 100])
        RESULTS[STAGE] = True
        STAGE = 'request_native_support_owner_isolation'
        support = BASE + '/index.php?fc=module&module=ordenowaprocurement&controller=support&id_request=' + str(request_id)
        a.get(support)
        thread = visible(a, '[data-testid="support-thread"]')
        form = visible(a, 'form:has([data-testid="support-send"])')
        post_key = form.find_element(By.CSS_SELECTOR, '[name="idempotency_key"]').get_attribute('value')
        post_token = form.find_element(By.CSS_SELECTOR, '[name="token"]').get_attribute('value')
        visible(a, '[data-testid="support-message"]').send_keys('SYNTHETIC_CUSTOMER_MESSAGE')
        visible(a, '[data-testid="support-send"]').click()
        visible(a, '[data-testid="support-message-body"]')
        response = fetch(a, support, {'action': 'message', 'id_request': request_id, 'message': 'SYNTHETIC_CUSTOMER_MESSAGE',
                                      'idempotency_key': post_key, 'token': post_token})
        check(response['status'] == 200)
        response = fetch(b, support)
        check(response['status'] == 404 and response['private'])
        response = fetch(b, support, {'action': 'message', 'id_request': request_id, 'message': 'SYNTHETIC_FORBIDDEN_MESSAGE',
                                      'idempotency_key': 'f' * 64, 'token': token})
        check(response['status'] == 404)
        workspace(b, '&view=points')
        check(visible(b, '[data-testid="points-balance"]').get_attribute('data-balance') == '0')
        command = ['docker', 'compose', '-f', 'compose.yaml', '-f', 'tests/procurement/ci.compose.yaml', '-p', os.environ['CI_COMPOSE_PROJECT_NAME'],
                   'exec', '-T', 'prestashop', 'php', '/tmp/ordenowa-procurement-ci/ci_support.php']
        native_result = subprocess.run(command, capture_output=True, timeout=60)
        check(native_result.returncode == 0)
        a.get(support)
        bodies = [x.text for x in a.find_elements(By.CSS_SELECTOR, '[data-testid="support-message-body"]')]
        check('SYNTHETIC_CUSTOMER_MESSAGE' in bodies and 'SYNTHETIC_PUBLIC_REPLY' in bodies)
        check(not any('SYNTHETIC_PRIVATE_NOTE' in body or 'SYNTHETIC_FORBIDDEN_MESSAGE' in body for body in bodies))
        RESULTS[STAGE] = True
        STAGE = 'private_noindex_and_retail_denials'
        response = fetch(a, endpoint + '&view=points')
        check(response['status'] == 200 and response['private'] and response['noindex'])
        for controller in ('cart', 'order', 'history', 'addresses', 'address', 'order-slip', 'order-follow', 'order-detail'):
            response = fetch(a, BASE + '/index.php?controller=' + controller)
            check(response['status'] in (403, 404, 410))
        RESULTS[STAGE] = True
        STAGE = 'responsive_keyboard_private_captures'
        for width in (320, 360, 375, 390, 414, 768, 1024, 1280, 1440, 1920):
            viewport(a, width)
            workspace(a, '&view=points')
            visible(a, '[data-testid="points-balance"]')
            check(a.execute_script('return document.documentElement.scrollWidth <= window.innerWidth + 1'))
            a.find_element(By.TAG_NAME, 'body').send_keys(Keys.TAB)
            check(a.execute_script('return document.activeElement !== document.body'))
        for width in (390, 1440):
            for color in ('light', 'dark'):
                viewport(a, width)
                a.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': color}]})
                workspace(a, '&view=points')
                visible(a, '[data-testid="points-balance"]')
                safe_capture(a, 'points-redacted-' + str(width) + '-' + color)
        RESULTS[STAGE] = True
    finally:
        for browser in browsers:
            try:
                browser.quit()
            except Exception:
                pass


if __name__ == '__main__':
    status = 0
    try:
        main()
    except Exception as error:
        # Source-controlled stage and class only; Selenium exceptions include
        # page text, URL tokens and input values in their normal messages.
        print('FAIL procurement browser stage=' + STAGE + ' type=' + type(error).__name__, file=sys.stderr)
        status = 1
    (DEST / 'browser-outcome.json').write_text(json.dumps({'passed': status == 0, 'stages': RESULTS, 'failed_stage': STAGE if status else None}) + '\n')
    sys.exit(status)
