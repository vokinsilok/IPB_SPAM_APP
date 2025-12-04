"""
Регистрация аккаунтов на ukc.gov.ua из CSV файла
"""
import asyncio
import csv
import logging
import argparse
import re
from datetime import datetime
from pathlib import Path
import subprocess
import time
import requests
from playwright.async_api import async_playwright, Page
from proxy_config import (
    find_working_proxy,
    format_proxy_for_playwright,
    log_proxy_usage,
    print_proxy_stats
)
# Email confirmation отключен - требуется ручное подтверждение

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Пути
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REGISTRATIONS_DIR = BASE_DIR / "registrations"
FIREMAIL_ACCOUNTS_CSV = DATA_DIR / "firemail_accounts.csv"
UKC_ACCOUNTS_CSV = REGISTRATIONS_DIR / "ukc_registered.csv"
PEOPLES_CSV = DATA_DIR / "peoples.csv"
OUTPUT_DIR = REGISTRATIONS_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Путь к файлу с ссылками подтверждения
CONFIRMATION_LINKS_FILE = OUTPUT_DIR / "confirmation_links.txt"

# Фиксированный адрес (из примера)
DEFAULT_ADDRESS = {
    'city': 'Запоріжжя',
    'district': 'Запорізький, Запорізька',
    'street': 'вул. Новокузнецька',
    'building': '10',
    'apartment': '157'
}

# Фиксированный телефон (если нет в CSV)
DEFAULT_PHONE = '979509573'

# Задержка перед стартом сценария (секунды)
START_DELAY_SECONDS = 12

# Настройки прокси перенесены в proxy_config.py
# Используется автоматический поиск рабочего прокси


def generate_password(length=16):
    """Генерация случайного пароля"""
    import random
    import string
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))


