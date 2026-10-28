#!/usr/bin/env python3
"""Two native AdminAccess requests against an employee-free disposable profile; safe aggregate artifacts only."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import parse_qs, urlparse, urlencode
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

STAGE = 'acl_isolation_guard'
RESULTS: dict[str, bool] = {}
AJAX_RESULTS: dict[str, list[dict]] = {}
BASE = os.environ['SHOP_BASE_URL'].rstrip('/')
RUN = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
PROJECT = os.environ['CI_COMPOSE_PROJECT_NAME']
COMPOSE = ['docker', 'compose', '-f', 'compose.yaml', '-f', 'tests/procurement/ci.compose.yaml', '-p', PROJECT]
DEST = Path(os.environ['QA_ARTIFACT_DIR'])


def check(value: bool) -> None:
    if not value:
        raise AssertionError(STAGE)


def native(mode: str) -> None:
    result = subprocess.run(COMPOSE + ['exec', '-T', '--user', 'www-data', 'prestashop', 'php', '/tmp/ordenowa-procurement-ci/ci_acl.php', mode], capture_output=True, text=True)
    check(result.returncode == 0)


def visible(driver, selector):
    return WebDriverWait(driver, 30).until(lambda d: next((x for x in d.find_elements(By.CSS_SELECTOR, selector) if x.is_displayed()), False))


def toggle(driver, endpoint: str, token: str, state: dict, enabled: bool, cleanup=False) -> None:
    result = driver.execute_async_script('''
      const [endpoint,token,profile,tab,enabled,cleanup,done]=arguments;
      const url=new URL(endpoint);url.searchParams.set('token',token);
      for(const [k,v]of Object.entries({ajax:'1',action:'updateAccess',submitAddAccess:'1',id_profile:String(profile),id_tab:cleanup?'-1':String(tab),perm:cleanup?'all':'view',enabled:enabled?'1':'0',addFromParent:'0'}))url.searchParams.set(k,v);
      fetch(url.href,{method:'GET',credentials:'same-origin',cache:'no-store',headers:{'X-Requested-With':'XMLHttpRequest'}})
        .then(async r=>done({status:r.status,ok:(await r.text())==='ok'})).catch(()=>done({status:0,ok:false}));
    ''', endpoint, token, state['profile_id'], state['tab_id'], enabled, cleanup)
    check(result['status'] == 200 and result['ok'])


def native_checkbox(driver, state: dict, enabled: bool) -> None:
    checkbox = visible(driver, '#table_' + str(state['profile_id']) + ' input.ajaxPower[data-classname="AdminOrdenowaProcurement"][data-type="view"]')
    check(checkbox.is_enabled() and checkbox.is_selected() != enabled)
    driver.execute_script('''
      window.__ordenowaAclResults=[];
      jQuery(document).off('ajaxComplete.ordenowaAcl').on('ajaxComplete.ordenowaAcl',(event,xhr,settings)=>{
        const data=String(settings.data||'');
        const url=new URL(settings.url,location.href);
        if(data.includes('action=updateAccess')||url.searchParams.get('action')==='updateAccess')window.__ordenowaAclResults.push({status:xhr.status,ok:xhr.responseText==='ok'});
      });
    ''')
    checkbox.click()
    try:
        results = WebDriverWait(driver, 30).until(lambda d: d.execute_script('return jQuery.active===0 && window.__ordenowaAclResults.length===arguments[0] ? window.__ordenowaAclResults : null',len(state['expected_roles'])))
    finally:
        AJAX_RESULTS['grant' if enabled else 'revoke'] = driver.execute_script('return window.__ordenowaAclResults.map(r=>({status:r.status,ok:r.ok}))')
    check(all(result['status'] == 200 and result['ok'] for result in results))
    driver.refresh()
    checkbox = visible(driver, '#table_' + str(state['profile_id']) + ' input.ajaxPower[data-classname="AdminOrdenowaProcurement"][data-type="view"]')
    check(checkbox.is_selected() == enabled)


def main() -> None:
    global STAGE
    check(BASE == 'http://localhost:18081' and os.environ.get('PS_DOMAIN') == 'localhost:18081')
    check(os.environ.get('CI') == 'true' and os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('KURANEA_ISOLATED_CI') == '1')
    check(os.environ.get('ORDENOWA_APP_MODE') == 'procurement' and bool(re.fullmatch(r'[0-9]+-[0-9]+', RUN)) and PROJECT == 'ordenowa-procurement-ci-' + RUN)
    private = Path(os.environ['PROCUREMENT_IDENTITY_FILE']).parent
    check(private.is_dir() and json.loads(Path(os.environ['PROCUREMENT_IDENTITY_FILE']).read_text())['run'] == RUN)
    acl_file = private / 'acl.json'
    STAGE = 'acl_dedicated_profile'
    native('prepare')
    copied = subprocess.run(COMPOSE + ['cp', 'prestashop:/tmp/ordenowa-procurement-ci/acl.json', str(acl_file)], capture_output=True, text=True)
    check(copied.returncode == 0)
    state = json.loads(acl_file.read_text())
    check(state['run'] == RUN and state['profile_id'] != state['actor_profile_id'])
    options = Options()
    for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--window-size=1280,960'):
        options.add_argument(flag)
    if os.environ.get('CHROME_BIN'):
        options.binary_location = os.environ['CHROME_BIN']
    driver_path = shutil.which('chromedriver')
    driver = webdriver.Chrome(options=options, service=Service(driver_path)) if driver_path else webdriver.Chrome(options=options)
    granted = False
    endpoint = token = ''
    try:
        STAGE = 'acl_native_admin_login'
        driver.get(BASE + '/admin-kuranea/')
        visible(driver, '#login_form input[name="email"],input[type="email"]').send_keys(os.environ['ADMIN_MAIL'])
        visible(driver, '#login_form input[name="passwd"],input[name="password"],input[type="password"]').send_keys(os.environ['ADMIN_PASSWD'] + Keys.ENTER)
        # The official permissions tab can be absent from the current sidebar.
        # Its authoritative native Link URL comes from the installed BO router.
        WebDriverWait(driver, 30).until(lambda d: bool(d.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminOrdenowaProcurement"]')))
        session_url = driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminOrdenowaProcurement"]')[0].get_attribute('href')
        token = parse_qs(urlparse(session_url).query).get('token', [''])[0]
        check(bool(token))
        endpoint = state['access_url']
        check(urlparse(endpoint).netloc == urlparse(BASE).netloc)
        check(parse_qs(urlparse(endpoint).query).get('controller') == ['AdminAccess'])
        endpoint += ('&' if '?' in endpoint else '?') + urlencode({'token': token, 'id_profile': state['profile_id']})
        driver.get(endpoint)
        visible(driver, '#access_form')
        check(not driver.find_elements(By.CSS_SELECTOR, '#login_form'))
        STAGE = 'acl_official_hook_native_grant'
        # An interrupted UI/readback can follow a committed native request.
        # Keep this employee-free target eligible for guarded cleanup in that case.
        granted = True
        native_checkbox(driver, state, True)
        native('grant')
        RESULTS[STAGE] = True
        STAGE = 'acl_official_hook_native_revoke'
        native_checkbox(driver, state, False)
        granted = False
        native('revoke')
        RESULTS[STAGE] = True
    finally:
        if granted and endpoint and token:
            try:
                toggle(driver, endpoint, token, state, False, cleanup=True)
            except Exception:
                pass
        driver.quit()
        acl_file.unlink(missing_ok=True)


if __name__ == '__main__':
    passed = False
    try:
        main()
        passed = True
        print('PASS native AdminAccess grant/revoke, official audit hook readback and preserved unrelated permissions')
    except Exception:
        print('FAIL native ACL browser stage=' + STAGE)
    finally:
        DEST.mkdir(parents=True, exist_ok=True)
        (DEST / 'acl-browser.json').write_text(json.dumps({'passed': passed, 'stages': RESULTS, 'native_ui_ajax': AJAX_RESULTS, 'failed_stage': None if passed else STAGE}, sort_keys=True) + '\n')
    raise SystemExit(0 if passed else 1)
