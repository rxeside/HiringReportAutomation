import { getStatus, refreshReport } from './modules/api.js';
import { updateStatusUI, initRefreshButton } from './modules/ui.js';
import { initFilters } from './modules/filters.js';
import { initCommentEditing } from './modules/comments.js';

function main() {
    const appContainer = document.getElementById('app-container');
    if (!appContainer) {
        console.error('Не найден корневой элемент приложения #app-container');
        return;
    }

    const coworkersData = JSON.parse(appContainer.dataset.coworkers || '{}');
    const reportData = JSON.parse(appContainer.dataset.report || '[]');

    let wasUpdating = false;

    initFilters(coworkersData, reportData);
    initCommentEditing();
    initRefreshButton(handleRefreshClick);
    
    const pollStatus = async () => {
        try {
            const status = await getStatus();
            updateStatusUI(status);

            if (wasUpdating && !status.is_updating) {
                window.location.reload();
            }
            wasUpdating = status.is_updating;
        } catch (error) {
            console.error(error.message);
        }
    };
    
    setInterval(pollStatus, 5000);
    pollStatus();

    async function handleRefreshClick() {
        try {
            const data = await refreshReport();
            if (data.message === "Обновление запущено в фоновом режиме.") {
                updateStatusUI({ is_updating: true });
            } else {
                alert('Ошибка: ' + (data.message || 'Не удалось запустить обновление.'));
            }
        } catch (error) {
            console.error('Сетевая ошибка при запуске обновления:', error);
            alert('Произошла ошибка при отправке запроса на обновление.');
        }
    }
}

document.addEventListener('DOMContentLoaded', main);