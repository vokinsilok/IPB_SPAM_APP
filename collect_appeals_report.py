"""
Сбор отчётов по обращениям с ukc.gov.ua
"""
import asyncio
import csv
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests
from playwright.async_api import async_playwright, Page

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Пути
BASE_DIR = Path(__file__).resolve().parent
REGISTRATIONS_DIR = BASE_DIR / "registrations"
UKC_ACCOUNTS_CSV = REGISTRATIONS_DIR / "ukc_registered.csv"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_ukc_accounts():
    """Загрузка зарегистрированных UKC аккаунтов"""
    accounts = []
    
    if not UKC_ACCOUNTS_CSV.exists():
        logger.error(f"✗ Файл не найден: {UKC_ACCOUNTS_CSV}")
        return accounts
    
    with open(UKC_ACCOUNTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'registered' in row.get('status', '').lower():
                accounts.append({
                    'email': row['email'],
                    'password': row['ukc_password'],
                    'full_name': row['full_name']
                })
    
    logger.info(f"✓ Загружено {len(accounts)} UKC аккаунтов")
    return accounts


async def login_to_ukc(page: Page, email: str, password: str):
    """Вход в UKC аккаунт"""
    logger.info(f"Авторизация: {email}")
    
    try:
        logger.info("Открываю ukc.gov.ua...")
        
        try:
            await page.goto("https://ukc.gov.ua/", timeout=90000, wait_until='commit')
            logger.info(f"✓ Страница начала загружаться: {page.url}")
            
            await page.wait_for_load_state('domcontentloaded', timeout=30000)
            logger.info(f"✓ Страница загружена: {page.url}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"✗ Ошибка при загрузке страницы: {error_msg}")
            
            if "ERR_TIMED_OUT" in error_msg or "timeout" in error_msg.lower():
                logger.error("⚠ Таймаут при подключении к сайту")
            
            return False
        
        await asyncio.sleep(3)
        
        if "challenge" in page.url or "__cf_chl" in page.url or "checking" in page.url.lower():
            logger.warning("⚠ Обнаружена проверка безопасности, ожидание...")
            await asyncio.sleep(10)
            logger.info(f"Текущий URL после ожидания: {page.url}")
        
        # Клик на "Особистий кабінет"
        try:
            await page.get_by_role("button", name="Особистий кабінет").click(timeout=10000)
            logger.info("✓ Нажата кнопка 'Особистий кабінет'")
        except Exception as e:
            logger.error(f"✗ Не найдена кнопка 'Особистий кабінет': {e}")
            return False
        
        await asyncio.sleep(1)
        
        # Ввод email
        await page.locator("input[type=\"email\"]").click()
        await page.locator("input[type=\"email\"]").fill(email)
        
        # Ввод пароля
        await page.get_by_role("banner").get_by_role("textbox", name="Пароль").click()
        await page.get_by_role("banner").get_by_role("textbox", name="Пароль").fill(password)
        
        # Нажатие "Увійти"
        await page.get_by_role("banner").get_by_role("button", name="Увійти").click()
        
        await asyncio.sleep(2)
        
        # Проверка успешной авторизации
        if "https://ukc.gov.ua/portal/" in page.url:
            logger.info("✓ Успешная авторизация")
            return True
        else:
            logger.error(f"✗ Авторизация не удалась. Текущий URL: {page.url}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Ошибка при авторизации: {e}")
        return False


async def collect_appeals_data(page: Page):
    """Сбор данных об обращениях"""
    logger.info("Сбор данных об обращениях...")
    
    try:
        # Переход на страницу обращений
        await page.goto("https://ukc.gov.ua/portal/appeals")
        await asyncio.sleep(2)
        
        # Здесь нужно добавить логику сбора данных
        # Это примерный код - селекторы нужно адаптировать
        
        appeals_data = []
        
        logger.info(f"✓ Собрано обращений: {len(appeals_data)}")
        return appeals_data
        
    except Exception as e:
        logger.error(f"✗ Ошибка при сборе данных: {e}")
        return []


async def process_account(account: dict, output_dir: Path):
    """Обработка одного UKC аккаунта"""
    all_appeals_data = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Вход в аккаунт
            if not await login_to_ukc(page, account['email'], account['password']):
                await browser.close()
                return []
            
            # Сбор данных об обращениях
            appeals_data = await collect_appeals_data(page)
            all_appeals_data.extend(appeals_data)
            
        except Exception as e:
            logger.error(f"✗ Ошибка обработки аккаунта {account['email']}: {e}")
        finally:
            await browser.close()
    
    return all_appeals_data


async def main():
    """Главная функция"""
    logger.info("=" * 80)
    logger.info("СБОР ОТЧЁТОВ ПО ОБРАЩЕНИЯМ")
    logger.info("=" * 80)
    
    # Загрузка аккаунтов
    accounts = load_ukc_accounts()
    if not accounts:
        logger.error("✗ Нет аккаунтов для обработки!")
        return
    
    # Создание директории для отчётов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = REPORTS_DIR / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_data = []
    
    # Обработка каждого аккаунта
    for idx, account in enumerate(accounts, start=1):
        logger.info(f"\n>>> Прогресс: {idx}/{len(accounts)} <<<")
        logger.info(f"Обработка: {account['full_name']} ({account['email']})")
        
        appeals_data = await process_account(account, output_dir)
        all_data.extend(appeals_data)
        
        await asyncio.sleep(2)
    
    # Сохранение отчёта
    if all_data:
        report_file = output_dir / "appeals_report.csv"
        with open(report_file, 'w', newline='', encoding='utf-8') as f:
            if all_data:
                writer = csv.DictWriter(f, fieldnames=all_data[0].keys())
                writer.writeheader()
                writer.writerows(all_data)
        
        logger.info(f"✓ Отчёт сохранён: {report_file}")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("СБОР ОТЧЁТОВ ЗАВЕРШЁН")
    logger.info(f"Всего обращений: {len(all_data)}")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