def save_confirmation_link(email, link, full_name=""):
    """Сохранение ссылки подтверждения в текстовый файл"""
    try:
        # Создаём файл с заголовком, если он не существует
        if not CONFIRMATION_LINKS_FILE.exists():
            with open(CONFIRMATION_LINKS_FILE, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("ССЫЛКИ ПОДТВЕРЖДЕНИЯ РЕГИСТРАЦИИ UKC\n")
                f.write("="*80 + "\n")
                f.write("Этот файл содержит все ссылки подтверждения email для регистрации на ukc.gov.ua\n")
                f.write("Используйте эти ссылки для ручного подтверждения в случае необходимости\n")
                f.write("="*80 + "\n")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(CONFIRMATION_LINKS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Дата: {timestamp}\n")
            f.write(f"Email: {email}\n")
            if full_name:
                f.write(f"ФИО: {full_name}\n")
            f.write(f"Ссылка подтверждения:\n{link}\n")
        logger.info(f"✓ Ссылка подтверждения сохранена в {CONFIRMATION_LINKS_FILE}")
    except Exception as e:
        logger.warning(f"⚠ Не удалось сохранить ссылку подтверждения: {e}")


def load_people_from_csv(csv_path):
    """Загрузка данных людей из CSV"""
    people = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig автоматически убирает BOM
        reader = csv.DictReader(f)
        for row in reader:
            # Определение пола по отчеству
            patronymic = row.get('Отчество', '').strip()
            gender = 'Чоловік' if patronymic.endswith(('ович', 'ійович', 'йович')) else 'Жінка'
            
            # Телефон из CSV или дефолтный
            phone = row.get('Моб. тел.', '').strip()
            if not phone:
                phone = DEFAULT_PHONE
            # Убираем все кроме цифр
            phone = ''.join(c for c in phone if c.isdigit())
            
            people.append({
                'first_name': row.get('Имя', '').strip(),
                'last_name': row.get('Фамилия', '').strip(),
                'patronymic': patronymic,
                'birth_date': row.get('Дата рождения', '').strip(),
                'gender': gender,
                'phone': phone,
                'raw_data': row
            })
    return people


def load_firemail_accounts():
    """Загрузка аккаунтов Firemail"""
    accounts = []
    if not FIREMAIL_ACCOUNTS_CSV.exists():
        logger.error(f"✗ Файл не найден: {FIREMAIL_ACCOUNTS_CSV}")
        logger.info("Запустите сначала: python scripts/import_firemail.py")
        return accounts
    
    if FIREMAIL_ACCOUNTS_CSV.stat().st_size == 0:
        logger.error(f"✗ Файл пустой: {FIREMAIL_ACCOUNTS_CSV}")
        logger.info("Запустите сначала: python scripts/import_firemail.py")
        return accounts
    
    with open(FIREMAIL_ACCOUNTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'email' in row and 'password' in row:
                accounts.append({
                    'email': row['email'],
                    'password': row['password']
                })
    
    logger.info(f"✓ Загружено {len(accounts)} Firemail аккаунтов")
    return accounts


def load_registered_ukc_accounts():
    """
    Загрузка уже зарегистрированных UKC аккаунтов
    Возвращает:
    - registered_emails: set - использованные Firemail аккаунты
    - registered_people: set - обработанные люди (по ФИО)
    """
    registered_emails = set()
    registered_people = set()
    ukc_file = OUTPUT_DIR / "ukc_registered.csv"
    
    if not ukc_file.exists():
        return registered_emails, registered_people
    
    try:
        with open(ukc_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get('email', '').strip()
                full_name = row.get('full_name', '').strip()
                status = row.get('status', '').strip()
                
                # Добавляем email (любой статус - чтобы не использовать повторно)
                if email:
                    registered_emails.add(email.lower())
                
                # Добавляем ФИО только для успешных регистраций
                if full_name and ('registered' in status.lower() or 'success' in status.lower()):
                    # Нормализуем ФИО для сравнения
                    normalized_name = ' '.join(full_name.lower().split())
                    registered_people.add(normalized_name)
        
        if registered_emails:
            logger.info(f"✓ Найдено {len(registered_emails)} использованных Firemail аккаунтов")
        if registered_people:
            logger.info(f"✓ Найдено {len(registered_people)} уже обработанных людей")
        return registered_emails, registered_people
    except Exception as e:
        logger.warning(f"⚠ Ошибка загрузки зарегистрированных аккаунтов: {e}")
        return set(), set()


# Функции transliterate, normalize_name, generate_username_from_person удалены - не используются с Firemail


async def wait_for_manual_action(page: Page, message: str):
    """Ожидание ручного действия пользователя"""
    logger.info("=" * 80)
    logger.info(f"⚠️  {message}")
    logger.info("=" * 80)
    input("Нажмите Enter когда выполните действие...")


# Функция confirm_email_in_onionmail удалена - используется confirm_email_via_imap из email_confirmer.py


async def register_ukc_account(page: Page, context, browser, person: dict, email: str, firemail_password: str):
    """Регистрация аккаунта на ukc.gov.ua"""
    first_name = person['first_name']
    last_name = person['last_name']
    patronymic = person['patronymic']
    birth_date = person['birth_date']
    gender = person['gender']
    phone = person['phone']
    
    # Генерируем пароль для UKC
    ukc_password = generate_password()

    # Обработка телефона: убираем 0 в начале если длина 10 символов
    if phone and len(phone) == 10 and phone.startswith('0'):
        phone = phone[1:]  # Убираем первый символ (0)
        logger.info(f"Телефон обработан: убран ведущий 0, результат: {phone}")
    
    # Проверка длины пароля (минимум 1 цифра)
    if not any(c.isdigit() for c in ukc_password):
        if len(ukc_password) < 16:
            ukc_password = ukc_password + '1'
        else:
            ukc_password = ukc_password[:-1] + '1'
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"Регистрация на UKC: {first_name} {patronymic} {last_name}")
    logger.info(f"Email: {email}")
    logger.info(f"Пол: {gender}")
    logger.info(f"Телефон: {phone}")
    logger.info("=" * 80)
    
    try:
        # Шаг 1: Открываем ukc.gov.ua
        logger.info("Открываю ukc.gov.ua...")
        
        try:
            # Пробуем загрузить страницу с более мягким условием ожидания
            await page.goto("https://ukc.gov.ua/", timeout=90000, wait_until='commit')
            logger.info(f"✓ Страница начала загружаться: {page.url}")
            
            # Ждём полной загрузки
            await page.wait_for_load_state('domcontentloaded', timeout=30000)
            logger.info(f"✓ Страница загружена: {page.url}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"✗ Ошибка при загрузке страницы: {error_msg}")
            
            # Дополнительная диагностика
            if "ERR_TIMED_OUT" in error_msg or "timeout" in error_msg.lower():
                logger.error("⚠ Таймаут при подключении к сайту")
                logger.error("Возможные причины:")
                logger.error("  1. Сайт недоступен из вашей сети")
                logger.error("  2. Проблемы с DNS")
                logger.error("  3. Блокировка на уровне провайдера/файрвола")
                logger.error("Попробуйте открыть https://ukc.gov.ua/ в обычном браузере")
            
            raise
        
        # Ждём для прохождения возможных проверок безопасности
        await asyncio.sleep(3)
        
        # Проверяем Cloudflare или другие защиты
        if "challenge" in page.url or "__cf_chl" in page.url or "checking" in page.url.lower():
            logger.warning("⚠ Обнаружена проверка безопасности, ожидание...")
            await asyncio.sleep(10)
            logger.info(f"Текущий URL после ожидания: {page.url}")
            
            # Если всё ещё на странице проверки - ждём вручную
            if "challenge" in page.url or "__cf_chl" in page.url:
                await wait_for_manual_action(page, "Пройдите проверку Cloudflare")
        
        # Шаг 2: Клик на "Зареєструйтеся"
        logger.info("Нажимаю 'Зареєструйтеся'...")
        await page.get_by_role("link", name="Зареєструйтеся").click()
        await asyncio.sleep(2)
        
        # Шаг 3: Email и пароль
        logger.info("Заполняю email и пароль...")
        await page.fill('#email', email)
        await page.fill('#password', ukc_password)
        await page.fill('#password_repeat', ukc_password)
        await page.get_by_role("button", name="Продовжити").click()
        await asyncio.sleep(2)
        
        # Шаг 4: Выбор типа особи
        logger.info("Выбираю 'Фізична особа'...")
        await page.locator("div").filter(has_text=re.compile(r"^Оберіть тип особи$")).nth(1).click()
        await page.get_by_text("Фізична особа").click()
        await page.get_by_role("button", name="Продовжити").click()
        await asyncio.sleep(2)
        
        # Шаг 5: Персональные данные
        logger.info("Заполняю персональные данные...")
        
        # Заполняем текстовые поля напрямую по ID (как в старом проекте)
        logger.info(f"Заполняю Прізвище: {last_name}")
        await page.fill('#surname', last_name)
        await asyncio.sleep(0.3)
        
        logger.info(f"Заполняю Ім'я: {first_name}")
        await page.fill('#name', first_name)
        await asyncio.sleep(0.3)
        
        logger.info(f"Заполняю По батькові: {patronymic}")
        await page.fill('#patronymic', patronymic)
        await asyncio.sleep(0.5)
        
        # Пол (dropdown) - ищем по label "Стать"
        logger.info(f"Выбираю пол: {gender}")
        gender_dropdown = page.locator('label:has-text("Стать")').locator('..').locator('.Dropdown-control')
        await gender_dropdown.click(timeout=10000)
        await asyncio.sleep(0.5)
        await page.get_by_text(gender, exact=True).click(timeout=10000)
        
        await asyncio.sleep(0.5)
        
        # Телефоны
        logger.info(f"Заполняю телефоны: {phone}")
        await page.fill('#phone', phone)
        await page.fill('#additional_phone', phone)
        
        await asyncio.sleep(0.5)
        
        # Соціальний стан (dropdown)
        logger.info("Выбираю соціальний стан: Військовослужбовець")
        social_dropdown = page.locator('label:has-text("Соціальний стан")').locator('..').locator('.Dropdown-control')
        await social_dropdown.click(timeout=10000)
        await asyncio.sleep(0.5)
        await page.get_by_text("Військовослужбовець", exact=True).click(timeout=10000)
        
        await asyncio.sleep(0.5)
        
        # Категорія - Учасник війни (чекбокс)
        logger.info("Отмечаю: Учасник війни")
        await page.locator("label:has-text('Учасник війни')").click(timeout=10000)
        
        await asyncio.sleep(1)
        
        # Шаг 6: Адрес
        logger.info("Заполняю адрес...")
        
        # Индекс
        await page.fill('#zip', '61000')
        
        # Населенный пункт (React-Select)
        logger.info("Выбираю город: Запоріжжя")
        try:
            city_field = page.locator('form .form-field:has(label:has-text("Населений пункт"))')
            await city_field.wait_for(state='visible', timeout=10000)
            
            # Проверяем, не выбран ли уже город
            try:
                selected = await city_field.locator('.dropdown__single-value').inner_text(timeout=1000)
                if 'Запоріжжя' in selected:
                    logger.info("✓ Город уже выбран")
                    await page.wait_for_selector('#street:not(.dropdown--is-disabled)', timeout=10000)
                else:
                    raise Exception("Другой город выбран")
            except:
                # Город не выбран, выбираем
                city_input = city_field.locator('[id^="react-select-"][id$="-input"]')
                await city_input.focus()
                await city_input.fill('')
                await city_input.type("Запоріжжя", delay=30)
                
                # Ждём появления списка
                await asyncio.sleep(2)
                
                # Просто нажимаем Enter для выбора первой опции
                await page.keyboard.press('Enter')
                logger.info("✓ Нажал Enter для выбора города")
                
                # Ждём пока поле street станет активным
                await page.wait_for_selector('#street:not(.dropdown--is-disabled)', timeout=10000)
                logger.info("✓ Город выбран")
                
        except Exception as e:
            logger.error(f"✗ Ошибка выбора города: {e}")
        
        await asyncio.sleep(1)
        
        # Улица (React-Select)
        logger.info("Выбираю улицу: Новокузнецька")
        try:
            street_field = page.locator('form .form-field:has(label:has-text("Вулиця"))')
            await street_field.wait_for(state='visible', timeout=10000)
            
            # Проверяем, не выбрана ли уже улица
            try:
                selected = await street_field.locator('.dropdown__single-value').inner_text(timeout=1000)
                if 'Новокузнецька' in selected:
                    logger.info("✓ Улица уже выбрана")
                else:
                    raise Exception("Другая улица выбрана")
            except:
                # Улица не выбрана, выбираем
                street_input = street_field.locator('[id^="react-select-"][id$="-input"]')
                await street_input.focus()
                await street_input.fill('')
                await street_input.type("в", delay=30)
                
                # Ждём появления списка
                await asyncio.sleep(2)
                
                # Просто нажимаем Enter для выбора первой опции
                await page.keyboard.press('Enter')
                logger.info("✓ Нажал Enter для выбора улицы")
                
        except Exception as e:
            logger.error(f"✗ Ошибка выбора улицы: {e}")
        
        # Дом и квартира
        await page.fill('#building', DEFAULT_ADDRESS['building'])
        await page.fill('#flat', DEFAULT_ADDRESS['apartment'])
        
        await asyncio.sleep(2)
        
        # Шаг 7: Обход reCAPTCHA и нажатие кнопки регистрации
        logger.info("Обход капчи...")
        try:
            await page.evaluate("""
            () => {
              const token = 'TEST_TOKEN_' + Math.random().toString(36).slice(2);
              const fire = (el) => { try { el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); } catch(e) {} };
              // Set any grecaptcha response fields
              const areas = Array.from(document.querySelectorAll('textarea[id^="g-recaptcha-response"], textarea[name="g-recaptcha-response"]'));
              areas.forEach(t => { try { t.value = token; fire(t); } catch(e) {} });
              const inputs = Array.from(document.querySelectorAll('input[id^="g-recaptcha-response"], input[name="g-recaptcha-response"]'));
              inputs.forEach(t => { try { t.value = token; fire(t); } catch(e) {} });
              // Create hidden textarea if none exist
              if (areas.length === 0 && inputs.length === 0) {
                try {
                  const form = document.querySelector('form') || document.body;
                  const ta = document.createElement('textarea');
                  ta.id = 'g-recaptcha-response';
                  ta.name = 'g-recaptcha-response';
                  ta.style.display = 'none';
                  ta.value = token;
                  form.appendChild(ta);
                  fire(ta);
                } catch(e) {}
              }
              try { if (window.grecaptcha && typeof grecaptcha.getResponse === 'function') { grecaptcha.getResponse(); } } catch(e) {}
              // Enable action buttons
              const labels = ['Продовжити','Відправити','Надіслати','Отправить'];
              const nodes = Array.from(document.querySelectorAll('button, input[type="submit"]'));
              nodes.forEach(b => {
                const txt = (b.textContent || b.value || '').trim();
                if (labels.some(l => txt.includes(l))) { try { b.removeAttribute('disabled'); b.disabled = false; } catch(e) {} }
              });
            }
            """)
            logger.info("✓ Обход капчи выполнен")
            
            # Нажимаем кнопку "Продовжити"
            await asyncio.sleep(1)
            logger.info("Нажимаю кнопку 'Продовжити'...")
            await page.get_by_role("button", name="Продовжити").click()
            
            # Ждём редиректа как признак успешной регистрации
            logger.info("Ожидаю редиректа...")
            registration_successful = False
            try:
                # Ждём изменения URL или появления страницы подтверждения
                await page.wait_for_url(lambda url: '/portal' in url or 'success' in url.lower(), timeout=30000)
                logger.info(f"✓ Редирект выполнен: {page.url}")
                registration_successful = True
            except Exception as e:
                logger.warning(f"⚠ Редирект не произошёл за 30 секунд: {e}")
                logger.info(f"Текущий URL: {page.url}")
                # Проверяем есть ли ошибки на странице
                try:
                    error = await page.locator('.error, .alert-danger, [class*="error"]').first.inner_text(timeout=2000)
                    logger.error(f"✗ Ошибка на странице: {error}")
                    return {
                        'success': False,
                        'status': 'registration_error',
                        'error': error,
                        'email': email,
                        'ukc_password': ukc_password,
                        'firemail_password': firemail_password,
                        'full_name': f"{first_name} {patronymic} {last_name}",
                        'phone': phone,
                        'submitted': True,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                except:
                    pass
            
            # Если редирект НЕ выполнен - выходим
            if not registration_successful:
                logger.error("✗ Регистрация не завершена - редирект не произошёл")
                return {
                    'success': False,
                    'status': 'registration_failed_no_redirect',
                    'email': email,
                    'ukc_password': ukc_password,
                    'firemail_password': firemail_password,
                    'full_name': f"{first_name} {patronymic} {last_name}",
                    'phone': phone,
                    'submitted': True,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            
        except Exception as e:
            logger.warning(f"⚠ Не удалось обойти капчу: {e}")
            await wait_for_manual_action(page, "Решите капчу вручную и нажмите 'Продовжити'")
        
        # Шаг 8: Регистрация успешна! Сразу возвращаем результат
        logger.info("=" * 80)
        logger.info("✓✓✓ РЕГИСТРАЦИЯ НА UKC УСПЕШНА!")
        logger.info(f"Email: {email}")
        logger.info(f"Пароль UKC: {ukc_password}")
        logger.info(f"Пароль Firemail: {firemail_password}")
        logger.info("=" * 80)
        logger.info("")
        logger.info("⚠ ТРЕБУЕТСЯ РУЧНОЕ ПОДТВЕРЖДЕНИЕ EMAIL:")
        logger.info("1. Откройте https://firemail.de в браузере")
        logger.info(f"2. Войдите с данными: {email} / {firemail_password}")
        logger.info("3. Найдите письмо от ukc.gov.ua")
        logger.info("4. Кликните по ссылке подтверждения")
        logger.info("=" * 80)
        
        full_name = f"{first_name} {patronymic} {last_name}"
        
        # Возвращаем успешный результат сразу после редиректа
        return {
            'success': True,
            'status': 'registered_needs_manual_confirmation',
            'email': email,
            'ukc_password': ukc_password,
            'firemail_password': firemail_password,
            'full_name': full_name,
            'phone': phone,
            'submitted': True,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        logger.error(f"✗ Ошибка при регистрации: {e}")
        
        # Проверяем, был ли выполнен редирект (регистрация успешна)
        try:
            current_url = page.url
            if '/portal' in current_url or 'signup' in current_url:
                logger.info("✓ Несмотря на ошибку, редирект выполнен - регистрация успешна!")
                return {
                    'success': True,
                    'status': 'registered_needs_manual_confirmation',
                    'email': email,
                    'ukc_password': ukc_password,
                    'firemail_password': firemail_password,
                    'full_name': f"{first_name} {patronymic} {last_name}",
                    'phone': phone,
                    'submitted': True,
                    'error': str(e),
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
        except:
            pass
        
        return {
            'success': False,
            'status': f"error: {str(e)}",
            'email': email,
            'ukc_password': ukc_password,
            'firemail_password': firemail_password,
            'full_name': f"{first_name} {patronymic} {last_name}",
            'phone': phone,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


def save_results(results, output_file):
    """Сохранение результатов в единый CSV файл без дублей.
    Записываем:
    - все успешные
    - а также неуспешные, если была отправка формы (submitted=True)
    Дедупликация только успешных по email.
    """
    if not results:
        return
    
    # Формируем записи для сохранения
    records_to_consider = [r for r in results if r.get('submitted') or r.get('success')]
    if not records_to_consider:
        logger.warning("⚠ Нет попыток регистрации для сохранения")
        return
    
    fieldnames = ['full_name', 'phone', 'email', 'ukc_password', 'firemail_password', 'status', 'submitted', 'timestamp']
    
    # Читаем существующие строки и собираем успешные email для дедупликации
    existing_success_emails = set()
    existing_rows = []
    if output_file.exists():
        try:
            with open(output_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = (row.get('email') or '').strip().lower()
                    status = (row.get('status') or '').strip().lower()
                    if email and status == 'success':
                        existing_success_emails.add(email)
                    existing_rows.append(row)
        except Exception as e:
            logger.warning(f"⚠ Ошибка чтения существующего файла: {e}")
    
    # Добавляем новые записи, успешные не дублируем по email
    new_count = 0
    for r in records_to_consider:
        row = {
            'full_name': r.get('full_name', ''),
            'phone': r.get('phone', ''),
            'email': r.get('email', ''),
            'ukc_password': r.get('ukc_password', ''),
            'firemail_password': r.get('firemail_password', ''),
            'status': r.get('status', ''),
            'submitted': str(bool(r.get('submitted'))),
            'timestamp': r.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        }
        email_lower = row['email'].strip().lower()
        if r.get('success'):
            if email_lower in existing_success_emails:
                continue
            existing_success_emails.add(email_lower)
        existing_rows.append(row)
        new_count += 1
    
    # Записываем обратно
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)
    
    if new_count > 0:
        logger.info(f"✓ Добавлено {new_count} новых записей в: {output_file}")
    else:
        logger.info(f"✓ Все записи уже были в файле: {output_file}")


async def main(count=None):
    """Главная функция"""
    logger.info("=" * 80)
    logger.info("РЕГИСТРАЦИЯ АККАУНТОВ НА UKC.GOV.UA С FIREMAIL")
    logger.info("=" * 80)
    
    # Загрузка данных
    logger.info(f"Загрузка данных из: {PEOPLES_CSV}")
    people = load_people_from_csv(PEOPLES_CSV)
    logger.info(f"Загружено персон: {len(people)}")
    
    # Загрузка Firemail аккаунтов
    logger.info(f"Загрузка Firemail аккаунтов из: {FIREMAIL_ACCOUNTS_CSV}")
    firemail_accounts = load_firemail_accounts()
    
    if not firemail_accounts:
        logger.error("✗ Нет аккаунтов Firemail!")
        logger.error("Запустите сначала: python import_firemail.py")
        return
    
    logger.info(f"Загружено Firemail аккаунтов: {len(firemail_accounts)}")
    
    # Ограничение количества
    if count and count < len(people):
        people = people[:count]
        logger.info(f"Будет обработано: {count} персон")
    
    # Проверяем, что хватит аккаунтов
    if len(firemail_accounts) < len(people):
        logger.warning(f"⚠ Недостаточно Firemail аккаунтов! Нужно: {len(people)}, есть: {len(firemail_accounts)}")
        people = people[:len(firemail_accounts)]
    
    # Запуск браузера с прокси и новым профилем
    logger.info("Запуск браузера с проверкой прокси...")
    
    # Подключение к браузеру через Playwright
    async with async_playwright() as p:
        # Создаём уникальную директорию для профиля браузера
        profile_dir = BASE_DIR / "browser_profiles" / "registration_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Сначала запускаем временный браузер для проверки прокси
        logger.info("")
        logger.info("Поиск рабочего прокси для gov.ua...")
        temp_browser = await p.chromium.launch(headless=False)
        temp_context = await temp_browser.new_context()
        temp_page = await temp_context.new_page()
        
        # Ищем рабочий прокси
        working_proxy = await find_working_proxy(temp_page)
        await temp_page.close()
        await temp_context.close()
        await temp_browser.close()
        
        if not working_proxy:
            logger.error("✗ Не найден рабочий прокси для gov.ua!")
            logger.error("Добавьте больше прокси в proxy_config.py")
            return
        
        # Запускаем браузер с профилем и найденным прокси
        proxy_config = format_proxy_for_playwright(working_proxy)
        logger.info(f"✓ Используется прокси: {working_proxy['name']} ({working_proxy['server']})")
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            proxy=proxy_config,
            locale='uk-UA',
            color_scheme='light',
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            timezone_id='Europe/Kiev',
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        results = []
        # Единый файл для всех регистраций UKC
        output_file = OUTPUT_DIR / "ukc_registered.csv"
        
        # Загружаем уже зарегистрированные UKC аккаунты и обработанных людей
        registered_emails, registered_people = load_registered_ukc_accounts()
        
        # Регистрация каждого человека с Firemail аккаунтами
        firemail_idx = 0  # Индекс для Firemail аккаунтов
        
        for idx, person in enumerate(people, start=1):
            logger.info(f"\n>>> Прогресс: {idx}/{len(people)} <<<")
            logger.info("")
            
            # Проверяем, не обработан ли уже этот человек
            full_name = f"{person['first_name']} {person['patronymic']} {person['last_name']}"
            normalized_name = ' '.join(full_name.lower().split())
            
            if normalized_name in registered_people:
                logger.warning(f"⚠ Человек {full_name} уже обработан, пропускаю...")
                results.append({
                    'success': False,
                    'status': 'person_already_processed',
                    'email': '',
                    'ukc_password': '',
                    'firemail_password': '',
                    'full_name': full_name,
                    'phone': person['phone'],
                    'submitted': False,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                continue
            
            # Проверяем, есть ли ещё Firemail аккаунты
            if firemail_idx >= len(firemail_accounts):
                logger.error(f"✗ Закончились Firemail аккаунты! Обработано {firemail_idx} из {len(people)}")
                break
            
            # Берём следующий неиспользованный Firemail аккаунт
            while firemail_idx < len(firemail_accounts):
                firemail_account = firemail_accounts[firemail_idx]
                email = firemail_account['email']
                firemail_password = firemail_account['password']
                firemail_idx += 1
                
                # Проверяем, не использован ли уже этот email
                if email.lower() not in registered_emails:
                    break
                else:
                    logger.warning(f"⚠ Email {email} уже использован, беру следующий...")
            else:
                logger.error(f"✗ Все Firemail аккаунты уже использованы!")
                break
            
            result = await register_ukc_account(page, context, browser, person, email, firemail_password)
            results.append(result)
            
            # Сохраняем промежуточные результаты
            save_results(results, output_file)
            
            # Пауза между регистрациями
            if idx < len(people):
                logger.info("Пауза 5 секунд перед следующей регистрацией...")
                await asyncio.sleep(5)
        
        # Финальная статистика
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("РЕГИСТРАЦИЯ ЗАВЕРШЕНА")
        logger.info("=" * 80)
        logger.info(f"Всего обработано: {len(results)}")
        logger.info(f"Успешно: {successful}")
        logger.info(f"Неудачно: {failed}")
        if successful > 0:
            logger.info(f"Результаты: {output_file}")
        else:
            logger.info("Нет успешных регистраций для сохранения")
        logger.info("="*80)
        
        # Выводим статистику использования прокси
        print_proxy_stats()
        
        await context.close()
        input("\nНажмите Enter для завершения...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Регистрация аккаунтов на ukc.gov.ua')
    parser.add_argument('--count', type=int, help='Количество аккаунтов для регистрации')
    
    args = parser.parse_args()
    
    # Прокси теперь управляются через proxy_manager.py
    asyncio.run(main(count=args.count))
