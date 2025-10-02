import { updateComment } from './api.js';

let activeTextarea = null;

async function finishEditing() {
    if (!activeTextarea) return;

    const textarea = activeTextarea;
    const cell = textarea.closest('.comment-cell');
    const span = cell.querySelector('.editable-comment');
    const originalComment = textarea.dataset.originalValue;
    const newComment = textarea.value.trim();

    activeTextarea = null;
    textarea.remove();
    span.style.display = '';

    if (newComment === originalComment) {
        span.textContent = originalComment;
        return;
    }

    span.textContent = newComment;

    try {
        const vacancyName = cell.dataset.vacancyName;
        await updateComment(vacancyName, newComment);
    } catch (error) {
        console.error('Сетевая ошибка при сохранении:', error);
        alert('Ошибка при сохранении: ' + error.message);
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

function handleTableClick(event) {
    const cell = event.target.closest('.comment-cell');

    if (!cell || cell.querySelector('textarea')) {
        return;
    }

    const span = cell.querySelector('.editable-comment');
    if (span) {
        switchToEditMode(span, cell);
    }
}

export function initCommentEditing() {
    const tableBody = document.querySelector('table tbody');
    if (tableBody) {
        tableBody.addEventListener('click', handleTableClick);
    }
}