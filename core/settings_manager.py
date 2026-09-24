import json
from pathlib import Path
from typing import Dict

DEFAULT_STOP_WORDS = [
    'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'всё', 'мочь', 'она',
    'так', 'её', 'его', 'но', 'да', 'ты', 'к', 'ко', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только',
    'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь',
    'когда', 'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или', 'ни', 'быть', 'был', 'него',
    'до', 'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничего',
    'ей', 'может', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их',
    'чем', 'была', 'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под',
    'будет', 'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем',
    'мой', 'твой', 'свой', 'это', 'такой', 'тот', 'сейчас', 'просто', 'тип', 'большой',
    'можно', 'около', 'ещё', 'хз', 'че', 'чё', 'крч', 'ладный', 'хороший', 'человек',
    'про', 'сегодня', 'завтра', 'нибыть', 'бл', 'год', 'очень', 'другой', 'вк', 'час', 'вроде',
    'типо', 'весь', 'через', 'либо', 'куда', 'хотя', 'чтобы', 'поэтому', 'который', 'именно', 'наш',
    'чуть', 'сразу', 'при', 'э', 'почти', 'каждый', 'всегда', 'ваш', 'почему', 'после', 'наш', 'вчера'
]

DEFAULT_ERROR_WHITELIST = [

    'вк', 'тг', 'лк', 'тт', 'лс', 'акк', 'паблик', 'чат', 'медиа', 'юзер',
    'телеграм', 'телега', 'инста', 'ютуб', 'видос', 'скрин', 'голосовое', 'гс',

    'спс', 'плз', 'плиз', 'пж', 'нз', 'бб', 'ку', 'прив', 'кнш', 'хах', 'кста', 'хз',
    'всм', 'смысле', 'ща', 'щас', 'лан', 'ладно', 'крч', 'кароче', 'типа', 'типо', 'пздц',
    'пон', 'днс', 'екб', 'екат', 'мск', 'спб', 'чито', 'дыа', 'кст', 'збс', 'кароч', 'погодь',
    'капец', 'пипец', 'писец', 'дарова', 'мейби', 'рил', 'рофл', 'чел', 'вайб', 'жиза',

    'огэ', 'егэ', 'вуз', 'препод', 'дз', 'гдз', 'курсач', 'оффлайн', 'онлайн',
    'дедлайн',

    'пк', 'комп', 'гамать', 'катка', 'тима', 'ранг', 'лвл', 'скилл', 'нуб', 'про',
    'чит', 'бан', 'краш', 'баг', 'фича', 'апнуть', 'фулл', 'фул', 'хп',
    'стрим', 'донат', 'гайд', 'имхо', 'видюха', 'треш', 'трэш', 'кринж',
    'форсить', 'хейт', 'абьюз', 'слив'
]

DEFAULT_PROFANITY_BLACKLIST = [
    'дурак', 'дебил', 'идиот', 'бестолочь', 'сука', 'тупица', 'бездарь', 'ничтожество',
    'гнида', 'урод', 'скотина', 'лох', 'чмо', 'лошара', 'жопа', 'говно'
]

# ============================================================
# Промпт для LLM-анализа тем и сентимента
# ============================================================
DEFAULT_LLM_SYSTEM_PROMPT = """You are a strict data labeling bot. Analyze the provided Russian chat log.
STEP 1: Write a brief analysis in the 'reason' field explaining what the text is about and explicitly noting the emotional climate (fights, accusations, joking, neutral talk).
STEP 2: Based on your analysis, choose the most accurate 'topic' and 'sentiment'.
CRITICAL RULES:
- Never label a dialogue as 'Нейтральный' if people are arguing, accusing, teasing, threating, or expressing frustration. 
- If text is emotionally charged, force yourself to choose the most fitting specific emotion from the allowed list."""


# Списки тем и сентиментов (используются и в промпте, и в схеме JSON)
DEFAULT_LLM_TOPICS = [
    "Работа и учеба",
    "Организация и встречи",
    "Быт и повседневность",
    "Развлечения и хобби",
    "Юмор и мемы",
    "Медицина и здоровье",
    "Домашние животные и питомцы",
    "Новости и события",
    "Поздравления",
    "Сплетни и обсуждение других",
    "Спор и полемика",
    "Конфликт и выяснение отношений",
    "Отношения и чувства",
    "Флирт",
    "Интим и секс (18+)",
    "Философия и смысл жизни",
]

