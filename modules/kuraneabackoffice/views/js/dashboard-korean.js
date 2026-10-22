(function () {
  'use strict';

  function localizeDateRange() {
    var range = document.querySelector('#date-range');
    if (!range) return;

    range.querySelectorAll('.form-date-body label').forEach(function (label) {
      var value = label.textContent.trim();
      if (value === 'From') label.textContent = '시작일';
      if (value.toLowerCase() === 'to') label.textContent = '종료일';
    });

    range.querySelectorAll('[name="date_from"], [name="compare_date_from"]').forEach(function (input) {
      input.setAttribute('placeholder', '시작일');
    });
    range.querySelectorAll('[name="date_to"], [name="compare_date_to"]').forEach(function (input) {
      input.setAttribute('placeholder', '종료일');
    });

    var summary = document.querySelector('#datepickerExpand .hidden-xs');
    if (summary) {
      var walker = document.createTreeWalker(summary, NodeFilter.SHOW_TEXT);
      var node;
      while ((node = walker.nextNode())) {
        node.nodeValue = node.nodeValue.replace(/\bFrom\b/g, '시작일').replace(/\bTo\b/g, '종료일');
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', localizeDateRange, { once: true });
  } else {
    localizeDateRange();
  }
})();
