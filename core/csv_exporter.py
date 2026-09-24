import os
import asyncio
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from core.utils import parse_message

async def process_csv_export_async(folder_path: str, mass_mode: bool, log_callback):
    try:
        base_path = Path(folder_path).resolve()

        # Автосоздание папки проекта csv_data
        output_dir = Path(".").resolve() / "csv_data"
        output_dir.mkdir(exist_ok=True)

        target_folders = []

        if mass_mode:
            # Массовый режим: ищем папку messages
            source_dir = base_path if base_path.name == "messages" else base_path / "messages"
            if not source_dir.exists() or not source_dir.is_dir():
                log_callback(f"❌ Ошибка массовой обработки: Папка 'messages' не найдена по пути {source_dir}\n")
                return

            # Собираем все подпапки внутри messages
            for entry in source_dir.iterdir():
                if entry.is_dir() and entry.name not in ["profile", "wall", "photos", "video", "audio", "docs"]:
                    target_folders.append(entry)
            log_callback(f"📂 Найдено папок чатов для массового экспорта: {len(target_folders)}\n\n")
        else:
            # Обычный режим: проверяем конкретную выбранную папку чата
            if not base_path.exists() or not base_path.is_dir():
                log_callback(f"❌ Ошибка: Указанная папка не существует.\n")
                return
            target_folders.append(base_path)

        total_files_parsed = 0
        total_chats_exported = 0

        # ОСНОВНОЕ ИЗМЕНЕНИЕ: Обрабатываем и сохраняем каждый чат изолированно
        for folder in target_folders:
            # Собираем только файлы сообщений (исключая индексный файл)
            html_files = [f for f in os.listdir(folder) if f.endswith('.html') and f != "index-messages.html"]

            if not html_files:
                if not mass_mode:
                    log_callback(f"⚠️ В папке '{folder.name}' отсутствуют файлы сообщений (.html).\n")
                    return
                continue  # В массовом режиме просто пропускаем пустые папки

            log_callback(f"📦 Обработка чата: '{folder.name}' (Найдено файлов: {len(html_files)})\n")

            # Список сообщений конкретно ДЛЯ ЭТОГО чата
            chat_messages = []

            for html_file in html_files:
                file_full_path = folder / html_file
                try:
                    def read_and_parse():
                        with open(file_full_path, "r", encoding="windows-1251", errors="ignore") as file:
                            soup = BeautifulSoup(file, "lxml")
                            return [parse_message(msg) for msg in soup.find_all('div', class_='message')]

                    messages = await asyncio.to_thread(read_and_parse)
                    chat_messages.extend(messages)
                    total_files_parsed += 1
                except Exception as file_err:
                    log_callback(f"   ⚠️ Ошибка чтения файла {html_file}: {file_err}\n")

                await asyncio.sleep(0.001)

            # Если в чате нашлись сообщения, сохраняем его в отдельный файл прямо сейчас
            if chat_messages:
                def save_chat_dataframe(messages_list, chat_folder_name):
                    df = pd.DataFrame(messages_list)
                    if 'date' in df.columns:
                        df.sort_values('date', inplace=True)

                    # Имя файла теперь жестко привязано к названию папки чата (например, messages_id123.csv)
                    filename = f"{chat_folder_name}_vk.csv"
                    final_csv_path = output_dir / filename

                    df.to_csv(final_csv_path, index=False, encoding='utf-8-sig')
                    return final_csv_path

                # Выносим сохранение тяжелого DataFrame в отдельный поток, чтобы UI не зависал
                final_path = await asyncio.to_thread(save_chat_dataframe, chat_messages, folder.name)
                log_callback(f"   💾 Чат сохранен: {final_path.name}\n")
                total_chats_exported += 1
            else:
                log_callback(f"   ℹ️ В чате '{folder.name}' не найдено валидных сообщений.\n")

        # Финальный отчет в лог
        log_callback(f"\n🎉 Процесс полностью завершен!\n")
        log_callback(f"🔹 Успешно экспортировано чатов: {total_chats_exported}\n")
        log_callback(f"🔹 Всего обработано HTML-файлов: {total_files_parsed}\n")
    except Exception as e:
        log_callback(f"💥 Критическая ошибка экспорта: {e}\n")