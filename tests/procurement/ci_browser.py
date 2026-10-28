#!/usr/bin/env python3
"""Native-session acceptance. Artifacts contain fixed stage labels/booleans only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import subprocess
import shutil
import traceback
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse, urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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


def make_browser(options):
    path = shutil.which('chromedriver')
    return webdriver.Chrome(options=options, service=Service(path)) if path else webdriver.Chrome(options=options)


def check(value: bool) -> None:
    if not value:
        raise AssertionError(STAGE)


def visible(driver, selector):
    return WebDriverWait(driver, 30).until(lambda d: next((x for x in d.find_elements(By.CSS_SELECTOR, selector) if x.is_displayed()), False))


def with_query(url, **values):
    parsed = urlparse(url)
    fields = [(key, value) for key, value in parse_qsl(parsed.query) if key not in values]
    return urlunparse(parsed._replace(query=urlencode(fields + list(values.items()))))


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


def native_page_url(controller, locale='ja'):
    # Friendly native account routes are authoritative. Appending id_lang to
    # the legacy raw auth query can produce a native 404 on multilingual shops.
    route = IDENTITY['routes'][locale][controller]
    target, base = urlparse(route), urlparse(BASE)
    check(target.scheme == base.scheme and target.netloc == base.netloc)
    check(not target.username and not target.password and target.path.startswith('/'))
    return route


def login_customer(driver, side):
    driver.get(native_page_url('authentication'))
    visible(driver, 'input[name="email"]').send_keys(IDENTITY['customers'][side]['email'])
    visible(driver, 'input[name="password"],input[name="passwd"]').send_keys(IDENTITY['password'])
    visible(driver, 'button[data-link-action="sign-in"],button[name="submitLogin"]').click()
    WebDriverWait(driver, 30).until(lambda d: not d.find_elements(By.CSS_SELECTOR, 'form#login-form'))
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
    token_form = visible(driver, '.ordenowa-procurement-admin form[method="get"]')
    token = token_form.find_element(By.CSS_SELECTOR, 'input[name="token"]').get_attribute('value')
    check(bool(token))
    response = fetch(driver, driver.current_url, dict(fields, procurement_action=action, token=token))
    check(response['status'] == 403 and response['private'])


def native_identity(driver, side):
    driver.get(native_page_url('identity'))
    email = visible(driver, 'form input[name="email"]').get_attribute('value')
    check(email == IDENTITY['customers'][side]['email'])
    check(not driver.find_elements(By.CSS_SELECTOR, '#login-form'))


def native_admin_form_url(action, controller, form_token):
    check(controller in ('AdminOrdenowaProcurement', 'AdminOrdenowaProcurementReviews',
                         'AdminOrdenowaProcurementPoints', 'AdminOrdenowaProcurementAudit', 'AdminOrdenowaProcurementPolicies'))
    target, base = urlparse(action), urlparse(BASE)
    fields = parse_qs(target.query)
    check(target.scheme == base.scheme and target.netloc == base.netloc and not target.username and not target.password)
    check(target.path in ('/admin-kuranea/', '/admin-kuranea/index.php') and fields.get('controller') == [controller])
    check(bool(form_token) and len(fields.get('token', [])) == 1 and bool(fields['token'][0]))
    return action


def admin_page(driver, controller):
    # Native menu links carry the correct per-controller native CSRF token.
    links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller=' + controller + '"]')
    if links:
        href = links[0].get_attribute('href')
    else:
        # Native role-limited navigation may omit sibling links. Exercise the
        # route using this employee's own native authenticated masked token;
        # the app must still enforce READ and action ACL independently.
        current = urlparse(driver.current_url)
        query = parse_qs(current.query)
        check(bool(query.get('token', [''])[0]))
        fields = [(key, value) for key, value in parse_qsl(current.query) if key != 'controller']
        href = urlunparse(current._replace(query=urlencode(fields + [('controller', controller)])))
    check(urlparse(href).netloc == urlparse(BASE).netloc)
    driver.get(href)
    visible(driver, '.ordenowa-procurement-admin')
    if not links:
        # The copied source-controller URL token is not a target-controller
        # token. Use the authorized target page's untouched native form action.
        selector = '[data-testid="procurement-policy-settings"]' if controller == 'AdminOrdenowaProcurementPolicies' else '.ordenowa-procurement-admin form[method="get"]'
        target_form = visible(driver, selector)
        own_token = target_form.find_element(By.CSS_SELECTOR, 'input[name="token"]').get_attribute('value')
        canonical = native_admin_form_url(target_form.get_attribute('action'), controller, own_token)
        driver.get(canonical)
        visible(driver, selector)
    response = fetch(driver, driver.current_url)
    check(response['status'] == 200 and response['private'])


def wait_admin_submission(driver, form):
    # The previous document may still report "complete" while its server POST
    # starts. Observe its replacement before reading success or closing it.
    WebDriverWait(driver, 30).until(lambda d: EC.staleness_of(form)(d)
                                  and d.execute_script('return document.readyState') == 'complete')


def admin_form(driver, action, fields):
    form = visible(driver, '[data-testid="procurement-' + action + '"]')
    check(form.tag_name == 'form')
    for name, value in fields.items():
        fill(form, name, value)
    form.find_element(By.CSS_SELECTOR, '[name="procurement_action"][value="' + action + '"]').click()
    wait_admin_submission(driver, form)
    check(not driver.find_elements(By.CSS_SELECTOR, '.alert-danger'))


def viewport_ready(driver, width):
    state = driver.execute_script("""
        // Resolve responsive styles before observing their native transitions.
        void document.documentElement.offsetHeight;
        return {width: innerWidth, transitions: document.getAnimations()
            .filter(animation => typeof animation.transitionProperty === 'string')
            .map(animation => ({pending: animation.pending, playState: animation.playState}))};
    """)
    return state['width'] == width and all(not animation['pending'] and animation['playState'] in ('finished', 'idle')
                                           for animation in state['transitions'])


def viewport(driver, width):
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': width < 768,
    })
    # Hummingbird transitions anchor font sizes/padding after responsive changes.
    # Observe completion within the original budget before measuring/capturing.
    WebDriverWait(driver, 30).until(lambda d: viewport_ready(d, width))
    check(driver.execute_script('return window.innerWidth') == width)


def safe_capture(driver, name):
    original_body = driver.execute_script('return document.body.innerHTML')
    # No live HTML, input values, customer identities, point values, URLs,
    # cookies, browser logs or unredacted screenshots leave this process.
    driver.execute_script("""
        for (const e of document.querySelectorAll('input,textarea,select')) {e.value='';e.disabled=true;}
        for (const e of document.querySelectorAll('img')) {if(!e.closest('[data-testid=product-photo]')){e.removeAttribute('src');e.removeAttribute('srcset');}e.removeAttribute('alt');}
        for (const e of document.querySelectorAll('a')) {e.removeAttribute('href');}
        const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
        let n;while(n=w.nextNode()){if(n.textContent.trim())n.textContent='[synthetic acceptance]';}
        for(const e of document.querySelectorAll('[title],[aria-label]')) {e.removeAttribute('title');e.removeAttribute('aria-label');}
    """)
    driver.save_screenshot(str(DEST / (name + '.png')))
    # Restore in-memory DOM before the next viewport assertion. Broad redaction
    # changes text widths and must not become a synthetic overflow defect.
    driver.execute_script('document.body.innerHTML=arguments[0]', original_body)


def capture_static(driver, artifact_prefix='confirmation', extra_labels=(), widths=(320, 390, 1440), artifact_locale=None, scroll_selector=None, required_visible=()):
    command = ['docker', 'compose', '-f', 'compose.yaml', '-f', 'tests/procurement/ci.compose.yaml', '-p', os.environ['CI_COMPOSE_PROJECT_NAME'],
               'exec', '-T', '-u', 'www-data', 'prestashop', 'php', '/tmp/ordenowa-procurement-ci/ci_labels.php']
    result = subprocess.run(command, capture_output=True, timeout=60)
    check(result.returncode == 0)
    labels = json.loads(result.stdout) + list(extra_labels)
    original_body = driver.execute_script('return document.body.innerHTML')
    for width in widths:
        viewport(driver, width)
        check(driver.execute_script('return document.documentElement.scrollWidth<=innerWidth+1'))
        driver.execute_script("scrollTo({top:0,behavior:'instant'})")
        driver.execute_async_script('const done=arguments[0];document.fonts.ready.then(()=>requestAnimationFrame(()=>requestAnimationFrame(done)));')
        if scroll_selector:
            check(driver.execute_async_script("""
                const [selector,done]=arguments;const target=document.querySelector(selector);
                if(!target){done(false);return;}
                target.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});
                requestAnimationFrame(()=>requestAnimationFrame(()=>done(true)));
            """, scroll_selector))
        if required_visible:
            target_state = driver.execute_script("""
                return arguments[0].every(selector=>{
                    const nodes=[...document.querySelectorAll(selector)];
                    return nodes.length>0&&nodes.every(node=>{
                        const r=node.getBoundingClientRect(),s=getComputedStyle(node);
                        const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
                        return r.width>0&&r.height>0&&r.left>=-1&&r.top>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight
                            &&s.display!=='none'&&s.visibility==='visible'&&+s.opacity>0
                            &&!!hit&&(hit===node||node.contains(hit));
                    });
                });
            """, list(required_visible))
            check(target_state)
        # Proven native v5 pixel overlay: does not replace text nodes, change
        # form values/enabled state, or modify source geometry.
        geometry = driver.execute_script("\nconst old=document.getElementById('owa-safe-pixel-mask');if(old)old.remove();\nconst before=[document.documentElement.scrollWidth,document.documentElement.scrollHeight];\nconst controls=[...document.querySelectorAll('input,textarea,button,select')].map(e=>e.disabled);\nconst allowed=arguments[0].filter(x=>x.trim().length>=2).sort((a,b)=>b.length-a.length);\nfor(const e of document.querySelectorAll('input:not([type=hidden]),textarea')){e.style.color='transparent';e.style.caretColor='transparent';e.style.webkitTextFillColor='transparent';}\nfor(const e of document.querySelectorAll('img')){const keep=e.matches('.ow-product-media img,.ow-gallery-images img,.kuranea-brand__image')&&e.complete&&e.naturalWidth>0;if(!keep)e.style.visibility='hidden';}\nfor(const e of document.querySelectorAll('[title]'))e.removeAttribute('title');\nconst masks=[];const walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;\nwhile(node=walk.nextNode()){\n if(!node.textContent.trim()||['SCRIPT','STYLE','OPTION'].includes(node.parentElement?.tagName)||node.parentElement?.closest('#owa-safe-pixel-mask'))continue;\n const text=node.textContent;let pos=0;\n while(pos<text.length){let at=text.length,label='';for(const value of allowed){const found=text.indexOf(value,pos);if(found>=0&&(found<at||(found===at&&value.length>label.length))){at=found;label=value;}}\n  if(at>pos&&text.slice(pos,at).trim()){const range=document.createRange();range.setStart(node,pos);range.setEnd(node,at);for(const rect of range.getClientRects())if(rect.width&&rect.height)masks.push({x:rect.left,y:rect.top,w:rect.width,h:rect.height});range.detach();}\n  pos=label?at+label.length:text.length;\n }\n}\nconst canvas=document.createElement('canvas');canvas.id='owa-safe-pixel-mask';canvas.width=innerWidth;canvas.height=innerHeight;canvas.setAttribute('aria-hidden','true');canvas.style.cssText='position:fixed!important;inset:0!important;width:'+innerWidth+'px!important;height:'+innerHeight+'px!important;pointer-events:none!important;z-index:2147483647!important;margin:0!important;padding:0!important;border:0!important';\nconst ctx=canvas.getContext('2d');ctx.fillStyle='#dce3eb';for(const r of masks)ctx.fillRect(Math.floor(r.x)-1,Math.floor(r.y)-1,Math.ceil(r.w)+2,Math.ceil(r.h)+2);document.body.appendChild(canvas);\nreturn {before,after:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],scroll:scrollY,controls:controls.every((state,index)=>state===[...document.querySelectorAll('input,textarea,button,select')][index].disabled),mask_rectangles:masks.length};\n", labels)
        check(abs(geometry['before'][0]-geometry['after'][0])<=1 and abs(geometry['before'][1]-geometry['after'][1])<=1 and geometry['controls'])
        path = DEST / (artifact_prefix + '-redacted-static-labels-' + ((artifact_locale + '-') if artifact_locale else '') + str(width) + '.png')
        driver.save_screenshot(str(path))
        stable = driver.execute_script('return scrollY') == geometry['scroll']
        if not stable:
            path.unlink(missing_ok=True)
        check(stable)
        # Native tokens and original values never leave RAM or enter pixels.
        driver.execute_script('document.body.innerHTML=arguments[0]', original_body)
    viewport(driver, 1440)



def fetch(driver, url, data=None):
    return driver.execute_async_script("""
        const [url,data,done]=arguments;
        fetch(url,{method:data?'POST':'GET',credentials:'same-origin',
          headers:data?{'Content-Type':'application/x-www-form-urlencoded'}:{},
          body:data?new URLSearchParams(data).toString():undefined})
        .then(async r=>{const t=await r.text();const doc=new DOMParser().parseFromString(t,'text/html');done({status:r.status,
          redirected:r.redirected,
          workspaceDestination:new URL(r.url).origin===location.origin&&new URL(r.url).pathname.endsWith('/module/ordenowaprocurement/workspace'),
          workspaceContent:!!doc.querySelector('[data-testid=workspace]'),
          retailContent:!!doc.querySelector('#checkout,#checkout-process,[id^=checkout-],#cart,.payment-options'),
          ownerContent:!!doc.querySelector('[data-testid=assignment-detail],[data-testid=request-detail],[data-testid=support-thread]'),
          loginForm:!!doc.querySelector('#login-form'),
          private:r.headers.get('cache-control')?.includes('no-store')||false,
          noindex:(r.headers.get('x-robots-tag')||'').includes('noindex')||/name=["']robots["'][^>]+noindex/.test(t)});})
        .catch(()=>done({status:0}));
    """, url, data)


def closed_checkout_redirect(driver, url):
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    cookie = '; '.join(item['name'] + '=' + item['value'] for item in driver.get_cookies())
    # Native cookies and redirects stay in RAM; only fixed booleans leave.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(Request(url, headers={'Cookie': cookie}), timeout=20):
            check(False)
    except HTTPError as response:
        check(response.code in (301, 302, 303, 307, 308))
        target = urlparse(urljoin(url, response.headers.get('Location', '')))
        base = urlparse(BASE)
        check((target.scheme, target.netloc) == (base.scheme, base.netloc) and not target.fragment)
        check(target.path in ('/', '/index.php', '/en/', '/ko/'))
        query = parse_qs(target.query)
        check(set(query) <= {'controller', 'id_lang', 'isolang'} and query.get('controller', ['index']) == ['index'])
    result = fetch(driver, url)
    check(result['status'] == 200 and result['redirected'] and result['workspaceDestination'] and result['workspaceContent'])
    check(result['private'] and result['noindex'] and not result['retailContent'] and not result['loginForm'])


def retail_state(mode):
    command = ['docker', 'compose', '-f', 'compose.yaml', '-f', 'tests/procurement/ci.compose.yaml', '-p', os.environ['CI_COMPOSE_PROJECT_NAME'],
               'exec', '-T', '-u', 'www-data', 'prestashop', 'php', '/tmp/ordenowa-procurement-ci/ci_retail_boundary.php', mode]
    result = subprocess.run(command, capture_output=True, timeout=60)
    check(result.returncode == 0)


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
        admin, a, b = (make_browser(options) for _ in range(3))
        browsers.extend((admin, a, b))
        STAGE = 'admin_native_login'
        login_admin(admin, os.environ['ADMIN_MAIL'], os.environ['ADMIN_PASSWD'])
        STAGE = 'native_policy_save_fresh_readback'
        admin_page(admin, 'AdminOrdenowaProcurementPolicies')
        policy_form = visible(admin, '[data-testid="procurement-policy-settings"]')
        check(policy_form.find_element(By.CSS_SELECTOR, '[name="version"]').get_attribute('value') == '0')
        policy_values = {'operator_name': 'SYNTHETIC CI operator', 'support_email': 'support@example.invalid'}
        policy_copy = {
            'ja': '隔離 CI 用の合成規約です。実運用の承認を示しません。',
            'en': 'Synthetic isolated CI policy; operating approval requires real inputs.',
            'ko': '격리 CI 합성 정책입니다. 실제 운영 정보는 별도로 확인해야 합니다.',
        }
        for section in ('terms', 'privacy', 'points'):
            for locale, text in policy_copy.items():
                policy_values[section + '_' + locale] = section + ': ' + text + '<script data-ci-policy>window.CI_POLICY_EXECUTED=1</script>'
        for name, value in policy_values.items():
            fill(policy_form, name, value)
        STAGE = 'native_policy_invalid_csrf_no_write'
        original_action = policy_form.get_attribute('action')
        wrong_fields = {element.get_attribute('name'): element.get_attribute('value') for element in policy_form.find_elements(By.CSS_SELECTOR, 'input[name],textarea[name]')}
        wrong_fields.update(save_policy='1', token='ci-invalid-native-token')
        parsed_action = urlparse(original_action)
        wrong_query = urlencode([(key, 'ci-invalid-native-token' if key in ('token', '_token') else value) for key, value in parse_qsl(parsed_action.query)])
        invalid_action = urlunparse(parsed_action._replace(query=wrong_query))
        for target in (original_action, invalid_action):
            response = fetch(admin, target, wrong_fields)
            check(response['status'] == 403)
            admin.get(original_action)
            policy_form = visible(admin, '[data-testid="procurement-policy-settings"]')
            check(policy_form.find_element(By.CSS_SELECTOR, '[name="version"]').get_attribute('value') == '0')
        RESULTS[STAGE] = True
        STAGE = 'native_policy_save_fresh_readback'
        for name, value in policy_values.items():
            fill(policy_form, name, value)
        policy_form.find_element(By.CSS_SELECTOR, 'button[name="save_policy"]').click()
        wait_admin_submission(admin, policy_form)
        check(not admin.find_elements(By.CSS_SELECTOR, '.alert-danger'))
        admin.quit()
        browsers.remove(admin)
        admin = make_browser(options)
        browsers.append(admin)
        login_admin(admin, os.environ['ADMIN_MAIL'], os.environ['ADMIN_PASSWD'])
        admin_page(admin, 'AdminOrdenowaProcurementPolicies')
        policy_form = visible(admin, '[data-testid="procurement-policy-settings"]')
        check(policy_form.find_element(By.CSS_SELECTOR, '[name="version"]').get_attribute('value') == '1')
        for name, value in policy_values.items():
            check(policy_form.find_element(By.CSS_SELECTOR, '[name="' + name + '"]').get_attribute('value') == value)
        for locale, language_id in IDENTITY['languages'].items():
            for section in ('terms', 'privacy', 'points'):
                public_url = with_query(IDENTITY['routes'][locale]['policy'], section=section)
                a.get(public_url)
                response = fetch(a, public_url)
                check(response['status'] == 200)
                public = visible(a, '[data-testid="procurement-public-policy"]')
                check(policy_copy[locale] in public.text and not public.find_elements(By.CSS_SELECTOR, 'script[data-ci-policy]'))
                check(a.execute_script('return window.CI_POLICY_EXECUTED === undefined'))
        RESULTS[STAGE] = True
        STAGE = 'admin_assign_product'
        admin_page(admin, 'AdminOrdenowaProcurement')
        admin_form(admin, 'assign', {'id_customer': IDENTITY['customers']['a']['id'], 'id_product': IDENTITY['product_id'], 'id_product_attribute': IDENTITY.get('product_attribute_id', 0),
                                    'default_quantity': 1, 'max_quantity': 3, 'instructions': 'Synthetic acceptance instruction'})
        RESULTS[STAGE] = True
        STAGE = 'reviewed_category_navigation_filters'
        login_customer(a, 'a')
        native_identity(a, 'a')
        category_path = IDENTITY['category_path']
        check(len(category_path) == 2 and category_path[1]['id_parent'] == category_path[0]['id_category'])
        category_labels = [name for node in category_path for name in node['names'].values()]
        for locale in ('ja', 'en', 'ko'):
            route = IDENTITY['routes'][locale]['workspace']
            a.get(route)
            nav = visible(a, '[data-testid="category-navigation"]')
            parent = nav.find_element(By.XPATH, './/li[a[text()=' + json.dumps(category_path[0]['names'][locale],ensure_ascii=False) + ']]')
            leaf = parent.find_element(By.XPATH, './ul/li/a[text()=' + json.dumps(category_path[1]['names'][locale],ensure_ascii=False) + ']')
            leaf_url = leaf.get_attribute('href')
            check(parse_qs(urlparse(leaf_url).query).get('category') == [str(category_path[1]['id_category'])])
            # Only explicitly reviewed synthetic category names join the static
            # copy allowlist. Preserve real controls/photos and mask other data.
            capture_static(a, 'categories-target', extra_labels=category_labels, artifact_locale=locale,
                           scroll_selector='[data-testid=category-navigation]',
                           required_visible=('[data-testid=category-navigation] > a', '[data-testid=category-navigation] li > a'))
            a.get(leaf_url)
            check(len(a.find_elements(By.CSS_SELECTOR, '[data-testid="assignment-card"]')) == 1)
            a.get(with_query(route, category=2147483647))
            visible(a, '[data-testid="workspace"]')
            check(not a.find_elements(By.CSS_SELECTOR, '[data-testid="assignment-card"]'))
        RESULTS[STAGE] = True
        STAGE = 'customer_a_confirm_submit'
        workspace(a)
        card = visible(a, '[data-testid="assignment-card"]')
        assignment_id = int(card.get_attribute('data-assignment-id'))
        workspace(a, '&view=assignment&id_assignment=' + str(assignment_id))
        detail = visible(a, '[data-testid="assignment-detail"]')
        photos = detail.find_elements(By.CSS_SELECTOR, '[data-testid="product-photo"] img')
        check(len(photos) >= 2)
        check(len({photo.get_attribute('src') for photo in photos}) == len(photos))
        WebDriverWait(a, 30).until(lambda d: all(d.execute_script('return arguments[0].complete && arguments[0].naturalWidth > 0', photo) for photo in photos))
        for width, color in ((1440, 'light'), (390, 'dark')):
            viewport(a, width)
            a.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': color}]})
            workspace(a, '&view=assignment&id_assignment=' + str(assignment_id))
            photos = a.find_elements(By.CSS_SELECTOR, '[data-testid="product-photo"] img')
            check(len(photos) >= 2)
            WebDriverWait(a, 30).until(lambda d: all(d.execute_script('return arguments[0].complete && arguments[0].naturalWidth > 0', photo) for photo in photos))
            capture_static(a, 'gallery-' + color + '-target', extra_labels=category_labels, widths=(width,),
                           scroll_selector='[data-testid=product-gallery]',
                           required_visible=('[data-testid=product-gallery] summary', '.ow-gallery-images [data-testid=product-photo]'))
        viewport(a, 1440)
        a.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'light'}]})
        for locale in ('ja', 'en', 'ko'):
            a.get(with_query(IDENTITY['routes'][locale]['workspace'], view='assignment', id_assignment=assignment_id))
            detail = visible(a, '[data-testid="assignment-detail"]')
            check(a.find_element(By.TAG_NAME, 'html').get_attribute('lang').startswith(locale))
            fill(detail, 'quantity', 2)
            visible(a, '[data-testid="review-request"]').send_keys(Keys.ENTER)
            confirmation = visible(a, '[data-testid="confirm-request"]')
            check(a.find_element(By.TAG_NAME, 'html').get_attribute('lang').startswith(locale))
            version = confirmation.find_element(By.CSS_SELECTOR, '[name="version"]').get_attribute('value')
            capture_static(a, 'confirmation-' + locale + '-target', scroll_selector='.ow-request-form .ow-actions',
                           required_visible=('.ow-request-form [data-testid=submit-request]', '.ow-request-form .ow-actions > a', '[data-testid=confirmed-quantity]'))
        # The three confirmations only render a preview. Submit exactly once.
        visible(a, '[data-testid="submit-request"]').send_keys(Keys.ENTER)
        visible(a, '[data-testid="request-detail"]')
        workspace(a, '&view=requests')
        request_id = int(visible(a, '[data-testid="request-row"]').get_attribute('data-request-id'))
        RESULTS[STAGE] = True
        STAGE = 'customer_b_owner_denials'
        login_customer(b, 'b')
        native_identity(b, 'b')
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
            check(response['status'] == 404 and response['private'] and not response['ownerContent'] and not response['loginForm'])
            native_identity(b, 'b')
        response = fetch(b, endpoint, {'action': 'submit', 'token': token, 'id_assignment': assignment_id, 'version': version,
                                       'quantity': 2, 'idempotency_key': 'b' * 64})
        check(response['status'] == 404 and response['private'] and not response['ownerContent'] and not response['loginForm'])
        native_identity(b, 'b')
        response = fetch(b, endpoint + '&view=points&id_customer=' + str(IDENTITY['customers']['a']['id']))
        check(response['status'] == 404 and response['private'] and not response['ownerContent'] and not response['loginForm'])
        native_identity(b, 'b')
        workspace(b, '&view=points')
        check(visible(b, '[data-testid="points-balance"]').get_attribute('data-balance') == '0')
        check(not b.find_elements(By.CSS_SELECTOR, '[data-testid="ledger-entry"]'))
        RESULTS[STAGE] = True
        STAGE = 'native_readonly_review_denial'
        reader = make_browser(options)
        browsers.append(reader)
        login_admin(reader, IDENTITY['reader']['email'], IDENTITY['password'])
        admin_page(reader, 'AdminOrdenowaProcurementPolicies')
        readonly_policy = visible(reader, '[data-testid="procurement-policy-settings"]')
        check(not readonly_policy.find_elements(By.CSS_SELECTOR, 'button[name="save_policy"]'))
        own_policy_token = readonly_policy.find_element(By.CSS_SELECTOR, '[name="token"]').get_attribute('value')
        response = fetch(reader, reader.current_url, dict(policy_values, save_policy='1', version='1', token=own_policy_token))
        check(response['status'] == 403 and response['private'])
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
        a = make_browser(options)
        browsers.append(a)
        login_customer(a, 'a')
        native_identity(a, 'a')
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
        native_identity(a, 'a')
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
        native_identity(b, 'b')
        response = fetch(b, support)
        check(response['status'] == 404 and response['private'] and not response['ownerContent'] and not response['loginForm'])
        native_identity(b, 'b')
        response = fetch(b, support, {'action': 'message', 'id_request': request_id, 'message': 'SYNTHETIC_FORBIDDEN_MESSAGE',
                                      'idempotency_key': 'f' * 64, 'token': token})
        check(response['status'] == 404 and response['private'] and not response['ownerContent'] and not response['loginForm'])
        native_identity(b, 'b')
        workspace(b, '&view=points')
        check(visible(b, '[data-testid="points-balance"]').get_attribute('data-balance') == '0')
        command = ['docker', 'compose', '-f', 'compose.yaml', '-f', 'tests/procurement/ci.compose.yaml', '-p', os.environ['CI_COMPOSE_PROJECT_NAME'],
                   'exec', '-T', '-u', 'www-data', 'prestashop', 'php', '/tmp/ordenowa-procurement-ci/ci_support.php']
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
        retail_state('snapshot')
        for controller in ('cart', 'order', 'history', 'addresses', 'address', 'order-slip', 'order-follow', 'order-detail'):
            response = fetch(a, BASE + '/index.php?controller=' + controller)
            if controller == 'order' and response['status'] == 200:
                closed_checkout_redirect(a, BASE + '/index.php?controller=order')
                native_identity(a, 'a')
            else:
                check(response['status'] in (403, 404, 410))
        retail_state('compare')
        RESULTS[STAGE] = True
        STAGE = 'responsive_keyboard_private_captures'
        for width in (320, 360, 375, 390, 430, 768, 1024, 1280, 1440, 1920):
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
        sites = [frame for frame in traceback.extract_tb(error.__traceback__) if Path(frame.filename).name == 'ci_browser.py' and frame.name == 'main']
        if sites:
            print('FAIL procurement browser source=ci_browser.py:' + str(sites[-1].lineno), file=sys.stderr)
        status = 1
    (DEST / 'browser-outcome.json').write_text(json.dumps({'passed': status == 0, 'stages': RESULTS, 'failed_stage': STAGE if status else None}) + '\n')
    sys.exit(status)
