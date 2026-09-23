'use strict';

const assert = require('node:assert/strict');
const dialogs = require('./js/core/dialogs.js');

function choice(value) {
  const attributes = new Map([['aria-pressed', 'false']]);
  return {
    dataset:{appDialogChoice:value},
    getAttribute:name => attributes.get(name) || null,
    setAttribute:(name, next) => attributes.set(name, next),
  };
}

const first = choice('前端');
const field = {value:''};
let closeValue = '';
const dialog = {close:value => { closeValue = value; }};

assert.equal(dialogs.chooseOption(first, {multiple:true, field, dialog}), true);
assert.equal(first.getAttribute('aria-pressed'), 'true');
assert.equal(field.value, '');
assert.equal(closeValue, '');
dialogs.chooseOption(first, {multiple:true, field, dialog});
assert.equal(first.getAttribute('aria-pressed'), 'false');

const single = choice('后端');
assert.equal(dialogs.chooseOption(single, {field, dialog}), true);
assert.equal(field.value, '后端');
assert.equal(closeValue, 'confirm');

console.log('Dialog choice contract tests passed.');
