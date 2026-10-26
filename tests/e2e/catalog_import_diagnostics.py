#!/usr/bin/env python3
"""Validate and safely serialize the fixed catalog-import browser diagnostics."""
from __future__ import annotations

import argparse
import binascii
import json
from pathlib import Path
import struct
from typing import Any


BOOLEAN_FIELDS = {
    'same_admin_origin', 'admin_path_matches', 'controller_parameter_present', 'controller_allowed',
    'login_form_visible', 'product_url_field_visible', 'submit_control_visible', 'submit_attempted',
    'submit_returned', 'batch_progress_container_visible', 'progress_visible',
    'token_rejected_notice_visible', 'mutation_access_denied_notice_visible',
    'empty_url_notice_visible', 'batch_save_failure_notice_visible', 'batch_created_notice_visible',
    'option_guard_notice_visible',
    'unclassified_alert_visible', 'read_only_notice_visible', 'access_denied_notice_visible',
    'queue_unavailable_notice_visible', 'manager_route_matches',
    'manager_product_id_parameter_present', 'manager_product_id_parameter_matches',
    'manager_link_same_origin', 'manager_link_path_matches',
    'manager_link_controller_parameter_present', 'manager_link_controller_matches',
    'manager_link_product_id_parameter_present', 'manager_link_product_id_valid',
    'manager_id_field_present', 'manager_id_field_hidden', 'manager_product_id_field_matches',
    'manager_editor_visible', 'manager_load_failure_notice_visible',
    'manager_permission_denied_notice_visible', 'manager_inactive_notice_visible',
    'failure_screenshot_captured',
}
INTEGER_LIMITS = {
    'progress_value': 1_000_000, 'progress_max': 1_000_000, 'row_count': 1000,
    'submitted_url_count': 10, 'visible_alert_count': 20,
}
OPTIONAL_INTEGER_FIELDS = {'progress_value', 'progress_max'}
CLICK_TARGETS = {
    'category_checkbox', 'translation_en_checkbox', 'translation_ko_checkbox',
    'options_confirmation_checkbox', 'image_rights_confirmation_checkbox',
    'native_draft_submit', 'rejection_submit',
}
CLICK_SUBSTAGES = {
    'reject_rakuten_submit', 'approve_category_checkbox', 'approve_translation_review_en',
    'approve_translation_review_ko', 'approve_options_confirmation',
    'approve_image_rights_confirmation', 'approve_submit',
}
CLICK_ACTIONS = {'native_click'}
CENTER_HIT_RELATIONS = {
    'target', 'target_descendant', 'target_label', 'modal', 'backdrop', 'alert',
    'fixed_navigation', 'other', 'unknown', 'outside_viewport',
}
OCCLUDER_CATEGORIES = {
    'none', 'label', 'modal', 'modal_backdrop', 'alert', 'fixed_header',
    'fixed_navigation', 'other', 'unknown',
}
CLICK_DIAGNOSTIC_FIELDS = {
    'substage', 'target', 'action', 'attempted', 'returned', 'visible', 'enabled',
    'target_rect', 'occluder_rect', 'center_in_viewport', 'center_hit_relation', 'occluder_category',
}
STRING_ENUMS = {
    'stage': {
        'launch', 'login', 'review_menu_route', 'manager_menu_route', 'manager_navigation',
        'batch_review_navigation', 'batch_url_field', 'batch_submit_control', 'batch_submit_click',
        'batch_completion_wait', 'batch_progress_readback', 'reject_rakuten', 'approve_amazon',
        'native_readback', 'reimport_review_navigation', 'reimport_url_field',
        'reimport_submit_control', 'reimport_submit_click', 'reimport_completion_wait',
        'reimport_progress_readback', 'reimport', 'unknown',
    },
    'last_completed_stage': {
        'not_started', 'launch', 'login', 'review_menu_route', 'manager_menu_route', 'manager_navigation',
        'batch_review_navigation', 'batch_url_field', 'batch_submit_control', 'batch_submit_click',
        'batch_completion_wait', 'batch_progress_readback', 'reject_rakuten', 'approve_amazon',
        'native_readback', 'reimport_review_navigation', 'reimport_url_field',
        'reimport_submit_control', 'reimport_submit_click', 'reimport_completion_wait',
        'reimport_progress_readback', 'reimport', 'unknown',
    },
    'admin_controller': {'AdminKuraneaCatalogReview', 'AdminOrdenowaProductManager', 'other_admin', 'unknown'},
    'page_class': {
        'controller_access_denied', 'batch_capability_denied', 'queue_unavailable',
        'mutation_token_rejected', 'mutation_capability_denied', 'batch_save_error',
        'batch_created_without_progress', 'unsupported_options_guard', 'unclassified_alert', 'login_form',
        'catalog_import_form', 'manager_access_denied', 'manager_load_error',
        'manager_editor', 'manager_editor_missing', 'other_admin',
    },
    'current_substage': {
        'not_started', 'approved_product_link', 'manager_navigation',
        'native_editor_id_presence', 'native_editor_form_check', 'native_editor_readback',
        'reimport_navigation', 'reimport_editor_id_presence', 'reimport_editor_form_check',
        'reimport_editor_readback', 'reject_guard_readback', 'reject_status_readback', 'unknown',
    },
    'manager_link_path_class': {
        'admin_directory', 'admin_directory_slash', 'admin_index_php', 'other', 'unknown',
    },
    'document_ready_state': {'loading', 'interactive', 'complete', 'unknown'},
    'last_completed_substage': CLICK_SUBSTAGES | {
        'not_started', 'batch_complete', 'reject_guard_readback', 'reject_status_readback', 'unknown',
    },
    'exception_class': {
        'AssertionError', 'ElementClickInterceptedException', 'ElementNotInteractableException',
        'NoSuchElementException', 'OSError', 'RuntimeError', 'StaleElementReferenceException',
        'TimeoutException', 'ValueError', 'WebDriverException', 'Exception',
    },
}
DIAGNOSTIC_FIELDS = (
    BOOLEAN_FIELDS
    | set(INTEGER_LIMITS)
    | {'stage', 'last_completed_stage', 'last_completed_substage', 'click_diagnostics',
       'admin_controller', 'page_class', 'document_ready_state', 'current_substage',
       'manager_link_path_class', *OPTIONAL_INTEGER_FIELDS,
       'document_response_status', 'exception_class'}
)


