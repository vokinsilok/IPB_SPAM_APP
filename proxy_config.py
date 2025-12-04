"""
Конфигурация и управление прокси для работы с gov.ua
"""
import logging
import random
from typing import Optional, Dict, List
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# ========================================
# ГЛОБАЛЬНЫЕ НАСТРОЙКИ ПРОКСИ
# ========================================
USE_PROXY = False  # True - использовать прокси, False - работать без прокси

# ========================================
# РЕЗИДЕНТСКИЕ ПРОКСИ (РЕКОМЕНДУЕТСЯ)
# ========================================
# Резидентские прокси лучше работают с gov.ua
# так как используют реальные IP-адреса

# Прокси 1: Венгрия (Bicske) - Ротация каждые 5 минут
RESIDENTIAL_HUNGARY = {
    'enabled': True,
    'name': 'Hungary_Bicske',
    'host': 'pool.proxy.market',
    'port_range': (10000, 10999),
    'username': 'cdldukvBPwuN',
    'password': 'Y4hkyOSa',
    'protocol': 'http',  # или 'socks5'
    'country': 'Венгрия',
    'region': 'Fejér',
    'city': 'Bicske',
    'rotation': '5 минут',
    'type': 'rotating'
}

# Прокси 2: Болгария (Asenovgrad) - Липкая сессия (sticky)
RESIDENTIAL_BULGARIA = {
    'enabled': True,
    'name': 'Bulgaria_Asenovgrad',
    'host': 'pool.proxy.market',
    'port_range': (10000, 10999),
    'username': 'qFMu6NcuG3w7',
    'password': 'tj4PxXN6',
    'protocol': 'http',  # или 'socks5'
    'country': 'Болгария',
    'region': 'Plovdiv',
    'city': 'Asenovgrad',
    'rotation': 'Липкая сессия',
    'type': 'sticky'
}

# Список всех резидентских прокси
RESIDENTIAL_PROXIES = [
    RESIDENTIAL_BULGARIA,   # Приоритет: липкая сессия лучше для gov.ua
    RESIDENTIAL_HUNGARY,    # Резерв: ротация каждые 5 минут
]


def generate_residential_proxies(count: int = 5, per_pool: int = 3) -> List[Dict]:
    """
    Генерация списка резидентских прокси из всех пулов
    
    Args:
        count: Общее количество прокси для генерации (не используется при per_pool)
        per_pool: Количество прокси из каждого пула
    
    Returns:
        Список конфигураций прокси
    """
    all_proxies = []
    
    for pool in RESIDENTIAL_PROXIES:
        if not pool.get('enabled', True):
            continue
        
        # Генерируем случайные порты из диапазона для этого пула
        ports = random.sample(
            range(pool['port_range'][0], pool['port_range'][1] + 1),
            min(per_pool, pool['port_range'][1] - pool['port_range'][0] + 1)
        )
        
        for idx, port in enumerate(ports, 1):
            proxy_name = f"{pool['name']}_{idx}"
            all_proxies.append({
                'name': proxy_name,
                'server': f"{pool['protocol']}://{pool['host']}:{port}",
                'username': pool['username'],
                'password': pool['password'],
                'active': True,
                'type': 'residential',
                'country': pool.get('country', 'Unknown'),
                'city': pool.get('city', 'Unknown'),
                'rotation': pool.get('rotation', 'Unknown'),
                'session_type': pool.get('type', 'unknown')
            })
    
    return all_proxies


# Список прокси (добавьте несколько для ротации)
PROXY_LIST = [
    {
        'name': 'Primary',
        'server': 'http://213.232.69.46:8000',
        'username': 'ZTCGxU',
        'password': 'LBea9D',
        'active': True,
        'type': 'datacenter'
    },
    # Добавьте резервные прокси здесь
    # {
    #     'name': 'Backup1',
    #     'server': 'http://IP:PORT',
    #     'username': 'USER',
    #     'password': 'PASS',
    #     'active': True,
    #     'type': 'datacenter'
    # },
]

# Прокси без авторизации (если есть)
PROXY_LIST_NO_AUTH = [
    # {
    #     'name': 'Free1',
    #     'server': 'http://IP:PORT',
    #     'active': True,
    #     'type': 'free'
    # },
]


