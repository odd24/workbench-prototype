const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = __dirname;
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const stylesheets = [
  'tokens.css',
  'base.css',
  'components.css',
  'layout.css',
  'records.css',
  'management.css',
  'editor.css',
  'knowledge-base.css',
  'concept-map.css',
  'responsive.css',
];
const css = stylesheets
  .map(file => fs.readFileSync(path.join(root, 'css', file), 'utf8'))
  .join('\n');

for (const file of stylesheets) {
  const source = fs.readFileSync(path.join(root, 'css', file), 'utf8');
  const header = file === 'responsive.css'
    ? /^\/\* RF-404: responsive overrides/
    : new RegExp(`^/\\* RF-403: ${file.replace('.css', '')};`);
  assert.match(source, header);
  assert.equal((source.match(/\{/g) || []).length, (source.match(/\}/g) || []).length, `${file} has unbalanced blocks`);
}
const responsiveCss = fs.readFileSync(path.join(root, 'css', 'responsive.css'), 'utf8');
const managementCss = fs.readFileSync(path.join(root, 'css', 'management.css'), 'utf8');
assert.match(responsiveCss, /@media\b/);
assert.match(managementCss, /\.tag-edit\{grid-template-columns:20px 36px minmax\(80px,1fr\) auto\}/);
assert.match(managementCss, /\.status-edit-row\{grid-template-columns:20px 34px minmax\(70px,1fr\) 22px auto\}/);
assert.match(responsiveCss, /\.tag-edit\{grid-template-columns:20px 36px minmax\(70px,1fr\) auto\}/);
assert.match(responsiveCss, /\.status-edit-row\{grid-template-columns:20px 34px minmax\(64px,1fr\) 22px auto\}/);
for (const file of stylesheets.filter(file => file !== 'responsive.css')) {
  assert.doesNotMatch(fs.readFileSync(path.join(root, 'css', file), 'utf8'), /@media\b/, `${file} must not contain responsive overrides`);
}
const mediaConditions = [...responsiveCss.matchAll(/@media\s*\(([^)]+)\)/g)].map(match => match[1]);
assert.equal(new Set(mediaConditions).size, mediaConditions.length, 'media conditions must be consolidated');
assert.deepEqual(
  mediaConditions.filter(condition => condition.startsWith('max-width')).map(condition => Number(condition.match(/\d+/)[0])),
  [1050, 1000, 980, 920, 900, 800, 760, 720, 700, 680, 620, 600, 560, 520, 500, 480],
  'max-width overrides must cascade from wide to narrow',
);
assert.match(responsiveCss, /\.document-dialog\.unified-editor-host\{max-width:100vw;overflow:hidden\}/);
assert.match(responsiveCss, /\.document-dialog\.unified-editor-host \.document-outline\{flex-basis:min\(190px,72vw\);width:min\(190px,72vw\)/);

const linkedStylesheets = [...html.matchAll(/href="css\/([^"?]+)\?v=20260918-1"/g)]
  .map(match => match[1]);
assert.deepEqual(linkedStylesheets, stylesheets, 'stylesheet load order must match the refactoring plan');
assert.equal(fs.existsSync(path.join(root, 'styles.css')), false, 'legacy stylesheet should be removed');

const tokenCss = fs.readFileSync(path.join(root, 'css', 'tokens.css'), 'utf8');
assert.equal((tokenCss.match(/^:root\s*\{/gm) || []).length, 1, 'global tokens should have one root block');
assert.equal((tokenCss.match(/^body\.dark\s*\{/gm) || []).length, 1, 'dark theme tokens should have one block');

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

const javascriptFiles = [];
function collectJavascript(directory) {
  for (const entry of fs.readdirSync(directory, {withFileTypes:true})) {
    const location = path.join(directory, entry.name);
    if (entry.isDirectory()) collectJavascript(location);
    else if (entry.name.endsWith('.js')) javascriptFiles.push(location);
  }
}
collectJavascript(path.join(root, 'js'));
javascriptFiles.push(path.join(root, 'app.js'), path.join(root, 'concept-map.js'));

const dynamicClasses = new Set();
for (const file of javascriptFiles) {
  const source = fs.readFileSync(file, 'utf8');
  for (const call of source.matchAll(/classList\.(?:add|remove|toggle|contains)\(\s*['"]([a-z][a-z0-9_-]*)['"]/gi)) {
    dynamicClasses.add(call[1]);
  }
  for (const assignment of source.matchAll(/className\s*=\s*['"]([^'"]+)['"]/g)) {
    for (const value of assignment[1].split(/\s+/)) dynamicClasses.add(value);
  }
  for (const template of source.matchAll(/class="([^"]+)"/g)) {
    const staticClassNames = template[1].replace(/\$\{[^}]*\}/g, '');
    for (const value of staticClassNames.split(/\s+/)) {
      if (/^[a-z][a-z0-9_-]*$/i.test(value) && !value.endsWith('-')) dynamicClasses.add(value);
    }
  }
}

const unstyledHooks = new Set([
  'asset-category-tag',
  'asset-new-category-name',
  'outline-collapsed',
  'remove-status',
  'status-edit-list',
  'status-usage-button',
  'tag-usage-button',
]);
const missingDynamicClasses = [...dynamicClasses]
  .filter(value => !unstyledHooks.has(value))
  .filter(value => !css.includes(`.${value}`))
  .sort();
assert.deepEqual(missingDynamicClasses, [], 'dynamic/template classes must be styled or declared as unstyled hooks');

console.log('Stylesheet contract tests passed.');
