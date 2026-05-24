(function () {
  function isEditing(target) {
    if (!target || !target.closest) {
      return false;
    }
    return Boolean(target.closest('input, textarea, select, [contenteditable="true"]'));
  }

  function hasForegroundModal() {
    return Boolean(document.querySelector('.create-task-modal.open, .settings-modal.open, .skills-modal.open, .chat-modal.open'));
  }

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape' || event.defaultPrevented) {
      return;
    }
    if (isEditing(event.target) || hasForegroundModal()) {
      return;
    }

    var drawer = document.getElementById('task-detail-drawer');
    if (!drawer || !drawer.classList.contains('open')) {
      return;
    }

    var closeButton = document.getElementById('task-detail-esc-close');
    if (!closeButton) {
      return;
    }

    event.preventDefault();
    closeButton.click();
  });
})();