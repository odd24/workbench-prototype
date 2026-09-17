const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = __dirname;
const css = fs.readFileSync(path.join(root, 'styles.css'), 'utf8');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');

assert.equal((css.match(/^:root\s*\{/gm) || []).length, 1, 'global tokens should have one root block');
assert.equal((css.match(/^body\.dark\s*\{/gm) || []).length, 1, 'dark theme tokens should have one block');

for (const token of [
  '--control-height',
  '--control-radius',
  '--dialog-radius',
  '--focus-ring',
  '--type-page-title',
  '--type-body',
  '--type-meta',
]) {
  assert.match(css, new RegExp(`${token}\\s*:`), `missing shared token ${token}`);
}

assert.equal((css.match(/\.primary-button,\.secondary-button\{/g) || []).length, 1, 'button base should be consolidated');
assert.match(css, /button:focus-visible,[^\n]+\[contenteditable\]:focus-visible\{/);
assert.match(css, /button:disabled\{opacity:\.55;cursor:not-allowed;box-shadow:none\}/);
assert.match(css, /\.create-dialog input,\.create-dialog select,\.create-dialog textarea\{[^}]+var\(--control-height\)[^}]+var\(--control-radius\)/);
assert.match(css, /\.create-dialog input:focus,\.create-dialog textarea:focus\{[^}]+var\(--focus-ring\)/);
assert.match(html, /styles\.css\?v=20260917-1/);

console.log('Stylesheet contract tests passed.');
