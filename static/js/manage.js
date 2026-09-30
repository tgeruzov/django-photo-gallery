// Раздел управления фото: порядок перетаскиванием, выбор и удаление.
// Порядок сохраняется сам через полсекунды после изменения.

document.addEventListener('DOMContentLoaded', initManagePhotos);

function initManagePhotos() {
  const root = document.getElementById('manage-photos');
  const grid = document.getElementById('manage-grid');
  if (!root || !grid) return;

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const hint = document.getElementById('manage-hint');
  const actions = document.getElementById('manage-actions');
  const selectedLabel = document.getElementById('manage-selected');
  const saveStatus = document.getElementById('manage-save');
  const announcer = document.getElementById('manage-announce');
  const dialog = document.getElementById('manage-delete-dialog');
  const countBadge = document.getElementById('manage-photo-count');
  const EASE = 'cubic-bezier(0.2, 0.7, 0.2, 1)';

  const tiles = () => Array.from(grid.children);
  const tileId = tile => Number(tile.dataset.id);
  const buttonOf = tile => tile.querySelector('.manage-tile-button');
  const currentOrder = () => tiles().map(tileId);
  const sameOrder = (a, b) => a.length === b.length && a.every((id, i) => id === b[i]);

  const selected = new Set();
  let anchor = null; // от него Shift+клик выделяет диапазон
  let busy = false; // идёт удаление: порядок и выбор не трогаем
  let savedOrder = currentOrder();

  // Выбор

  function setSelected(tile, on) {
    tile.classList.toggle('is-selected', on);
    buttonOf(tile).setAttribute('aria-pressed', String(on));
    if (on) selected.add(tile);
    else selected.delete(tile);
  }

  function toggleTile(tile, range) {
    if (range && anchor && anchor.isConnected && anchor !== tile) {
      const list = tiles();
      const [from, to] = [list.indexOf(anchor), list.indexOf(tile)].sort((a, b) => a - b);
      list.slice(from, to + 1).forEach(item => setSelected(item, true));
    } else {
      setSelected(tile, !selected.has(tile));
      anchor = tile;
    }
    syncToolbar();
  }

  function clearSelection() {
    Array.from(selected).forEach(tile => setSelected(tile, false));
    anchor = null;
    syncToolbar();
  }

  function syncToolbar() {
    const count = selected.size;
    actions.hidden = count === 0;
    hint.hidden = count > 0;
    selectedLabel.textContent = `Выбрано: ${count}`;
  }

  // Номера и подписи мест после любого изменения порядка
  function renumber() {
    tiles().forEach((tile, index) => {
      tile.querySelector('.manage-tile-number').textContent = String(index + 1).padStart(2, '0');
      buttonOf(tile).setAttribute('aria-label', `${tile.dataset.label}, место ${index + 1}`);
    });
  }

  // FLIP: остальные плитки плавно доезжают до новых мест, а не прыгают
  function flip(mutate) {
    if (reduceMotion.matches) {
      mutate();
      return;
    }
    const before = new Map(tiles().map(tile => [tile, tile.getBoundingClientRect()]));
    mutate();
    tiles().forEach(tile => {
      const from = before.get(tile);
      if (!from || tile.classList.contains('is-placeholder')) return;
      const to = tile.getBoundingClientRect();
      const dx = from.left - to.left;
      const dy = from.top - to.top;
      if (!dx && !dy) return;
      tile.animate(
        [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }],
        { duration: 220, easing: EASE }
      );
    });
  }

  // Сохранение порядка: запросы идут строго по очереди, чтобы старый
  // порядок не перезаписал новый, если ответы придут в другом порядке
  let saveTimer = null;
  let saveChain = Promise.resolve();
  let fadeTimer = null;

  function setSaveStatus(state, message) {
    clearTimeout(fadeTimer);
    saveStatus.classList.toggle('is-error', state === 'error');
    saveStatus.textContent = message || '';
    if (state === 'error') {
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'manage-retry';
      retry.textContent = 'Повторить';
      retry.addEventListener('click', () => scheduleSave(0));
      saveStatus.append(' ', retry);
    }
    if (state === 'saved') {
      fadeTimer = setTimeout(() => {
        saveStatus.textContent = '';
      }, 2500);
    }
  }

  function scheduleSave(delay = 500) {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      saveTimer = null;
      saveChain = saveChain.then(saveOrder);
    }, delay);
  }

  async function saveOrder() {
    const order = currentOrder();
    if (sameOrder(order, savedOrder)) return;
    setSaveStatus('saving', 'Сохраняем порядок...');
    try {
      await postJson(root.dataset.reorderUrl, { ids: order });
      savedOrder = order;
      if (!saveTimer) setSaveStatus('saved', 'Порядок сохранён');
    } catch (error) {
      setSaveStatus('error', `Порядок не сохранился: ${error.message}.`);
    }
  }

  const hasUnsavedOrder = () => !sameOrder(currentOrder(), savedOrder);

  window.addEventListener('beforeunload', event => {
    if (!hasUnsavedOrder()) return;
    event.preventDefault();
    event.returnValue = '';
  });

  async function postJson(url, body) {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': root.dataset.csrf,
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify(body),
    });
    const type = response.headers.get('content-type') || '';
    // Истёкшая сессия: запрос ушёл редиректом на страницу входа
    if (response.redirected && !type.includes('application/json')) {
      window.location.href = response.url;
      throw new Error('сессия истекла');
    }
    if (!type.includes('application/json')) {
      throw new Error(response.status === 403 ? 'обновите страницу' : `ошибка сервера ${response.status}`);
    }
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || `ошибка сервера ${response.status}`);
    return data;
  }

  // Перемещения порядка

  function moveTiles(movedTiles, where) {
    if (!movedTiles.length) return;
    flip(() => {
      if (where === 'top') {
        movedTiles.slice().reverse().forEach(tile => grid.prepend(tile));
      } else {
        movedTiles.forEach(tile => grid.append(tile));
      }
    });
    renumber();
    scheduleSave();
    movedTiles[0].scrollIntoView({ block: 'nearest', behavior: reduceMotion.matches ? 'auto' : 'smooth' });
    announce(where === 'top' ? `Перемещено в начало: ${movedTiles.length}` : `Перемещено в конец: ${movedTiles.length}`);
  }

  function announce(message) {
    announcer.textContent = message;
  }

  // Число колонок сетки: плитки первой строки стоят на одной высоте
  function columnCount() {
    const list = tiles();
    if (!list.length) return 1;
    const top = list[0].offsetTop;
    const count = list.findIndex(tile => tile.offsetTop !== top);
    return count === -1 ? list.length : count;
  }

  // Удаление

  function confirmDelete(count) {
    const title = dialog.querySelector('.manage-dialog-title');
    title.textContent = count === 1 ? 'Удалить это фото?' : `Удалить фото: ${count}?`;
    if (typeof dialog.showModal !== 'function') {
      return Promise.resolve(window.confirm(title.textContent));
    }
    return new Promise(resolve => {
      dialog.returnValue = '';
      dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true });
      dialog.showModal();
    });
  }

  async function deleteSelected() {
    const victims = tiles().filter(tile => selected.has(tile));
    if (!victims.length || busy) return;
    if (!(await confirmDelete(victims.length))) return;

    busy = true;
    root.classList.add('is-busy');
    setSaveStatus('saving', 'Удаляем...');
    const ids = victims.map(tileId);
    try {
      const data = await postJson(root.dataset.deleteUrl, { ids });
      victims.forEach(tile => setSelected(tile, false));
      anchor = null;
      await Promise.all(
        victims.map(tile =>
          tile
            .animate([{ opacity: 1 }, { opacity: 0, transform: 'scale(0.94)' }], {
              duration: reduceMotion.matches ? 120 : 200,
              easing: EASE,
              fill: 'forwards',
            })
            .finished.catch(() => {})
        )
      );
      flip(() => victims.forEach(tile => tile.remove()));
      savedOrder = savedOrder.filter(id => !ids.includes(id));
      renumber();
      syncToolbar();
      if (countBadge) countBadge.textContent = String(data.total);
      setSaveStatus('saved', `Удалено: ${data.deleted}`);
      announce(`Удалено фото: ${data.deleted}`);
      // Удалили всё: страница покажет пустое состояние со ссылкой на загрузку
      if (!tiles().length) window.location.reload();
    } catch (error) {
      setSaveStatus('error', `Не удалилось: ${error.message}.`);
    } finally {
      busy = false;
      root.classList.remove('is-busy');
    }
  }

  // Перетаскивание на Pointer Events: мышь начинает после сдвига на 6px,
  // палец - после удержания 350 мс, иначе это обычная прокрутка страницы

  let drag = null;
  let suppressClick = false;

  grid.addEventListener('pointerdown', event => {
    const tile = event.target.closest('.manage-tile');
    if (!tile || busy || drag || (event.pointerType === 'mouse' && event.button !== 0)) return;
    drag = {
      tile,
      pointerId: event.pointerId,
      type: event.pointerType,
      startX: event.clientX,
      startY: event.clientY,
      x: event.clientX,
      y: event.clientY,
      active: false,
      timer: null,
      raf: 0,
      ghost: null,
      startIndex: tiles().indexOf(tile),
    };
    if (event.pointerType !== 'mouse') {
      drag.timer = setTimeout(startDrag, 350);
    }
  });

  window.addEventListener('pointermove', event => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag.x = event.clientX;
    drag.y = event.clientY;
    if (!drag.active) {
      const distance = Math.hypot(drag.x - drag.startX, drag.y - drag.startY);
      if (drag.type === 'mouse' && distance > 6) startDrag();
      else if (drag.type !== 'mouse' && distance > 10) cancelPendingDrag();
      return;
    }
    moveGhost();
    updatePlaceholder();
  });

  window.addEventListener('pointerup', event => finishDrag(event));
  window.addEventListener('pointercancel', event => finishDrag(event));

  // Пока палец тащит фото, страница не прокручивается
  document.addEventListener(
    'touchmove',
    event => {
      if (drag && drag.active) event.preventDefault();
    },
    { passive: false }
  );

  // Долгое нажатие на фото не открывает меню "сохранить картинку"
  grid.addEventListener('contextmenu', event => {
    if (event.target.closest('.manage-tile')) event.preventDefault();
  });

  function cancelPendingDrag() {
    if (!drag) return;
    clearTimeout(drag.timer);
    drag = null;
  }

  function startDrag() {
    if (!drag || drag.active) return;
    clearTimeout(drag.timer);
    const { tile } = drag;
    const rect = tile.getBoundingClientRect();
    drag.active = true;
    drag.offsetX = drag.startX - rect.left;
    drag.offsetY = drag.startY - rect.top;

    const ghost = tile.cloneNode(true);
    ghost.classList.add('manage-ghost');
    ghost.classList.remove('is-placeholder');
    ghost.removeAttribute('data-id');
    ghost.setAttribute('aria-hidden', 'true');
    ghost.style.width = `${rect.width}px`;
    ghost.style.height = `${rect.height}px`;
    document.body.appendChild(ghost);
    drag.ghost = ghost;

    tile.classList.add('is-placeholder');
    document.body.classList.add('is-sorting');
    if (drag.type === 'touch' && navigator.vibrate) navigator.vibrate(8);
    moveGhost();
    autoScroll();
  }

  function moveGhost() {
    const x = drag.x - drag.offsetX;
    const y = drag.y - drag.offsetY;
    drag.ghost.style.transform = `translate(${x}px, ${y}px) scale(1.04)`;
  }

  function updatePlaceholder() {
    const under = document.elementFromPoint(drag.x, drag.y);
    const target = under && under.closest('.manage-tile');
    const list = tiles();
    const from = list.indexOf(drag.tile);

    if (target && target !== drag.tile && grid.contains(target)) {
      const to = list.indexOf(target);
      flip(() => grid.insertBefore(drag.tile, from < to ? target.nextSibling : target));
      return;
    }
    // Пустое место после последней плитки: фото уходит в конец
    const last = list[list.length - 1];
    if (under === grid && last !== drag.tile) {
      const rect = last.getBoundingClientRect();
      if (drag.y > rect.bottom || (drag.y > rect.top && drag.x > rect.right)) {
        flip(() => grid.append(drag.tile));
      }
    }
  }

  // У верхнего и нижнего края окна страница сама прокручивается
  function autoScroll() {
    if (!drag || !drag.active) return;
    const edge = 72;
    let dy = 0;
    if (drag.y < edge) dy = -Math.ceil((edge - drag.y) / 5);
    else if (drag.y > window.innerHeight - edge) dy = Math.ceil((drag.y - (window.innerHeight - edge)) / 5);
    if (dy) {
      window.scrollBy(0, dy);
      updatePlaceholder();
    }
    drag.raf = requestAnimationFrame(autoScroll);
  }

  function finishDrag(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const current = drag;
    drag = null;
    clearTimeout(current.timer);
    cancelAnimationFrame(current.raf);
    if (!current.active) return;

    // Клик после перетаскивания не должен ещё и выбирать фото
    suppressClick = true;
    setTimeout(() => {
      suppressClick = false;
    }, 0);

    const { tile, ghost } = current;
    document.body.classList.remove('is-sorting');
    const settle = () => {
      ghost.remove();
      tile.classList.remove('is-placeholder');
    };
    const rect = tile.getBoundingClientRect();
    if (reduceMotion.matches) {
      settle();
    } else {
      ghost
        .animate(
          [
            { transform: ghost.style.transform },
            { transform: `translate(${rect.left}px, ${rect.top}px) scale(1)` },
          ],
          { duration: 180, easing: EASE, fill: 'forwards' }
        )
        .finished.then(settle, settle);
    }

    const newIndex = tiles().indexOf(tile);
    if (newIndex !== current.startIndex) {
      renumber();
      scheduleSave();
      announce(`Фото на месте ${newIndex + 1}`);
    }
  }

  // Клавиатура и клики

  grid.addEventListener('click', event => {
    const tile = event.target.closest('.manage-tile');
    if (!tile || suppressClick || busy) return;
    toggleTile(tile, event.shiftKey);
  });

  grid.addEventListener('keydown', event => {
    const tile = event.target.closest('.manage-tile');
    if (!tile || busy) return;
    const list = tiles();
    const index = list.indexOf(tile);
    const step = {
      ArrowLeft: -1,
      ArrowRight: 1,
      ArrowUp: -columnCount(),
      ArrowDown: columnCount(),
    }[event.key];

    if (step !== undefined) {
      event.preventDefault();
      const target = Math.max(0, Math.min(list.length - 1, index + step));
      if (target === index) return;
      if (event.altKey) {
        // Alt со стрелками двигает фото, фокус едет вместе с ним
        flip(() => grid.insertBefore(tile, target > index ? list[target].nextSibling : list[target]));
        renumber();
        scheduleSave();
        buttonOf(tile).focus();
        announce(`Фото на месте ${target + 1}`);
      } else {
        buttonOf(list[target]).focus();
      }
      return;
    }
    if (event.key === 'Delete' && selected.size) {
      event.preventDefault();
      deleteSelected();
    }
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && selected.size && !(dialog && dialog.open)) clearSelection();
  });

  actions.addEventListener('click', event => {
    const button = event.target.closest('[data-action]');
    if (!button || busy) return;
    const chosen = tiles().filter(tile => selected.has(tile));
    const action = button.dataset.action;
    if (action === 'top' || action === 'bottom') moveTiles(chosen, action);
    else if (action === 'clear') clearSelection();
    else if (action === 'delete') deleteSelected();
  });
}
