import pandas as pd
import pymorphy3
from collections import Counter
import re, os, sys
import emoji
from spellchecker import SpellChecker
import requests
import json

class ChatAnalyzer:
    def __init__(self, csv_filepath: str,
                 stop_words=None,
                 error_whitelist=None,
                 profanity_blacklist=None):
        """Инициализация класса анализатора."""
        df = pd.read_csv(csv_filepath, parse_dates=['date'])
        self.df = df.copy()
        self.df['date'] = pd.to_datetime(self.df['date'], errors='coerce')
        self.df['text'] = self.df['text'].fillna('').astype(str)

        unique_senders = self.df['sender'].nunique()
        if unique_senders > 2:
            raise ValueError(
                f"Чат содержит {unique_senders} участников. "
                f"Для анализа личной переписки требуется ровно 2 участника. "
                f"Если у вас групповой чат — используйте Анализ групповых чатов."
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

        # --- Словари теперь приходят извне (или берём дефолт из SettingsManager) ---
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

        # Флаг и колонка для кэширования лемм
        self._is_lemmatized = False
        self.df['text_lemmas'] = None

    @staticmethod
    def _is_spam(text: str, uniqueness_threshold: float = 0.1, min_len: int = 10) -> bool:
        """
        Внутренний метод для фильтрации спама (повторяющихся символов).
        Если уникальных символов слишком мало относительно длины текста, это спам.
        """
        if len(text) < min_len:
            return False

        unique_chars = len(set(text.lower()))
        # Если доля уникальных символов меньше порога — это спам (например, "ааааа" -> 1/5 = 0.2)
        if (unique_chars / len(text)) < uniqueness_threshold:
            return True
        return False

    def get_longest_messages(self, top_n: int = 10, sender: str = None) -> pd.DataFrame:
        """
        Возвращает топ самых длинных сообщений по убыванию, исключая ссылки.
        :param top_n: Количество сообщений в топе.
        :param sender: Имя отправителя для фильтрации. Если None, поиск по всем.
        """
        # 1. Фильтруем по отправителю, если он задан
        filtered_df = self.df
        if sender is not None:
            filtered_df = filtered_df[filtered_df['sender'] == sender]

        if filtered_df.empty:
            return pd.DataFrame()

        # 2. Исключаем спам-сообщения
        non_spam_mask = ~filtered_df['text'].apply(self._is_spam)
        clean_df = filtered_df[non_spam_mask].copy()

        # === НОВЫЙ БЛОК: ОЧИСТКА ОТ ССЫЛОК ===
        # Регулярное выражение для поиска любых URL-адресов
        url_pattern = r'https?://\S+|www\.\S+|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|\b\S+\.(?:com|ru|net|org|info|edu|gov|io|me|cc|tv|am)\b'

        # Создаем временную колонку с текстом БЕЗ ссылок для точного расчета длины
        # (Исходный текст в 'text' не меняем, чтобы он красиво выводился в отчете)
        clean_df['text_for_len'] = clean_df['text'].str.replace(url_pattern, '', regex=True).str.strip()

        # Исключаем сообщения, которые состояли только из ссылки (после очистки они стали пустыми)
        clean_df = clean_df[clean_df['text_for_len'] != '']

        # 3. Считаем длину сообщений по ОЧИЩЕННОМУ тексту
        clean_df['text_len'] = clean_df['text_for_len'].str.len()

        # 4. Сортируем по убыванию реальной длины и берем топ-N
        result = clean_df.sort_values(by='text_len', ascending=False).head(top_n)
        return result[['sender', 'date', 'text', 'text_len']]

    def get_volume_statistics(self) -> dict:
        """
        Возвращает общую статистику объемов переписки:
        - Общее количество сообщений в чате.
        - Количество сообщений по каждому участнику.
        - Среднюю длину сообщения в словах (общую и для каждого).
        """
        # Считаем количество слов в каждом сообщении (разбиваем по пробелам)
        # Очищаем от лишних пробелов по краям, чтобы split() работал корректно
        words_count = self.df['text'].str.strip().apply(lambda x: len(x.split()) if x else 0)

        # Создаем временные колонки для удобства расчета
        temp_df = self.df.copy()
        temp_df['words_count'] = words_count
        # Маркер: было ли в сообщении хотя бы одно слово (чтобы не делить на пустые сообщения)
        temp_df['has_words'] = temp_df['words_count'] > 0

        # --- Расчет общих метрик по всему чату ---
        total_messages = len(temp_df)

        # Средняя длина среди сообщений, содержащих текст
        text_messages = temp_df[temp_df['has_words']]
        overall_avg_words = text_messages['words_count'].mean() if not text_messages.empty else 0.0

        # --- Расчет метрик по каждому участнику ---
        sender_stats = {}

        # Группируем по отправителям
        for sender, group in temp_df.groupby('sender'):
            # Количество сообщений автора
            msg_count = len(group)

            # Среднее количество слов автора (только для его текстовых сообщений)
            author_text_msgs = group[group['has_words']]
            avg_words = author_text_msgs['words_count'].mean() if not author_text_msgs.empty else 0.0

            sender_stats[sender] = {
                'messages_count': msg_count,
                'avg_words_per_message': round(avg_words, 2)
            }

        # Формируем итоговый структурированный словарь
        return {
            'total_messages': total_messages,
            'overall_avg_words': round(overall_avg_words, 2),
            'senders': sender_stats
        }

    def _prepare_time_diffs(self) -> pd.DataFrame:
        """Внутренний метод: надежно сортирует сообщения и считает паузы между ними."""
        # reset_index гарантирует, что если у сообщений совпадает секунда,
        # сохранится их исходный порядок из файла (стабильная сортировка)
        df_time = self.df.dropna(subset=['date']).reset_index(drop=True)
        df_time = df_time.sort_values('date', kind='mergesort').copy()

        # Пауза перед текущим сообщением (разница с предыдущим)
        df_time['time_diff'] = df_time['date'].diff()
        # Кто отправил предыдущее сообщение
        df_time['prev_sender'] = df_time['sender'].shift(1)
        return df_time

    def get_longest_session(self, max_break_minutes: int = 15) -> dict:
        """
        Находит самый длинный непрерывный диалог (сессию),
        где перерыв между сообщениями не превышал max_break_minutes.
        Возвращает метаданные и полный текст диалога.
        """
        df_time = self._prepare_time_diffs()
        if len(df_time) < 2:
            return {}

        # Определяем границы новых сессий
        is_new_session = (df_time['time_diff'] > pd.Timedelta(minutes=max_break_minutes)) | df_time['time_diff'].isna()
        df_time['session_id'] = is_new_session.cumsum()

        # Находим ID самой длинной сессии
        session_counts = df_time['session_id'].value_counts()
        if session_counts.empty:
            return {}

        longest_session_id = session_counts.idxmax()

        # Вытаскиваем все сообщения этой сессии (они уже отсортированы по дате)
        session_df = df_time[df_time['session_id'] == longest_session_id].copy()

        # Формируем красивый сплошной текст диалога
        dialogue_lines = []
        for _, row in session_df.iterrows():
            # Форматируем дату для компактности: '2023-10-25 15:30:12'
            formatted_date = row['date'].strftime('%Y-%m-%d %H:%M:%S')
            # Заменяем пустой текст (если это картинка или стикер), чтобы не было пустоты
            msg_text = row['text'] if row['text'] else "[Вложение/Стикер/Медиафайл]"

            line = f"[{formatted_date}] {row['sender']}: {msg_text}"
            dialogue_lines.append(line)

        full_dialogue_text = "\n".join(dialogue_lines)

        return {
            'start_time': session_df['date'].min(),
            'end_time': session_df['date'].max(),
            'messages_count': len(session_df),
            'duration': session_df['date'].max() - session_df['date'].min(),
            'dialogue_text': full_dialogue_text  # <- Добавили новое поле
        }

    def get_reply_time_stats(self, max_gap_minutes: int = 240, context_length: int = 5) -> dict:
        """
        Вычисляет детальную статистику времени ответа и возвращает контекст самого долгого ответа.

        :param max_gap_minutes: Порог в минутах (по умолчанию 4 часа).
        """
        df_time = self._prepare_time_diffs()

        # Реальным ответом считается сообщение, отправленное ПОСЛЕ сообщения ДРУГОГО участника
        # И только если перерыв между ними НЕ превышает max_gap_minutes
        gap_delta = pd.Timedelta(minutes=max_gap_minutes)

        replies = df_time[
            (df_time['sender'] != df_time['prev_sender']) &
            df_time['time_diff'].notna() &
            (df_time['time_diff'] <= gap_delta)
            ].copy()

        if replies.empty:
            return {}

        # Переводим паузы в секунды для точных математических расчетов
        replies['seconds'] = replies['time_diff'].dt.total_seconds()

        # --- 1. Общие метрики по всей переписке ---
        overall_avg = replies['seconds'].mean()
        overall_median = replies['seconds'].median()

        # --- 2. Рекорды (самый быстрый / самый долгий) ---
        # Самый быстрый ответ
        min_seconds = replies['seconds'].min()
        fastest_messages = replies[replies['seconds'] == min_seconds]
        fastest_senders = fastest_messages['sender'].unique()

        if len(fastest_senders) == 1:
            fastest_winner = fastest_senders[0]
        else:
            fastest_winner = "Ничья (несколько участников)"

        # --- Самый долгий ответ + сбор контекста ---
        max_idx = replies['seconds'].idxmax()
        slowest_row = replies.loc[max_idx]

        pos = df_time.index.get_loc(max_idx)

        start_pos = max(0, pos - context_length)
        end_pos = min(len(df_time), pos + context_length)
        context_df = df_time.iloc[start_pos:end_pos]

        context_messages = []
        for _, row in context_df.iterrows():
            msg_text = row['text'] if str(row['text']).strip() else "[Вложение/Стикер/Медиафайл]"
            context_messages.append({
                "sender": row['sender'],
                "date": row['date'].strftime('%Y-%m-%d'),
                "time": row['date'].strftime('%H:%M'),
                "text": msg_text,
                "is_slowest": bool(row.name == max_idx),
            })

        # --- 3. Метрики для каждого участника отдельно ---
        sender_stats = {}
        for sender, group in replies.groupby('sender'):
            sender_stats[sender] = {
                'avg_reply': pd.to_timedelta(group['seconds'].mean(), unit='s'),
                'median_reply': pd.to_timedelta(group['seconds'].median(), unit='s')
            }

        return {
            'overall_avg': pd.to_timedelta(overall_avg, unit='s'),
            'overall_median': pd.to_timedelta(overall_median, unit='s'),
            'fastest': {
                'time': pd.to_timedelta(min_seconds, unit='s'),
                'winner': fastest_winner
            },
            'slowest': {
                'time': pd.to_timedelta(slowest_row['seconds'], unit='s'),
                'winner': slowest_row['sender'],
                'context_messages': context_messages,
            },
            'senders': sender_stats
        }

    def get_hourly_activity_data(self) -> pd.Series:
        """Возвращает распределение количества сообщений по часам суток (0-23)."""
        return self.df['date'].dt.hour.value_counts().reindex(range(24), fill_value=0).sort_index()

    def get_monthly_intensity_data(self) -> pd.Series:
        """Возвращает интенсивность переписки, сгруппированную по месяцам за все время."""
        # Период 'M' группирует по месяцам (например, 2023-01, 2023-02)
        return self.df.groupby(self.df['date'].dt.to_period('M')).size()

    def get_laugh_statistics(self) -> dict:
        """
        Считает количество «смеха» (ахаха, лол, кек) в сообщениях участников.
        Возвращает общее количество упоминаний и плотность смеха на одно сообщение.
        """
        laugh_regex = re.compile(r'\b(?:[аахаееооззiиы]{3,}|[aaxaxheheh]{3,})\b', re.IGNORECASE)
        slang_laugh = {'лол', 'кек', 'lol', 'kek'}

        stats = {}
        for sender, group in self.df.groupby('sender'):
            total_messages = len(group)
            if total_messages == 0:
                continue

            laugh_count = 0
            for text in group['text']:
                words = re.findall(r'[a-zа-яё]+', text.lower())
                for word in words:
                    if laugh_regex.match(word) or word in slang_laugh:
                        laugh_count += 1

            stats[sender] = {
                'total_laugh_count': laugh_count,
                'laugh_density': round(laugh_count / total_messages, 4)
            }
        return stats


    def _prepare_lemmas(self):
        """
        Внутренний метод: один раз лемматизирует всю переписку
        и сохраняет структуры слов прямо в DataFrame.
        """
        if self._is_lemmatized:
            return

        laugh_regex = re.compile(r'\b(?:[аахаееооззiиы]+|[aaxaxheheh]+)\b', re.IGNORECASE)

        def parse_text(text):
            # Извлекаем слова из исходного текста
            words = re.findall(r'[a-zа-яё]+', text.lower())
            parsed_words = []

            for word in words:
                # 1. ЗАЩИТА: Проверяем, не является ли слово вариацией смеха
                if laugh_regex.match(word) and len(set(word)) <= 3 and len(word) >= 3:
                    continue
                if word in {'лол', 'кек', 'lol', 'kek'}:  # Точечно убираем сленговый смех
                    continue

                # Вызываем разбор и ОБЯЗАТЕЛЬНО берем первый, самый вероятный вариант ([0])
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

    def get_top_words(self, top_n: int = 10, exclude_basic_verbs: bool = False) -> dict:
        """
        Возвращает топ N самых частых слов (использует единый кэш parsed_text).
        Учитывает только русские слова.

        :param exclude_basic_verbs: Если True, убирает из топа базовые высокочастотные глаголы.
        """
        self._prepare_lemmas()

        # Список базовых разговорных глаголов-"шумов"
        basic_verbs = {
            'знать', 'хотеть', 'делать', 'сказать', 'говорить', 'пойти', 'идти', 'видеть', 'задать',
            'понять', 'сделать', 'думать', 'смотреть', 'давать', 'писать', 'написать', 'узнать', 'решить',
            'мочь', 'смочь', 'стать', 'взять', 'прийти', 'найти', 'ждать', 'жить', 'играть', 'стоить', 'ответить',
            'иметь', 'казаться', 'посмотреть', 'спросить', 'сидеть', 'стоять', 'слышать', 'скинуть', 'кинуть',
            'гулять', 'понимать', 'помнить', 'купить', 'зайти', 'выйти', 'попробовать', 'дать', 'го', 'слушать',
            'подумать', 'задавать', 'забыть', 'решать', 'позвонить', 'брать', 'сдать', 'ходить', 'приехать', 'покупать',
            'сходить', 'оставить', 'заплатить', 'положить', 'убрать', 'записать', 'молчать', 'уйти', 'поехать',
            'отправить', 'поговорить', 'получиться', 'спрашивать', 'спать', 'заниматься'
        }

        result = {}

        def filter_stop_words(parsed_text_series):
            russian_words = []
            for message_words in parsed_text_series:
                for word_info in message_words:
                    lemma = word_info['lemma']

                    # Проверяем на русские буквы
                    if not re.match(r'^[а-яё]+$', lemma):
                        continue

                    # Фильтруем стандартные стоп-слова
                    if lemma in self.stop_words:
                        continue

                    # Фильтруем базовые глаголы, если поднят соответствующий флаг
                    if exclude_basic_verbs and lemma in basic_verbs:
                        continue

                    russian_words.append(lemma)
            return russian_words

        # 1. Общий топ
        overall_words = filter_stop_words(self.df['parsed_text'])
        result['overall'] = Counter(overall_words).most_common(top_n)

        # 2. Топ по каждому участнику
        result['senders'] = {}
        for sender, group in self.df.groupby('sender'):
            sender_words = filter_stop_words(group['parsed_text'])
            result['senders'][sender] = Counter(sender_words).most_common(top_n)

        return result

    def get_vocabulary_richness(self) -> dict:
        """
        Вычисляет лексическое богатство для каждого участника:
        - Общее количество сказанных значимых слов.
        - Количество уникальных слов (уникальных лемм после очистки от стоп-слов).
        - Коэффициент лексического разнообразия (TTR).
        """
        self._prepare_lemmas()  # Гарантируем, что разбор текста готов

        stats = {}
        for sender, group in self.df.groupby('sender'):
            # Собираем все леммы автора из новой структуры parsed_text и убираем стоп-слова
            all_lemmas = [
                word_info['lemma']
                for message_words in group['parsed_text']
                for word_info in message_words
                if word_info['lemma'] not in self.stop_words
            ]

            total_words = len(all_lemmas)
            unique_words = len(set(all_lemmas))

            # Коэффициент TTR (отношение уникальных слов к общему числу)
            ttr = round(unique_words / total_words, 4) if total_words > 0 else 0.0

            stats[sender] = {
                'total_meaningful_words': total_words,
                'unique_words_count': unique_words,
                'lexical_diversity_ttr': ttr
            }

        return stats

    def get_ttr_over_time(self, period: str = 'M') -> dict:
        """
        Вычисляет TTR по временным периодам для каждого участника и средний TTR.
        """
        self._prepare_lemmas()  # Гарантируем наличие кэшированных лемм

        # Создаем временную копию с периодами для группировки
        df_time = self.df.dropna(subset=['date']).copy()
        df_time['period'] = df_time['date'].dt.to_period(period)

        stats = {}

        # Функция для расчета TTR на основе новой структуры parsed_text
        def calc_ttr(parsed_text_series):
            all_lemmas = [
                word_info['lemma']
                for message_words in parsed_text_series
                for word_info in message_words
                if word_info['lemma'] not in self.stop_words
            ]
            total = len(all_lemmas)
            if total < 10:  # Игнорируем слишком пустые периоды
                return None
            unique = len(set(all_lemmas))
            return round(unique / total, 4)

        for sender, group in df_time.groupby('sender'):
            # Группируем по периодам внутри каждого пользователя
            period_series = group.groupby('period')['parsed_text'].apply(calc_ttr).dropna()

            # Считаем среднее значение TTR по всем периодам
            mean_period_ttr = period_series.mean() if not period_series.empty else 0.0

            stats[sender] = {
                'timeline': period_series,
                'mean_period_ttr': round(mean_period_ttr, 4)
            }

        return stats


    def get_emoji_statistics(self, top_n: int = 10) -> dict:
        """
        Анализирует использование эмодзи в переписке.
        Возвращает:
        - Общее количество эмодзи (всего и по авторам).
        - Топ N эмодзи (общий и по авторам).
        - Частоту использования (среднее кол-во на сообщение и % сообщений со смайликами).
        """

        # Внутренняя функция для извлечения ВСЕХ эмодзи из строки
        def extract_emojis(text):
            return [c['emoji'] for c in emoji.emoji_list(text)]

        # Создаем копию для расчетов
        df_emoji = self.df.copy()
        # Вытаскиваем списки эмодзи для каждой строки
        df_emoji['extracted_emojis'] = df_emoji['text'].apply(extract_emojis)
        df_emoji['emoji_count'] = df_emoji['extracted_emojis'].apply(len)
        df_emoji['has_emoji'] = df_emoji['emoji_count'] > 0

        # --- Функция-помощник для сборки метрик по датафрейму/группе ---
        def calculate_metrics(sub_df):
            total_msgs = len(sub_df)
            if total_msgs == 0:
                return {}

            # Собираем все эмодзи в один плоский список
            all_emojis_list = [emo for emojis in sub_df['extracted_emojis'] for emo in emojis]
            total_emojis = len(all_emojis_list)
            msgs_with_emoji = sub_df['has_emoji'].sum()

            # Расчет частот
            avg_per_msg = total_emojis / total_msgs
            pct_of_msgs = (msgs_with_emoji / total_msgs) * 100

            return {
                'total_count': total_emojis,
                'top_emojis': Counter(all_emojis_list).most_common(top_n),
                'avg_per_message': round(avg_per_msg, 3),
                'percentage_of_messages': round(pct_of_msgs, 2)
            }

        # 1. Считаем общую статистику по всему чату
        overall_stats = calculate_metrics(df_emoji)

        # 2. Считаем статистику по каждому участнику отдельно
        sender_stats = {}
        for sender, group in df_emoji.groupby('sender'):
            sender_stats[sender] = calculate_metrics(group)

        return {
            'overall': overall_stats,
            'senders': sender_stats
        }

    def get_dialogue_initiators(self, min_gap_minutes: int = 240) -> dict:
        """
        Определяет, кто и сколько раз первым начинал диалог после долгого молчания.

        :param min_gap_minutes: Время паузы (в минутах), после которого диалог считается новым.
                                По умолчанию 240 минут (4 часа).
        """
        # Готовим надежно отсортированные данные по времени (индексы там идут от 0 до N)
        df_time = self._prepare_time_diffs()
        if df_time.empty:
            return {}

        # Находим сообщения, перед которыми была пауза больше или равна min_gap_minutes
        gap_delta = pd.Timedelta(minutes=min_gap_minutes)
        is_initiation = (df_time['time_diff'] >= gap_delta) | df_time['time_diff'].isna()

        # Самое первое сообщение во всей истории — это ВСЕГДА первая инициация.
        # Используем .iloc[0] для гарантированного доступа к первой строке вне зависимости от её индекса.
        is_initiation.iloc[0] = True

        # Фильтруем только те сообщения, которые стали началом нового диалога
        initiations = df_time[is_initiation]

        # Считаем количество инициаций для каждого участника
        initiator_counts = initiations['sender'].value_counts()
        total_initiations = len(initiations)

        # Формируем статистику в процентах
        stats = {}
        for sender, count in initiator_counts.items():
            stats[sender] = {
                'count': int(count),
                'percentage': round((count / total_initiations) * 100, 2)
            }

        return {
            'total_new_dialogues': total_initiations,
            'initiators': stats
        }

    def get_pos_distribution(self) -> dict:
        """
        Вычисляет процентное распределение частей речи для всего чата
        и для каждого участника отдельно.
        """
        self._prepare_lemmas()

        # Словарь для перевода тегов на русский язык
        pos_map = {
            'NOUN': 'Существительные', 'VERB': 'Глаголы', 'INFN': 'Глаголы (инф.)',
            'ADJF': 'Прилагательные', 'ADJS': 'Прилагательные (кр.)',
            'ADVB': 'Наречия', 'NPRO': 'Местоимения', 'PREP': 'Предлоги',
            'CONJ': 'Союзы', 'PRCL': 'Частицы', 'INTJ': 'Междометия',
            'NUMR': 'Числительные',
            'PRTF': 'Причастия', 'PRTS': 'Причастия (кр.)',
            'GRCH': 'Деепричастия'
        }

        def process_group(group_df):
            # Собираем все POS-теги из списков
            all_pos = [w['pos'] for res in group_df['parsed_text'] for w in res]
            # Переводим и фильтруем (объединяем инфинитивы с глаголами для простоты, если нужно)
            translated_pos = [pos_map.get(tag, 'Другое') for tag in all_pos]

            counter = Counter(translated_pos)
            total = sum(counter.values())

            # Переводим в проценты
            distribution = {pos: round((count / total) * 100, 2) for pos, count in counter.items()}
            # Сортируем по убыванию процентов
            return dict(sorted(distribution.items(), key=lambda item: item[1], reverse=True))

        stats = {'overall': process_group(self.df), 'senders': {}}
        for sender, group in self.df.groupby('sender'):
            stats['senders'][sender] = process_group(group)

        return stats

    def get_grammar_features_distribution(self) -> dict:
        """
        Вычисляет детальное распределение грамматических признаков для каждого участника
        на основе исходных словоформ (исправлена проблема инфинитивов).
        """
        self._prepare_lemmas()

        labels_map = {
            '1per': '1-е лицо (я, мы)', '2per': '2-е лицо (ты, вы)', '3per': '3-е лицо (он, они)',
            'sing': 'Единственное', 'plur': 'Множественное',
            'masc': 'Мужской', 'femn': 'Женский', 'neut': 'Средний',
            'past': 'Прошедшее', 'pres': 'Настоящее', 'futr': 'Будущее'
        }

        stats = {}

        for sender, group in self.df.groupby('sender'):
            pronoun_persons, pronoun_numbers = [], []
            noun_genders, noun_numbers = [], []
            verb_times = []

            for message_words in group['parsed_text']:
                for word_info in message_words:
                    # ВАЖНО: берем оригинальное слово для точного разбора признаков!
                    orig_word = word_info['original']

                    parse_result = self.morph.parse(orig_word)[0]
                    grammemes = parse_result.tag
                    pos = grammemes.POS

                    if pos == 'NPRO':
                        person = next((g for g in ['1per', '2per', '3per'] if g in grammemes), None)
                        number = next((g for g in ['sing', 'plur'] if g in grammemes), None)
                        if person: pronoun_persons.append(labels_map[person])
                        if number: pronoun_numbers.append(labels_map[number])

                    elif pos == 'NOUN':
                        gender = next((g for g in ['masc', 'femn', 'neut'] if g in grammemes), None)
                        number = next((g for g in ['sing', 'plur'] if g in grammemes), None)
                        if gender: noun_genders.append(labels_map[gender])
                        if number: noun_numbers.append(labels_map[number])

                    elif pos in ['VERB', 'INFN']:
                        time = next((g for g in ['past', 'pres', 'futr'] if g in grammemes), None)
                        if time:
                            verb_times.append(labels_map[time])
                        elif pos == 'INFN':
                            verb_times.append('Инфинитив')

            def to_percentages(lst):
                if not lst: return {"Нет данных": 100.0}
                counter = Counter(lst)
                total = sum(counter.values())
                return {k: round((v / total) * 100, 2) for k, v in counter.most_common()}

            stats[sender] = {
                'pronoun': {
                    'person': to_percentages(pronoun_persons),
                    'number': to_percentages(pronoun_numbers)
                },
                'noun': {
                    'gender': to_percentages(noun_genders),
                    'number': to_percentages(noun_numbers)
                },
                'verb': {
                    'time': to_percentages(verb_times)
                }
            }

        return stats

    def _count_errors_in_text(self, text: str) -> list:
        """
        Внутренний метод: очищает строку и возвращает список НАСТОЯЩИХ опечаток.
        Исправлен: теперь SpellChecker является главным фильтром,
        а угадывание pymorphy3 заблокировано.
        """
        if not text.strip():
            return []

        # 1. Извлекаем слова (только русские буквы)
        words = re.findall(r'[а-яё]+', text.lower())
        potential_errors = []

        for word in words:
            # Пропускаем слишком короткие обрубки букв (меньше 3 символов)
            if len(word) <= 2:
                continue

            # Проверяем по вашему белому списку сленга
            if word in self.error_whitelist:
                continue

            # Добавляем в список для проверки спеллчекером
            potential_errors.append(word)

        if not potential_errors:
            return []

        # 2. Ищем слова, в которых SpellChecker видит ошибку
        misspelled = self.spell.unknown(potential_errors)

        if not misspelled:
            return []

        # 3. Финальный фильтр с помощью pymorphy3:
        # Заставляем его проверять слова СТРОГО, без включения режима "угадывания" (prediction)
        # по флексам и концам слов. Если анализатор без угадывания слово не знает — это точно ошибка.
        real_errors = []
        for word in misspelled:
            # Просим pymorphy3 разобрать слово, исключив методы предсказания для неизвестных слов
            parse_results = self.morph.parse(word)

            # Проверяем, получен ли разбор базовыми методами словаря, а не угадывателем (prediction)
            is_dictionary_word = any(
                any(method[0].__class__.__name__ == 'DictionaryAnalyzer' for method in parse.methods_stack)
                for parse in parse_results
            )

            # Если слово НЕ найдено в официальном словаре pymorphy3 — подтверждаем ошибку
            if not is_dictionary_word:
                real_errors.append(word)

        return real_errors

    def get_spelling_statistics(self) -> dict:
        """
        Считает количество ошибок/опечаток за всю переписку для каждого участника.
        Возвращает: общее число ошибок, плотность на одно сообщение и топ частых опечаток.
        """
        stats = {}

        for sender, group in self.df.groupby('sender'):
            total_messages = len(group)
            if total_messages == 0:
                continue

            # Считаем ошибки для каждого сообщения автора
            all_errors = [err for text in group['text'] for err in self._count_errors_in_text(text)]

            total_errors = len(all_errors)
            # Плотность: сколько ошибок в среднем приходится на одно сообщение
            error_density = total_errors / total_messages

            stats[sender] = {
                'total_errors': total_errors,
                'error_density': round(error_density, 4),
                'top_misspelled': Counter(all_errors).most_common(10)  # Топ-5 частых опечаток
            }

        return stats

    def get_error_dynamics(self, period: str = 'M') -> dict:
        """
        Вычисляет изменение плотности ошибок по заданным периодам времени.
        :param period: 'M' - месяц, 'Q' - квартал, 'Y' - год
        """
        df_time = self.df.dropna(subset=['date']).copy()
        df_time['period'] = df_time['date'].dt.to_period(period)
        all_periods = df_time['period'].sort_values().unique()

        stats = {}
        for sender, group in df_time.groupby('sender'):
            timeline_density = pd.Series(0.0, index=all_periods)

            for p, p_group in group.groupby('period'):
                total_msgs = len(p_group)
                if total_msgs == 0:
                    continue
                # Считаем сумму всех ошибок за этот период
                period_errors_count = sum(len(self._count_errors_in_text(text)) for text in p_group['text'])
                timeline_density.loc[p] = round(period_errors_count / total_msgs, 4)

            stats[sender] = timeline_density

        return stats

    def _extract_profanity(self, text: str) -> list:
        """Внутренний метод: находит только настоящие матерные слова."""
        if not text.strip():
            return []

        # Разбиваем текст на чистые слова
        words = re.findall(r'[а-яёa-z0-9\-]+', text.lower())

        found_words = []
        for word in words:
            # 1. ЗАЩИТА: Если слово содержит легальный корень (тебя, небольшой, рублей), сразу пропускаем его
            if any(safe_root in word for safe_root in self._profanity_safe_roots):
                continue

            # 2. Проверяем по жесткому черному списку
            if word in self.profanity_blacklist:
                found_words.append(word)
            # 3. Проверяем по строгому регулярному выражению
            elif self.profanity_regex.match(word):
                found_words.append(word)

        return found_words

    def get_profanity_statistics(self) -> dict:
        """
        Считает количество использования мата за всю переписку для каждого участника.
        Возвращает: общее число матерных слов, плотность на сообщение и личный топ слов.
        """

        stats = {}

        for sender, group in self.df.groupby('sender'):
            total_messages = len(group)
            if total_messages == 0:
                continue

            # Собираем все матерные слова автора
            all_profanity = [word for text in group['text'] for word in self._extract_profanity(text)]

            total_count = len(all_profanity)
            density = total_count / total_messages

            stats[sender] = {
                'total_profanity_count': total_count,
                'profanity_density': round(density, 4),
                'top_profanity': Counter(all_profanity).most_common(10)  # Топ-5 любимых матерных слов
            }

        return stats

    def get_profanity_dynamics(self, period: str = 'M') -> dict:
        """
        Вычисляет изменение плотности мата по заданным периодам времени.
        :param period: 'M' - месяц, 'Q' - квартал, 'Y' - год
        """
        df_time = self.df.dropna(subset=['date']).copy()
        df_time['period'] = df_time['date'].dt.to_period(period)
        all_periods = df_time['period'].sort_values().unique()

        stats = {}
        for sender, group in df_time.groupby('sender'):
            timeline_density = pd.Series(0.0, index=all_periods)

            for p, p_group in group.groupby('period'):
                total_msgs = len(p_group)
                if total_msgs == 0:
                    continue
                # Считаем сумму матерных слов за период
                period_profanity_count = sum(len(self._extract_profanity(text)) for text in p_group['text'])
                timeline_density.loc[p] = round(period_profanity_count / total_msgs, 4)

            stats[sender] = timeline_density

        return stats

    def analyze_topics_and_sentiment(self, server_url: str, split_minutes: int = 360) -> pd.DataFrame:
        """
        Разбивает переписку на диалоги и классифицирует каждый диалог
        по теме и эмоциональному характеру с помощью LLM с гарантией JSON-формата.
        """
        # 1. Готовим данные и определяем границы сессий
        df_time = self.df.dropna(subset=['date']).reset_index(drop=True)
        df_time = df_time.sort_values('date', kind='mergesort').copy()
        df_time['time_diff'] = df_time['date'].diff()
        is_new_dialogue = (df_time['time_diff'] > pd.Timedelta(minutes=split_minutes)) | df_time['time_diff'].isna()
        df_time['dialogue_id'] = is_new_dialogue.cumsum()

        # ============================================================
        # НОВОЕ: тянем промпт и списки из настроек
        # ============================================================
        from core.settings_manager import SettingsManager
        _sm = SettingsManager()
        system_prompt = _sm.llm_system_prompt
        topics_enum = _sm.llm_topics
        sentiments_enum = _sm.llm_sentiments

        results = []
        grouped = df_time.groupby("dialogue_id")
        total_dialogues = len(grouped)

        # Перебираем сессии
        for d_id, group in grouped:
            if len(group) < 3:
                continue

            dialogue_lines = []
            for _, row in group.iterrows():
                sender = str(row["sender"]).strip() if pd.notna(row["sender"]) else "Неизвестный"
                text = str(row["text"]).strip() if pd.notna(row["text"]) else ""
                if text:
                    dialogue_lines.append(f"[{sender}]: {text}")

            full_dialogue_text = "\n".join(dialogue_lines)
            if not full_dialogue_text.strip():
                continue

            # Формируем JSON-запрос со строгой схемой ответа (JSON Schema)
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",
                     "content": f"Analyze this dialogue:\n<dialogue>\n{full_dialogue_text}\n</dialogue>"}
                ],
                "temperature": 0.2,
                "max_tokens": 200,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "chat_analysis_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "reason": {
                                    "type": "string",
                                    "description": "Сначала подробно проанализируй текст диалога на русском языке. Напиши, о чем конкретно идет речь."
                                },
                                "topic": {
                                    "type": "string",
                                    "description": "Strictly classify the core substance based on your reason above.",
                                    "enum": topics_enum
                                },
                                "sentiment": {
                                    "type": "string",
                                    "description": "CRITICAL: Do NOT default to 'Нейтральный' if your own analysis mentions conflict, teasing, accusation, frustration, or threats! Match the emotion strictly.",
                                    "enum": sentiments_enum
                                }
                            },
                            "required": ["reason", "topic", "sentiment"],
                            "additionalProperties": False
                        }
                    }
                }
            }
            try:
                response = requests.post(server_url, json=payload, timeout=720)
                response.raise_for_status()
                response_data = response.json()
                llm_output = response_data["choices"][0]["message"]["content"].strip()
                parsed_json = json.loads(llm_output)
                final_topic = parsed_json.get("topic", "Не определено")
                final_sentiment = parsed_json.get("sentiment", "Не определено")
                final_reason = parsed_json.get("reason", "")
                results.append({
                    "dialogue_id": int(d_id),
                    "messages_count": int(len(group)),
                    "topic": final_topic,
                    "sentiment": final_sentiment,
                    "reason": final_reason,
                })
                print(f"[{d_id}/{total_dialogues}] Успешно обработан.")
            except Exception as e:
                print(f"Ошибка при обработке диалога {d_id} через JSON API: {e}")
                print("Пропускаем ИИ-анализ остальных диалогов.")
                break

        return pd.DataFrame(results)

    @staticmethod
    def format_timedelta(td):
        """Превращает Timedelta или секунды в понятную строку на русском языке."""
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

    def get_avg_message_length_dynamics(self, period: str = 'M') -> dict:
        """
        Вычисляет изменение средней длины сообщения (в словах) по заданным периодам.
        :param period: 'M' - месяц, 'Q' - квартал, 'Y' - год
        """
        df_time = self.df.dropna(subset=['date']).copy()
        df_time['period'] = df_time['date'].dt.to_period(period)
        all_periods = df_time['period'].sort_values().unique()

        # Считаем количество слов (разбиение по пробелам, исключая пустые)
        df_time['words_count'] = df_time['text'].str.strip().apply(
            lambda x: len(x.split()) if x else 0
        )
        # Фильтруем пустые сообщения, чтобы не занижать среднюю длину
        df_time = df_time[df_time['words_count'] > 0]

        stats = {}
        for sender, group in df_time.groupby('sender'):
            timeline_density = pd.Series(0.0, index=all_periods)
            for p, p_group in group.groupby('period'):
                if p_group.empty:
                    continue
                # Считаем среднее количество слов за этот период
                timeline_density.loc[p] = round(p_group['words_count'].mean(), 2)
            stats[sender] = timeline_density
        return stats
