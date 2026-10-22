#!/usr/bin/env python3
"""Real Chromium checks in a disposable PrestaShop CI shop.

This is not a paid checkout E2E: commerce remains disabled until real seller
authorization. Order persistence is verified separately via unpaid native
PaymentModule in verify_native_order_persistence.php.
"""
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
PRODUCT_ID = int(os.environ["CI_TEST_PRODUCT_ID"])
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
DEST.mkdir(parents=True, exist_ok=True)

def assert_true(value, message):
    if not value:
        raise AssertionError(message)

def visit(browser, path):
    browser.get(f"{BASE}{path}")
    WebDriverWait(browser, 40).until(
        lambda b: b.execute_script("return document.readyState") == "complete"
    )
    return browser

def run_viewport(width, height, label):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=ja-JP")
    driver = webdriver.Chrome(options=options)
    try:
        driver.set_window_size(width, height)
        visit(driver, "/")
        assert_true("ORDENOWA" in driver.page_source.upper(), "Shopfront is missing ORDENOWA text brand.")
        driver.save_screenshot(str(DEST / f"{label}-home.png"))

        visit(driver, "/index.php?" + urlencode({
            "controller": "product", "id_product": PRODUCT_ID
        }))
        WebDriverWait(driver, 25).until(lambda b: "[CI ONLY]" in b.find_element(By.TAG_NAME, "body").text)
        assert_true("404" not in driver.title, "CI product detail page did not render.")
        assert_true("JPY" in driver.page_source or "¥" in driver.page_source,
                    "JPY product price was not rendered on the product page.")
        driver.save_screenshot(str(DEST / f"{label}-product-detail.png"))
        buttons = driver.find_elements(By.CSS_SELECTOR, "button[data-button-action='add-to-cart'], .add-to-cart")
        assert_true(bool(buttons), "No add-to-cart control on active synthetic product.")
        button = next((b for b in buttons if b.is_displayed() and b.is_enabled()), None)
        assert_true(button is not None, "All add-to-cart controls are inactive.")
        # PrestaShop mobile CSS may use smooth scrolling and a fixed bottom
        # navigation. Wait for scrolling to settle before using a real pointer
        # click; never bypass a genuine overlap with a JavaScript click.
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior:'instant', block:'center', inline:'nearest'});",
            button,
        )
        def button_center_accessible(browser):
            return browser.execute_script(
                """
                const el = arguments[0], box = el.getBoundingClientRect();
                const x = box.left + box.width / 2, y = box.top + box.height / 2;
                if (x < 0 || x >= innerWidth || y < 70 || y >= innerHeight - 90) {
                    return false;
                }
                const target = document.elementFromPoint(x, y);
                return target === el || el.contains(target);
                """,
                button,
            )

        try:
            WebDriverWait(driver, 15, poll_frequency=0.25).until(button_center_accessible)
            button.click()
        except Exception:
            driver.save_screenshot(str(DEST / f"{label}-add-to-cart-click-failure.png"))
            details = driver.execute_script(
                """
                const el = arguments[0], b = el.getBoundingClientRect();
                const x = b.left + b.width / 2, y = b.top + b.height / 2;
                const blocker = document.elementFromPoint(x, Math.min(innerHeight - 1, Math.max(0, y)));
                return {box:{x:b.x,y:b.y,width:b.width,height:b.height},
                        viewport:{width:innerWidth,height:innerHeight},
                        scrollY,scrollHeight:document.documentElement.scrollHeight,
                        hitTag:blocker && blocker.tagName,
                        hitClass:blocker && String(blocker.className).slice(0,120)};
                """,
                button,
            )
            print(f"Browser add-to-cart pointer click failed on {label}: {details}", file=sys.stderr)
            raise
        time.sleep(2)
        visit(driver, "/index.php?controller=cart&action=show")
        cart_product_ids = [
            item.get_attribute("data-id-product")
            for item in driver.find_elements(
                By.CSS_SELECTOR,
                '.cart__item [data-link-action="delete-from-cart"][data-id-product]',
            )
        ]
        assert_true(
            cart_product_ids == [str(PRODUCT_ID)],
            "Browser cart does not contain exactly the active CI-only test product.",
        )
        assert_true(
            "[CI ONLY]" in driver.find_element(By.TAG_NAME, "body").text,
            "Browser cart does not contain the CI-only test product.",
        )
        driver.save_screenshot(str(DEST / f"{label}-cart.png"))

        visit(driver, "/index.php?controller=order")
        assert_true(not re.search(r"(order|checkout)", urlparse(driver.current_url).path.lower())
                    and "controller=order" not in urlparse(driver.current_url).query.lower(),
                    "Unauthorized live checkout route did not redirect.")
        assert_true(not driver.find_elements(By.CSS_SELECTOR, ".payment-option, #payment-confirmation"),
                    "Payment controls are publicly accessible before seller authorization.")
        driver.save_screenshot(str(DEST / f"{label}-blocked-checkout.png"))

        overflow = driver.execute_script(
            "return document.documentElement.scrollWidth > window.innerWidth + 2"
        )
        assert_true(not overflow, f"Horizontal overflow at {width}px viewport.")
        print(f"PASS: {label} Chromium home, product, cart, sale-gate and responsive assertions")
    except Exception as error:
        try:
            driver.save_screenshot(str(DEST / f"{label}-failure.png"))
        except Exception:
            pass
        print(f"FAIL: {label} storefront browser QA ({type(error).__name__})", file=sys.stderr)
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    for width, height, label in ((1440, 960, "desktop"), (390, 844, "mobile")):
        run_viewport(width, height, label)
