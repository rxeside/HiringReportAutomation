const elements = {
    overlay: document.getElementById('update-overlay'),
    refreshButton: document.getElementById('refreshButton'),
    lastUpdatedSpan: document.getElementById('last-updated-time'),
};

/**
 * Обновляет UI на основе статуса от сервера.
 * @param {Object} status - { is_updating: boolean, last_updated_str: string }
 */
export function updateStatusUI(status) {
    if (status.is_updating) {
        elements.overlay.classList.remove('hidden');
        if (elements.refreshButton) {
            elements.refreshButton.disabled = true;
            elements.refreshButton.textContent = 'Обновление...';
        }
    } else {
        elements.overlay.classList.add('hidden');
        if (elements.refreshButton) {
            elements.refreshButton.disabled = false;
            elements.refreshButton.textContent = 'Обновить сейчас';
        }
    }

    if (elements.lastUpdatedSpan && status.last_updated) {
        elements.lastUpdatedSpan.textContent = `Последнее обновление: ${status.last_updated} МСК`;
    }
}

export function initRefreshButton(onClick) {
    if (elements.refreshButton) {
        elements.refreshButton.addEventListener('click', onClick);
    }
}