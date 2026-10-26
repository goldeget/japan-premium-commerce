(function () {
  'use strict';

  function initializePreview(form) {
    var input = form.querySelector('input[type="file"][name="import_product_images[]"]');
    var preview = form.querySelector('[data-catalog-image-preview]');
    var status = preview ? preview.querySelector('[data-preview-status]') : null;
    var items = preview ? preview.querySelector('[data-preview-items]') : null;
    var objectUrls = [];

    if (!input || !preview || !status || !items || !window.URL
      || typeof window.URL.createObjectURL !== 'function'
      || typeof window.URL.revokeObjectURL !== 'function') {
      return;
    }

    function clearPreview() {
      objectUrls.forEach(function (objectUrl) {
        window.URL.revokeObjectURL(objectUrl);
      });
      objectUrls = [];
      items.textContent = '';
      preview.setAttribute('data-preview-count', '0');
    }

    input.addEventListener('change', function () {
      clearPreview();
      var files = Array.prototype.slice.call(input.files || []);
      var imageFiles = files.filter(function (file) {
        return ['image/jpeg', 'image/png', 'image/webp'].indexOf(file.type) !== -1;
      });
      status.textContent = files.length === 0
        ? '파일을 선택하면 업로드 예정 이미지의 미리보기가 표시됩니다.'
        : '선택한 로컬 이미지 ' + imageFiles.length + '개 · 사용권 승인과 별도';
      preview.setAttribute('data-preview-count', String(imageFiles.length));

      imageFiles.slice(0, 5).forEach(function (file, index) {
        var objectUrl = window.URL.createObjectURL(file);
        objectUrls.push(objectUrl);

        var image = document.createElement('img');
        image.src = objectUrl;
        image.alt = '선택한 업로드 이미지 ' + (index + 1) + ' 미리보기';
        image.decoding = 'async';
        image.style.maxWidth = '180px';
        image.style.maxHeight = '180px';
        image.style.objectFit = 'contain';
        image.style.margin = '0 12px 12px 0';
        items.appendChild(image);
      });

      if (files.length > 5) {
        var limitNotice = document.createElement('p');
        limitNotice.textContent = '미리보기는 최대 5개까지 표시합니다. 업로드 개수를 확인해 주세요.';
        items.appendChild(limitNotice);
      }
      if (imageFiles.length !== files.length) {
        var unsupportedNotice = document.createElement('p');
        unsupportedNotice.textContent = '일부 파일은 JPG, PNG, WebP 이미지가 아니어서 미리보기를 표시하지 않았습니다.';
        items.appendChild(unsupportedNotice);
      }
    });

    form.addEventListener('reset', clearPreview);
  }

  function initialize() {
    Array.prototype.forEach.call(
      document.querySelectorAll('.catalog-import-review-form'),
      initializePreview
    );
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
}());
