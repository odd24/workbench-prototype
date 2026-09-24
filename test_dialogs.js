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

function keyEvent(target, overrides = {}) {
  return {
    key:'Enter',
    target,
    prevented:false,
    preventDefault() { this.prevented = true; },
    ...overrides,
  };
}

let clicks = 0;
const submitButton = {disabled:false, click:() => { clicks += 1; }};
const titleInput = {tagName:'INPUT', type:'text'};
const titleEnter = keyEvent(titleInput);
assert.equal(dialogs.submitOnEnter(titleEnter, submitButton), true);
assert.equal(titleEnter.prevented, true);
assert.equal(clicks, 1);

assert.equal(dialogs.submitOnEnter(keyEvent({tagName:'TEXTAREA'}), submitButton), false);
assert.equal(dialogs.submitOnEnter(keyEvent(titleInput, {isComposing:true}), submitButton), false);
assert.equal(dialogs.submitOnEnter(keyEvent(titleInput, {shiftKey:true}), submitButton), false);
assert.equal(dialogs.submitOnEnter(keyEvent({tagName:'SELECT'}), submitButton), true);
assert.equal(clicks, 2);
submitButton.disabled = true;
assert.equal(dialogs.submitOnEnter(keyEvent({tagName:'SELECT'}), submitButton), false);
assert.equal(clicks, 2);

console.log('Dialog contract tests passed.');
