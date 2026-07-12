(() => {
  const sync = (group) => {
    const parent = group.querySelector('[data-parent-checkbox]');
    const children = [...group.querySelectorAll('.child-choices input[type="checkbox"]')];
    if (!parent || !children.length) return;
    const checked = children.filter((child) => child.checked).length;
    parent.checked = checked === children.length;
    parent.indeterminate = checked > 0 && checked < children.length;
  };
  const connect = (group) => {
    const parent = group.querySelector('[data-parent-checkbox]');
    const children = [...group.querySelectorAll('.child-choices input[type="checkbox"]')];
    if (!parent || !children.length || parent.dataset.connected) return;
    parent.dataset.connected = 'true';
    parent.addEventListener('change', () => {
      children.forEach((child) => { child.checked = parent.checked; });
      sync(group);
    });
    children.forEach((child) => child.addEventListener('change', () => sync(group)));
    sync(group);
  };
  const connectAll = (root = document) => root.querySelectorAll('.parent-child-group').forEach(connect);
  document.addEventListener('DOMContentLoaded', () => connectAll());
  document.addEventListener('formset:added', (event) => connectAll(event.target));
})();
