// Завантаження імен із LocalStorage
const names = JSON.parse(localStorage.getItem('customNames')) || {};

// Завантаження перекладів за замовчуванням
fetch('assets/translations.json')
    .then(response => response.json())
    .then(defaultNames => {
        // Об'єднати імена з LocalStorage та початкових даних
        Object.assign(names, defaultNames);
        replaceNamesInText();
    });

// Редагування імен
document.getElementById('edit-names').addEventListener('click', () => {
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

// Функція для заміни імен у тексті
function replaceNamesInText() {
    document.querySelectorAll('[data-name]').forEach(element => {
        const originalName = element.dataset.name;
        const translation = names[originalName]?.singular?.nominative || originalName;
        element.textContent = translation;
    });
}
