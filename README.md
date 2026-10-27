# Skyrim Modlist Helper

Учебный сервис на FastAPI для работы со списком модов
Skyrim Special Edition.

## Назначение

Сервис предназначен для пользователей, которые хотят просматривать
небольшой каталог модов, находить записи по названию и описанию,
получать сведения о моде из Nexus Mods и проверять зависимости,
явно внесённые в демонстрационный каталог.

## Возможности

- Каталог из четырёх демонстрационных записей.
- Фильтрация по категории.
- Поиск по названию и описанию.
- Получение мода по локальному ID.
- Загрузка карточки мода из Nexus Mods по Nexus ID.
- Добавление загруженного мода в текущий каталог.
- Проверка явно указанных зависимостей.
- Запуск напрямую или через Nginx.
- Автоматические тесты и GitHub Actions.

## Ограничения

- Поиск выполняется только по текущему каталогу приложения.
- Глобальный поиск по всему Nexus Mods не реализован.
- Загруженные записи хранятся в памяти и исчезают после перезапуска.
- Рекомендуется запускать один процесс Uvicorn: память не разделяется
  между несколькими процессами.
- Моды не скачиваются и не устанавливаются.
- Требования импортированных модов автоматически не извлекаются.
- Проверка не определяет конфликты, порядок загрузки и совместимость.
- Отсутствие данных о зависимостях не означает отсутствие требований.
- Перед установкой нужно читать инструкции на Nexus Mods.

## Архитектура

Браузер → Nginx:8080 → Uvicorn:8000 → FastAPI.

Для получения карточки мода FastAPI обращается к Nexus Mods API.

Основные функции работают без API-ключа.

## Требования

- Ubuntu или Ubuntu в WSL.
- Python 3.10 или новее.
- Git.
- python3-venv.
- Nginx для запуска через обратный прокси.

В CI используется Python 3.12.

## Установка

```bash
git clone https://github.com/YOUR_USERNAME/skyrim-modlist-helper.git
cd skyrim-modlist-helper

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip check
```

Для установки только зависимостей приложения:

```bash
python -m pip install -r requirements.txt
```

## Настройки

Создать локальный файл:

```bash
cp .env.example .env
chmod 600 .env
```

Переменные:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| LOG_LEVEL | INFO | Уровень логирования приложения |
| NEXUS_API_KEY | пусто | Личный ключ Nexus Mods |
| NEXUS_TIMEOUT_SECONDS | 10 | Тайм-аут обращения к Nexus Mods |

Допустимый тайм-аут: больше 0 и не больше 60 секунд.

LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL.
Неизвестное значение заменяется на INFO.

Ключ можно получить в настройках API аккаунта Nexus Mods:

https://www.nexusmods.com/users/myaccount?tab=api

Настоящий .env и ключ нельзя публиковать.

Загрузку .env выполняет Uvicorn при передаче --env-file .env.
Самостоятельно приложение файл .env не читает.

## Запуск

Обычный запуск без --reload:

```bash
python -m uvicorn app_final:app \
  --env-file .env \
  --host 127.0.0.1 \
  --port 8000
```

Запуск для разработки:

```bash
python -m uvicorn app_final:app --env-file .env --reload
```

Документация:

http://localhost:8000/docs

Остановка: Ctrl + C.

## Nginx

Установка:

```bash
sudo apt update
sudo apt install -y nginx
```

Подключение конфигурации из корня проекта:

```bash
sudo cp deploy/nginx.conf /etc/nginx/conf.d/skyrim-modlist-helper.conf
sudo nginx -t
```

При использовании systemd:

```bash
sudo systemctl restart nginx
sudo systemctl status nginx --no-pager
```

Без systemd:

```bash
sudo service nginx restart
sudo service nginx status
```

Uvicorn запускается отдельно и должен продолжать работать на порту 8000.

Документация через Nginx:

http://localhost:8080/docs

Проверки:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8080/health
```

Если стандартный сайт Nginx на порту 80 мешает запуску, сначала
нужно проверить конфликт портов. На свежей учебной установке
неиспользуемый стандартный сайт можно отключить:

```bash
sudo unlink /etc/nginx/sites-enabled/default
sudo nginx -t
```

После успешной проверки перезапустить Nginx.

Не следует отключать чужие сайты на рабочем сервере.

## Маршруты

| Метод | Маршрут | Описание |
|---|---|---|
| GET | /health | Работоспособность |
| GET | /version | Версия |
| GET | /mods | Каталог |
| GET | /mods?category=interface | Фильтрация |
| GET | /mods/search?q=sky | Поиск в текущем каталоге |
| GET | /mods/{mod_id} | Локальная карточка |
| GET | /categories | Категории |
| POST | /build/check | Известные зависимости |
| GET | /nexus/mods/{mod_id} | Получение карточки из Nexus Mods |

Поиск поддерживает параметры limit и offset.

## Примеры

Работоспособность:

```bash
curl http://localhost:8080/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

