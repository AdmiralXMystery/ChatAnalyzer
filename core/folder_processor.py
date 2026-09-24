# import asyncio
# import shutil
# from pathlib import Path
# from bs4 import BeautifulSoup
# from core.utils import clean_folder_name
#
#
# def get_html_content(file_path: Path) -> str:
#     for encoding in ["utf-8", "windows-1251", "cp1251"]:
#         try:
#             with open(file_path, "r", encoding=encoding) as file:
#                 return file.read()
#         except UnicodeDecodeError:
#             continue
#     raise ValueError("Не удалось определить кодировку файла.")
#
#
#
# async def process_vk_archive_async(archive_root: str, target_dir: str,
#                                    copy_mode: bool, log_callback):
#     try:
#         root_path = Path(archive_root).resolve()
#
#         # 1. Защита и строгое определение папки messages
#         # Если пользователь выбрал саму папку messages, работаем с ней.
#         # Если выбран корень архива (где messages лежит внутри), спускаемся в неё.
#         if root_path.name == "messages":
#             source_dir = root_path
#         else:
#             source_dir = root_path / "messages"
#
#         # Если папка messages вообще не существует по указанному пути
#         if not source_dir.exists() or not source_dir.is_dir():
#             log_callback(f"❌ Ошибка: Папка 'messages' не найдена по пути: {source_dir}\n")
#             return
#
#         target_path = Path(target_dir).resolve() if target_dir else None
#         file_html_path = source_dir / "index-messages.html"
#
#         # Проверка существования критически важного файла индекса
#         if not file_html_path.exists():
#             log_callback(f"❌ Ошибка: Файл индекса {file_html_path.name} не найден.\n")
#             return
#
#         # Если включен режим копирования, создаем целевую папку назначения
#         if copy_mode and target_path:
#             target_path.mkdir(parents=True, exist_ok=True)
#
#         log_callback(f"📖 Чтение и парсинг файла '{file_html_path.name}'...\n")
#         await asyncio.sleep(0.01)
#
#         # Читаем HTML файл индекса
#         html_content = get_html_content(file_html_path)
#         soup = BeautifulSoup(html_content, "html.parser")
#         links = soup.find_all("a", href=True)
#
#         success_count = 0
#         already_processed_count = 0  # Счетчик уже переименованных папок
#         mode_text = "копирование" if copy_mode else "переименование на месте"
#         log_callback(f"⚙️ Режим работы: {mode_text}. Начинаем обработку...\n\n")
#
#         for link in links:
#             name = link.get_text(strip=True) or "Без названия"
#             url = link["href"].replace("\\", "/")
#
#             # Защита от выхода на уровень вверх (профиль и т.д.)
#             if ".." in url or url.startswith("/"):
#                 continue
#
#             url_parts = url.split("/")
#             if not url_parts or len(url_parts) < 2:
#                 continue
#
#             folder_id = url_parts[0]
#
#             # Пропускаем системные папки
#             if folder_id in ["profile", "wall", "photos", "video", "audio", "docs"]:
#                 continue
#
#             source_folder_path = source_dir / folder_id
#             cleaned_name = clean_folder_name(name)
#             new_folder_name = f"{cleaned_name} ({folder_id})"
#
#             # Путь, если папка ВПЕРВЫЕ обрабатывается или ПЕРЕИМЕНОВАНА на месте
#             already_renamed_path = source_dir / new_folder_name
#
#             # Проверяем: если исходной папки нет, но есть папка с новым именем (уже переименована)
#             if not source_folder_path.is_dir() and already_renamed_path.is_dir():
#                 already_processed_count += 1
#
#                 # Если включен режим копирования, мы МОЖЕМ скопировать даже уже переименованную папку!
#                 if copy_mode and target_path:
#                     final_folder_path = target_path / new_folder_name
#                     if not final_folder_path.exists():
#                         try:
#                             await asyncio.to_thread(
#                                 shutil.copytree,
#                                 str(already_renamed_path),
#                                 str(final_folder_path),
#                                 dirs_exist_ok=True
#                             )
#                             log_callback(f"✅ Скопирована уже переименованная: {new_folder_name}\n")
#                             success_count += 1
#                             await asyncio.sleep(0.005)
#                             continue
#                         except Exception as e:
#                             log_callback(f"⚠️ Ошибка копирования переименованной папки ({folder_id}): {e}\n")
#
#             # Стандартная логика для исходных (необработанных) папок
#             if source_folder_path.is_dir():
#                 final_folder_path = (target_path if copy_mode else source_dir) / new_folder_name
#
#                 try:
#                     if final_folder_path.exists():
#                         log_callback(f"⏭️ Пропущено (уже существует): {new_folder_name}\n")
#                         continue
#
#                     if copy_mode:
#                         await asyncio.to_thread(shutil.copytree, str(source_folder_path), str(final_folder_path),
#                                                 dirs_exist_ok=True)
#                         action_log = "скопировано"
#                     else:
#                         await asyncio.to_thread(source_folder_path.rename, final_folder_path)
#                         action_log = "переименовано на месте"
#
#                     log_callback(f"✅ Успешно: [{name}] ({folder_id}) — {action_log}\n")
#                     success_count += 1
#
#                 except Exception as e:
#                     log_callback(f"⚠️ Ошибка обработки для папки ({folder_id}): {e}\n")
#
#                 await asyncio.sleep(0.005)
#
#         # Финальный вывод логов с анализом результатов
#         if success_count == 0 and already_processed_count > 0:
#             if not copy_mode:
#                 log_callback(
#                     f"ℹ️ Выполнение остановлено: все папки ({already_processed_count}) уже были переименованы ранее на месте!\n")
#             else:
#                 log_callback(
#                     f"ℹ️ Обработка завершена: новые папки не найдены, а переименованные папки уже скопированы в целевую директорию.\n")
#         else:
#             log_callback(f"\n🎉 Процесс полностью завершен! Всего успешно обработано чатов: {success_count}\n")
#
#     except Exception as e:
#         log_callback(f"💥 Критическая ошибка: {e}\n")


