// Завантаження імен із LocalStorage
const names = JSON.parse(localStorage.getItem('customNames')) || {};

// Завантаження перекладів за замовчуванням
fetch('assets/translations.json') // Шлях виправлено на assets/translations.json
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(defaultNames => {
        // Злиття імен з користувацькими та дефолтними, з пріоритетом на користувацькі
        for (let name in defaultNames) {
            if (names[name]) {
                names[name] = { ...defaultNames[name], ...names[name] };
            } else {
                names[name] = defaultNames[name];
            }
        }
        replaceNamesInText(); // Заміна імен після злиття
    })
    .catch(error => {
        console.error('Не вдалося завантажити translations.json:', error);
    });

// Завантаження списку глав у бокову панель
fetch('assets/chapters_config.json')
    .then(response => response.json())
    .then(config => {
        const chapterList = document.getElementById('chapter-list');
        config.chapters.forEach(chapter => {
            const listItem = document.createElement('li');
            const link = document.createElement('a');
            link.href = `chapter_template.html?chapter=${chapter.id}`;
            link.textContent = chapter.title;
            listItem.appendChild(link);
            chapterList.appendChild(listItem);
        });

        // Завантаження даних для конкретної глави
        const urlParams = new URLSearchParams(window.location.search);
        const chapterId = urlParams.get('chapter');
        if (chapterId) {
            const chapterConfig = config.chapters.find(ch => ch.id === chapterId);
            if (chapterConfig) {
                document.getElementById('chapter-title').textContent = chapterConfig.title;
                fetch(`../${chapterConfig.textFile}`)
                    .then(response => response.text())
                    .then(text => {
                        document.getElementById('chapter-text').innerHTML = text;
                        replaceNamesInText(); // Заміна імен у тексті
                    })
                    .catch(err => console.error('Помилка завантаження тексту:', err));
            } else {
                console.error('Глава не знайдена.');
            }
        }
    })
    .catch(err => console.error('Помилка завантаження конфігурації глав:', err));



// Функція для ініціалізації заголовка та тексту для кожної глави
function initializePage() {
    const chapterTitle = document.getElementById('chapter-title');
    const chapterText = document.getElementById('chapter-text');
    
    // Оновлення заголовку та тексту для конкретної глави
    if (window.location.pathname.includes('chapter1.html')) {
        chapterTitle.textContent = 'Глава 1';
        chapterText.textContent = 'Текст глави 1...';
    } else if (window.location.pathname.includes('chapter2.html')) {
        chapterTitle.textContent = 'Глава 2';
        chapterText.textContent = 'Текст глави 2...';
    }
    // Додати більше перевірок для інших глав...
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

// ініціалізація кнопки редагування
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

// Згортання/розгортання бічної панелі
function initializeSidebarToggle() {
    const toggleButton = document.getElementById('toggle-sidebar');
    const sidebar = document.getElementById('sidebar');
    if (toggleButton) {
        toggleButton.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            toggleButton.textContent = sidebar.classList.contains('collapsed') ? 'Зміст' : 'Зміст';
        });
    }
}

// Викликати функцію для ініціалізації кнопки редагування та бічної панелі
initializeEditButton();
initializeSidebarToggle();
replaceNamesInText();
