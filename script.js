// Завантаження імен із LocalStorage
const names = JSON.parse(localStorage.getItem('customNames')) || {};

// Завантаження перекладів за замовчуванням
fetch('../assets/translations.json') // Шлях виправлено на assets/translations.json
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(defaultNames => {
        // Об'єднати імена з LocalStorage та початкових даних
        Object.assign(names, defaultNames);
        replaceNamesInText();
    })
    .catch(error => {
        console.error('Не вдалося завантажити translations.json:', error);
    });

// Редагування імен
function initializeEditButton() {
    const editButton = document.getElementById('edit-names');
    if (editButton) {
        editButton.addEventListener('click', () => {
            const userNames = prompt("Введіть свої переклади імен у форматі JSON:", JSON.stringify(names, null, 2));
            if (userNames) {
                try {
                    const parsedNames = JSON.parse(userNames);
                    Object.assign(names, parsedNames);
                    localStorage.setItem('customNames', JSON.stringify(names));
                    replaceNamesInText();
                    alert("Імена збережено!");
                } catch (e) {
                    alert("Помилка в форматі JSON!");
                }
            }
        });
    }
}

// Функція для заміни імен у тексті
function replaceNamesInText() {
    document.querySelectorAll('[data-name]').forEach(element => {
        const originalName = element.dataset.name;
        const nameForm = element.dataset.form || 'singular'; // за замовчуванням однина
        const caseForm = element.dataset.case || 'nominative'; // за замовчуванням називний відмінок
        const translation = names[originalName]?.[nameForm]?.[caseForm] || originalName;
        element.textContent = translation;
    });
}

// Викликати функцію для ініціалізації кнопки редагування лише якщо вона існує
initializeEditButton();
