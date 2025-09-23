document.addEventListener('DOMContentLoaded', () => {
    let wasUpdating = false;

    initCommentEditing();
    initFilters();
    initRefreshButton();

    const pollStatus = async () => {
        try {
            const response = await fetch('/status');
            if (!response.ok) {
                console.error('Ошибка при получении статуса.');
                return;
            }
            const status = await response.json();

            updateUI(status);

            if (wasUpdating && !status.is_updating) {
                window.location.reload();
            }

            wasUpdating = status.is_updating;

        } catch (error) {
            console.error('Сетевая ошибка при опросе статуса:', error);
        }
    };

    setInterval(pollStatus, 5000);
    pollStatus();
});


function updateUI(status) {
    const overlay = document.getElementById('update-overlay');
    const refreshButton = document.getElementById('refreshButton');
    const lastUpdatedSpan = document.getElementById('last-updated-time');

    if (status.is_updating) {
        overlay.classList.remove('hidden');
        if (refreshButton) {
            refreshButton.disabled = true;
            refreshButton.textContent = 'Обновление...';
        }
    } else {
        overlay.classList.add('hidden');
        if (refreshButton) {
            refreshButton.disabled = false;
            refreshButton.textContent = 'Обновить сейчас';
        }
    }

    if (lastUpdatedSpan && status.last_updated_str) {
        lastUpdatedSpan.textContent = status.last_updated_str;
    }
}


function initRefreshButton() {
    const refreshButton = document.getElementById('refreshButton');
    if (refreshButton) {
        refreshButton.addEventListener('click', async function() {
            try {
                const response = await fetch('/refresh-report', { method: 'POST' });
                const data = await response.json();

                if (response.ok) {
                    updateUI({ is_updating: true, last_updated_str: document.getElementById('last-updated-time')?.textContent });
                } else {
                    alert('Ошибка: ' + (data.message || 'Не удалось запустить обновление.'));
                }
            } catch (error) {
                console.error('Сетевая ошибка при запуске обновления:', error);
                alert('Произошла ошибка при отправке запроса на обновление.');
            }
        });
    }
}


function initCommentEditing() {
    const tableBody = document.querySelector('table tbody');
    if (tableBody) {
        tableBody.addEventListener('click', handleTableClick);
    }
}

function initFilters() {
    const priorityToggle = document.getElementById('priority-toggle');
    const recruiterFilterElement = document.getElementById('recruiter-filter');

    if (priorityToggle) {
        priorityToggle.addEventListener('change', applyFilters);
    }

    const recruiterOptions = Object.entries(window.coworkersData).map(([id, name]) => ({
        value: id,
        text: name
    }));

    new TomSelect(recruiterFilterElement, {
        options: recruiterOptions,
        items: ['all'],
        allowEmptyOption: true,
        plugins: ['clear_button'],
        onChange: function() {
            applyFilters();
        }
    });

    applyFilters();
}

function applyFilters() {
    const priorityToggle = document.getElementById('priority-toggle');
    const tomSelectInstance = document.getElementById('recruiter-filter').tomselect;
    const selectedRecruiterId = tomSelectInstance.getValue();

    const rows = document.querySelectorAll('table tbody tr');

    const showOnlyPriority = priorityToggle.checked;

    rows.forEach(row => {
        const isPriority = row.dataset.priority === 'true';
        const priorityMatch = !showOnlyPriority || isPriority;

        let recruiterMatch = false;
        if (selectedRecruiterId === 'all' || selectedRecruiterId === '') {
            recruiterMatch = true;
        } else {
            const memberIds = JSON.parse(row.dataset.members || '[]');
            if (memberIds.includes(parseInt(selectedRecruiterId, 10))) {
                recruiterMatch = true;
            }
        }

        if (priorityMatch && recruiterMatch) {
            row.classList.remove('hidden-by-filters');
        } else {
            row.classList.add('hidden-by-filters');
        }
    });
}


let activeTextarea = null;

function handleTableClick(event) {
    const cell = event.target.closest('.comment-cell');
    if (!cell || cell.querySelector('textarea')) {
        return;
    }
    const span = cell.querySelector('.editable-comment');
    if (!span) return;
    switchToEditMode(span, cell);
}

function switchToEditMode(span, cell) {
    const originalComment = span.textContent.trim();
    activeTextarea = document.createElement('textarea');
    activeTextarea.className = 'editing-comment';
    activeTextarea.value = originalComment;
    activeTextarea.dataset.originalValue = originalComment;
    span.style.display = 'none';
    cell.appendChild(activeTextarea);
    activeTextarea.focus();
    activeTextarea.select();
    activeTextarea.addEventListener('blur', finishEditing);
    activeTextarea.addEventListener('keydown', handleKeyDown);
}

async function finishEditing() {
    if (!activeTextarea) return;
    const textarea = activeTextarea;
    const cell = textarea.closest('.comment-cell');
    const span = cell.querySelector('.editable-comment');
    const originalComment = textarea.dataset.originalValue;
    const newComment = textarea.value.trim();
    activeTextarea = null;
    textarea.removeEventListener('blur', finishEditing);
    textarea.removeEventListener('keydown', handleKeyDown);
    if (textarea.parentNode) {
        textarea.parentNode.removeChild(textarea);
    }
    span.style.display = '';
    if (newComment === originalComment) {
        span.textContent = originalComment;
        return;
    }
    span.textContent = newComment;
    try {
        const vacancyName = cell.dataset.vacancyName;
        const response = await fetch('/update-comment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vacancy_name: vacancyName, comment: newComment })
        });
        if (!response.ok) {
            const data = await response.json();
            console.error('Ошибка сохранения на сервере:', data);
            alert('Ошибка при сохранении: ' + (data.detail || 'Неизвестная ошибка'));
            span.textContent = originalComment;
        }
    } catch (error) {
        console.error('Сетевая ошибка при сохранении:', error);
        alert('Произошла сетевая ошибка. Изменения не сохранены.');
        span.textContent = originalComment;
    }
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        event.target.blur();
    } else if (event.key === 'Escape') {
        event.target.value = event.target.dataset.originalValue;
        event.target.blur();
    }
}