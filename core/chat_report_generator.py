import numpy as np
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Agg')
import re
from core.chat_analyzer import ChatAnalyzer
import requests


class ChatReportGenerator:
    """Класс для генерации HTML-отчета по анализу чата"""

    def __init__(self, csv_path: str, output_dir: str = ".", settings_manager=None):
        self.csv_path = csv_path
        self.output_dir = output_dir
        self.settings_manager = settings_manager  # <-- новое
        self.analyzer = None
        self.llm = None

        # Хранилище для данных
        self.stats = {}
        self.longest_list = []
        self.initiation_stats = {}
        self.session_data = {}
        self.speed_data = {}
        self.top_words_data = {}
        self.vocabulary_data = {}
        self.ttr_history = {}
        self.emoji_data = {}
        self.pos_dist = {}
        self.grammar_charts = {}
        self.spell_stats_data = {}
        self.error_history = {}
        self.profanity_data = {}
        self.profanity_history = {}
        self.laugh_data = {}
        self.word_clouds_paths = {}
        self.llm_results_df = None
        self.msg_length_history = {}

        import os
        os.makedirs(output_dir, exist_ok=True)

    def initialize(self):
        """Инициализация анализатора"""
        print("🚀 Инициализация анализатора чата...")

        if self.settings_manager is not None:
            self.analyzer = ChatAnalyzer(
                self.csv_path,
                stop_words=self.settings_manager.stop_words,
                error_whitelist=self.settings_manager.error_whitelist,
                profanity_blacklist=self.settings_manager.profanity_blacklist,
            )
        else:
            self.analyzer = ChatAnalyzer(self.csv_path)

        print(f"✅ Данные загружены. Всего сообщений: {len(self.analyzer.df)}")
        return self

    def collect_statistics(self, enabled_features: dict):
        """Сбор статистических данных на основе выбранных чекбоксов"""
        print("\n📊 Сбор статистических данных...")

        # Базовая статистика нужна всегда для формирования скелета отчёта
        self.stats = self.analyzer.get_volume_statistics()

        # 1. Динамика длины сообщений
        if enabled_features.get("msg_length"):
            print("  Анализ динамики средней длины сообщений...")
            self.msg_length_history = self.analyzer.get_avg_message_length_dynamics(period='M')
            self._generate_msg_length_chart()

        # 2. Самые длинные сообщения
        if enabled_features.get("longest_messages"):
            print("  Анализ самых длинных сообщений...")
            self.longest_list = self._prepare_longest_messages()

        # 3. Инициаторы диалогов и сессии
        if enabled_features.get("sessions"):
            print("  Анализ инициаторов диалогов...")
            self.initiation_stats = self.analyzer.get_dialogue_initiators(min_gap_minutes=360)
            print("  Поиск самой длительной сессии...")
            self.session_data = self._prepare_session_data()

        # 4. Скорость ответов
        if enabled_features.get("reply_speed"):
            print("  Анализ скорости ответов...")
            self.speed_data = self._prepare_speed_data()

        # 5. Активность по часам и месяцам
        if enabled_features.get("activity_charts"):
            print("  Анализ активности по часам и месяцам...")
            self._generate_hourly_chart()
            self._generate_monthly_chart()

        # 6. Лексическое богатство (Vocabulary & TTR)
        if enabled_features.get("vocabulary"):
            print("  Анализ лексического богатства...")
            self.top_words_data = self.analyzer.get_top_words(top_n=20)
            self.vocabulary_data = self.analyzer.get_vocabulary_richness()
            print("  Анализ динамики TTR...")
            self.ttr_history = self.analyzer.get_ttr_over_time(period='M')
            self._generate_ttr_chart()

        # 7. Эмодзи
        if enabled_features.get("emoji"):
            print("  Анализ эмодзи...")
            self.emoji_data = self.analyzer.get_emoji_statistics()

        # 8. Части речи и грамматика
        if enabled_features.get("linguistics"):
            print("  Анализ частей речи и грамматических признаков...")
            self.pos_dist = self.analyzer.get_pos_distribution()
            self._generate_pos_chart()
            self.grammar_charts = self._generate_grammar_charts()

        # 9. Орфография и ошибки
        if enabled_features.get("spelling"):
            print("  Анализ орфографии...")
            self.spell_stats_data = self.analyzer.get_spelling_statistics()
            self.error_history = self.analyzer.get_error_dynamics(period='M')
            self._generate_error_chart()

        # 10. Обсценная лексика (Мат)
        if enabled_features.get("profanity"):
            print("  Анализ нецензурной лексики...")
            self.profanity_data = self.analyzer.get_profanity_statistics()
            self.profanity_history = self.analyzer.get_profanity_dynamics(period='M')
            self._generate_profanity_chart()

        # 11. Смех и смайлы
        if enabled_features.get("laughter"):
            print("  Анализ смеха и смайлов...")
            self.laugh_data = self.analyzer.get_laugh_statistics()

        # 12. Облака слов
        if enabled_features.get("wordclouds"):
            print("  Генерация облаков слов...")
            self.word_clouds_paths = self._generate_wordclouds()

        return self

    def _prepare_longest_messages(self):
        """Подготовка списка самых длинных сообщений"""
        longest_msgs = self.analyzer.get_longest_messages(top_n=10)
        result = []
        for idx, row in longest_msgs.iterrows():
            formatted_date = row['date'].strftime('%Y-%m-%d %H:%M') if hasattr(row['date'], 'strftime') else str(
                row['date'])
            result.append({
                "sender": row['sender'],
                "date": formatted_date,
                "text_len": row['text_len'],
                "text": row['text'][:200] + "..." if len(row['text']) > 200 else row['text']
            })
        return result

    def _prepare_session_data(self):
        """Подготовка данных о сессии"""
        session = self.analyzer.get_longest_session(max_break_minutes=15)
        if not session:
            return {}

        raw_lines = session['dialogue_text'].split('\n')
        preview_messages = []
        first_sender = None

        def parse_chat_line(line):
            match = re.match(r'^\[(.*?)\] (.*?): (.*)$', line)
            if match:
                date_time, sender, text = match.groups()
                time_short = date_time.split(' ')[1][:5] if ' ' in date_time else date_time
                return {"sender": sender, "time": time_short, "text": text, "is_divider": False}
            return None

        for line in raw_lines[:10]:
            msg = parse_chat_line(line)
            if msg:
                if first_sender is None:
                    first_sender = msg["sender"]
                preview_messages.append(msg)

        if len(raw_lines) > 20:
            skipped_count = len(raw_lines) - 20
            preview_messages.append({
                "is_divider": True,
                "text": f"✂️ Пропущено {skipped_count} сообщений диалога..."
            })

        for line in raw_lines[-10:]:
            msg = parse_chat_line(line)
            if msg:
                if first_sender is None:
                    first_sender = msg["sender"]
                preview_messages.append(msg)

        return {
            "start_time": session['start_time'].strftime('%Y-%m-%d %H:%M') if hasattr(session['start_time'],
                                                                                      'strftime') else str(
                session['start_time']),
            "end_time": session['end_time'].strftime('%Y-%m-%d %H:%M') if hasattr(session['end_time'],
                                                                                  'strftime') else str(
                session['end_time']),
            "duration": str(session['duration']),
            "messages_count": session['messages_count'],
            "preview_messages": preview_messages,
            "first_sender": first_sender
        }

    def _prepare_speed_data(self):
        """Подготовка данных о скорости ответов"""
        time_stats = self.analyzer.get_reply_time_stats(max_gap_minutes=360, context_length=5)
        if not time_stats:
            return {}

        formatted_senders = {}
        for sender, user_time in time_stats['senders'].items():
            formatted_senders[sender] = {
                "avg_reply": self.analyzer.format_timedelta(user_time['avg_reply']),
                "median_reply": self.analyzer.format_timedelta(user_time['median_reply'])
            }

        return {
            "overall_avg": self.analyzer.format_timedelta(time_stats['overall_avg']),
            "overall_median": self.analyzer.format_timedelta(time_stats['overall_median']),
            "fastest_time": self.analyzer.format_timedelta(time_stats['fastest']['time']),
            "fastest_winner": time_stats['fastest']['winner'],
            "slowest_time": self.analyzer.format_timedelta(time_stats['slowest']['time']),
            "slowest_winner": time_stats['slowest']['winner'],
            "slowest_winner_context_messages": time_stats['slowest']['context_messages'],
            "senders": formatted_senders,
        }

    def _generate_hourly_chart(self):
        """Генерация графика часовой активности"""
        hourly_activity = self.analyzer.get_hourly_activity_data()
        fig = plt.figure(figsize=(10, 4.5))
        plt.plot(hourly_activity.index, hourly_activity.values, color='dodgerblue', marker='o', linewidth=2)
        plt.bar(hourly_activity.index, hourly_activity.values, color='skyblue', alpha=0.4)
        plt.title('Средняя активность по времени суток', fontsize=12, pad=10)
        plt.xlabel('Час суток')
        plt.ylabel('Количество сообщений')
        plt.xticks(range(0, 24, 2))
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()
        plt.savefig(f'{self.output_dir}/chart_hourly.png', dpi=150, bbox_inches='tight')
        plt.close(fig)

    def _generate_monthly_chart(self):
        """Генерация графика месячной активности"""
        monthly_intensity = self.analyzer.get_monthly_intensity_data()
        months_str = monthly_intensity.index.astype(str)

        fig = plt.figure(figsize=(10, 4.5))
        plt.plot(months_str, monthly_intensity.values, color='crimson', marker='s', linewidth=2)
        plt.title('Интенсивность общения по месяцам (за все время)', fontsize=12, pad=10)
        plt.xlabel('Месяц')
        plt.ylabel('Количество сообщений')

        step = max(1, len(months_str) // 12)
        plt.xticks(range(0, len(months_str), step), months_str[::step], rotation=45, ha='right')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()
        plt.savefig(f'{self.output_dir}/chart_monthly.png', dpi=150, bbox_inches='tight')
        plt.close(fig)

    def _generate_ttr_chart(self):
        """Генерация графика динамики TTR"""
        fig = plt.figure(figsize=(10, 5))
        colors = ['dodgerblue', 'crimson', 'forestgreen', 'darkorange']
        for i, (sender, data) in enumerate(self.ttr_history.items()):
            timeline = data['timeline']
            if timeline.empty:
                continue
            timestamps = timeline.index.to_timestamp()
            plt.plot(timestamps, timeline.values, label=f"{sender} (ср: {data['mean_period_ttr']})",
                     color=colors[i % len(colors)], marker='o', linewidth=2)
        plt.title('Динамика лексического богатства (TTR) со временем')
        plt.xlabel('Дата')
        plt.ylabel('Коэффициент TTR (выше = разнообразнее речь)')
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.legend()
        plt.gcf().autofmt_xdate()
        plt.tight_layout()
        plt.savefig(f'{self.output_dir}/ttr_dynamics.png', dpi=150, bbox_inches='tight')
        plt.close(fig)

    def _generate_pos_chart(self):
        """Генерация графика распределения частей речи"""
        if not self.pos_dist or 'senders' not in self.pos_dist:
            return

        senders_data = self.pos_dist['senders']
        num_senders = len(senders_data)

        fig, axes = plt.subplots(1, num_senders, figsize=(6 * num_senders, 5))
        if num_senders == 1:
            axes = [axes]

        custom_colors = ['#a78bfa', '#60a5fa', '#34d399', '#fbcfe8', '#fef08a',
                         '#93c5fd', '#a7f3d0', '#fde047', '#fca5a5', '#c084fc',
                         '#fed7aa', '#cbd5e1']

        for ax, (sender, dist) in zip(axes, senders_data.items()):
            top_n_features = 11
            top_items = list(dist.items())[:top_n_features]
            other_pct = sum(pct for pos, pct in list(dist.items())[top_n_features:])

            labels = [item[0] for item in top_items]
            sizes = [item[1] for item in top_items]

            if other_pct > 0:
                labels.append('Другое')
                sizes.append(round(other_pct, 2))

            wedges, _ = ax.pie(sizes, startangle=140, colors=custom_colors[:len(sizes)],
                               wedgeprops=dict(width=0.5, edgecolor='w'))

            left_annotations = []
            right_annotations = []

            for i, p in enumerate(wedges):
                ang = (p.theta2 - p.theta1) / 2. + p.theta1
                y = np.sin(np.deg2rad(ang))
                x = np.cos(np.deg2rad(ang))
                is_right = x >= 0
                text_label = f"{labels[i]} ({sizes[i]}%)"

                info = {
                    "xy": (x, y),
                    "ang": ang,
                    "text": text_label,
                    "base_y": 1.35 * y,
                    "target_x": 1.4 * np.sign(x),
                    "horizontalalignment": "left" if is_right else "right"
                }

                if is_right:
                    right_annotations.append(info)
                else:
                    left_annotations.append(info)

            min_distance = 0.14
            for side_notes in [left_annotations, right_annotations]:
                if not side_notes:
                    continue
                side_notes.sort(key=lambda item: item["base_y"])
                for idx in range(1, len(side_notes)):
                    prev_y = side_notes[idx - 1]["base_y"]
                    curr_y = side_notes[idx]["base_y"]
                    if (curr_y - prev_y) < min_distance:
                        if curr_y > 0:
                            side_notes[idx]["base_y"] = prev_y + min_distance
                        else:
                            side_notes[idx]["base_y"] = prev_y + min_distance
                for idx in range(len(side_notes) - 2, -1, -1):
                    next_y = side_notes[idx + 1]["base_y"]
                    curr_y = side_notes[idx]["base_y"]
                    if (next_y - curr_y) < min_distance:
                        side_notes[idx]["base_y"] = next_y - min_distance

            for side_notes in [left_annotations, right_annotations]:
                for note in side_notes:
                    target_y = note["base_y"]
                    connectionstyle = f"angle,angleA=0,angleB={90 if target_y > note['xy'][1] else -90},rad=0"
                    ax.annotate(note["text"], xy=note["xy"], xytext=(note["target_x"], target_y),
                                horizontalalignment=note["horizontalalignment"], fontsize=9,
                                fontweight='500', arrowprops=dict(arrowstyle="-", color="#94a3b8",
                                                                  lw=0.9, connectionstyle=connectionstyle))

            ax.set_title(f"{sender}", fontsize=14, pad=55)

        plt.suptitle('Лингвистический портрет: распределение частей речи', fontsize=16, y=1.1)
        plt.tight_layout()
        plt.savefig(f'{self.output_dir}/pos_distribution.png', dpi=150, bbox_inches='tight')
        plt.close(fig)

    def _generate_grammar_charts(self):
        """Генерация грамматических портретов"""
        grammar_stats = self.analyzer.get_grammar_features_distribution()
        if not grammar_stats:
            return {}

        grammar_charts = {}
        colors_person = ['#60a5fa', '#34d399', '#f87171']
        colors_number = ['#c084fc', '#fb923c']
        colors_gender = ['#60a5fa', '#f472b6', '#94a3b8']
        colors_time = ['#fbbf24', '#2dd4bf', '#a78bfa', '#cbd5e1']

        for sender, categories in grammar_stats.items():
            fig, axes = plt.subplots(2, 3, figsize=(14, 8))

            plot_config = [
                (axes[0, 0], categories['pronoun']['person'], 'Местоимения: по лицам', colors_person),
                (axes[0, 1], categories['pronoun']['number'], 'Местоимения: по числам', colors_number),
                (axes[1, 0], categories['noun']['gender'], 'Существительные: по роду', colors_gender),
                (axes[1, 1], categories['noun']['number'], 'Существительные: по числам', colors_number),
                (axes[0, 2], categories['verb']['time'], 'Глаголы: по времени', colors_time)
            ]

            axes[1, 2].axis('off')

            for ax, data_dict, title, colors_set in plot_config:
                clean_dict = {k: v for k, v in data_dict.items() if k != "Нет данных"}
                if clean_dict:
                    ax.pie(clean_dict.values(), labels=clean_dict.keys(), autopct='%1.1f%%',
                           startangle=140, colors=colors_set[:len(clean_dict)])
                    ax.set_title(title, fontsize=11, fontweight='bold', pad=10)
                else:
                    ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center', color='gray')
                    ax.axis('off')
                    ax.set_title(title, fontsize=11, fontweight='bold', pad=10)

            plt.suptitle(f"Психолингвистический портрет: {sender}", fontsize=16, fontweight='bold', y=0.98)
            plt.tight_layout()

            safe_sender_name = "".join([c for c in sender if c.isalpha() or c.isdigit()]).lower()
            img_filename = f"{self.output_dir}/grammar_{safe_sender_name}.png"
            plt.savefig(img_filename, dpi=150, bbox_inches='tight')
            plt.close(fig)
            grammar_charts[sender] = img_filename

        return grammar_charts

    def _generate_error_chart(self):
        """Генерация графика динамики ошибок"""
        fig = plt.figure(figsize=(11, 5))
        colors = ['dodgerblue', 'crimson', 'forestgreen']

        for i, (sender, timeline) in enumerate(self.error_history.items()):
            if timeline.empty:
                continue
            timestamps = timeline.index.to_timestamp()
            plt.plot(timestamps, timeline.values, label=f"{sender} (ошибки/сообщ.)",
                     color=colors[i % len(colors)], marker='o', linewidth=2)

        plt.title('Изменение плотности опечаток и ошибок со временем')
        plt.xlabel('Дата переписки')
        plt.ylabel('Среднее кол-во ошибок в одном сообщении')
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.legend()
        plt.gcf().autofmt_xdate(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(f'{self.output_dir}/error_dynamics.png', dpi=150, bbox_inches='tight')
        plt.close(fig)

    def _generate_profanity_chart(self):
        """Генерация графика динамики мата"""
        fig = plt.figure(figsize=(11, 5))
        colors_prof = ['#dc3545', '#007bff', '#28a745']

        for i, (sender, timeline) in enumerate(self.profanity_history.items()):
            if timeline.empty:
                continue
            timestamps = timeline.index.to_timestamp()
            plt.plot(timestamps, timeline.values, label=f"Мат у: {sender}",
                     color=colors_prof[i % len(colors_prof)], marker='v', linewidth=2)

        plt.title('Динамика плотности использования нецензурной лексики со временем')
        plt.xlabel('Дата переписки')
        plt.ylabel('Среднее кол-во матерных слов в одном сообщении')
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.legend()
        plt.gcf().autofmt_xdate(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(f'{self.output_dir}/profanity_dynamics.png', dpi=150, bbox_inches='tight')
        plt.close(fig)

    def _generate_wordclouds(self):
        """Генерация облаков слов со строгой нормализацией путей для HTML"""

        def save_word_cloud(top_words_list, title="Облако слов", filename="wordcloud.png"):
            if not top_words_list:
                return None

            from wordcloud import WordCloud
            words_dict = dict(top_words_list)
            wordcloud = WordCloud(width=1600, height=800, scale=2, background_color='white',
                                  colormap='tab10', max_words=100, prefer_horizontal=0.7)
            wordcloud.generate_from_frequencies(words_dict)
            fig = plt.figure(figsize=(12, 6))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.title(title, fontsize=16, pad=15)
            plt.axis('off')
            plt.tight_layout()

            filepath = f"{self.output_dir}/{filename}"
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close(fig)

            # ИСПРАВЛЕНИЕ 1: В HTML возвращаем ТОЛЬКО имя файла,
            # так как report.html лежит в этой же папке кэша чата!
            return filename

        top_words_cloud = self.analyzer.get_top_words(top_n=100, exclude_basic_verbs=True)
        paths = {"overall": "", "senders": {}}

        paths["overall"] = save_word_cloud(
            top_words_cloud['overall'],
            title="Общие темы и частые слова в переписке",
            filename="wordcloud_overall.png"
        )

        for sender, words_list in top_words_cloud['senders'].items():
            safe_name = "".join([c for c in sender if c.isalpha() or c.isdigit()]).lower()
            filename_sender = f"wordcloud_{safe_name}.png"

            save_word_cloud(
                words_list,
                title=f"Облако слов участника: {sender}",
                filename=filename_sender
            )

            # ИСПРАВЛЕНИЕ 2: Для отправителей тоже отдаем только имя файла
            paths["senders"][sender] = filename_sender

        return paths

    def initialize_llm(self):
        """Проверка связи с локальным сервером LM Studio"""
        print("\n🌐 Проверка подключения к LM Studio...")
        # По умолчанию LM Studio запускает сервер на порту 1234
        self.lm_studio_url = "http://localhost:1234/v1/chat/completions"

        try:
            # Быстрая проверка, запущен ли сервер
            response = requests.get("http://localhost:1234/v1/models", timeout=3)
            if response.status_code == 200:
                print("✅ Успешно подключено к LM Studio! Сервер готов.")
            else:
                print("⚠️ Сервер LM Studio ответил со странным кодом, но он запущен.")
        except requests.exceptions.RequestException:
            print("❌ Ошибка: Сервер LM Studio НЕ запущен на http://localhost:1234")
            print("💡 Пожалуйста, запустите LM Studio и включите 'Local Server' перед началом.")
            # Не прерываем программу, чтобы отработала хотя бы математическая часть отчета
        return self


    def run_llm_analysis(self):
        """Запуск ИИ-анализа диалогов через API LM Studio"""
        print("\n🧠 Запуск разметки диалогов с помощью локальной ИИ (через LM Studio)...")
        self.llm_results_df = self.analyzer.analyze_topics_and_sentiment(self.lm_studio_url, split_minutes=360)

        if self.llm_results_df.empty:
            print("⚠️ Не удалось разметить диалоги через ИИ (возможно, сервер был выключен).")
        else:
            print(f"✅ Размечено {len(self.llm_results_df)} диалогов")
            self._generate_llm_charts()

        return self

    def _generate_llm_charts(self):
        """Генерация графиков на основе LLM анализа"""
        print("  Построение графиков по темам...")
        plt.rcParams["font.family"] = "sans-serif"

        # Строим график тем
        self._plot_pastel_horizontal(
            self.llm_results_df,
            column="topic",
            title="Распределение диалогов по темам",
            filename="chart_topics.png"
        )

        # Строим график сентиментов
        self._plot_pastel_horizontal(
            self.llm_results_df,
            column="sentiment",
            title="Распределение диалогов по характеру (сентименту)",
            filename="chart_sentiment.png"
        )
        print(" Графики LLM анализа сохранены")

    def _plot_pastel_horizontal(self, df, column, title, filename):
        """Построение горизонтального столбцового графика с динамическим размером"""
        if df.empty or column not in df.columns:
            print(f" Нет данных для построения графика по колонке '{column}'")
            return

        counts = df[column].value_counts().sort_values(ascending=True)

        # === ДИНАМИЧЕСКИЙ РАЗМЕР ===
        # Автоматически увеличиваем высоту графика в зависимости от количества уникальных категорий
        num_categories = len(counts)
        graph_height = max(4.5, num_categories * 0.45)

        fig, ax = plt.subplots(figsize=(10, graph_height))

        # === РАСШИРЕННАЯ ПАСТЕЛЬНАЯ ПАЛИТРА (24 уникальных оттенка) ===
        fruitella_palette = [
            "#C7CEEA", "#A3E4D7", "#BFFCC6", "#FFFFBA", "#FFDFBA", "#FFB3BA", "#FFC6FF", "#E8AEB7",
            "#B3C5FF", "#C4FAF8", "#D9FFF4", "#FFF5BA", "#FFDAC1", "#FFCBCB", "#F6A6FF", "#F4C2C2",
            "#A8E6CF", "#DCEDC8", "#FFD3B6", "#FFAAA6", "#FF8B94", "#D8B4F8", "#A7EDE7", "#FFE5A3"
        ]
        colors = [fruitella_palette[i % len(fruitella_palette)] for i in range(num_categories)]

        bars = ax.barh(counts.index, counts.values, color=colors, edgecolor="#333333", height=0.65)

        max_val = counts.max() if not counts.empty else 0
        x_offset = max_val * 0.015

        for bar in bars:
            width = bar.get_width()
            ax.text(width + x_offset, bar.get_y() + bar.get_height() / 2.0,
                    f"{int(width)}", ha="left", va="center", fontsize=10, fontweight="bold", color="black")

        ax.set_title(title, fontsize=14, fontweight="bold", pad=20, color="black")
        ax.set_xlabel("Количество диалогов", fontsize=11, labelpad=10, color="black")
        ax.grid(axis='x', linestyle='--', alpha=0.8, color='#cccccc')
        ax.set_axisbelow(True)

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.spines["left"].set_color("#dddddd")
        ax.spines["bottom"].set_color("#cccccc")
        ax.tick_params(axis="both", which="both", length=0)

        plt.tight_layout()
        plt.savefig(f'{self.output_dir}/{filename}', dpi=150, bbox_inches='tight')
        plt.close(fig)

    def generate_html_report(self, template_file="report_template.html"):
        """Генерация HTML отчета"""
        print("\n📄 Генерация HTML отчета...")

        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template(template_file)

        data_to_render = {
            "total_messages": self.stats.get("total_messages", 0),
            "overall_avg_words": self.stats.get("overall_avg_words", 0),
            "senders": self.stats.get("senders", {}),
            "longest_messages_list": self.longest_list,
            "initiation_stats": self.initiation_stats,
            "session_data": self.session_data if self.session_data else None,
            "speed_data": self.speed_data if self.speed_data else None,
            "top_words": self.top_words_data,
            "vocabulary_data": self.vocabulary_data,
            "ttr_history_exists": bool(self.ttr_history),
            "emoji_data": self.emoji_data,
            "pos_charts_exists": bool(self.pos_dist),
            "grammar_charts": self.grammar_charts if self.grammar_charts else None,
            "spell_stats": self.spell_stats_data,
            "error_charts_exists": bool(self.error_history),
            "profanity_data": self.profanity_data,
            "profanity_charts_exists": bool(self.profanity_history),
            "laugh_data": self.laugh_data,
            "word_clouds": self.word_clouds_paths,
            "llm_charts_exists": bool(self.llm_results_df is not None and not self.llm_results_df.empty),
            "msg_length_charts_exists": bool(self.msg_length_history),
        }

        final_html = template.render(**data_to_render)
        report_path = f"{self.output_dir}/report.html"  # Отчёт ложится в папку кэша чата

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(final_html)


        return report_path

    def run(self, enabled_features: dict, template_file="report_template.html"):
        """Полный пайплайн генерации отчета на основе флагов из GUI"""
        print("\n" + "=" * 50)
        print("🚀 НАЧАЛО ГЕНЕРАЦИИ ОТЧЕТА ПО ЛИЧНОМУ ЧАТУ")
        print("=" * 50)

        self.initialize()

        # Передаем чекбоксы в сборщик статистики
        self.collect_statistics(enabled_features)

        # ИИ-анализ запускаем только если проставлен соответствующий чекбокс
        if enabled_features.get("ai_analysis"):
            self.initialize_llm()
            self.run_llm_analysis()

        report_path = self.generate_html_report(template_file)

        print("\n" + "=" * 50)
        print(f"🎉 ГОТОВО! Отчет создан: {report_path}")
        print("=" * 50)
        return report_path

    def _generate_msg_length_chart(self):
        """Генерация графика динамики средней длины сообщений"""
        fig = plt.figure(figsize=(11, 5))
        colors = ['dodgerblue', 'crimson', 'forestgreen', 'darkorange']

        for i, (sender, timeline) in enumerate(self.msg_length_history.items()):
            if timeline.empty:
                continue
            timestamps = timeline.index.to_timestamp()
            plt.plot(timestamps, timeline.values, label=f"Ср. длина у: {sender}",
                     color=colors[i % len(colors)], marker='o', linewidth=2)

        plt.title('Изменение средней длины сообщений (в словах) со временем')
        plt.xlabel('Дата переписки')
        plt.ylabel('Среднее кол-во слов в одном сообщении')
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.legend()
        plt.gcf().autofmt_xdate(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(f'{self.output_dir}/msg_length_dynamics.png', dpi=150, bbox_inches='tight')
        plt.close(fig)