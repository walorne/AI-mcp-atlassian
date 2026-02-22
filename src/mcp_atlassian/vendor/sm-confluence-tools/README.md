# sm-confluence-tools

Библиотека для выполнения самых разнообразных операций с Confluence :)

Инструменты для парсинга и преобразования страниц Confluence в Markdown с поддержкой специальных макросов (PlantUML).

Под капотом используется библиотека [confluence-markdown-exporter](https://github.com/Spenhouet/confluence-markdown-exporter)

## Возможности

- Парсинг страниц Confluence по ID
- Конвертация HTML-контента в Markdown
- Поддержка макросов PlantUML
- Экспорт вложений
- Обработка Jira-таблиц
- Гибкая настройка логирования

## Установка

### Из корпоративного репозитория

Первая команда устанавливает в глобальные настройки корпоративный репозиторий.

```bash
pip config set global.index-url https://artifactory.app.local/artifactory/api/pypi/pypi.virt/simple
```

Если на машине надо собирать проекты и без vpn, то надо еще добавить глобальный репозиторий как дополнительный (**extra**-index-url):
```bash
pip config set global.extra-index-url https://pypi.org/simple
```

Затем установить библиотеку:
```bash
pip install sm-confluence-tools
```

### Для разработки

```bash
git clone https://gitlab.app.local/ai/sm-confluence-tools.git
cd sm-confluence-tools
pip install -e ".[dev]"
```

## Использование в других проектах

### В pyproject.toml другого проекта

Добавьте зависимость в секцию `[project.dependencies]`:

```toml
[project]
dependencies = [
    "sm-confluence-tools",
    # другие зависимости...
]
```

И добавить секцию с нашим репозиторием:
```
[tool.uv]
native-tls = true

[[tool.uv.index]]
name = "smlab"
url = "https://artifactory.app.local/artifactory/api/pypi/pypi.virt/simple"
```

Если хочется собирать без vpn (и локально уже выкачана sm-confluence-tools), то вставляем и наш репозиторий, и публичный:
```
[tool.uv]
native-tls = true
index-strategy = "unsafe-best-match"

[[tool.uv.index]]
name = "smlab"
url = "https://artifactory.app.local/artifactory/api/pypi/pypi.virt/simple"

[[tool.uv.index]]
name = "pypi"
url = "https://pypi.org/simple"
default = true
```

### В requirements.txt другого проекта

```txt
sm-confluence-tools
```

### С указанием конкретной версии

```toml
# В pyproject.toml
dependencies = [
    "sm-confluence-tools==0.1.5",
]
```

# Использование

### CLI (запуск из командной строки)

Команда `sm-cf-export` загружает страницу Confluence, сохраняет метаданные, HTML, Markdown, данные редактора и список вложений, затем экспортирует вложения. Поддерживаются таймауты и запись логов в файл.

1. Установите переменную окружения `CONFLUENCE_TOKEN` (или создайте файл `.env` из `.env.example` и сохраните там токен).
Можно еще установить JIRA_TOKEN, чтобы выгружать страницы, где есть плагины jira.

2. Запуск по ID страницы или по URL:
   ```bash
   sm-cf-export 1222798993
   sm-cf-export "https://confluence.app.local/pages/viewpage.action?pageId=1222798993"
   ```

3. Настройка через меню в командной строке (аналогично `confluence-markdown-exporter config`):
   ```bash
   sm-cf-export config
   ```
   Открывается интерактивное меню.

Справка по параметрам:
   ```bash
   sm-cf-export -h
   ```

**Еще примеры:**

```bash
# Сложная страница и отладка
sm-cf-export --page-id 1222798993 --timeout 60 --log-level DEBUG

# Своя папка для результатов
sm-cf-export 1222798993 --output-dir ./my-export
```

## Быстрый старт в коде

Самая минималистичная версия:
```python
from sm_confluence_tools import SmConfluenceTools

client = SmConfluenceTools(confluence_token="confluence token here!")

page = client.Page.from_url("https://confluence.app.local/pages/viewpage.action?pageId=1234412311")
markdown = page.markdown
```

Работающий пример в [`quick_start.py`](examples/quick_start.py).

## Примеры

Больше примеров использования можно найти в директории [`examples/`](examples/):

- [`basic_usage.py`](examples/basic_usage.py) - базовый пример использования
- Дополнительные примеры будут добавлены в будущем

## Запуск примера basic_usage.py

Сначала установите переменные среды или укажите значения прямо в коде вот тут:
```python
    confluence_token = os.getenv("CONFLUENCE_TOKEN")
    jira_token = os.getenv("JIRA_TOKEN")
```

```bash
# Запуск базового примера
python examples/basic_usage.py
```

## Тестирование

```bash
# Запуск всех тестов
pytest

# Запуск с покрытием кода
pytest --cov=sm_confluence_tools

# Запуск конкретного теста
pytest tests/test_stub.py
```

## Разработка

### Установка зависимостей для разработки

```bash
pip install -e ".[dev]"
```

### Форматирование кода

```bash
# Форматирование с black
black src/ tests/ examples/

# Сортировка импортов
isort src/ tests/ examples/

# Проверка с flake8
flake8 src/ tests/ examples/

# Проверка типов
mypy src/
```

### Инкремент версии

1. Описать изменения в [CHANGELOG.md](CHANGELOG.md) под заголовком \#\# [Unreleased]
2. Выполнить ```bump-my-version bump patch```
3. ```git push --follow-tags```

### Pre-commit hooks (опционально)

```bash
# Установка pre-commit hooks
pre-commit install

# Запуск проверки вручную
pre-commit run --all-files
```

## Основные классы

### Page

Основной класс для работы со страницами Confluence.

**Методы:**
- `Page.from_id(page_id: int) -> Page` - загрузка страницы по ID
- `page.export()` - экспорт страницы с вложениями
- `page.markdown` - свойство для получения Markdown контента

**Свойства:**
- `id` - ID страницы
- `title` - заголовок страницы
- `space` - пространство Confluence
- `body` - HTML контент страницы
- `body_export` - HTML для экспорта
- `editor2` - XML контент редактора (на самом деле там контент первой версии)
- `attachments` - список вложений
- `ancestors` - список предков страницы
- `labels` - метки страницы

### Attachment

Класс для работы с вложениями.

**Методы:**
- `Attachment.from_page_id(page_id: int) -> List[Attachment]` - получение вложений страницы
- `attachment.export()` - скачивание вложения

## Поддерживаемые макросы

- **PlantUML** - автоматическая конвертация в Markdown код-блоки
- **Jira** - обработка Jira-макросов и таблиц

## Требования

- Python 3.12+

## Лицензия

MIT License. См. файл [LICENSE](LICENSE).

## История изменений

См. файл [CHANGELOG.md](CHANGELOG.md).

## Поддержка

При возникновении проблем или вопросов:
1. Проверьте [CHANGELOG.md](CHANGELOG.md) на известные проблемы
2. Посмотрите примеры в директории [`examples/`](examples/)
3. Создайте issue в [GitLab](https://gitlab.app.local/ai/sm-confluence-tools/-/issues)

## Авторы

SM Lab <lab@example.com>
