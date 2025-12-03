"""
Тест сетевого подключения к Firemail серверам
"""
import socket
import ssl

servers = [
    ("imap.firemail.de", 993),
    ("imap.firemail.de", 143),
    ("pop.firemail.de", 995),
    ("smtp.firemail.de", 465),
    ("smtp.firemail.de", 587),
]

print("Тестирование доступности серверов Firemail")
print("=" * 80)

for server, port in servers:
    print(f"\nПроверка: {server}:{port}")
    
    # 1. Проверка DNS
    try:
        ip = socket.gethostbyname(server)
        print(f"  ✓ DNS: {server} -> {ip}")
    except Exception as e:
        print(f"  ✗ DNS ошибка: {e}")
        continue
    
    # 2. Проверка TCP подключения
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((server, port))
        sock.close()
        
        if result == 0:
            print(f"  ✓ TCP порт {port} открыт")
        else:
            print(f"  ✗ TCP порт {port} закрыт (код: {result})")
            continue
    except Exception as e:
        print(f"  ✗ TCP ошибка: {e}")
        continue
    
    # 3. Проверка SSL (если порт SSL)
    if port in [993, 995, 465]:
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection((server, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=server) as ssock:
                    print(f"  ✓ SSL handshake успешен")
                    print(f"    Протокол: {ssock.version()}")
        except socket.timeout:
            print(f"  ✗ SSL handshake timeout")
        except Exception as e:
            print(f"  ✗ SSL ошибка: {e}")

print("\n" + "=" * 80)
print("Тест завершён")
print("\nЕсли все порты закрыты:")
print("1. Проверьте firewall/антивирус")
print("2. Попробуйте VPN")
print("3. Проверьте, не блокирует ли провайдер эти порты")
