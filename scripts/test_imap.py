"""
Тест подключения к IMAP Firemail
"""
import imaplib
import ssl

email_address = "watkins5668@firemail.eu"
password = "HCtZUaeFmk%j"

print(f"Тестирование IMAP для: {email_address}")
print("=" * 80)

# Пробуем разные серверы
# Согласно документации: imap.firemail.de:993 для всех доменов
servers = [
    ("imap.firemail.de", 993, True),
    ("pop.firemail.de", 995, True),  # POP3 для сравнения
    ("imap.firemail.de", 143, False),
]

for server, port, use_ssl in servers:
    print(f"\nПробую: {server}:{port} (SSL={use_ssl})")
    try:
        if use_ssl:
            # Пробуем с разными SSL контекстами
            try:
                # Стандартное подключение
                imap = imaplib.IMAP4_SSL(server, port, timeout=10)
                print(f"✓ Подключение успешно!")
                
                # Пробуем логин
                try:
                    imap.login(email_address, password)
                    print(f"✓ Логин успешен!")
                    
                    # Пробуем выбрать INBOX
                    imap.select("INBOX")
                    print(f"✓ INBOX выбран!")
                    
                    # Получаем список папок
                    status, folders = imap.list()
                    print(f"Папки: {folders}")
                    
                    imap.close()
                    imap.logout()
                    print("=" * 80)
                    print("✓✓✓ ВСЁ РАБОТАЕТ! ✓✓✓")
                    print(f"Используйте: {server}:{port} с SSL")
                    print("=" * 80)
                    break
                except imaplib.IMAP4.error as e:
                    print(f"✗ Ошибка логина: {e}")
                except Exception as e:
                    print(f"✗ Ошибка после логина: {e}")
            except ssl.SSLError as e:
                print(f"✗ SSL ошибка: {e}")
                
                # Пробуем с отключенной проверкой сертификата
                try:
                    print("  Пробую без проверки сертификата...")
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    
                    imap = imaplib.IMAP4_SSL(server, port, ssl_context=ssl_context, timeout=10)
                    print(f"  ✓ Подключение успешно (без проверки сертификата)!")
                    
                    imap.login(email_address, password)
                    print(f"  ✓ Логин успешен!")
                    
                    imap.select("INBOX")
                    print(f"  ✓ INBOX выбран!")
                    
                    imap.close()
                    imap.logout()
                    print("=" * 80)
                    print("✓✓✓ РАБОТАЕТ БЕЗ ПРОВЕРКИ СЕРТИФИКАТА! ✓✓✓")
                    print(f"Используйте: {server}:{port} с SSL (без проверки сертификата)")
                    print("=" * 80)
                    break
                except Exception as e2:
                    print(f"  ✗ Тоже не сработало: {e2}")
            except Exception as e:
                print(f"✗ Ошибка подключения: {e}")
        else:
            # Без SSL
            try:
                imap = imaplib.IMAP4(server, port, timeout=10)
                print(f"✓ Подключение успешно (без SSL)!")
                
                imap.login(email_address, password)
                print(f"✓ Логин успешен!")
                
                imap.close()
                imap.logout()
                print("=" * 80)
                print("✓✓✓ РАБОТАЕТ БЕЗ SSL! ✓✓✓")
                print(f"Используйте: {server}:{port} без SSL")
                print("=" * 80)
                break
            except Exception as e:
                print(f"✗ Ошибка: {e}")
    except Exception as e:
        print(f"✗ Общая ошибка: {e}")

print("\nТест завершён")
