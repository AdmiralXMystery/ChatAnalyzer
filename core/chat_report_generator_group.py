import os
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Agg')

from core.chat_analyzer_group import GroupChatAnalyzer


class GroupChatReportGenerator:
    """Генератор HTML-отчёта по анализу ГРУППОВОГО чата."""

    def __init__(self, csv_path: str, output_dir: str = ".", settings_manager=None):
        self.csv_path = csv_path
        self.output_dir = output_dir
        self.settings_manager = settings_manager
        self.analyzer = None

        # Хранилище данных
        self.volume_data = {}
        self.daily_activity = {}
        self.timeline_data = {}
        self.longest_messages = []
        self.pause_data = {}
        self.top_words_data = {}
        self.word_map_data = {}
        self.emoji_data = {}
        self.profanity_data = {}

        # Пути к сгенерированным графикам/облакам
        self.chart_paths = {}
        self.wordcloud_path = None

        os.makedirs(output_dir, exist_ok=True)

    # ============================================================
    # ИНИЦИАЛИЗАЦИЯ
    # ============================================================
    def initialize(self):
        """Инициализация анализатора группового чата."""
        print("🚀 Инициализация анализатора ГРУППОВОГО чата...")

        if self.settings_manager is not None:
            self.analyzer = GroupChatAnalyzer(
                self.csv_path,
                stop_words=self.settings_manager.stop_words,
                error_whitelist=self.settings_manager.error_whitelist,
                profanity_blacklist=self.settings_manager.profanity_blacklist,
            )
        else:
            self.analyzer = GroupChatAnalyzer(self.csv_path)

        print(f"✅ Данные загружены. Всего сообщений: {len(self.analyzer.df)}")
        print(f"👥 Участников: {self.analyzer.df['sender'].nunique()}")
        return self

    # ============================================================
    # СБОР СТАТИСТИКИ
    # ============================================================
    def collect_statistics(self, enabled_features: dict):
        """Сбор статистики на основе выбранных чекбоксов."""
        print("\n📊 Сбор статистических данных...")

        # Базовая статистика нужна всегда
        print("  Объёмы переписки...")
        self.volume_data = self.analyzer.get_volume_statistics()

        # 1. Суточная активность
        if enabled_features.get("daily_activity", True):
            print("  Суточная активность...")
            self.daily_activity = self.analyzer.get_daily_activity()

        # 2. График активности (автомасштаб)
        if enabled_features.get("activity_chart", True):
            print("  График активности по времени...")
            self.timeline_data = self.analyzer.get_activity_timeline()
            self._generate_activity_chart()

        # 3. Топ участников (полезно для группового чата)
        if enabled_features.get("top_senders", True):
            print("  Топ участников...")
            self._generate_top_senders_chart()

        # 4. Самые длинные сообщения
        if enabled_features.get("longest_messages", True):
            print("  Топ длинных сообщений...")
            self.longest_messages = self._prepare_longest_messages()

        # 5. Самый долгий перерыв
        if enabled_features.get("longest_pause", True):
            print("  Самый долгий перерыв...")
            self.pause_data = self._prepare_pause_data()

        # 6. Топ слов + карта слов
        if enabled_features.get("top_words", True):
            print("  Топ слов...")
            self.top_words_data = self.analyzer.get_top_words(top_n=30)
            self.word_map_data = self.analyzer.get_word_map()

        # 7. Эмодзи
        if enabled_features.get("emoji", True):
            print("  Эмодзи...")
            self.emoji_data = self.analyzer.get_emoji_statistics(top_n=15)

        # 8. Мат
        if enabled_features.get("profanity", True):
            print("  Нецензурная лексика...")
            self.profanity_data = self.analyzer.get_profanity_statistics(top_n=15)

        # 9. Облако слов
        if enabled_features.get("wordcloud", True):
            print("  Облако слов...")
            self.wordcloud_path = self._generate_wordcloud()

        return self

    # ============================================================
    # ПОДГОТОВКА ДАННЫХ
    # ============================================================
    def _prepare_longest_messages(self):
        """Подготовка списка самых длинных сообщений."""
        df = self.analyzer.get_longest_messages(top_n=10)
        result = []
        for _, row in df.iterrows():
            formatted_date = (
                row['date'].strftime('%Y-%m-%d %H:%M')
                if hasattr(row['date'], 'strftime') else str(row['date'])
            )
            text = row['text']
            result.append({
                "sender": row['sender'],
                "date": formatted_date,
                "text_len": int(row['text_len']),
                "text": text[:300] + "..." if len(text) > 300 else text
            })
        return result

    def _prepare_pause_data(self):
        """Подготовка данных о самом долгом перерыве."""
        pause = self.analyzer.get_longest_pause(context_length=3)
        if not pause:
            return {}

        return {
            "duration": self.analyzer.format_timedelta(pause['pause_duration']),
            "before_date": pause['pause_after_date'].strftime('%Y-%m-%d %H:%M:%S')
            if hasattr(pause['pause_after_date'], 'strftime') else str(pause['pause_after_date']),
            "after_date": pause['pause_before_date'].strftime('%Y-%m-%d %H:%M:%S')
            if hasattr(pause['pause_before_date'], 'strftime') else str(pause['pause_before_date']),
            "context_dialogue": pause['context_dialogue']
        }

    # ============================================================
    # ГРАФИКИ
    # ============================================================
    def _generate_activity_chart(self):
        """График активности переписки с автомасштабом."""
        series = self.timeline_data.get('series')
        if series is None or series.empty:
            return

        scale_label = self.timeline_data['scale_label']
        x_labels = series.index.tolist()
        y_values = series.values

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(range(len(x_labels)), y_values, marker='o',
                linewidth=1.8, markersize=4, color='steelblue')
        ax.fill_between(range(len(x_labels)), y_values, alpha=0.15, color='steelblue')

        step = max(1, len(x_labels) // 15)
        ax.set_xticks(range(0, len(x_labels), step))
        ax.set_xticklabels(x_labels[::step], rotation=45, ha='right')

        ax.set_title(f'Активность переписки (по {scale_label})', fontsize=13, pad=12)
        ax.set_xlabel(f'Период (по {scale_label})')
        ax.set_ylabel('Количество сообщений')
        ax.grid(True, linestyle='--', alpha=0.5)

        plt.tight_layout()
        path = f'{self.output_dir}/chart_activity.png'
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        self.chart_paths['activity'] = 'chart_activity.png'

    def _generate_top_senders_chart(self):
        """Горизонтальная диаграмма топ-15 участников по сообщениям."""
        senders = self.volume_data.get('senders', {})
        if not senders:
            return

        sorted_senders = sorted(
            senders.items(),
            key=lambda kv: kv[1]['messages_count'],
            reverse=True
        )[:15]

        names = [s[0] for s in sorted_senders][::-1]
        counts = [s[1]['messages_count'] for s in sorted_senders][::-1]

        height = max(5, len(names) * 0.4)
        fig, ax = plt.subplots(figsize=(10, height))
        bars = ax.barh(names, counts, color='mediumseagreen',
                       edgecolor='#333', height=0.65)

        max_val = max(counts) if counts else 0
        x_offset = max_val * 0.015

        for bar in bars:
            width = bar.get_width()
            ax.text(width + x_offset, bar.get_y() + bar.get_height() / 2.0,
                    f"{int(width)}", ha='left', va='center',
                    fontsize=9, fontweight='bold')

        ax.set_title('Топ-15 участников по количеству сообщений',
                     fontsize=13, pad=12)
        ax.set_xlabel('Количество сообщений')
        ax.grid(axis='x', linestyle='--', alpha=0.5)
        ax.set_axisbelow(True)
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)

        plt.tight_layout()
        plt.savefig(f'{self.output_dir}/chart_top_senders.png',
                    dpi=150, bbox_inches='tight')
        plt.close(fig)
        self.chart_paths['top_senders'] = 'chart_top_senders.png'

    # ============================================================
    # ОБЛАКО СЛОВ
    # ============================================================
    def _generate_wordcloud(self):
        """Генерация облака слов из общей карты слов."""
        try:
            from wordcloud import WordCloud
        except ImportError:
            print("  ⚠️ wordcloud не установлен: pip install wordcloud")
            return None

        frequencies = self.word_map_data.get('word_frequencies', {})
        if not frequencies:
            return None

        wc = WordCloud(
            width=1600, height=800, scale=2,
            background_color='white',
            colormap='tab10',
            max_words=200,
            collocations=False,
            prefer_horizontal=0.85,
            random_state=42
        )
        wc.generate_from_frequencies(frequencies)

        fig = plt.figure(figsize=(12, 6))
        plt.imshow(wc, interpolation='bilinear')
        plt.title('Облако слов группового чата', fontsize=16, pad=15)
        plt.axis('off')
        plt.tight_layout()

        path = f'{self.output_dir}/wordcloud_overall.png'
        plt.savefig(path, dpi=200, bbox_inches='tight')
        plt.close(fig)

        return 'wordcloud_overall.png'
    # ============================================================
    # HTML-ОТЧЁТ
    # ============================================================
    def generate_html_report(self, template_file="group_report_template.html"):
        """Генерация HTML-отчёта."""
        print("\n📄 Генерация HTML-отчёта...")

        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template(template_file)

        # Подготовим компактные списки для удобного рендера
        top_words_list = self.top_words_data.get('overall', [])
        word_map_unique = self.word_map_data.get('unique_words_count', 0)
        word_map_total = self.word_map_data.get('total_words_count', 0)

        data_to_render = {
            # Общие объёмы
            "total_messages": self.volume_data.get("total_messages", 0),
            "total_participants": self.volume_data.get("total_participants", 0),
            "senders": self.volume_data.get("senders", {}),

            # Суточная активность
            "daily_activity": self.daily_activity,

            # График активности
            "timeline_scale_label": self.timeline_data.get('scale_label'),
            "activity_chart": self.chart_paths.get('activity'),

            # Топ участников
            "top_senders_chart": self.chart_paths.get('top_senders'),

            # Длинные сообщения
            "longest_messages_list": self.longest_messages,

            # Перерыв
            "pause_data": self.pause_data if self.pause_data else None,

            # Топ слов + карта слов
            "top_words": top_words_list,
            "word_map_unique": word_map_unique,
            "word_map_total": word_map_total,

            # Эмодзи
            "emoji_data": self.emoji_data,

            # Мат
            "profanity_data": self.profanity_data,

            # Облако слов
            "wordcloud_path": self.wordcloud_path,
        }

        final_html = template.render(**data_to_render)
        report_path = f"{self.output_dir}/report.html"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(final_html)

        # print(f"✅ Отчёт сохранён: {report_path}")
        return report_path

    # ============================================================
    # ПОЛНЫЙ ПАЙПЛАЙН
    # ============================================================
    def run(self, enabled_features: dict,
            template_file="group_report_template.html"):
        print("\n" + "=" * 50)
        print("🚀 ГЕНЕРАЦИЯ ОТЧЁТА ПО ГРУППОВОМУ ЧАТУ")
        print("=" * 50)

        self.initialize()
        self.collect_statistics(enabled_features)

        report_path = self.generate_html_report(template_file)

        print("\n" + "=" * 50)
        print(f"🎉 ГОТОВО! Отчёт создан: {report_path}")
        print("=" * 50)
        return report_path