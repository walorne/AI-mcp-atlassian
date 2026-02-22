# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.9] - 2026-02-12

### Added
- Вывод XML draw.io в Markdown: макрос draw.io конвертируется в блок кода `xml`
- Получение кода PlantUML из внешних файлов при использовании `!include <url>` в макросе

## [0.1.8] - 2026-02-10

### Added
- Добавлены ссылки на Confluence в breadcrumbs
- Добавлена настройка через команду `sm-cf-export config`
- Добавлены параметры CLI

### Changed
- Упрощена инициализация клиента - автоматическая загрузка токенов из `.env`, если они не предоставлены явно
- Упрощена обработка аргументов в CLI, удалён параметр `--page-id`
- Экспорт: файлы получают осмысленные имена, не используются вложенные пути, сохраняются только файлы, упомянутые на странице
- Обновлена структура сохранения HTML-файлов

### Fixed
- Улучшена логика сопоставления Jira-таблиц
- Добавлена обработка сообщений об ошибках в Jira-таблицах (класс `jim-error-message-table`)

## [0.1.7] - 2026-01-30

### Added
- CLI (sm-cf-export)

### Changed
- Обновлена документация по настройке pypi-репозиториев

## [0.1.6] - 2026-01-30

- Работает SSL
- Весь код отполирован, чтобы проходили все линтеры

## [0.1.5] - 2026-01-29

### Fixed
- Для публикации явно указывается сертификат

## [0.1.4] - 2026-01-29

### Changed
- Используется другой образ с python и нашим корп. сертификатом
- Основной репой для pip пока сделал публичную
- Пробую публиковать новые версии через CI

## [0.1.3] - 2026-01-29

### Fixed
- changelog version bump

## [0.1.2] - 2026-01-29

### Added
- Publication to local pypi repo

## [0.1.1] - 2026-01-29

### Added
- Initial release of sm-confluence-tools library
- Confluence page parsing functionality
- Markdown conversion with PlantUML macro support
- Support of various types of Confluence URLs

### Changed
- Refactored from script-based to library-based architecture
- Improved error handling and logging
- Enhanced type safety with type hints

### Fixed
- Initialization order (settings first, then calling Confluence)

### Security

## [0.1.0] - 2026-01-28

### Added
- Initial library structure
- Core Page and Attachment classes
- Basic documentation and examples
- MIT license
- Development tooling configuration (black, flake8, pytest, etc.)