def get_all_proxies() -> List[Dict]:
    """
    Получить полный список прокси (резидентские + обычные)
    
    Returns:
        Объединённый список всех прокси
    """
    all_proxies = []
    
    # Сначала добавляем резидентские (приоритет)
    if any(pool.get('enabled', True) for pool in RESIDENTIAL_PROXIES):
        residential = generate_residential_proxies(per_pool=3)  # 3 прокси из каждого пула
        all_proxies.extend(residential)
        
        # Статистика по странам
        countries = {}
        for proxy in residential:
            country = proxy.get('country', 'Unknown')
            countries[country] = countries.get(country, 0) + 1
        
        logger.info(f"✓ Сгенерировано {len(residential)} резидентских прокси:")
        for country, count in countries.items():
            logger.info(f"  - {country}: {count} прокси")
    
    # Затем добавляем обычные
    all_proxies.extend(PROXY_LIST)
    all_proxies.extend(PROXY_LIST_NO_AUTH)
    
    return all_proxies


async def test_proxy_connection(page: Page, proxy_config: Dict, timeout: int = 15000) -> bool:
    """
    Проверка работоспособности прокси с gov.ua
    
    Args:
        page: Playwright page объект
        proxy_config: Конфигурация прокси
        timeout: Таймаут в миллисекундах
    
    Returns:
        True если прокси работает, False если нет
    """
    try:
        logger.info(f"Тестирую прокси: {proxy_config['name']} ({proxy_config['server']})")
        
        # Тест 1: Проверка IP через прокси
        try:
            await page.goto('https://api.ipify.org?format=json', timeout=timeout)
            ip_content = await page.content()
            logger.info(f"  ✓ IP через прокси: {ip_content}")
        except Exception as e:
            logger.error(f"  ✗ Не удалось получить IP: {e}")
            return False
        
        # Тест 2: Проверка доступа к gov.ua (критично!)
        try:
            await page.goto('https://ukc.gov.ua/', timeout=timeout)
            title = await page.title()
            logger.info(f"  ✓ Доступ к ukc.gov.ua: {title[:50]}...")
            
            # Проверка, что не попали на страницу блокировки
            content = await page.content()
            if 'access denied' in content.lower() or 'blocked' in content.lower():
                logger.error("  ✗ Прокси заблокирован на ukc.gov.ua")
                return False
            
            return True
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'timeout' in error_msg:
                logger.error(f"  ✗ Таймаут при подключении к ukc.gov.ua")
            elif 'dns' in error_msg:
                logger.error(f"  ✗ Проблема с DNS через прокси")
            elif 'connection' in error_msg:
                logger.error(f"  ✗ Не удалось подключиться через прокси")
            else:
                logger.error(f"  ✗ Ошибка доступа к ukc.gov.ua: {e}")
            return False
            
    except Exception as e:
        logger.error(f"  ✗ Критическая ошибка при тесте прокси: {e}")
        return False


async def find_working_proxy(page: Page, proxy_list: List[Dict] = None) -> Optional[Dict]:
    """
    Поиск рабочего прокси из списка
    
    Args:
        page: Playwright page объект
        proxy_list: Список прокси для проверки (по умолчанию get_all_proxies())
    
    Returns:
        Конфигурация рабочего прокси или None
    """
    if proxy_list is None:
        proxy_list = get_all_proxies()
    
    logger.info("=" * 80)
    logger.info("ПОИСК РАБОЧЕГО ПРОКСИ ДЛЯ GOV.UA")
    logger.info("=" * 80)
    
    active_proxies = [p for p in proxy_list if p.get('active', True)]
    
    if not active_proxies:
        logger.error("✗ Нет активных прокси в списке!")
        return None
    
    # Показываем статистику по типам
    residential_count = len([p for p in active_proxies if p.get('type') == 'residential'])
    datacenter_count = len([p for p in active_proxies if p.get('type') == 'datacenter'])
    
    logger.info(f"Всего прокси для проверки: {len(active_proxies)}")
    if residential_count > 0:
        logger.info(f"  - Резидентских: {residential_count}")
    if datacenter_count > 0:
        logger.info(f"  - Датацентр: {datacenter_count}")
    
    for idx, proxy in enumerate(active_proxies, 1):
        logger.info(f"\n>>> Проверка {idx}/{len(active_proxies)}: {proxy['name']} <<<")
        
        if await test_proxy_connection(page, proxy):
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"✓✓✓ НАЙДЕН РАБОЧИЙ ПРОКСИ: {proxy['name']}")
            logger.info(f"Сервер: {proxy['server']}")
            
            # Дополнительная информация для резидентских прокси
            if proxy.get('type') == 'residential':
                logger.info(f"Тип: Резидентский")
                if 'country' in proxy:
                    logger.info(f"Страна: {proxy['country']}")
                if 'city' in proxy:
                    logger.info(f"Город: {proxy['city']}")
                if 'rotation' in proxy:
                    logger.info(f"Ротация: {proxy['rotation']}")
            
            logger.info("=" * 80)
            return proxy
        
        logger.warning(f"⚠ Прокси {proxy['name']} не подходит для gov.ua")
    
    logger.error("")
    logger.error("=" * 80)
    logger.error("✗ НИ ОДИН ПРОКСИ НЕ РАБОТАЕТ С GOV.UA!")
    logger.error("=" * 80)
    return None


