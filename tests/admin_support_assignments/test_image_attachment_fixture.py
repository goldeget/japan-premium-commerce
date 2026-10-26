"""Synthetic support image and binary readback contracts, without browser execution."""
from __future__ import annotations

import hashlib
import struct
import unittest
import zlib

from tests.e2e.test_ci_customer_support_browser_contract import load_script


class SupportImageAttachmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.support = load_script()

    def fixture(self):
        self.assertTrue(hasattr(self.support, 'synthetic_support_png'), 'support acceptance needs a real generated PNG')
        return self.support.synthetic_support_png('ORDENOWA_CI_SYNTHETIC_123')

    def test_generated_fixture_is_one_pixel_png_with_valid_crc_and_synthetic_marker(self):
        data = self.fixture()
        self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertLessEqual(len(data), 4096)
        chunks = []
        offset = 8
        while offset < len(data):
            size = struct.unpack('>I', data[offset:offset + 4])[0]
            kind = data[offset + 4:offset + 8]
            payload = data[offset + 8:offset + 8 + size]
            crc = struct.unpack('>I', data[offset + 8 + size:offset + 12 + size])[0]
            self.assertEqual(zlib.crc32(kind + payload) & 0xffffffff, crc)
            chunks.append((kind, payload))
            offset += 12 + size
        self.assertEqual([b'IHDR', b'tEXt', b'IDAT', b'IEND'], [kind for kind, _ in chunks])
        self.assertEqual((1, 1, 8, 2, 0, 0, 0), struct.unpack('>IIBBBBB', chunks[0][1]))
        self.assertEqual(b'Comment\x00ORDENOWA_CI_SYNTHETIC_123', chunks[1][1])
        self.assertEqual(4, len(zlib.decompress(chunks[2][1])))
        self.assertEqual(len(data), offset)

    def test_generated_fixture_rejects_non_synthetic_marker(self):
        self.fixture()
        for marker in ('', 'person@example.test', '../private', 'x' * 129, '개인정보'):
            with self.subTest(marker_type='invalid'), self.assertRaises(ValueError):
                self.support.synthetic_support_png(marker)

    def test_upload_fixture_checks_name_mime_extension_content_and_size(self):
        data = self.fixture()
        self.support.validate_synthetic_upload('ordenowa-support-image.png', data, 'image/png')
        self.support.validate_synthetic_upload('ordenowa-support-text.txt', b'ORDENOWA_CI_SYNTHETIC_123', 'text/plain')
        invalid = [
            ('../image.png', data, 'image/png'), ('image.php.png', data, 'image/png'),
            ('image.php', data, 'image/png'), ('image.png', data, 'text/html'),
            ('image.jpg', data, 'image/jpeg'), ('image.png', b'<html>CI_ONLY</html>', 'image/png'),
            ('image.png', data[:-1], 'image/png'), ('image.png', data + b'x' * 4096, 'image/png'),
        ]
        for name, content, mime in invalid:
            with self.subTest(case=name), self.assertRaises(ValueError):
                self.support.validate_synthetic_upload(name, content, mime)

    def test_native_image_link_requires_one_safe_png_filename(self):
        self.fixture()
        self.assertTrue(hasattr(self.support, 'assert_image_attachment_filename'))
        self.support.assert_image_attachment_filename('http://localhost:18080/admin/secured-file?fileName=abc123.png')
        for query in ('fileName=../private.png', 'fileName=%2Fprivate.png', 'fileName=a.php.png',
                      'fileName=a.txt', 'fileName=a.png&fileName=b.png', ''):
            with self.subTest(case='unsafe filename'), self.assertRaises(AssertionError):
                self.support.assert_image_attachment_filename('http://localhost:18080/admin/secured-file?' + query)

    def test_binary_admin_readback_requires_same_digest_size_png_mime_and_safe_filename(self):
        data = self.fixture()
        valid = {'status': 200, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                 'mime': 'image/png', 'pngSignature': True, 'safeFilename': True}
        self.support.assert_image_attachment_response(valid, data)
        for field, value in [('status', 403), ('size', len(data) + 1), ('sha256', '0' * 64),
                             ('mime', 'text/html'), ('mime', 'application/octet-stream'), ('pngSignature', False), ('safeFilename', False)]:
            with self.subTest(field=field), self.assertRaises(AssertionError):
                self.support.assert_image_attachment_response(dict(valid, **{field: value}), data)
        with self.assertRaises(AssertionError):
            self.support.assert_image_attachment_response(None, data)


if __name__ == '__main__':
    unittest.main()
