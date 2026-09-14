(function () {
  const themeStorageKey = "elemental-theme";
  const themeButton = document.querySelector("[data-elemental-theme-toggle]");
  const root = document.documentElement;

  function applyTheme(theme, persist) {
    const selected = theme === "dark" ? "dark" : "light";
    root.dataset.theme = selected;
    root.dataset.bsTheme = selected;
    if (themeButton) {
      const nextLabel = selected === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro";
      themeButton.setAttribute("aria-label", nextLabel);
      themeButton.title = nextLabel;
      const label = themeButton.querySelector(".visually-hidden");
      if (label) label.textContent = nextLabel;
      const icon = themeButton.querySelector("i");
      if (icon) {
        icon.classList.toggle("bi-sun", selected === "dark");
        icon.classList.toggle("bi-moon-stars", selected !== "dark");
      }
    }
    if (persist) {
      try {
        window.localStorage.setItem(themeStorageKey, selected);
        window.localStorage.removeItem("profesor-theme");
      } catch (_error) {
        // La preferencia no es esencial; el tema sigue activo durante la visita.
      }
    }
  }

  applyTheme(root.dataset.theme || "light", false);
  if (themeButton) {
    themeButton.addEventListener("click", function () {
      applyTheme(root.dataset.theme === "dark" ? "light" : "dark", true);
    });
  }

  const storageKey = "elemental-sidebar-collapsed";
  const body = document.body;
  const button = document.querySelector("[data-elemental-sidebar-toggle]");
  if (!button) return;

  function applyCollapsed(collapsed) {
    body.classList.toggle("elemental-sidebar-collapsed", collapsed);
    button.setAttribute("aria-expanded", collapsed ? "false" : "true");
    button.title = collapsed ? "Expandir menú" : "Contraer menú";
    const label = button.querySelector(".visually-hidden");
    if (label) label.textContent = button.title;
    const icon = button.querySelector("i");
    if (icon) {
      icon.classList.toggle("bi-layout-sidebar-inset", !collapsed);
      icon.classList.toggle("bi-layout-sidebar", collapsed);
    }
  }

  let collapsed = false;
  try {
    collapsed = window.localStorage.getItem(storageKey) === "true";
  } catch (_error) {
    collapsed = false;
  }
  applyCollapsed(collapsed);
  window.requestAnimationFrame(function () {
    body.classList.add("elemental-sidebar-ready");
  });

  button.addEventListener("click", function () {
    collapsed = !body.classList.contains("elemental-sidebar-collapsed");
    applyCollapsed(collapsed);
    try {
      window.localStorage.setItem(storageKey, String(collapsed));
    } catch (_error) {
      // La preferencia no es esencial; el control sigue funcionando en memoria.
    }
  });
})();