def get_primary_proxy() -> Dict:
    """Получить основной прокси"""
    active = [p for p in PROXY_LIST if p.get('active', True)]
    if active:
        return active[0]
    return PROXY_LIST[0] if PROXY_LIST else {}


def format_proxy_for_playwright(proxy_config: Dict) -> Dict:
    """
    Форматирование прокси для Playwright context
    
    Args:
        proxy_config: Конфигурация прокси
    
    Returns:
        Словарь для передачи в browser.new_context(proxy=...)
    """
    result = {'server': proxy_config['server']}
    
    if 'username' in proxy_config and 'password' in proxy_config:
        result['username'] = proxy_config['username']
        result['password'] = proxy_config['password']
    
    return result


# Рекомендации по типам прокси для gov.ua
PROXY_RECOMMENDATIONS = """
🎯 РЕКОМЕНДАЦИИ ПО ПРОКСИ ДЛЯ GOV.UA

ТИП ПРОКСИ:
1. РЕЗИДЕНТСКИЕ - ЛУЧШИЙ ВЫБОР ⭐⭐⭐⭐⭐⭐
   - Используют реальные IP домашних пользователей
   - Минимальная вероятность блокировки
   - Отлично работают с Cloudflare и DNSSEC
   - Пример: pool.proxy.market (1000 портов)
   - ТЕКУЩИЙ СТАТУС: ✅ ВКЛЮЧЕНЫ

2. HTTPS прокси (HTTP/HTTPS) - ХОРОШИЙ ВЫБОР ⭐⭐⭐⭐⭐
   - Полная совместимость с DNSSEC
   - Стабильная работа с Cloudflare
   - Формат: http://IP:PORT или https://IP:PORT

3. SOCKS5 - АЛЬТЕРНАТИВА ⭐⭐⭐⭐
   - Быстрее HTTPS
   - Работает с большинством сайтов
   - Формат: socks5://IP:PORT
   - Может быть проблема с DNS

4. SOCKS4 - НЕ РЕКОМЕНДУЕТСЯ ⭐⭐
   - Не поддерживает авторизацию
   - Устаревший протокол

ВАЖНО:
- gov.ua использует DNSSEC - не все прокси поддерживают
- Cloudflare защита - резидентские прокси работают лучше
- Резидентский пул: 1000 портов (10000-10999)
- Автоматическая ротация прокси из пула
"""


def print_proxy_recommendations():
    """Вывести рекомендации по прокси"""
    print(PROXY_RECOMMENDATIONS)


# Статистика использования прокси
PROXY_STATS = {}


def log_proxy_usage(proxy_name: str, success: bool):
    """Логирование использования прокси"""
    if proxy_name not in PROXY_STATS:
        PROXY_STATS[proxy_name] = {'success': 0, 'failed': 0}
    
    if success:
        PROXY_STATS[proxy_name]['success'] += 1
    else:
        PROXY_STATS[proxy_name]['failed'] += 1


def get_proxy_stats() -> Dict:
    """Получить статистику использования прокси"""
    return PROXY_STATS.copy()


def print_proxy_stats():
    """Вывести статистику использования прокси"""
    if not PROXY_STATS:
        logger.info("Нет статистики использования прокси")
        return
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("СТАТИСТИКА ИСПОЛЬЗОВАНИЯ ПРОКСИ")
    logger.info("=" * 80)
    
    for proxy_name, stats in PROXY_STATS.items():
        total = stats['success'] + stats['failed']
        success_rate = (stats['success'] / total * 100) if total > 0 else 0
        
        logger.info(f"\n{proxy_name}:")
        logger.info(f"  Успешно: {stats['success']}")
        logger.info(f"  Ошибок:  {stats['failed']}")
        logger.info(f"  Всего:   {total}")
        logger.info(f"  Успех:   {success_rate:.1f}%")
    
    logger.info("=" * 80)
