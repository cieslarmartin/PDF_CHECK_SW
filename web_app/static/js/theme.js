/**
 * DokuCheck – celoplošné přepínání světlý / tmavý režim.
 * Uložení do localStorage (klíč dokucheck-theme), aplikace na <html data-theme="light|dark">.
 */
(function () {
  var key = 'dokucheck-theme';
  function get() {
    try {
      return localStorage.getItem(key) || 'light';
    } catch (e) {
      return 'light';
    }
  }
  function set(theme) {
    theme = theme === 'dark' ? 'dark' : 'light';
    try {
      localStorage.setItem(key, theme);
    } catch (e) {}
    document.documentElement.setAttribute('data-theme', theme);
    return theme;
  }
  set(get());
  window.toggleTheme = function () {
    return set(get() === 'dark' ? 'light' : 'dark');
  };
  window.getTheme = function () {
    return get();
  };
})();
