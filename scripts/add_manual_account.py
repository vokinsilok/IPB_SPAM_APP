"""
Интерактивное добавление существующего аккаунта UKC в CSV
"""
import csv
from pathlib import Path
from datetime import datetime

def add_account():
    print("=" * 80)
    print("ДОБАВЛЕНИЕ СУЩЕСТВУЮЩЕГО АККАУНТА UKC")
    print("=" * 80)
    
    # Запрашиваем данные
    email = input("Email (Firemail): ").strip()
    firemail_password = input("Пароль Firemail: ").strip()
    full_name = input("ФИО (Прізвище Ім'я По батькові): ").strip()
    phone = input("Телефон: ").strip()
    ukc_password = input("Пароль UKC (Enter если неизвестен): ").strip() or "UNKNOWN"
    
    account = {
        'full_name': full_name,
        'phone': phone,
        'email': email,
        'ukc_password': ukc_password,
        'firemail_password': firemail_password,
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
    
    # Проверяем, не добавлен ли уже этот email
    if file_exists:
        with open(output_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('email', '').strip().lower() == email.lower():
                    print(f"\n⚠ Email {email} уже есть в файле!")
                    overwrite = input("Перезаписать? (y/n): ").strip().lower()
                    if overwrite != 'y':
                        print("Отменено")
                        return
                    break
    
    # Открываем файл для добавления
    with open(output_file, 'a', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['full_name', 'phone', 'email', 'ukc_password', 'firemail_password', 'status', 'submitted', 'timestamp']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        # Если файл новый - пишем заголовок
        if not file_exists or output_file.stat().st_size == 0:
            writer.writeheader()
        
        # Добавляем запись
        writer.writerow(account)
    
    print("\n" + "=" * 80)
    print(f"✓ Аккаунт добавлен в {output_file}")
    print(f"  Email: {account['email']}")
    print(f"  ФИО: {account['full_name']}")
    print(f"  Статус: {account['status']}")
    print("=" * 80)

if __name__ == "__main__":
    try:
        add_account()
    except KeyboardInterrupt:
        print("\n\nОтменено")
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
