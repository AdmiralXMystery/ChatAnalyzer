import json
import asyncio
from pathlib import Path
import pandas as pd
from core.utils import clean_folder_name


async def process_json_export_async(file_or_folder_path: str, log_callback):
    try:
        base_path = Path(file_or_folder_path).resolve()

        # Автосоздание папки проекта csv_data (как в вашем исходном коде)
        output_dir = Path(".").resolve() / "csv_data"
        output_dir.mkdir(exist_ok=True)

        # Определяем, где искать json-файл
        if base_path.is_dir():
            json_file = base_path / "result.json"
        else:
            json_file = base_path

        if not json_file.exists():
            log_callback(f"❌ Ошибка: Файл JSON не найден по пути {json_file}\n")
            return

        log_callback(f"📦 Чтение и парсинг Telegram JSON: '{json_file.name}'...\n")

        # Функция для тяжелого парсинга структуры JSON в отдельном потоке
        def read_and_parse_json():
            with open(json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            chats_to_process = {}

            # Сценарий 1: Массовый экспорт всего аккаунта Telegram
            if 'chats' in data and 'list' in data['chats']:
                for chat in data['chats']['list']:
                    chat_name = chat.get('name') or f"chat_{chat.get('id')}"
                    chat_name = clean_folder_name(chat_name)  # Используем вашу чистку из файла 2
                    chats_to_process[chat_name] = chat.get('messages', [])

            # Сценарий 2: Экспорт только одного конкретного чата Telegram
            elif 'messages' in data:
                chat_name = data.get('name') or base_path.parent.name or "telegram_chat"
                chat_name = clean_folder_name(chat_name)
                chats_to_process[chat_name] = data['messages']

            return chats_to_process

        chats_data = await asyncio.to_thread(read_and_parse_json)

        if not chats_data:
            log_callback("⚠️ Не удалось найти сообщения в структуре JSON.\n")
            return

        total_chats_exported = 0

        for chat_name, messages in chats_data.items():
            if not messages:
                continue

            log_callback(f"🔄 Обработка чата: '{chat_name}' (Сообщений: {len(messages)})\n")
            chat_messages = []

            for msg in messages:
                # Пропускаем сервисные уведомления (очистка истории, звонки и т.д.)
                if msg.get('type') != 'message':
                    continue

                # --- 1. Сборка текста (Telegram разбивает форматированный текст на списки) ---
                text_pieces = msg.get('text')
                full_text = ""
                if isinstance(text_pieces, list):
                    for piece in text_pieces:
                        if isinstance(piece, dict):
                            full_text += piece.get('text', '')
                        else:
                            full_text += str(piece)
                else:
                    full_text = str(text_pieces or "")

                # --- 2. Сборка вложений (attachments) в стиле вашего старого парсера ---
                attachments = []

                # Проверяем медиафайлы (фото, видео, голосовые, файлы)
                media_type = msg.get('media_type')
                file_path = msg.get('file')

                if file_path:
                    # Имитируем структуру из старого кода VK: [{'description': ..., 'url': ...}]
                    attachments.append({
                        'description': f"Telegram Media: {media_type or 'file'}",
                        'url': str(file_path)
                    })
                elif msg.get('photo'):
                    attachments.append({
                        'description': "Photo",
                        'url': str(msg.get('photo'))
                    })

                # --- 3. Формирование финального словаря (колонки как в вашем файле 2) ---
                parsed_msg = {
                    'id': msg.get('id'),
                    'sender': msg.get('from') or f"ID {msg.get('from_id', 'Unknown')}",  # 'sender' вместо 'from_name'
                    'date': msg.get('date'),  # В JSON дата уже в идеальном ISO формате 'YYYY-MM-DDTHH:MM:SS'
                    'text': full_text.strip(),
                    'attachments': attachments if attachments else []  # Сохраняем массив объектов
                }
                chat_messages.append(parsed_msg)

            # Сохранение результатов в файл (вынесено в отдельный поток)
            if chat_messages:
                def save_dataframe(messages_list, name):
                    df = pd.DataFrame(messages_list)
                    if 'date' in df.columns:
                        df.sort_values('date', inplace=True)

                    filename = f"{name}_tg.csv"
                    final_csv_path = output_dir / filename

                    # Сохраняем в utf-8-sig, чтобы Excel корректно читал русские буквы
                    df.to_csv(final_csv_path, index=False, encoding='utf-8-sig')
                    return final_csv_path

                final_path = await asyncio.to_thread(save_dataframe, chat_messages, chat_name)
                log_callback(f"   💾 Чат сохранен: {final_path.name}\n")
                total_chats_exported += 1

            await asyncio.sleep(0.001)

        log_callback(f"\n🎉 Процесс полностью завершен!\n")
        log_callback(f"🔹 Успешно экспортировано чатов: {total_chats_exported}\n")

    except Exception as e:
        log_callback(f"💥 Критическая ошибка экспорта JSON: {e}\n")