# Screen Implementation Plan

> For agentic workers: use superpowers:executing-plans for inline implementation and a final independent review.

Goal: Рабочий прозрачный референс для Windows с portable-сборкой.

Architecture: Чистая геометрия и I/O отдельно от Qt. Отдельное прозрачное окно на
каждый экран; независимая панель; системный пропуск ввода и RegisterHotKey.

Tech Stack: Python 3.12, PySide6 Essentials 6, ctypes, unittest, Ruff, PyInstaller.

Spec: docs/superpowers/specs/2026-11-02-glass-overlay-design.md

## Global Constraints

- Windows 10/11 x64; рисунок и пути пользователя не покидают ПК.
- Пропускать ввод через все изображение в режиме обводки.
- Панель и трей всегда дают способ восстановления, ошибки горячих клавиш отображаются.
- Предел изображения: 32 млн пикселей; сторона <=16384; проект <=64 MiB.
- Преобразования ограничены конечными значениями, размером 24–16384 логических пикселей.

## Review Focus

- Полностью прозрачный PNG и нулевая непрозрачность: ручки доступны в настройке.
- Смена мониторов/отрицательные координаты/DPI: центрирование восстанавливает изображение.
- Занятая глобальная клавиша: явное сообщение, панель/трей остаются способом возврата.
- Поврежденный или слишком большой файл/проект: текущий референс не теряется.
- Закрытие/повторные переключения: не остается прозрачных окон и регистраций клавиш.

### Task 1: Геометрия и загрузка

Files: screen_overlay/geometry.py, images.py, project.py; tests/test_geometry.py, test_images.py, test_project.py.

Interfaces: Placement(center_x, center_y, width, height, rotation); local_to_world,
world_to_local, zoom_at, resized; load_image(path), clipboard_image(mime);
save_project(path, image, placement, opacity, flips), load_project(path).

- [ ] Написать и запустить падающие unittest для zoom-anchor, повернутого resize,
  независимых размеров, ограничений и нечисловых значений.
- [ ] Реализовать геометрию, добиться прохождения тестов.
- [ ] Написать и запустить падающие тесты файлов/буфера и project roundtrip,
  некорректных данных и атомарного сохранения.
- [ ] Реализовать загрузку и проекты; python -m unittest discover -s tests -v должен пройти.

### Task 2: Оверлей, панель и Win32

Files: screen_overlay/{overlay,native,panel,app,__main__,__init__}.py, tests/test_gui.py, test_native.py.

Interfaces: OverlayWindow.changed(Placement), mode_requested; Controller управляет
изображением/геометрией/видимостью; HotkeyManager callback по имени действия.

- [ ] Написать падающие Qt-тесты прозрачного рендера, непрозрачности, ввода,
  смены режима, изменения размера, открытия/ошибки и восстановления панели.
- [ ] Реализовать отдельные прозрачные окна и русскую панель; тесты должны пройти.
- [ ] Добавить Windows-only тесты реальных native-стилей, доставки WM_HOTKEY и прохода клика.
- [ ] Проверить GUI визуально через screenshot и view_image.

### Task 3: Сборка и передача

Files: pyproject.toml, requirements*.txt, scripts/build_windows.ps1, Screen.spec,
.github/workflows/ci.yml, README.md, LICENSE, THIRD_PARTY_NOTICES.md.

- [ ] Добавить воспроизводимые зависимости, запуск из исходников и portable-сборку.
- [ ] Настроить Linux/Windows CI, тесты и запуск упакованного exe; загрузить ZIP artifact.
- [ ] Выполнить Ruff, unittest и smoke-test, независимое ревью; исправить существенные находки.
- [ ] Опубликовать код в репозитории, проверить Actions; передать инструкцию и ссылку на сборку.
