#!/usr/bin/env python3
"""Focused native procurement-mode account smoke; secrets/MIME stay only in memory."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import shutil
import traceback
import sys
from urllib.parse import urlparse

BASE = os.environ['SHOP_BASE_URL'].rstrip('/')
if BASE == 'http://127.0.0.1:18081' and os.environ.get('PS_DOMAIN') == 'localhost:18081':
    BASE = 'http://localhost:18081'
RUN = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
PROJECT = os.environ['CI_COMPOSE_PROJECT_NAME']
STAGE = 'guard'
RESULTS: dict[str, bool] = {}


def check(value):
    if not value:
        raise AssertionError(STAGE)


def native_click(driver, element):
    from selenium.webdriver.support.ui import WebDriverWait
    driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", element)
    WebDriverWait(driver, 30).until(lambda d: d.execute_script('''
        const e=arguments[0],r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;
        return !e.disabled&&r.width>0&&r.height>0&&x>=0&&x<innerWidth&&y>=0&&y<innerHeight&&e.contains(document.elementFromPoint(x,y));
    ''', element))
    element.click()


def native(payload):
    result = subprocess.run(['docker', 'compose', '-f', 'compose.yaml', '-f', 'tests/procurement/ci.compose.yaml', '-p', PROJECT,
                             'exec', '-T', '--user', 'www-data', 'prestashop', 'php', '/tmp/ordenowa-procurement-ci/accounts_native.php'],
                            input=json.dumps(payload), text=True, capture_output=True, timeout=45)
    check(result.returncode == 0)
    return json.loads(result.stdout)


def main():
    global STAGE
    check(os.environ.get('CI') == 'true' and os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('KURANEA_ISOLATED_CI') == '1')
    check(re.fullmatch(r'[0-9]+-[0-9]+', RUN) and PROJECT == 'ordenowa-procurement-ci-' + RUN)
    parsed = urlparse(BASE)
    check(parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost') and parsed.port == 18081)
    identity = json.loads(Path(os.environ['PROCUREMENT_IDENTITY_FILE']).read_text())
    check(identity['run'] == RUN)
    # Import only reusable account controls and reset/MIME predicates, never their legacy retail runners.
    os.environ.setdefault('MAILPIT_API_URL', 'http://127.0.0.1:18025')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e2e'))
    import verify_customer_account_browser as account
    import verify_ci_reset_email_locale as reset
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    account.BASE = BASE
    account.MAILPIT_API = 'http://127.0.0.1:18025'
    routes = native({'action': 'routes'})['routes']
    options = Options()
    for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,1000'):
        options.add_argument(flag)
    if os.environ.get('CHROME_BIN'):
        options.binary_location = os.environ['CHROME_BIN']
    for locale in ('ja', 'en', 'ko'):
        driver = None
        email = 'ordenowa-procurement-account-' + RUN + '-' + locale + '-' + secrets.token_hex(4) + '@example.invalid'
        password = 'Ci!7aA-' + secrets.token_hex(16)
        next_password = 'Reset!8bB-' + secrets.token_hex(16)
        try:
            driver_path = shutil.which('chromedriver')
            driver = webdriver.Chrome(options=options, service=Service(driver_path)) if driver_path else webdriver.Chrome(options=options)
            driver.set_page_load_timeout(45)
            driver.execute_cdp_cmd('Network.setBypassServiceWorker', {'bypass': True})
            driver.execute_cdp_cmd('Network.setCacheDisabled', {'cacheDisabled': True})
            route = routes[locale]
            for url in route.values():
                check(reset.same_origin(url, BASE))
            STAGE = 'signup_' + locale
            driver.get(route['registration'])
            form = account.visible(driver, '#customer-form')
            account.prepare_required_registration_fields(driver, form, email, password, {})
            check(not form.find_elements(By.CSS_SELECTOR, '[name=address1],[name=postcode],[name=city]'))
            native_click(driver, form.find_element(By.CSS_SELECTOR, 'button[type=submit]'))
            account.wait_for_registration_success(driver)
            current = native({'action': 'inspect', 'email': email})
            check(current['count'] == 1 and current['address_count'] == 0)
            RESULTS['signup_without_address_' + locale] = True
            STAGE = 'logout_login_' + locale
            driver.get(route['my-account'])
            native_click(driver, account.visible_signout_link(driver))
            driver.get(route['authentication'])
            account.visible(driver, '#login-form')
            account.submit_login(driver, email, password)
            driver.get(route['identity'])
            check(account.visible(driver, '#customer-form input[name=email]').get_attribute('value') == email)
            driver.get(route['my-account'])
            native_click(driver, account.visible_signout_link(driver))
            RESULTS['logout_login_' + locale] = True
            STAGE = 'duplicate_email_' + locale
            driver.get(route['registration'])
            form = account.visible(driver, '#customer-form')
            account.prepare_required_registration_fields(driver, form, email, password, {})
            native_click(driver, form.find_element(By.CSS_SELECTOR, 'button[type=submit]'))
            account.assert_duplicate_email_rejected(driver)
            check(native({'action': 'inspect', 'email': email})['count'] == 1)
            RESULTS['duplicate_email_denied_' + locale] = True
            STAGE = 'reset_request_' + locale
            driver.get(route['password'])
            account.visible(driver, 'input[name=email]').send_keys(email)
            native_click(driver, account.visible(driver, '#send-reset-link,form.forgotten-password button[type=submit]'))
            account.visible(driver, '.alert-success, .alert.alert-success')
            STAGE = 'reset_mime_' + locale
            reset_path = urlparse(route['password']).path
            _, message = account.reset_link_for(email, reset_path, timeout_seconds=60)
            raw_parts = reset.read_raw_mime_parts(account.MAILPIT_API, message)
            reset_url = reset.assert_message(message, locale, BASE, reset_path,
                {'raw_password': password, 'password_hash': current['password_hash'], 'customer_secure_key': current['secure_key']}, raw_parts)
            STAGE = 'reset_password_' + locale
            driver.get(reset_url)
            reset.assert_reset_page(driver, locale, BASE, reset_path)
            account.visible(driver, 'input[name=passwd]').send_keys(next_password)
            account.visible(driver, 'input[name=confirmation]').send_keys(next_password)
            native_click(driver, account.visible(driver, 'button[name=submitChangePassword],form button[type=submit]'))
            WebDriverWait(driver, 30).until(lambda d: not d.find_elements(By.CSS_SELECTOR, 'input[name=confirmation]'))
            updated = native({'action': 'inspect', 'email': email})
            check(updated['password_hash'] != current['password_hash'])
            driver.delete_all_cookies()
            driver.get(route['authentication'])
            account.assert_login_rejected(driver, email, password)
            driver.get(route['authentication'])
            account.submit_login(driver, email, next_password)
            driver.get(route['identity'])
            check(account.visible(driver, '#customer-form input[name=email]').get_attribute('value') == email)
            check(native({'action': 'inspect', 'email': email})['address_count'] == 0)
            RESULTS['reset_mime_and_new_login_' + locale] = True
        finally:
            if driver is not None:
                driver.quit()
    STAGE = 'complete'
    Path(os.environ['QA_ARTIFACT_DIR'], 'accounts-outcome.json').write_text(json.dumps({'passed': True, 'checks': RESULTS}, sort_keys=True) + '\n')
    print('PASS procurement native signup, duplicate email, logout/login and JA EN KO reset MIME/password acceptance')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Raw exceptions can include form values, reset links or captured MIME.
        print('FAIL procurement accounts stage=' + STAGE + ' type=' + type(error).__name__, file=sys.stderr)
        sites = [frame for frame in traceback.extract_tb(error.__traceback__) if Path(frame.filename).name == 'accounts_browser.py']
        if sites:
            print('FAIL procurement accounts source=accounts_browser.py:' + str(sites[-1].lineno), file=sys.stderr)
        Path(os.environ['QA_ARTIFACT_DIR'], 'accounts-outcome.json').write_text(json.dumps({'passed':False,'checks':RESULTS,'failed_stage':STAGE},sort_keys=True)+'\n')
        sys.exit(1)
