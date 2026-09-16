(function initializeCoreDialogs(global) {
  'use strict';

  const domCore = global.Workbench?.dom;

  function requireDomCore() {
    if (!domCore) throw new Error('Workbench.dom must load before Workbench.dialogs');
    return domCore;
  }

  function notify(title, detail = '对应 Markdown 文件已自动更新', error = false) {
    const {$} = requireDomCore();
    const toast = $('#toast');
    $('.toast > span').textContent = error ? '!' : '✓';
    $('.toast strong').textContent = title;
    $('.toast small').textContent = detail;
    toast.classList.toggle('error', error);
    toast.classList.add('visible');
    clearTimeout(notify.timer);
    notify.timer = setTimeout(() => toast.classList.remove('visible'), 3000);
  }

  function open({title, message = '', detail = '', confirmText = '确认', cancelText = '取消', danger = false, input = null}) {
    const {$, escapeHtml, safeColor} = requireDomCore();
    const dialog = $('#appDialog');
    if (dialog.open) dialog.close('cancel');
    dialog.classList.toggle('danger', danger);
    dialog.classList.toggle('input-mode', Boolean(input));
    $('.app-dialog-icon', dialog).textContent = danger ? '!' : '?';
    $('#appDialogEyebrow').textContent = input ? '填写信息' : danger ? '危险操作' : '请确认操作';
    $('#appDialogTitle').textContent = title;
    $('#appDialogMessage').textContent = message;
    $('#appDialogDetail').textContent = detail;
    $('#appDialogConfirm').textContent = confirmText;
    $('button[value="cancel"]:not(.dialog-close)', dialog).textContent = cancelText;
    const field = $('#appDialogInput');
    const options = $('#appDialogOptions');
    if (input) {
      $('#appDialogInputLabel').textContent = input.label || '请输入内容';
      field.type = input.type || 'text';
      field.value = input.value || '';
      field.placeholder = input.placeholder || '';
      field.required = input.required !== false;
      field.readOnly = Boolean(input.readOnly);
      const choices = Array.isArray(input.choices) ? input.choices.filter(choice => choice?.value || choice?.label) : [];
      options.hidden = !choices.length;
      options.innerHTML = choices.map(choice => `<button type="button" data-app-dialog-choice="${escapeHtml(choice.value || choice.label)}" style="--choice-color:${safeColor(choice.color)}"><i></i><span>${escapeHtml(choice.label || choice.value)}</span></button>`).join('');
      options.onclick = event => {
        const choice = event.target.closest('[data-app-dialog-choice]');
        if (!choice) return;
        field.value = choice.dataset.appDialogChoice;
        dialog.close('confirm');
      };
    } else {
      field.value = '';
      field.required = false;
      field.readOnly = false;
      options.hidden = true;
      options.innerHTML = '';
      options.onclick = null;
    }
    dialog.returnValue = 'cancel';
    dialog.showModal();
    setTimeout(() => {
      if (input) { field.focus(); if (input.select !== false) field.select(); }
      else $('#appDialogConfirm').focus();
    }, 20);
    return new Promise(resolve => dialog.addEventListener('close', () => resolve({confirmed:dialog.returnValue === 'confirm', value:field.value}), {once:true}));
  }

  async function confirm(options) {
    return (await open(options)).confirmed;
  }

  async function prompt(options) {
    const result = await open({...options, input:options.input || {label:options.label, value:options.value, placeholder:options.placeholder, type:options.type}});
    return result.confirmed ? result.value : null;
  }

  const input = global.document?.querySelector('#appDialogInput');
  input?.addEventListener('keydown', event => {
    if (event.key !== 'Enter' || event.isComposing) return;
    event.preventDefault();
    if (event.currentTarget.reportValidity()) global.document.querySelector('#appDialog').close('confirm');
  });

  const api = {notify, open, confirm, prompt};
  global.Workbench = global.Workbench || {};
  global.Workbench.dialogs = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
