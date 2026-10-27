// Aplica o tema salvo antes da primeira pintura e liga o botão de alternância.
(function () {
  'use strict';
  var KEY = 'resolveai-theme';
  var root = document.documentElement;
  var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function stored() {
    try {
      var value = window.localStorage.getItem(KEY);
      return value === 'light' || value === 'dark' ? value : null;
    } catch (e) {
      return null;
    }
  }

  function effective() {
    return root.dataset.theme || (media && media.matches ? 'dark' : 'light');
  }

  function sync() {
    var dark = effective() === 'dark';
    var meta = document.getElementById('theme-color');
    if (meta) meta.setAttribute('content', dark ? '#17151c' : '#f8f5fb');
    var button = document.getElementById('theme-toggle');
    if (button) {
      button.setAttribute('aria-pressed', String(dark));
      button.title = dark ? 'Usar tema claro' : 'Usar tema escuro';
    }
  }

  var initial = stored();
  if (initial) root.dataset.theme = initial;

  if (media && media.addEventListener) media.addEventListener('change', sync);

  document.addEventListener('DOMContentLoaded', function () {
    sync();
    var button = document.getElementById('theme-toggle');
    if (!button) return;
    button.addEventListener('click', function () {
      var next = effective() === 'dark' ? 'light' : 'dark';
      root.dataset.theme = next;
      try {
        window.localStorage.setItem(KEY, next);
      } catch (e) {
        /* armazenamento indisponível: o tema vale só nesta página */
      }
      sync();
    });
  });
})();
