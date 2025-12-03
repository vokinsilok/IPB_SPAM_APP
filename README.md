# IPB SPAM APP

Автоматизация регистрации и создания обращений на ukc.gov.ua

## Структура проекта

```
IPB_SPAM_APP/
├── data/                          # Данные (не в git)
│   ├── peoples.csv               # Данные военнослужащих
│   ├── firemail_accounts.csv     # Импортированные Firemail аккаунты
│   └── firemail_raw.txt          # Сырые данные Firemail для импорта
│
├── registrations/                 # Результаты регистрации (не в git)
│   ├── ukc_registered.csv        # Зарегистрированные UKC аккаунты
│   ├── appeals_database.json     # База данных обращений
│   └── confirmation_links.txt    # Ссылки подтверждения email
│
├── appeals/                       # Созданные обращения (не в git)
│   └── [ФИО]/                    # Папка для каждого человека
│       └── [Тема]/               # Папка для каждой темы
│           ├── appeal_ru.docx    # Текст на русском
│           ├── appeal_uk.docx    # Текст на украинском
│           └── screenshot.png    # Скриншот обращения
│
├── reports/                       # Отчёты (не в git)
│   └── appeals_report_*.xlsx     # Excel отчёты по обращениям
│
├── scripts/                       # Вспомогательные скрипты
│   ├── import_firemail.py        # Импорт Firemail аккаунтов
│   ├── add_manual_account.py     # Добавление аккаунта вручную
│   ├── add_existing_account.py   # Добавление существующего аккаунта
│   └── test_*.py                 # Тестовые скрипты
│
├── docs/                          # Документация
│   ├── QUICK_START.md            # Быстрый старт
│   └── REGISTRATION_FLOW.md      # Описание процесса регистрации
│
├── register_ukc.py               # Основной скрипт регистрации
├── create_appeals.py             # Создание обращений
├── collect_appeals_report.py     # Сбор отчётов
├── requirements.txt              # Зависимости
├── .env                          # Переменные окружения (не в git)
└── .gitignore                    # Игнорируемые файлы

```

## Основные скрипты

### 1. Импорт Firemail аккаунтов
```bash
python scripts/import_firemail.py
```
Импортирует аккаунты из `data/firemail_raw.txt` в `data/firemail_accounts.csv`

### 2. Регистрация на UKC
```bash
python register_ukc.py
```
Регистрирует аккаунты на ukc.gov.ua используя данные из:
- `data/peoples.csv` - данные военнослужащих
- `data/firemail_accounts.csv` - Firemail аккаунты

Результат сохраняется в `registrations/ukc_registered.csv`

### 3. Создание обращений
```bash
python create_appeals.py
```
Создаёт 10 обращений для каждого зарегистрированного аккаунта:
- Генерирует тексты через OpenAI
- Сохраняет в DOCX (русский и украинский)
- Делает скриншоты с подменой даты
- Сохраняет в базу данных

### 4. Сбор отчётов
```bash
python collect_appeals_report.py
```
Собирает все обращения в Excel отчёт

## Настройка

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Настройка .env
```env
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=openai/gpt-4o-mini
OPENAI_BASE_URL=https://openai.api.proxyapi.ru/v1
```

### 3. Подготовка данных
1. Поместите данные военнослужащих в `data/peoples.csv`
2. Поместите Firemail аккаунты в `data/firemail_raw.txt`
3. Запустите импорт: `python scripts/import_firemail.py`

## Особенности

- **Без прокси**: работает напрямую
- **Firemail**: использует готовые купленные аккаунты
- **Ручное подтверждение**: email подтверждается вручную через https://firemail.de
- **OpenAI**: генерация текстов обращений
- **Chrome debugging**: использует существующий Chrome с remote debugging
- **33 темы**: полный список тем с портала UKC

## Статусы регистрации

- `registered_needs_manual_confirmation` - зарегистрирован, требуется подтверждение email
- `registration_failed_no_redirect` - регистрация не удалась

## Поддержка

Для вопросов и проблем создавайте issue в репозитории.
