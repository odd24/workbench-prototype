(function initializeCoreState(global) {
  'use strict';

  const STATE_GROUPS = ['serverData', 'uiState', 'editorState', 'draftState'];

  function createRequestRegistry() {
    const active = new Map();

    function begin(channel, identity = '') {
      const previous = active.get(channel);
      const token = Object.freeze({
        channel,
        identity,
        version:(previous?.version || 0) + 1,
      });
      active.set(channel, token);
      return token;
    }

    function isCurrent(token, identity = token?.identity) {
      if (!token) return false;
      const current = active.get(token.channel);
      return current === token && Object.is(current.identity, identity);
    }

    function invalidate(channel) {
      return begin(channel, Symbol('invalidated'));
    }

    return Object.freeze({begin, isCurrent, invalidate});
  }

  function create(groups = {}) {
    const state = {};
    STATE_GROUPS.forEach(name => {
      state[name] = groups[name] || {};
    });
    state.requests = createRequestRegistry();
    return Object.freeze(state);
  }

  const state = Object.freeze({create, createRequestRegistry, groups:Object.freeze([...STATE_GROUPS])});
  global.Workbench = global.Workbench || {};
  global.Workbench.state = state;
  if (typeof module !== 'undefined' && module.exports) module.exports = state;
})(typeof window !== 'undefined' ? window : globalThis);
