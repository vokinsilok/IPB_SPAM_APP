"""
Импорт аккаунтов Firemail из текстового файла в CSV
Поддерживает разделители: : ; |
"""
import csv
import re
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Пути
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INPUT_FILE = DATA_DIR / "firemail_raw.txt"  # Сюда вставляете данные из заказа
OUTPUT_CSV = DATA_DIR / "firemail_accounts.csv"


def parse_firemail_line(line: str) -> tuple[str, str] | None:
    """
    Парсит строку с аккаунтом Firemail
    Поддерживает разделители: : ; |
    
    Возвращает: (email, password) или None
    """
    line = line.strip()
    if not line:
        return None
    
    # Пробуем разные разделители
    for separator in [':', ';', '|']:
        if separator in line:
            parts = [p.strip() for p in line.split(separator)]
            if len(parts) >= 2:
                email = parts[0]
                password = parts[1]
                
                # Проверяем, что email валидный
                if '@firemail.' in email and ('eu' in email or 'de' in email or 'at' in email):
                    return email, password
    
    return None


def import_firemail_accounts():
    """Импортирует аккаунты из текстового файла в CSV"""
    
    if not INPUT_FILE.exists():
        logger.error(f"✗ Файл не найден: {INPUT_FILE}")
        logger.info("Создайте файл firemail_raw.txt и вставьте туда данные из заказа")
        logger.info("Формат: email:password (или с разделителями ; или |)")
        return
    
    # Читаем существующие аккаунты
    existing_emails = set()
    if OUTPUT_CSV.exists() and OUTPUT_CSV.stat().st_size > 0:
        try:
            with open(OUTPUT_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'email' in row and row['email']:
                        existing_emails.add(row['email'].lower())
            logger.info(f"Загружено существующих аккаунтов: {len(existing_emails)}")
        except Exception as e:
            logger.warning(f"⚠ Не удалось прочитать существующие аккаунты: {e}")
    
    # Парсим новые аккаунты
    new_accounts = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            result = parse_firemail_line(line)
            if result:
                email, password = result
                if email.lower() not in existing_emails:
                    new_accounts.append({
                        'email': email,
                        'password': password
                    })
                    logger.info(f"✓ Найден аккаунт: {email}")
                else:
                    logger.info(f"⚠ Аккаунт уже существует: {email}")
    
    if not new_accounts:
        logger.warning("⚠ Новых аккаунтов не найдено")
        return
    
    # Записываем в CSV
    file_exists = OUTPUT_CSV.exists() and OUTPUT_CSV.stat().st_size > 0
    
    with open(OUTPUT_CSV, 'a', newline='', encoding='utf-8') as f:
        fieldnames = ['email', 'password']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerows(new_accounts)
    
    logger.info(f"✓ Добавлено новых аккаунтов: {len(new_accounts)}")
    logger.info(f"✓ Сохранено в: {OUTPUT_CSV}")


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("ИМПОРТ АККАУНТОВ FIREMAIL")
    logger.info("=" * 80)
    import_firemail_accounts()
