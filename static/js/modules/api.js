/**
 * @returns {Promise<Object>}
 */
export async function getStatus() {
    const response = await fetch('/status');
    if (!response.ok) {
        throw new Error('Ошибка при получении статуса.');
    }
    return response.json();
}

/**
 * @returns {Promise<Object>}
 */
export async function refreshReport() {
    const response = await fetch('/refresh-report', { method: 'POST' });
    return response.json();
}

/**
 * @param {string} vacancyName
 * @param {string} newComment
 * @returns {Promise<Object>}
 */
export async function updateComment(vacancyName, newComment) {
    const response = await fetch('/update-comment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vacancy_name: vacancyName, comment: newComment })
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Неизвестная ошибка сохранения');
    }

    return response.json();
}