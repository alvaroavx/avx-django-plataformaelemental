(function () {
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
