(function () {
  var dialogs = [
    ['task-detail-drawer', 'close-task-detail'],
    ['settings-modal', 'close-settings'],
    ['skills-modal', 'close-skills'],
    ['chat-modal', 'close-chat'],
    ['create-task-modal', 'close-create-task']
  ];
  var activeDialog = null;
  var returnFocus = new WeakMap();
  var observedFrames = new WeakSet();
  var observedDocuments = new WeakSet();

  function topDialog() {
    var visible = dialogs.map(function (entry) {
      return document.getElementById(entry[0]);
    }).filter(function (dialog) {
      return dialog && dialog.classList.contains('open') && dialog.getClientRects().length;
    });
    visible.sort(function (left, right) {
      return Number(getComputedStyle(left).zIndex) - Number(getComputedStyle(right).zIndex);
    });
    return visible[visible.length - 1] || null;
  }

  function focusableElements(dialog) {
    return Array.from(dialog.querySelectorAll(
      'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href], iframe, [tabindex]:not([tabindex="-1"])'
    )).filter(function (element) {
      return element.tabIndex >= 0 && element.getClientRects().length && !element.closest('.is-hidden');
    });
  }

  function focusFirst(dialog) {
    var entry = dialogs.find(function (item) { return item[0] === dialog.id; });
    var target = document.getElementById(entry[1]) || focusableElements(dialog)[0] || dialog;
    dialog.tabIndex = -1;
    target.focus();
  }

  function syncDialogs() {
    var nextDialog = topDialog();
    var assignee = document.querySelector('#create-task-assignee input[role="combobox"]');
    if (assignee) {
      assignee.setAttribute('aria-labelledby', 'create-task-assignee-label');
    }
    dialogs.forEach(function (entry) {
      var dialog = document.getElementById(entry[0]);
      if (dialog) {
        dialog.inert = dialog !== nextDialog;
        dialog.setAttribute('aria-hidden', dialog === nextDialog ? 'false' : 'true');
        dialog.setAttribute('aria-modal', dialog === nextDialog ? 'true' : 'false');
      }
    });
    var voice = document.getElementById('voice-overlay');
    if (voice) {
      var voiceHidden = !voice.classList.contains('open') || voice.classList.contains('disabled') || !!nextDialog;
      voice.inert = voiceHidden;
      voice.setAttribute('aria-hidden', voiceHidden ? 'true' : 'false');
      if (voiceHidden && voice.contains(document.activeElement) && !nextDialog) {
        var voiceTrigger = document.getElementById('open-chat');
        if (voiceTrigger) { voiceTrigger.focus(); }
      }
    }
    if (nextDialog !== activeDialog) {
      var previous = activeDialog;
      var restored = previous && !previous.classList.contains('open') ? returnFocus.get(previous) : null;
      activeDialog = nextDialog;
      if (restored && restored.isConnected && (!nextDialog || nextDialog.contains(restored))) {
        restored.focus();
      } else if (nextDialog) {
        if (!returnFocus.has(nextDialog) || !previous || previous.classList.contains('open')) {
          returnFocus.set(nextDialog, document.activeElement);
        }
        focusFirst(nextDialog);
      } else if (previous) {
        var fallback = document.getElementById('open-create-task');
        if (fallback) { fallback.focus(); }
      }
    }
    document.querySelectorAll('iframe').forEach(function (frame) {
      if (!observedFrames.has(frame)) {
        observedFrames.add(frame);
        frame.addEventListener('load', function () { observeFrame(frame); });
        observeFrame(frame);
      }
    });
  }

  function observeFrame(frame) {
    try {
      var frameDocument = frame.contentDocument;
      if (frameDocument && !observedDocuments.has(frameDocument)) {
        observedDocuments.add(frameDocument);
        frameDocument.addEventListener('keydown', handleKeydown);
      }
    } catch (error) {
      return;
    }
  }

  function handleKeydown(event) {
    if (event.defaultPrevented || event.isComposing) { return; }
    var dialog = topDialog();
    if (event.key === 'Escape' && dialog) {
      var entry = dialogs.find(function (item) { return item[0] === dialog.id; });
      var closeButton = document.getElementById(entry[1]);
      if (closeButton && !closeButton.matches(':disabled')) {
        event.preventDefault();
        closeButton.click();
      }
      return;
    }
    if (event.key === 'Tab' && dialog) {
      var targets = focusableElements(dialog);
      var first = targets[0];
      var last = targets[targets.length - 1];
      if (!first) {
        event.preventDefault();
        focusFirst(dialog);
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
      return;
    }
    var card = event.target.closest && event.target.closest('.task-card');
    if (!dialog && card && event.target === card && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      card.click();
    }
  }

  document.addEventListener('keydown', handleKeydown);
  document.addEventListener('click', function (event) {
    var drawer = document.getElementById('task-detail-drawer');
    var navigation = event.target.closest && event.target.closest('.task-card, #open-create-task');
    if (drawer && drawer.matches(':disabled') && navigation) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
  document.addEventListener('focusin', function (event) {
    var dialog = topDialog();
    if (dialog && !dialog.contains(event.target)) { focusFirst(dialog); }
  });
  new MutationObserver(syncDialogs).observe(document.documentElement, {
    childList: true, subtree: true, attributes: true, attributeFilter: ['class']
  });
  syncDialogs();
})();