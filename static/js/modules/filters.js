let recruiterTomSelect, vacancyTomSelect;

function applyFilters() {
    const priorityToggle = document.getElementById('priority-toggle');
    const selectedRecruiterIds = recruiterTomSelect ? recruiterTomSelect.getValue() : [];
    const selectedVacancyNames = vacancyTomSelect ? vacancyTomSelect.getValue() : [];
    const rows = document.querySelectorAll('table tbody tr');
    const showOnlyPriority = priorityToggle.checked;

    rows.forEach(row => {
        const isPriority = row.dataset.priority === 'true';
        const memberIds = JSON.parse(row.dataset.members || '[]');
        const vacancyName = row.dataset.vacancyName;

        const priorityMatch = !showOnlyPriority || isPriority;

        const recruiterMatch = selectedRecruiterIds.length === 0 ||
            selectedRecruiterIds.map(id => parseInt(id, 10)).some(id => memberIds.includes(id));

        const vacancyMatch = selectedVacancyNames.length === 0 ||
            selectedVacancyNames.includes(vacancyName);

        row.classList.toggle('hidden-by-filters', !(priorityMatch && recruiterMatch && vacancyMatch));
    });
}

/**
 * @param {Object} coworkersData
 * @param {Array} reportData
 */
export function initFilters(coworkersData, reportData) {
    const priorityToggle = document.getElementById('priority-toggle');
    const recruiterFilterElement = document.getElementById('recruiter-filter');
    const vacancyFilterElement = document.getElementById('vacancy-filter');

    if (priorityToggle) {
        priorityToggle.addEventListener('change', applyFilters);
    }

    const recruiterOptions = Object.entries(coworkersData).map(([id, name]) => ({ value: id, text: name }));
    recruiterTomSelect = new TomSelect(recruiterFilterElement, {
        options: recruiterOptions,
        plugins: ['remove_button'],
        onItemAdd: function() {
                this.setTextboxValue('');
                this.blur();
            },
        onChange: applyFilters
    });

    if (reportData && reportData.length > 0) {
        const vacancyOptions = reportData.map(row => ({
            value: row['название вакансии'],
            text: row['название вакансии']
        }));
        vacancyTomSelect = new TomSelect(vacancyFilterElement, {
            options: vacancyOptions,
            plugins: ['remove_button'],
            onItemAdd: function() {
                this.setTextboxValue('');
                this.blur();
            },
            onChange: applyFilters
        });
    }

    applyFilters();
}