DEFAULT_LLM_SENTIMENTS = [
    "Радостный и позитивный",
    "Доброжелательный и теплый",
    "Нейтральный",
    "Грустный и меланхоличный",
    "Депрессивный и тревожный",
    "Агрессивный и злой",
    "Раздраженный и недовольный",
    "Обиженный",
    "Напряженный и серьезный",
    "Саркастичный и ироничный",
    "Игривый и шутливый",
    "Романтичный",
    "Интимный (18+)",
    "Скучающий и вялый",
    "Удивленный и шокированный",
]


class SettingsManager:
    """Управляет пользовательскими словарями (стоп-слова, белый список, чёрный список мата)."""

    def __init__(self, settings_path: str = "settings.json"):
        self.settings_path = Path(settings_path).resolve()
        self.data = self._load()

    def _load(self) -> Dict:
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Дополняем недостающие ключи значениями по умолчанию
                    return {
                        "stop_words": loaded.get("stop_words", DEFAULT_STOP_WORDS.copy()),
                        "error_whitelist": loaded.get("error_whitelist", DEFAULT_ERROR_WHITELIST.copy()),
                        "profanity_blacklist": loaded.get("profanity_blacklist", DEFAULT_PROFANITY_BLACKLIST.copy()),
                        # НОВОЕ:
                        "llm_system_prompt": loaded.get("llm_system_prompt", DEFAULT_LLM_SYSTEM_PROMPT),
                        "llm_topics": loaded.get("llm_topics", DEFAULT_LLM_TOPICS.copy()),
                        "llm_sentiments": loaded.get("llm_sentiments", DEFAULT_LLM_SENTIMENTS.copy()),
                    }
            except (json.JSONDecodeError, OSError):
                pass  # Если файл битый — вернем дефолт

        return {
            "stop_words": DEFAULT_STOP_WORDS.copy(),
            "error_whitelist": DEFAULT_ERROR_WHITELIST.copy(),
            "profanity_blacklist": DEFAULT_PROFANITY_BLACKLIST.copy(),
            "llm_system_prompt": DEFAULT_LLM_SYSTEM_PROMPT,
            "llm_topics": DEFAULT_LLM_TOPICS.copy(),
            "llm_sentiments": DEFAULT_LLM_SENTIMENTS.copy(),
        }

    def save(self):
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # --- Удобные геттеры ---
    @property
    def stop_words(self) -> set:
        return set(self.data.get("stop_words", []))

    @property
    def error_whitelist(self) -> set:
        return set(self.data.get("error_whitelist", []))

    @property
    def profanity_blacklist(self) -> set:
        return set(self.data.get("profanity_blacklist", []))

    # --- НОВЫЕ геттеры для LLM ---
    @property
    def llm_system_prompt(self) -> str:
        return self.data.get("llm_system_prompt", DEFAULT_LLM_SYSTEM_PROMPT)

    @property
    def llm_topics(self) -> list:
        return list(self.data.get("llm_topics", DEFAULT_LLM_TOPICS))

    @property
    def llm_sentiments(self) -> list:
        return list(self.data.get("llm_sentiments", DEFAULT_LLM_SENTIMENTS))

    # --- Сеттеры ---
    def set_stop_words(self, words):
        self.data["stop_words"] = sorted(set(words))

    def set_error_whitelist(self, words):
        self.data["error_whitelist"] = sorted(set(words))

    def set_profanity_blacklist(self, words):
        self.data["profanity_blacklist"] = sorted(set(words))

    # --- НОВЫЕ сеттеры для LLM ---
    def set_llm_system_prompt(self, prompt: str):
        self.data["llm_system_prompt"] = prompt

    def set_llm_topics(self, topics):
        self.data["llm_topics"] = list(topics)

    def set_llm_sentiments(self, sentiments):
        self.data["llm_sentiments"] = list(sentiments)

    def reset_to_defaults(self):
        self.data = {
            "stop_words": DEFAULT_STOP_WORDS.copy(),
            "error_whitelist": DEFAULT_ERROR_WHITELIST.copy(),
            "profanity_blacklist": DEFAULT_PROFANITY_BLACKLIST.copy(),
            "llm_system_prompt": DEFAULT_LLM_SYSTEM_PROMPT,
            "llm_topics": DEFAULT_LLM_TOPICS.copy(),
            "llm_sentiments": DEFAULT_LLM_SENTIMENTS.copy(),
        }
        self.save()