Версия:

```bash
curl http://localhost:8080/version
```

Ожидаемый ответ:

```json
{"version":"0.1.0"}
```

Поиск:

```bash
curl "http://localhost:8080/mods/search?q=sky&limit=10&offset=0"
```

Получение SkyUI из Nexus Mods:

```bash
curl http://localhost:8080/nexus/mods/12604
```

Без ключа этот маршрут возвращает 503.
Остальные функции продолжают работать.

Проверка без известной зависимости:

```bash
curl -X POST \
  http://localhost:8080/build/check \
  -H "Content-Type: application/json" \
  -d '{"mod_ids":[12604]}'
```

Проверка с добавленной зависимостью:

```bash
curl -X POST \
  http://localhost:8080/build/check \
  -H "Content-Type: application/json" \
  -d '{"mod_ids":[12604,30379]}'
```

Поле known_dependencies_satisfied относится только к записанным
зависимостям. Поле unchecked_mod_ids содержит моды без подготовленных
данных о зависимостях.

## Тесты

```bash
python -m pytest -v
```

Отдельный запуск Uvicorn не нужен.

Тесты не обращаются в интернет и не используют настоящий API-ключ.
Внешние ответы подменяются.

## CI

Workflow запускается при push и pull request.

Шаги:

1. Установка Python.
2. Установка зависимостей.
3. Проверка зависимостей.
4. Запуск тестов.
5. Установка Nginx.
6. Проверка конфигурации через nginx -t.
7. Загрузка artifact skyrim-modlist-helper.

Artifact содержит код, зависимости, README, пример настроек
и конфигурацию Nginx.

Настоящий .env в artifact не включается.

CI не проверяет реальное подключение к Nexus Mods
и не выполняет сквозной HTTP-тест через Nginx.

## Логи

Логи приложения выводятся в терминал Uvicorn.

Основные события:

- запуск и остановка;
- обращение к каталогу;
- результат поиска;
- результат проверки зависимостей;
- результат обращения к Nexus Mods.

Логи Nginx:

```bash
sudo tail -n 20 /var/log/nginx/skyrim_access.log
sudo tail -n 20 /var/log/nginx/skyrim_error.log
```

LOG_LEVEL управляет логированием приложения.
Журналы Uvicorn и Nginx настраиваются отдельно.

## Диагностика

### No module named fastapi

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

### Could not import module app_final

Запускать Uvicorn из корня проекта, где находится app_final.py.

### Порт 8000 занят

Остановить предыдущий процесс.

Для прямого запуска можно выбрать другой порт, но тогда для работы
через Nginx нужно также изменить proxy_pass и перезагрузить конфигурацию.

### Nginx возвращает 502

Проверить приложение напрямую:

```bash
curl http://127.0.0.1:8000/health
```

Проверить журнал:

```bash
sudo tail -n 20 /var/log/nginx/skyrim_error.log
```

Убедиться, что Uvicorn запущен и proxy_pass указывает на правильный порт.

### Nexus Mods возвращает ошибку

- 503 с сообщением о конфигурации: проверить NEXUS_API_KEY.
- 503 с сообщением о лимите: подождать и не повторять запросы непрерывно.
- 502: проверить доступ, ключ, сеть и журнал приложения.
- 504: истёк тайм-аут внешнего запроса.
- 404: мод недоступен по указанному ID.

Ключ нельзя публиковать при обращении за помощью.

### Поиск не находит мод

Поиск не обращается ко всему Nexus Mods.

Сначала мод должен находиться в демонстрационном каталоге
или быть загружен через /nexus/mods/{mod_id}.

### После перезапуска исчезли загруженные моды

Это ожидаемо: каталог хранится в памяти.

### Корень / возвращает 404

Это ожидаемо. Используйте /docs или /health.

### CI красный

Открыть Actions → запуск → первый неуспешный шаг.

Локально выполнить:

```bash
python -m pip check
python -m pytest -v
sudo nginx -t
```

Для проверки именно конфигурации из репозитория предварительно
скопировать deploy/nginx.conf в /etc/nginx/conf.d/.

## Источники и статус проекта

Nexus Mods:

https://www.nexusmods.com/skyrimspecialedition

Документация REST API:

https://api.nexusmods.com/v1

Проект не является официальным сервисом Nexus Mods.
Тексты кратких демонстрационных описаний подготовлены для учебного проекта.