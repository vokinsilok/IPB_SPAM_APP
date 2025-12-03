"""
Тест подключения к Firemail аккаунту
Проверяет IMAP, POP3, SMTP
"""
import poplib
import imaplib
import smtplib
import ssl
import sys

def test_firemail_account(email, password):
    """Тестирование всех методов подключения"""
    print("=" * 80)
    print(f"ТЕСТИРОВАНИЕ FIREMAIL АККАУНТА: {email}")
    print("=" * 80)
    
    # SSL контекст
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    results = {
        'imap': False,
        'pop3': False,
        'smtp': False
    }
    
    # Тест 1: IMAP
    print("\n[ТЕСТ 1/3] IMAP (imap.firemail.de:993)")
    try:
        imap = imaplib.IMAP4_SSL("imap.firemail.de", 993, ssl_context=ssl_context, timeout=10)
        imap.login(email, password)
        imap.select('INBOX')
        results['imap'] = True
        print("✓ IMAP: Успешно!")
        imap.logout()
    except Exception as e:
        print(f"✗ IMAP: Ошибка - {e}")
    
    # Тест 2: POP3
    print("\n[ТЕСТ 2/3] POP3 (pop.firemail.de:995)")
    try:
        pop = poplib.POP3_SSL("pop.firemail.de", 995, context=ssl_context, timeout=10)
        pop.user(email)
        pop.pass_(password)
        num_messages = len(pop.list()[1])
        results['pop3'] = True
        print(f"✓ POP3: Успешно! Писем в ящике: {num_messages}")
        pop.quit()
    except Exception as e:
        print(f"✗ POP3: Ошибка - {e}")
    
    # Тест 3: SMTP
    print("\n[ТЕСТ 3/3] SMTP (smtp.firemail.de:465)")
    try:
        smtp = smtplib.SMTP_SSL("smtp.firemail.de", 465, context=ssl_context, timeout=10)
        smtp.login(email, password)
        results['smtp'] = True
        print("✓ SMTP: Успешно!")
        smtp.quit()
    except Exception as e:
        print(f"✗ SMTP: Ошибка - {e}")
    
    # Итоги
    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТЫ:")
    print(f"  IMAP: {'✓ Работает' if results['imap'] else '✗ Не работает'}")
    print(f"  POP3: {'✓ Работает' if results['pop3'] else '✗ Не работает'}")
    print(f"  SMTP: {'✓ Работает' if results['smtp'] else '✗ Не работает'}")
    
    if any(results.values()):
        print("\n✓ Учетные данные ВЕРНЫЕ - хотя бы один метод работает")
    else:
        print("\n✗ Учетные данные НЕВЕРНЫЕ или все порты заблокированы")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    # Тестовый аккаунт из логов
    test_email = "watson8743@firemail.de"
    test_password = "j5M5MH0b8slt"
    
    # Или введите свои данные
    if len(sys.argv) > 2:
        test_email = sys.argv[1]
        test_password = sys.argv[2]
    
    test_firemail_account(test_email, test_password)
