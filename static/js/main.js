let funnelChart = null;
let rejectionChart = null;
let vacancyTomSelect = null;
let recruiterTomSelect = null;
let stateTomSelect = null;

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('refreshButton').addEventListener('click', handleRefreshClick);

    document.getElementById('toggle-rejections-btn').addEventListener('click', function() {
        const container = document.getElementById('all-rejections-container');
        if (container.style.display === 'none') {
            container.style.display = 'block';
            this.textContent = 'Скрыть таблицу причин';
        } else {
            container.style.display = 'none';
            this.textContent = 'Показать все причины (Таблица)';
        }
    });

    const dateEndInput = document.getElementById('date-end');
    const dateStartInput = document.getElementById('date-start');
    const today = new Date();
    const pastDate = new Date();
    pastDate.setDate(today.getDate() - 90);
    dateEndInput.valueAsDate = today;
    dateStartInput.valueAsDate = pastDate;

    await initFilters();
    await loadAnalytics();

    document.getElementById('apply-filters').addEventListener('click', loadAnalytics);
});

async function initFilters() {
    stateTomSelect = new TomSelect('#state-select', { plugins: ['remove_button'], maxItems: null });

    try {
        const response = await fetch('/api/filters');
        const data = await response.json();

        const vacancySelect = document.getElementById('vacancy-select');
        data.vacancies.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v; opt.text = v;
            vacancySelect.appendChild(opt);
        });
        vacancyTomSelect = new TomSelect(vacancySelect, { plugins: ['remove_button'], maxItems: null });

        const recruiterSelect = document.getElementById('recruiter-select');
        Object.entries(data.coworkers).forEach(([id, name]) => {
            const opt = document.createElement('option');
            opt.value = id; opt.text = name;
            recruiterSelect.appendChild(opt);
        });
        recruiterTomSelect = new TomSelect(recruiterSelect, { plugins: ['remove_button'], maxItems: null });

    } catch (e) {
        console.error("Ошибка загрузки фильтров:", e);
    }
}

async function loadAnalytics() {
    const params = new URLSearchParams({
        start_date: document.getElementById('date-start').value,
        end_date: document.getElementById('date-end').value
    });

    if(vacancyTomSelect) vacancyTomSelect.getValue().forEach(v => params.append('vacancies', v));
    if(recruiterTomSelect) recruiterTomSelect.getValue().forEach(r => params.append('recruiters', r));
    if(stateTomSelect) stateTomSelect.getValue().forEach(s => params.append('states', s));

    try {
        const response = await fetch(`/api/analytics?${params.toString()}`);
        const data = await response.json();

        if (data.error) return alert("Ошибка API: " + data.error);

        updateKPI(data);
        renderFunnelChart(data.funnel);
        renderConversionTable(data.funnel);

        renderRejectionChart(data.rejections_flat);

        renderRejectionsTable(data.rejections_flat);
        renderSourcesTable(data.sources);

    } catch (e) {
        console.error("Ошибка сети:", e);
    }
}

function updateKPI(data) {
    document.getElementById('kpi-total').textContent = data.total_candidates;
    document.getElementById('kpi-vacancies').textContent = data.active_vacancies;
    document.getElementById('kpi-time').innerHTML = `${data.avg_time_to_offer} <span class="unit">календ. дн.</span>`;
}

function renderFunnelChart(funnelData) {
    const ctx = document.getElementById('funnelChart').getContext('2d');
    if (funnelChart) funnelChart.destroy();

    funnelChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: funnelData.map(d => d.stage),
            datasets: [{
                label: 'Кандидатов',
                data: funnelData.map(d => d.count),
                backgroundColor: '#3b82f6',
                borderRadius: 4
            }]
        },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
}

function renderRejectionChart(rejectionsFlat) {
    const ctx = document.getElementById('rejectionChart').getContext('2d');
    if (rejectionChart) rejectionChart.destroy();

    const topRejections = rejectionsFlat.sort((a,b) => b.count - a.count).slice(0, 10);
    const labels = topRejections.map(d => d.reason);
    const values = topRejections.map(d => d.count);

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
            plugins: {
                legend: { display: false },
                tooltip: { mode: 'nearest', intersect: true }
            }
        }
    });
}

function renderRejectionsTable(rejectionsFlat) {
    const tbody = document.querySelector('#rejections-table tbody');
    tbody.innerHTML = '';
    rejectionsFlat.sort((a,b) => b.count - a.count).forEach(r => {
        tbody.innerHTML += `
            <tr>
                <td>${r.reason}</td>
                <td class="text-right"><b>${r.count}</b></td>
                <td class="text-right" style="color:#6b7280">${r.percent}</td>
            </tr>`;
    });
}

function renderSourcesTable(sources) {
    const tbody = document.querySelector('#sources-table tbody');
    tbody.innerHTML = '';
    sources.sort((a,b) => b.total - a.total).forEach(row => {
        tbody.innerHTML += `
            <tr>
                <td>${row.source}</td>
                <td class="text-right"><b>${row.total}</b></td>
                <td class="text-right" style="color:#10b981"><b>${row.hired}</b></td>
                <td class="text-right" style="color:#3b82f6"><b>${row.probation}</b></td>
            </tr>`;
    });
}

function renderConversionTable(funnelData) {
    const tbody = document.querySelector('#conversion-table tbody');
    tbody.innerHTML = '';
    funnelData.forEach(row => {
        tbody.innerHTML += `
            <tr>
                <td>${row.stage}</td>
                <td class="text-right"><b>${row.count}</b></td>
                <td class="text-right">${row.conversion_step}</td>
                <td class="text-right" style="color:#6b7280">${row.conversion_total}</td>
            </tr>`;
    });
}

async function handleRefreshClick() {
    try {
        const response = await fetch('/refresh-report', { method: 'POST' });
        const data = await response.json();
        if (response.ok) { updateStatusUI({ is_updating: true }); }
        else { alert('Ошибка: ' + (data.message || 'Не удалось запустить обновление.')); }
    } catch (error) { alert('Произошла ошибка при отправке запроса на обновление.'); }
}

function updateStatusUI(status) {
    const overlay = document.getElementById('update-overlay');
    const btn = document.getElementById('refreshButton');

    if (status.is_updating) {
        overlay.classList.remove('hidden'); btn.disabled = true; btn.textContent = 'Обновление...';
    } else {
        overlay.classList.add('hidden'); btn.disabled = false; btn.textContent = 'Обновить сейчас';
    }

    if (status.last_updated_str) {
        document.getElementById('last-updated-date').textContent = status.last_updated_str;
    }
}

let wasUpdating = false;
setInterval(async () => {
    try {
        const response = await fetch('/status');
        const status = await response.json();
        updateStatusUI(status);
        if (wasUpdating && !status.is_updating) window.location.reload();
        wasUpdating = status.is_updating;
    } catch (e) {}
}, 5000);