def _validate_rect(value: Any) -> bool:
    if value is None:
        return True
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(type(item) is int for item in value)
        and -2000 <= value[0] <= 2000
        and -2000 <= value[1] <= 2000
        and 0 <= value[2] <= 2000
        and 0 <= value[3] <= 2000
    )


def _validate_click_diagnostics(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != CLICK_DIAGNOSTIC_FIELDS:
        raise ValueError('catalog import click diagnostic fields are not allowlisted')
    if value['substage'] not in CLICK_SUBSTAGES:
        raise ValueError('catalog import click substage is invalid')
    if value['target'] not in CLICK_TARGETS:
        raise ValueError('catalog import click target is invalid')
    if value['action'] not in CLICK_ACTIONS:
        raise ValueError('catalog import click action is invalid')
    for name in ('attempted', 'returned', 'visible', 'enabled', 'center_in_viewport'):
        if type(value[name]) is not bool:
            raise ValueError('catalog import click diagnostic boolean is invalid')
    if value['returned'] and not value['attempted']:
        raise ValueError('catalog import click return state is inconsistent')
    if not _validate_rect(value['target_rect']) or not _validate_rect(value['occluder_rect']):
        raise ValueError('catalog import click rectangle is invalid')
    if value['center_hit_relation'] not in CENTER_HIT_RELATIONS:
        raise ValueError('catalog import click hit-test relation is invalid')
    if value['occluder_category'] not in OCCLUDER_CATEGORIES:
        raise ValueError('catalog import click occluder category is invalid')


def _png_dimensions(path: Path) -> tuple[int, int]:
    """Validate a bounded, complete PNG with checksummed chunks and image data."""
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('catalog import safe failure screenshot exceeds the size limit')
    image = path.read_bytes()
    if not image.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('catalog import safe failure screenshot is not a PNG image')

    offset = 8
    width = height = None
    saw_idat = False
    saw_iend = False
    while offset + 12 <= len(image):
        length = struct.unpack('!I', image[offset:offset + 4])[0]
        kind = image[offset + 4:offset + 8]
        end = offset + 8 + length
        crc_end = end + 4
        if length > 32 * 1024 * 1024 or crc_end > len(image):
            raise ValueError('catalog import safe failure screenshot has a malformed PNG chunk')
        payload = image[offset + 8:end]
        expected_crc = struct.unpack('!I', image[end:crc_end])[0]
        if binascii.crc32(kind + payload) & 0xffffffff != expected_crc:
            raise ValueError('catalog import safe failure screenshot has an invalid PNG checksum')
        if offset == 8:
            if kind != b'IHDR' or length != 13:
                raise ValueError('catalog import safe failure screenshot has no valid IHDR')
            width, height = struct.unpack('!II', payload[:8])
        elif kind == b'IHDR':
            raise ValueError('catalog import safe failure screenshot contains multiple IHDR chunks')
        if kind == b'IDAT' and length > 0:
            saw_idat = True
        if kind == b'IEND':
            if length != 0:
                raise ValueError('catalog import safe failure screenshot has an invalid IEND')
            saw_iend = True
            offset = crc_end
            break
        offset = crc_end

    if width is None or height is None or not saw_idat or not saw_iend or offset != len(image):
        raise ValueError('catalog import safe failure screenshot is incomplete')
    return width, height


def validate(data: Any) -> dict[str, Any]:
    """Reject any unlisted field/value before diagnostic data can reach a CI annotation."""
    if not isinstance(data, dict) or set(data) != DIAGNOSTIC_FIELDS:
        raise ValueError('catalog import failure diagnostic fields are not allowlisted')
    for key in BOOLEAN_FIELDS:
        if type(data[key]) is not bool:
            raise ValueError('catalog import failure diagnostic boolean is invalid')
    for key, maximum in INTEGER_LIMITS.items():
        value = data[key]
        if value is None and key in OPTIONAL_INTEGER_FIELDS:
            continue
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError('catalog import failure diagnostic counter is invalid')
    response_status = data['document_response_status']
    if response_status is not None and (type(response_status) is not int or not 100 <= response_status <= 599):
        raise ValueError('catalog import document response status is invalid')
    for key, allowed in STRING_ENUMS.items():
        if type(data[key]) is not str or data[key] not in allowed:
            raise ValueError('catalog import failure diagnostic enum is invalid')
    _validate_click_diagnostics(data['click_diagnostics'])
    return data


def read_validated(path: Path) -> dict[str, Any]:
    try:
        return validate(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        raise ValueError('catalog import failure diagnostic is invalid') from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='emit canonical JSON only after validation')
    parser.add_argument('--validate', action='store_true', help='validate the file and optional screenshot')
    parser.add_argument('path', type=Path)
    parser.add_argument('screenshot', nargs='?', type=Path)
    args = parser.parse_args()
    if args.json == args.validate:
        parser.error('choose exactly one of --json or --validate')
    try:
        data = read_validated(args.path)
        if args.validate:
            if data['stage'] in {'batch_completion_wait', 'reimport_completion_wait'} and not data['failure_screenshot_captured']:
                raise ValueError('catalog import failure screenshot was not captured')
            if data['stage'] in {'approve_amazon', 'reject_rakuten'} and not data['failure_screenshot_captured']:
                raise ValueError('catalog import review form failure screenshot was not captured')
            click_diagnostics = data['click_diagnostics']
            if data['stage'] == 'approve_amazon' and data['exception_class'] == 'ElementClickInterceptedException':
                if (
                    not isinstance(click_diagnostics, dict)
                    or not click_diagnostics['attempted']
                    or click_diagnostics['returned']
                ):
                    raise ValueError('catalog import intercepted-click diagnostic is missing or inconsistent')
                if not data['failure_screenshot_captured']:
                    raise ValueError('catalog import intercepted-click screenshot was not captured')
            if data['failure_screenshot_captured'] and (
                args.screenshot is None or not args.screenshot.is_file() or args.screenshot.stat().st_size == 0
            ):
                raise ValueError('catalog import safe failure screenshot is missing')
            if data['stage'] in {'approve_amazon', 'reject_rakuten'}:
                screenshot_width, screenshot_height = _png_dimensions(args.screenshot)
                if not (320 <= screenshot_width <= 640 and 180 <= screenshot_height <= 480):
                    raise ValueError('catalog import review form failure screenshot crop is outside the safe bounds')
            if (data['stage'] == 'native_readback'
                    and data['manager_route_matches']
                    and data['manager_product_id_parameter_matches']
                    and (data['manager_editor_visible'] or data['manager_load_failure_notice_visible']
                         or data['manager_permission_denied_notice_visible'])):
                if not data['failure_screenshot_captured']:
                    raise ValueError('catalog import manager readback failure screenshot was not captured')
                screenshot_width, screenshot_height = _png_dimensions(args.screenshot)
                if not (320 <= screenshot_width <= 640 and 180 <= screenshot_height <= 480):
                    raise ValueError('catalog import manager readback screenshot crop is outside the safe bounds')
            print('PASS: catalog import failure diagnostics use an allowlisted safe schema.')
        else:
            print(json.dumps(data, sort_keys=True, separators=(',', ':')))
    except ValueError as error:
        print(str(error))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
