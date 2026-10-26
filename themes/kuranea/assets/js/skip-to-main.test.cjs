const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'skip-to-main.js'), 'utf8');

function setup(target) {
  let clickHandler;
  const animationFrames = [];
  const document = {
    addEventListener(name, handler) {
      assert.equal(name, 'click');
      clickHandler = handler;
    },
    getElementById(id) {
      assert.equal(id, 'main-content');
      return target;
    },
  };
  const window = {
    requestAnimationFrame(callback) {
      animationFrames.push(callback);
    },
  };
  vm.runInNewContext(source, { document, window });
  return {
    clickHandler,
    runAnimationFrames() {
      for (const callback of animationFrames) callback();
    },
  };
}

test('native skip-link activation makes the main target focusable and moves keyboard focus', () => {
  const attributes = new Map();
  const focusCalls = [];
  const target = {
    setAttribute(name, value) { attributes.set(name, value); },
    focus(options) { focusCalls.push(options); },
  };
  const fixture = setup(target);

  fixture.clickHandler({
    target: {
      closest(selector) {
        assert.equal(selector, 'a.skip-link[href="#main-content"]');
        return {};
      },
    },
  });

  assert.equal(attributes.get('tabindex'), '-1');
  assert.deepEqual(focusCalls, []);
  fixture.runAnimationFrames();
  assert.equal(focusCalls.length, 1);
  assert.equal(focusCalls[0].preventScroll, true);
});

test('ordinary clicks and missing targets do not move focus', () => {
  const focusCalls = [];
  const target = {
    setAttribute() {},
    focus(options) { focusCalls.push(options); },
  };
  const fixture = setup(target);

  fixture.clickHandler({ target: { closest: () => null } });
  fixture.runAnimationFrames();
  assert.equal(focusCalls.length, 0);

  const missingTarget = setup(null);
  missingTarget.clickHandler({ target: { closest: () => ({}) } });
  missingTarget.runAnimationFrames();

  assert.equal(focusCalls.length, 0);
});
