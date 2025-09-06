document.addEventListener('DOMContentLoaded', () => {
    initRefreshButton();
    initCommentEditing();
    initFilters();
});

function initRefreshButton() {
    const refreshButton = document.getElementById('refreshButton');
    if (refreshButton) {
        refreshButton.addEventListener('click', handleRefreshClick);
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
    const recruiterFilter = document.getElementById('recruiter-filter');

    if (priorityToggle) {
        priorityToggle.addEventListener('change', applyFilters);
    }
    if (recruiterFilter) {
        recruiterFilter.addEventListener('change', applyFilters);
    }

    applyFilters();
}

function applyFilters() {
    const priorityToggle = document.getElementById('priority-toggle');
    const recruiterFilter = document.getElementById('recruiter-filter');
    const rows = document.querySelectorAll('table tbody tr');

    const showOnlyPriority = priorityToggle.checked;
    const selectedRecruiterId = recruiterFilter.value;

    rows.forEach(row => {
        const isPriority = row.dataset.priority === 'true';
        const priorityMatch = !showOnlyPriority || isPriority;

        let recruiterMatch = false;
        if (selectedRecruiterId === 'all') {
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

async function handleRefreshClick() {
    const button = this;
    button.disabled = true;
    button.textContent = 'Обновление...';

    try {
        const response = await fetch('/refresh-report', { method: 'POST' });
        const data = await response.json();
        if (response.ok) {
            alert(data.message + '\nСтраница будет перезагружена.');
            window.location.reload();
        } else {
            alert('Ошибка при обновлении: ' + (data.detail || 'Неизвестная ошибка'));
        }
    } catch (error) {
        console.error('Сетевая ошибка при обновлении:', error);
        alert('Произошла ошибка при отправке запроса на обновление.');
    } finally {
        button.disabled = false;
        button.textContent = 'Обновить сейчас';
    }
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