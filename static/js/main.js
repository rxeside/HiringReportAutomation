// Глобальные переменные для графиков и селектов
let funnelChart = null;
let rejectionChart = null;
let vacancyTomSelect = null;
let recruiterTomSelect = null;

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Установка дат (последние 90 дней по умолчанию)
    const dateEndInput = document.getElementById('date-end');
    const dateStartInput = document.getElementById('date-start');
    
    const today = new Date();
    const pastDate = new Date();
    pastDate.setDate(today.getDate() - 90);

    dateEndInput.valueAsDate = today;
    dateStartInput.valueAsDate = pastDate;

    // 2. Инициализация селектов и загрузка списка фильтров
    await initFilters();

    // 3. Загрузка данных
    await loadAnalytics();

    // 4. Кнопка "Применить"
    document.getElementById('apply-filters').addEventListener('click', loadAnalytics);
});

async function initFilters() {
    try {
        const response = await fetch('/api/filters');
        const data = await response.json();

        // Вакансии
        const vacancySelect = document.getElementById('vacancy-select');
        data.vacancies.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v;
            opt.text = v;
            vacancySelect.appendChild(opt);
        });
        
        vacancyTomSelect = new TomSelect(vacancySelect, {
            plugins: ['remove_button'],
            maxItems: null
        });

        // Рекрутеры
        const recruiterSelect = document.getElementById('recruiter-select');
        Object.entries(data.coworkers).forEach(([id, name]) => {
            const opt = document.createElement('option');
            opt.value = id;
            opt.text = name;
            recruiterSelect.appendChild(opt);
        });

        recruiterTomSelect = new TomSelect(recruiterSelect, {
            plugins: ['remove_button'],
            maxItems: null
        });

    } catch (e) {
        console.error("Ошибка загрузки фильтров:", e);
    }
}

async function loadAnalytics() {
    const startDate = document.getElementById('date-start').value;
    const endDate = document.getElementById('date-end').value;
    
    // Получаем значения из TomSelect
    const vacancies = vacancyTomSelect ? vacancyTomSelect.getValue() : [];
    const recruiters = recruiterTomSelect ? recruiterTomSelect.getValue() : [];

    const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate
    });
    
    vacancies.forEach(v => params.append('vacancies', v));
    recruiters.forEach(r => params.append('recruiters', r));

    try {
        const response = await fetch(`/api/analytics?${params.toString()}`);
        const data = await response.json();

        if (data.error) {
            alert("Ошибка API: " + data.error);
            return;
        }

        updateKPI(data);
        renderFunnelChart(data.funnel);
        renderConversionTable(data.funnel);
        renderRejectionChart(data.rejections);
        renderSourcesList(data.sources);

    } catch (e) {
        console.error("Ошибка сети:", e);
    }
}

function updateKPI(data) {
    document.getElementById('kpi-total').textContent = data.total_candidates;
    document.getElementById('kpi-time').innerHTML = `${data.avg_time_to_offer} <span class="unit">дн.</span>`;
    
    // Ищем кол-во вышедших на работу (или принявших оффер)
    const hiredStage = data.funnel.find(s => s.stage === 'вышел на работу');
    document.getElementById('kpi-hired').textContent = hiredStage ? hiredStage.count : 0;
}

function renderFunnelChart(funnelData) {
    const ctx = document.getElementById('funnelChart').getContext('2d');
    const labels = funnelData.map(d => d.stage);
    const values = funnelData.map(d => d.count);

    if (funnelChart) funnelChart.destroy();

    funnelChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Кандидатов',
                data: values,
                backgroundColor: '#3b82f6',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y', // Горизонтальный
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } }
        }
    });
}

function renderRejectionChart(rejections) {
    const ctx = document.getElementById('rejectionChart').getContext('2d');
    
    // Берем топ 10
    const topRejections = rejections.sort((a,b) => b.count - a.count).slice(0, 10);
    const labels = topRejections.map(d => d.reason);
    const values = topRejections.map(d => d.count);

    if (rejectionChart) rejectionChart.destroy();

    rejectionChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Отказов',
                data: values,
                backgroundColor: '#ef4444',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } }
        }
    });
}

function renderConversionTable(funnelData) {
    const tbody = document.querySelector('#conversion-table tbody');
    tbody.innerHTML = '';

    funnelData.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.stage}</td>
            <td class="text-right"><b>${row.count}</b></td>
            <td class="text-right">${row.conversion_step}</td>
            <td class="text-right" style="color:#6b7280">${row.conversion_total}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderSourcesList(sources) {
    const container = document.getElementById('sources-list');
    container.innerHTML = '';
    
    sources.sort((a,b) => b.count - a.count).forEach(item => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `
            <span class="list-label">${item.source}</span>
            <span class="list-value">${item.count}</span>
        `;
        container.appendChild(div);
    });
}