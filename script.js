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
fetch('assets/chapters.json')
    .then(response => response.json())
    .then(majorChapters => {
        const chapterList = document.getElementById('chapter-list');

        majorChapters.forEach(majorChapter => {
            // Створюємо li для основної глави
            const majorLi = document.createElement('li');
            majorLi.textContent = `${majorChapter.id}. ${majorChapter.title}`;
            chapterList.appendChild(majorLi);

            // Створюємо вкладений ul для підглав
            const subUl = document.createElement('ul');
            majorLi.appendChild(subUl);

            // Додаємо підглави
            majorChapter.chapters.forEach(subChapter => {
                const subLi = document.createElement('li');
                const link = document.createElement('a');

                // Формуємо посилання з двома параметрами: major та sub
                // Наприклад: chapter_template.html?major=1&sub=1.1
                link.href = `chapter_template.html?major=${majorChapter.id}&sub=${subChapter.id}`;

                // Текст посилання — лише "1.1", "1.2" і т.д.
                link.textContent = subChapter.id;

                subLi.appendChild(link);
                subUl.appendChild(subLi);
            });
        });

        // Після побудови меню обробляємо URL, щоб завантажити потрібну підглаву
        loadChapter(majorChapters);
    })
    .catch(err => console.error('Помилка завантаження конфігурації глав:', err));

function loadChapter(majorChapters) {
    const urlParams = new URLSearchParams(window.location.search);
    const majorId = urlParams.get('major'); // Напр. "1"
    const subId = urlParams.get('sub');     // Напр. "1.1"

    // Якщо параметрів немає, нічого не робимо (можливо, це головна сторінка)
    if (!majorId || !subId) return;

    // Знаходимо основну главу
    const majorChapterConfig = majorChapters.find(ch => ch.id === majorId);
    if (!majorChapterConfig) {
        console.error('Основна глава не знайдена:', majorId);
        return;
    }

    // Знаходимо підглаву
    const subChapterConfig = majorChapterConfig.chapters.find(sub => sub.id === subId);
    if (!subChapterConfig) {
        console.error('Підглава не знайдена:', subId);
        return;
    }

    // Формуємо заголовок: "Визрівання 1.1"
    const chapterTitle = document.getElementById('chapter-title');
    chapterTitle.textContent = `${majorChapterConfig.title} ${subChapterConfig.id}`;

    // Завантажуємо файл із текстом
    fetch(subChapterConfig.textFile)
        .then(response => response.text())
        .then(text => {
            document.getElementById('chapter-text').innerHTML = text;
            replaceNamesInText(); // ваша функція для заміни імен
        })
        .catch(err => console.error('Помилка завантаження тексту:', err));

    // Аудіо, якщо воно є
    if (subChapterConfig.audioFile) {
        const audioContainer = document.getElementById('audio-container');
        // Очищаємо контейнер на випадок, якщо вже був інший аудіоплеєр
        audioContainer.innerHTML = '';
        const audioPlayer = document.createElement('audio');
        audioPlayer.controls = true;
        audioPlayer.src = subChapterConfig.audioFile;
        audioPlayer.type = 'audio/mpeg';
        audioContainer.appendChild(audioPlayer);
    }
}


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
        const nameForm = element.dataset.form || 'однина'; // за замовчуванням однина
        const caseForm = element.dataset.case || 'називний'; // за замовчуванням називний відмінок
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

    const homeButton = document.getElementById('back-to-home');
    if (homeButton) {
        homeButton.addEventListener('click', function () {
            window.location.href = "index.html";
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
            toggleButton.textContent = sidebar.classList.contains('collapsed') ? 'Розгорнути зміст' : 'Згорнути зміст';
        });
    }
}

// Викликати функцію для ініціалізації кнопки редагування та бічної панелі
initializeEditButton();
initializeSidebarToggle();
replaceNamesInText();
