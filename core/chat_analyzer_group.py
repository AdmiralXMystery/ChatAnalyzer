import pandas as pd
import pymorphy3
from collections import Counter
import re, os, sys
import emoji
from spellchecker import SpellChecker
import pymorphy3_dicts_ru


class GroupChatAnalyzer:
    """
    Анализатор группового чата (от 3 до 1000 участников).
    Предоставляет только базовую статистику без детального персонального анализа.
    """

    def __init__(self, csv_filepath: str,
                 stop_words=None,
                 error_whitelist=None,
                 profanity_blacklist=None,
                 min_participants: int = 3):
        """Инициализация класса анализатора группового чата."""
        df = pd.read_csv(csv_filepath, parse_dates=['date'])
        self.df = df.copy()
        self.df['date'] = pd.to_datetime(self.df['date'], errors='coerce')
        self.df['text'] = self.df['text'].fillna('').astype(str)

        # Проверка, что это действительно групповой чат
        unique_senders = self.df['sender'].nunique()
        if unique_senders < min_participants:
            raise ValueError(
                f"Чат содержит только {unique_senders} участников. "
                f"Для группового анализа требуется минимум {min_participants}."
            )

        # 1. Корректно определяем корень приложения для Windows (.py или .exe)
        if getattr(sys, 'frozen', False) or 'NUITKA_BINARY_DIR' in os.environ:
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        # 2. Ищем папку со словарями pymorphy3 в ресурсах сборки
        possible_morph_paths = [
            os.path.join(base_dir, "pymorphy3_dicts_ru", "data"),
            os.path.join(base_dir, "data"),
            os.path.dirname(os.path.abspath(__file__))
        ]

        dict_path = None
        for p in possible_morph_paths:
            if os.path.exists(os.path.join(p, 'meta.json')):
                dict_path = p
                break

        # 3. ТОТАЛЬНЫЙ СУПЕР-ОБХОД ДЛЯ PYMORPHY3 (Без import ложного модуля)
        if dict_path:
            from pymorphy3.dawg import OpcorporaDAWG
            from pymorphy3.units import get_default_units

            self.morph = pymorphy3.MorphAnalyzer(__builtins__)
            loaded_dict = OpcorporaDAWG().load(dict_path)
            self.morph.dictionary = loaded_dict
            self.morph.lang = 'ru'
            self._is_lemmatized = False
            self.morph._units = get_default_units(loaded_dict, reregister_plugins=False)
        else:
            self.morph = pymorphy3.MorphAnalyzer(lang='ru')

        # Словари приходят извне или берём дефолт
        from core.settings_manager import SettingsManager
        _defaults = SettingsManager()

        self.stop_words = set(stop_words) if stop_words is not None else _defaults.stop_words
        self.error_whitelist = set(error_whitelist) if error_whitelist is not None else _defaults.error_whitelist
        self.profanity_blacklist = set(
            profanity_blacklist) if profanity_blacklist is not None else _defaults.profanity_blacklist

        # 4. СУПЕР-ОБХОД ДЛЯ PYSPELLCHECKER (Загрузка словаря напрямую из файла)
        # Ищем папку resources, которую мы скопировали в корень
        spell_res_path = os.path.join(base_dir, "resources", "ru.json.gz")

        if os.path.exists(spell_res_path):
            # Если папка скопирована в корень или собрана Nuitka рядом с EXE
            self.spell = SpellChecker(language=None, local_dictionary=spell_res_path)
        else:
            # Запасной вариант для работы в IDE, если файл еще не перенесен
            try:
                self.spell = SpellChecker(language='ru')
            except Exception:
                # На всякий случай создаем пустой, чтобы приложение не падало, если словаря вообще нет
                self.spell = SpellChecker(language=None)

        self.profanity_regex = re.compile(
            r'\b(?:[уовызапередоподсразвзвзнаиотд]{1,4})?'  # Приставки от 1 до 4 букв (опционально)
            r'(?:'
            r'[хx][ууy][йяеиоу][а-яё]{0,5}|'  # Корень "хуй"
            r'[пp][ииi][ззz][ддd][а-яё]{0,5}|'  # Корень "пизда"
            r'еб[ануоёеи]ть?|еб[ауоыёеи]л[а-яё]{0,5}|'  # Глагольные формы ебать/ебал
            r'обдолб[а-яё]*|выёб[а-яё]*|заёб[а-яё]*|'
            r'бл[яяa][ддd][а-яё]{0,3}|блять|бля|'  # Бляд/бля
            r'фиг(?!ур|ляр)[а-яё]{1,5}|'  # нифига, дофига (исключаем "фиг" как отдельное слово, если оно пересекается)
            r'[хx][еe][рp](?!сон|увим|сонес)[а-яё]{1,5}|'  # похеру, нихера (исключаем голый "хер", если он сбоит)
            r'[хx][рp][еe][нн](?:ов|от|юч|яч|ец)[а-яё]*'
            r')\b',
            re.IGNORECASE
        )

        # Расширим список исключений для слов, которые могут содержать ложные совпадения
        self._profanity_safe_roots = [
            'теб', 'себ', 'больш', 'рубл', 'влюб', 'хлеб', 'стеб', 'греб', 'колеб', 'употреб',
            'что', 'это', 'как', 'для', 'или', 'они', 'его', 'ему'
        ]

        # Кэш лемм
        self._is_lemmatized = False
        self.df['parsed_text'] = None

    # ============================================================
    # 1. ОБЪЁМ ПЕРЕПИСКИ
    # ============================================================
    def get_volume_statistics(self) -> dict:
        """
        Общая статистика объёмов:
        - Общее количество сообщений
        - Количество сообщений по каждому участнику
        - Средняя длина сообщения (в словах) для каждого участника
        """
        words_count = self.df['text'].str.strip().apply(lambda x: len(x.split()) if x else 0)

        temp_df = self.df.copy()
        temp_df['words_count'] = words_count
        temp_df['has_words'] = temp_df['words_count'] > 0

        total_messages = len(temp_df)

        sender_stats = {}
        for sender, group in temp_df.groupby('sender'):
            msg_count = len(group)
            author_text_msgs = group[group['has_words']]
            avg_words = author_text_msgs['words_count'].mean() if not author_text_msgs.empty else 0.0
            sender_stats[sender] = {
                'messages_count': msg_count,
                'avg_words_per_message': round(avg_words, 2)
            }

        return {
            'total_messages': total_messages,
            'total_participants': self.df['sender'].nunique(),
            'senders': sender_stats
        }

    # ============================================================
    # 2. СРЕДНЯЯ СУТОЧНАЯ АКТИВНОСТЬ
    # ============================================================
    def get_daily_activity(self) -> dict:
        """
        Средняя суточная активность переписки:
        - Среднее количество сообщений в день
        - Среднее количество сообщений в день на одного участника
        - Количество активных дней (дней, в которые были сообщения)
        """
        df_time = self.df.dropna(subset=['date']).copy()
        if df_time.empty:
            return {}

        df_time['day'] = df_time['date'].dt.date
        messages_per_day = df_time.groupby('day').size()

        total_days_span = (df_time['date'].max() - df_time['date'].min()).days + 1
        active_days = len(messages_per_day)

        avg_per_day = messages_per_day.mean()
        avg_per_active_day = messages_per_day.mean()

        participants = self.df['sender'].nunique()

        return {
            'total_days_span': total_days_span,
            'active_days': active_days,
            'avg_messages_per_day': round(avg_per_day, 2),
            'avg_messages_per_active_day': round(avg_per_active_day, 2),
            'avg_messages_per_day_per_participant': round(avg_per_day / participants, 4) if participants else 0,
            'messages_per_day_series': messages_per_day  # для построения графика
        }

    # ============================================================
    # 3. ГРАФИК АКТИВНОСТИ С АВТОМАСШТАБОМ
    # ============================================================
    def get_activity_timeline(self) -> dict:
        """
        Возвращает временной ряд количества сообщений с автоматически
        подобранным масштабом группировки в зависимости от длительности переписки.

        Логика выбора масштаба:
        - <= 60 дней  -> по дням ('D')
        - <= 365 дней -> по неделям ('W')
        - <= 3 лет    -> по месяцам ('M')
        - иначе       -> по кварталам ('Q')
        """
        df_time = self.df.dropna(subset=['date']).copy()
        if df_time.empty:
            return {'scale': None, 'scale_label': None, 'series': pd.Series(dtype=int)}

        span_days = (df_time['date'].max() - df_time['date'].min()).days

        if span_days <= 60:
            scale, scale_label = 'D', 'дням'
        elif span_days <= 365:
            scale, scale_label = 'W', 'неделям'
        elif span_days <= 365 * 3:
            scale, scale_label = 'M', 'месяцам'
        else:
            scale, scale_label = 'Q', 'кварталам'

        series = df_time.groupby(df_time['date'].dt.to_period(scale)).size()
        series.index = series.index.astype(str)

        return {
            'scale': scale,
            'scale_label': scale_label,
            'span_days': span_days,
            'points_count': len(series),
            'series': series
        }

    # ============================================================
    # 4. ТОП САМЫХ ДЛИННЫХ СООБЩЕНИЙ
    # ============================================================
    @staticmethod
    def _is_spam(text: str, uniqueness_threshold: float = 0.1, min_len: int = 10) -> bool:
        """Фильтр спама по доле уникальных символов."""
        if len(text) < min_len:
            return False
        unique_chars = len(set(text.lower()))
        return (unique_chars / len(text)) < uniqueness_threshold

    def get_longest_messages(self, top_n: int = 10) -> pd.DataFrame:
        """
        Топ N самых длинных сообщений (исключая спам и ссылки).
        """
        url_pattern = (
            r'https?://\S+|www\.\S+|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|'
            r'\b\S+\.(?:com|ru|net|org|info|edu|gov|io|me|cc|tv|am)\b'
        )

        df = self.df.copy()
        non_spam_mask = ~df['text'].apply(self._is_spam)
        clean_df = df[non_spam_mask].copy()

        clean_df['text_for_len'] = clean_df['text'].str.replace(url_pattern, '', regex=True).str.strip()
        clean_df = clean_df[clean_df['text_for_len'] != '']
        clean_df['text_len'] = clean_df['text_for_len'].str.len()

        result = clean_df.sort_values(by='text_len', ascending=False).head(top_n)
        return result[['sender', 'date', 'text', 'text_len']]

    # ============================================================
    # 5. САМЫЙ ДОЛГИЙ ПЕРЕРЫВ
    # ============================================================
    def get_longest_pause(self, context_length: int = 5) -> dict:
        """
        Находит самый долгий перерыв в переписке и возвращает контекст
        (несколько сообщений до и после).
        """
        df_time = self.df.dropna(subset=['date']).reset_index(drop=True)
        df_time = df_time.sort_values('date', kind='mergesort').copy()

        if len(df_time) < 2:
            return {}

        df_time['time_diff'] = df_time['date'].diff()

        # Индекс строки, ПЕРЕД которой был самый долгий перерыв
        max_idx = df_time['time_diff'].idxmax()
        pause = df_time.loc[max_idx, 'time_diff']

        # Контекст: context_length сообщений до и после перерыва
        start_pos = max(0, max_idx - context_length)
        end_pos = min(len(df_time), max_idx + context_length)

        context_lines = []
        for i, row in df_time.iloc[start_pos:end_pos].iterrows():
            formatted_date = row['date'].strftime('%Y-%m-%d %H:%M:%S')
            msg_text = row['text'] if row['text'] else "[Вложение/Стикер/Медиафайл]"
            marker = " [ПОСЛЕ ЭТОГО СООБЩЕНИЯ ПАУЗА]" if i == max_idx - 1 else ""
            context_lines.append(f"[{formatted_date}] {row['sender']}: {msg_text}{marker}")

        return {
            'pause_duration': pause,
            'pause_before_date': df_time.loc[max_idx, 'date'],
            'pause_after_date': df_time.loc[max_idx - 1, 'date'],
            'context_dialogue': "\n".join(context_lines)
        }

    # ============================================================
    # 6. ЛЕММАТИЗАЦИЯ И ТОП СЛОВ
    # ============================================================
    def _prepare_lemmas(self):
        """Лемматизирует все сообщения один раз и кэширует результат."""
        if self._is_lemmatized:
            return

        laugh_regex = re.compile(r'\b(?:[аахаееооззiиы]+|[aaxaxheheh]+)\b', re.IGNORECASE)

        def parse_text(text):
            words = re.findall(r'[a-zа-яё]+', text.lower())
            parsed_words = []
            for word in words:
                if laugh_regex.match(word) and len(set(word)) <= 3 and len(word) >= 3:
                    continue
                if word in {'лол', 'кек', 'lol', 'kek'}:
                    continue
                parse_results = self.morph.parse(word)
                if not parse_results:
                    continue
                p = parse_results[0]
                parsed_words.append({
                    'original': word,
                    'lemma': p.normal_form,
                    'pos': str(p.tag.POS if p.tag.POS else 'UNKNOWN')
                })
            return parsed_words

        self.df['parsed_text'] = self.df['text'].apply(parse_text)
        self._is_lemmatized = True

    def get_top_words(self, top_n: int = 20) -> dict:
        """
        Общий топ N самых частых слов (по леммам, без стоп-слов, только русские).
        """
        self._prepare_lemmas()

        all_lemmas = []
        for message_words in self.df['parsed_text']:
            for word_info in message_words:
                lemma = word_info['lemma']
                if not re.match(r'^[а-яё]+$', lemma):
                    continue
                if lemma in self.stop_words:
                    continue
                all_lemmas.append(lemma)

        return {
            'overall': Counter(all_lemmas).most_common(top_n),
            'total_meaningful_words': len(all_lemmas),
            'unique_meaningful_words': len(set(all_lemmas))
        }

    def get_word_map(self) -> dict:
        """
        Общая «карта слов» для всего чата: частотное распределение лемм.
        Возвращает словарь {лемма: частота} и общее число уникальных лемм.
        """
        self._prepare_lemmas()

        counter = Counter()
        for message_words in self.df['parsed_text']:
            for word_info in message_words:
                lemma = word_info['lemma']
                if not re.match(r'^[а-яё]+$', lemma):
                    continue
                if lemma in self.stop_words:
                    continue
                counter[lemma] += 1

        return {
            'word_frequencies': dict(counter.most_common()),
            'unique_words_count': len(counter),
            'total_words_count': sum(counter.values())
        }

    # ============================================================
    # 7. ЭМОДЗИ
    # ============================================================
    def get_emoji_statistics(self, top_n: int = 10) -> dict:
        """
        Общая статистика по эмодзи:
        - Общее количество
        - Топ N
        - Среднее на сообщение
        - % сообщений с эмодзи
        """
        def extract_emojis(text):
            return [c['emoji'] for c in emoji.emoji_list(text)]

        df_emoji = self.df.copy()
        df_emoji['extracted_emojis'] = df_emoji['text'].apply(extract_emojis)
        df_emoji['emoji_count'] = df_emoji['extracted_emojis'].apply(len)
        df_emoji['has_emoji'] = df_emoji['emoji_count'] > 0

        total_msgs = len(df_emoji)
        if total_msgs == 0:
            return {}

        all_emojis_list = [e for emojis_ in df_emoji['extracted_emojis'] for e in emojis_]
        total_emojis = len(all_emojis_list)
        msgs_with_emoji = int(df_emoji['has_emoji'].sum())

        return {
            'total_count': total_emojis,
            'top_emojis': Counter(all_emojis_list).most_common(top_n),
            'avg_per_message': round(total_emojis / total_msgs, 3),
            'percentage_of_messages': round((msgs_with_emoji / total_msgs) * 100, 2)
        }

    # ============================================================
    # 8. НЕЦЕНЗУРНАЯ ЛЕКСИКА
    # ============================================================
    def _extract_profanity(self, text: str) -> list:
        """Внутренний метод: находит матерные слова с учётом безопасных корней."""
        if not text.strip():
            return []

        words = re.findall(r'[а-яёa-z0-9\-]+', text.lower())
        found_words = []
        for word in words:
            if any(safe_root in word for safe_root in self._profanity_safe_roots):
                continue
            if word in self.profanity_blacklist:
                found_words.append(word)
            elif self.profanity_regex.match(word):
                found_words.append(word)
        return found_words

    def get_profanity_statistics(self, top_n: int = 10) -> dict:
        """
        Общая статистика мата:
        - Общее количество
        - Плотность на одно сообщение
        - Топ N матерных слов
        """
        total_messages = len(self.df)
        if total_messages == 0:
            return {}

        all_profanity = []
        for text in self.df['text']:
            all_profanity.extend(self._extract_profanity(text))

        total_count = len(all_profanity)
        density = total_count / total_messages

        return {
            'total_profanity_count': total_count,
            'profanity_density': round(density, 4),
            'top_profanity': Counter(all_profanity).most_common(top_n)
        }

    # ============================================================
    # УТИЛИТЫ
    # ============================================================
    @staticmethod
    def format_timedelta(td) -> str:
        """Превращает Timedelta или секунды в понятную строку."""
        if pd.isna(td):
            return "Нет данных"
        if isinstance(td, (int, float)):
            td = pd.to_timedelta(td, unit='s')

        total_seconds = int(td.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        parts = []
        if days > 0: parts.append(f"{days} дн")
        if hours > 0: parts.append(f"{hours} ч")
        if minutes > 0: parts.append(f"{minutes} мин")
        if seconds > 0 or not parts: parts.append(f"{seconds} сек")
        return " ".join(parts)