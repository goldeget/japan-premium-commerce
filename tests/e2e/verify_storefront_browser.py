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
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from storefront_product_contract import product_page_failure_reason

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

def document_response_status(browser):
    status = browser.execute_script(
        """
        const entries = performance.getEntriesByType('navigation');
        const entry = entries.length ? entries[0] : null;
        return entry && Number.isInteger(entry.responseStatus) ? entry.responseStatus : null;
        """
    )
    return status if type(status) is int and 100 <= status <= 599 else None

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
        body = driver.find_element(By.TAG_NAME, "body")
        containers = driver.find_elements(By.CSS_SELECTOR, '[data-ps-ref="product-container"]')
        headings = driver.find_elements(By.CSS_SELECTOR, "h1.product__name")
        visible_heading = next((heading for heading in headings if heading.is_displayed()), None)
        product_forms = driver.find_elements(By.CSS_SELECTOR, "form#add-to-cart-or-refresh")
        product_ids = driver.find_elements(
            By.CSS_SELECTOR, "input#product_page_product_id[name='id_product']"
        )
        product_buttons = driver.find_elements(
            By.CSS_SELECTOR, "button[data-button-action='add-to-cart'], .add-to-cart"
        )
        visible_product_button = any(button.is_displayed() for button in product_buttons)
        active_product_button = next(
            (button for button in product_buttons if button.is_displayed() and button.is_enabled()),
            None,
        )
        response_status = document_response_status(driver)
        print(
            "Storefront product document response status: "
            f"{response_status if response_status is not None else 'unknown'}"
        )
        product_failure = product_page_failure_reason(
            response_status=response_status,
            body_id=body.get_attribute("id") or "",
            not_found_visible=any(
                element.is_displayed()
                for element in driver.find_elements(By.CSS_SELECTOR, ".page-content--not-found")
            ),
            product_container_count=len(containers),
            product_heading_count=len(headings),
            product_heading_visible=visible_heading is not None,
            product_heading_text=visible_heading.text if visible_heading is not None else "",
            product_form_count=len(product_forms),
            product_id_value=(
                product_ids[0].get_attribute("value") if len(product_ids) == 1 else None
            ),
            expected_product_id=PRODUCT_ID,
            add_to_cart_visible=visible_product_button,
            add_to_cart_enabled=active_product_button is not None,
        )
        assert_true(
            product_failure is None,
            f"CI product detail page did not render ({product_failure or 'unknown'}).",
        )
        assert_true("JPY" in driver.page_source or "¥" in driver.page_source,
                    "JPY product price was not rendered on the product page.")
        product_covers = driver.find_elements(
            By.CSS_SELECTOR, ".product__images .carousel-item.active img"
        )
        og_images = driver.find_elements(By.CSS_SELECTOR, 'meta[property="og:image"]')
        if product_covers:
            assert_true(
                len(og_images) == 1,
                "Product page must render only the product cover Open Graph image.",
            )
            cover_path = urlparse(product_covers[0].get_attribute("src") or "").path
            first_og_path = urlparse(og_images[0].get_attribute("content") or "").path
            cover_identity = re.sub(
                r"-[A-Za-z0-9_]+\.(?:jpe?g|png|webp)$",
                "",
                Path(cover_path).name,
                flags=re.IGNORECASE,
            )
            og_identity = re.sub(
                r"-[A-Za-z0-9_]+\.(?:jpe?g|png|webp)$",
                "",
                Path(first_og_path).name,
                flags=re.IGNORECASE,
            )
            assert_true(
                "/img/p/" in cover_path,
                "Rendered product cover URL is not a PrestaShop product image.",
            )
            assert_true(
                "/img/p/" in first_og_path
                and (Path(first_og_path).name == Path(cover_path).name or og_identity == cover_identity),
                "First product page Open Graph image is not the rendered product cover.",
            )
        else:
            assert_true(
                not og_images,
                "Global brand Open Graph image leaked onto a product page without a product cover.",
            )
        driver.save_screenshot(str(DEST / f"{label}-product-detail.png"))
        buttons = product_buttons
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