import asyncio
import shutil
from pathlib import Path
from bs4 import BeautifulSoup
from core.utils import clean_folder_name


def get_html_content(file_path: Path) -> str:
    for encoding in ["utf-8", "windows-1251", "cp1251"]:
        try:
            with open(file_path, "r", encoding=encoding) as file:
                return file.read()
        except UnicodeDecodeError:
            continue
    raise ValueError("Не удалось определить кодировку файла.")


async def process_vk_archive_async(archive_root: str, target_dir: str,
                                   copy_mode: bool, log_callback):
    try:
        root_path = Path(archive_root).resolve()

        if root_path.name == "messages":
            source_dir = root_path
        else:
            source_dir = root_path / "messages"

        if not source_dir.exists() or not source_dir.is_dir():
            await log_callback(f"❌ Ошибка: Папка 'messages' не найдена по пути: {source_dir}\n")
            return

        target_path = Path(target_dir).resolve() if target_dir else None
        file_html_path = source_dir / "index-messages.html"

        if not file_html_path.exists():
            await log_callback(f"❌ Ошибка: Файл индекса {file_html_path.name} не найден.\n")
            return

        if copy_mode and target_path:
            target_path.mkdir(parents=True, exist_ok=True)

        await log_callback(f"📖 Чтение и парсинг файла '{file_html_path.name}'...\n")
        await asyncio.sleep(0.01)

        # ИЗМЕНЕНО: чтение и парсинг — в отдельный поток,
        # чтобы не блокировать event loop Flet'а
        html_content = await asyncio.to_thread(get_html_content, file_html_path)
        soup = await asyncio.to_thread(BeautifulSoup, html_content, "html.parser")
        links = soup.find_all("a", href=True)

        success_count = 0
        already_processed_count = 0
        mode_text = "копирование" if copy_mode else "переименование на месте"
        await log_callback(f"⚙️ Режим работы: {mode_text}. Начинаем обработку...\n\n")

        for link in links:
            name = link.get_text(strip=True) or "Без названия"
            url = link["href"].replace("\\", "/")

            if ".." in url or url.startswith("/"):
                continue

            url_parts = url.split("/")
            if not url_parts or len(url_parts) < 2:
                continue

            folder_id = url_parts[0]

            if folder_id in ["profile", "wall", "photos", "video", "audio", "docs"]:
                continue

            source_folder_path = source_dir / folder_id
            cleaned_name = clean_folder_name(name)
            new_folder_name = f"{cleaned_name} ({folder_id})"
            already_renamed_path = source_dir / new_folder_name

            if not source_folder_path.is_dir() and already_renamed_path.is_dir():
                already_processed_count += 1

                if copy_mode and target_path:
                    final_folder_path = target_path / new_folder_name
                    if not final_folder_path.exists():
                        try:
                            await asyncio.to_thread(
                                shutil.copytree,
                                str(already_renamed_path),
                                str(final_folder_path),
                                dirs_exist_ok=True
                            )
                            await log_callback(f"✅ Скопирована уже переименованная: {new_folder_name}\n")
                            success_count += 1
                            await asyncio.sleep(0.01)
                            continue
                        except Exception as e:
                            await log_callback(f"⚠️ Ошибка копирования переименованной папки ({folder_id}): {e}\n")

            if source_folder_path.is_dir():
                final_folder_path = (target_path if copy_mode else source_dir) / new_folder_name

                try:
                    if final_folder_path.exists():
                        await log_callback(f"⏭️ Пропущено (уже существует): {new_folder_name}\n")
                        continue

                    if copy_mode:
                        await asyncio.to_thread(
                            shutil.copytree,
                            str(source_folder_path),
                            str(final_folder_path),
                            dirs_exist_ok=True
                        )
                        action_log = "скопировано"
                    else:
                        await asyncio.to_thread(source_folder_path.rename, final_folder_path)
                        action_log = "переименовано на месте"

                    await log_callback(f"✅ Успешно: [{name}] ({folder_id}) — {action_log}\n")
                    success_count += 1

                except Exception as e:
                    await log_callback(f"⚠️ Ошибка обработки для папки ({folder_id}): {e}\n")

                # ИЗМЕНЕНО: пауза больше — успевает отработать UI-обновление
                await asyncio.sleep(0.01)

        if success_count == 0 and already_processed_count > 0:
            if not copy_mode:
                await log_callback(
                    f"ℹ️ Выполнение остановлено: все папки ({already_processed_count}) уже были переименованы ранее на месте!\n")
            else:
                await log_callback(
                    f"ℹ️ Обработка завершена: новые папки не найдены, а переименованные папки уже скопированы в целевую директорию.\n")
        else:
            await log_callback(f"\n🎉 Процесс полностью завершен! Всего успешно обработано чатов: {success_count}\n")

    except Exception as e:
        await log_callback(f"💥 Критическая ошибка: {e}\n")