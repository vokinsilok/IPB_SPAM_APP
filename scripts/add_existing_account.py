"""
Добавление существующего аккаунта UKC в CSV
"""
import csv
from pathlib import Path
from datetime import datetime

# Данные существующего аккаунта
account = {
    'full_name': 'Ігор Васильович Ніфантов',
    'phone': '979509573',
    'email': 'watkins5668@firemail.eu',
    'ukc_password': 'Watkins5668',  # Пароль от UKC неизвестен
    'firemail_password': 'HCtZUaeFmk%j',
    'status': 'already_registered_manually',
    'submitted': 'True',
    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# Путь к файлу
output_dir = Path(__file__).resolve().parent.parent / "registrations"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "ukc_registered.csv"

# Проверяем существует ли файл
file_exists = output_file.exists()

# Открываем файл для добавления
with open(output_file, 'a', newline='', encoding='utf-8-sig') as f:
    fieldnames = ['full_name', 'phone', 'email', 'ukc_password', 'firemail_password', 'status', 'submitted', 'timestamp']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    
    # Если файл новый - пишем заголовок
    if not file_exists or output_file.stat().st_size == 0:
        writer.writeheader()
    
    # Добавляем запись
    writer.writerow(account)

print(f"✓ Аккаунт добавлен в {output_file}")
print(f"  Email: {account['email']}")
print(f"  ФИО: {account['full_name']}")
print(f"  Статус: {account['status']}")
