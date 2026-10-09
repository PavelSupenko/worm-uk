// Rough guesses of Ukrainian declension for a reader's own name, so a phone
// user only has to type the nominative. Covers common single-word patterns;
// the editor asks the reader to check the result.
import { CASES } from './names.js';

const SIBILANTS = 'жчшщ';
const CONSONANTS = 'бвгґджзклмнпрстфхцчшщ';
const ALTERNATION = { к: 'ц', г: 'з', х: 'с' }; // Сука → Суці, Морок → Мороці

// Returns { однина: {7 cases}, множина: {7 cases} } or null when the word is
// probably indeclinable or too ambiguous to guess (several words, -ь, -о...)
export function guessForms(nominative) {
    const word = nominative.trim();
    if (!word || /\s/.test(word)) return null;
    const lower = word.toLowerCase();
    const last = lower.at(-1);
    const stem = word.slice(0, -1);
    const stemLast = lower.at(-2) ?? '';
    let singular;
    let plural;

    if (lower.endsWith('ий')) {
        // Adjectival: Вартовий
        const base = word.slice(0, -2);
        singular = [word, base + 'ого', base + 'ому', base + 'ого', base + 'им', base + 'ому', word];
        plural = [base + 'і', base + 'их', base + 'им', base + 'их', base + 'ими', base + 'их', base + 'і'];
    } else if (last === 'а' && CONSONANTS.includes(stemLast)) {
        // Сука, Бакуда, Комашка
        const soft = SIBILANTS.includes(stemLast);
        const y = soft ? 'і' : 'и';
        const dative = (soft ? stem : alternate(stem)) + 'і';
        const genitivePlural = insertVowel(stem);
        singular = [word, stem + y, dative, stem + 'у', stem + (soft ? 'ею' : 'ою'), dative, stem + 'о'];
        plural = [stem + y, genitivePlural, stem + 'ам', genitivePlural, stem + 'ами', stem + 'ах', stem + y];
    } else if (last === 'я' && CONSONANTS.includes(stemLast)) {
        // Наклепниця
        singular = [word, stem + 'і', stem + 'і', stem + 'ю', stem + 'ею', stem + 'і', stem + 'е'];
        plural = [stem + 'і', stem + 'ь', stem + 'ям', stem + 'ь', stem + 'ями', stem + 'ях', stem + 'і'];
    } else if (last === 'й') {
        // Сергій
        singular = [word, stem + 'я', stem + 'ю', stem + 'я', stem + 'єм', stem + 'ї', stem + 'ю'];
        plural = [stem + 'ї', stem + 'їв', stem + 'ям', stem + 'їв', stem + 'ями', stem + 'ях', stem + 'ї'];
    } else if (CONSONANTS.includes(last)) {
        // Masculine: Морок, Регент
        const soft = SIBILANTS.includes(last);
        const velar = last in ALTERNATION;
        const y = soft ? 'і' : 'и';
        singular = [
            word, word + 'а', word + 'у', word + 'а', word + (soft ? 'ем' : 'ом'),
            velar ? alternate(word) + 'і' : word + 'і',
            word + (velar ? 'у' : 'е')
        ];
        plural = [word + y, word + 'ів', word + 'ам', word + 'ів', word + 'ами', word + 'ах', word + y];
    } else {
        return null;
    }
    return {
        однина: Object.fromEntries(CASES.map((nameCase, i) => [nameCase, singular[i]])),
        множина: Object.fromEntries(CASES.map((nameCase, i) => [nameCase, plural[i]]))
    };
}

function alternate(text) {
    const last = text.at(-1);
    const replacement = ALTERNATION[last];
    return replacement ? text.slice(0, -1) + replacement : text;
}

// Genitive plural of -ка nouns after a consonant gets a vowel: Комашка → Комашок
function insertVowel(stem) {
    const lower = stem.toLowerCase();
    if (lower.at(-1) === 'к' && CONSONANTS.includes(lower.at(-2) ?? '')) {
        return stem.slice(0, -1) + 'ок';
    }
    return stem;
}
