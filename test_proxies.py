"""
Тестирование работоспособности прокси на разных источниках
"""
import asyncio
import logging
from playwright.async_api import async_playwright
from proxy_config import RESIDENTIAL_PROXIES, PROXY_LIST

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Тестовые URL
TEST_URLS = {
    'Google': 'https://www.google.com',
    'Gov.ua': 'https://ukc.gov.ua/',
    'Yandex': 'https://yandex.ru'
}


async def test_proxy_on_url(page, proxy_config: dict, url_name: str, url: str, timeout: int = 15000) -> dict:
    """
    Тест прокси на конкретном URL
    
    Returns:
        dict с результатами теста
    """
    result = {
        'url_name': url_name,
        'url': url,
        'success': False,
        'error': None,
        'title': None,
        'load_time': None
    }
    
    try:
        import time
        start_time = time.time()
        
        await page.goto(url, timeout=timeout)
        
        result['load_time'] = round(time.time() - start_time, 2)
        result['title'] = await page.title()
        result['success'] = True
        
        # Проверка на блокировку
        content = await page.content()
        if 'access denied' in content.lower() or 'blocked' in content.lower():
            result['success'] = False
            result['error'] = 'Заблокирован'
        
    except Exception as e:
        error_msg = str(e).lower()
        if 'timeout' in error_msg:
            result['error'] = 'Таймаут'
        elif 'dns' in error_msg:
            result['error'] = 'DNS ошибка'
        elif 'connection' in error_msg:
            result['error'] = 'Ошибка подключения'
        else:
            result['error'] = str(e)[:50]
    
    return result


async def test_single_proxy(proxy_config: dict) -> dict:
    """
    Тестирование одного прокси на всех URL
    """
    proxy_name = proxy_config.get('name', 'Unknown')
    proxy_server = proxy_config.get('server', 'Unknown')
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"ТЕСТИРОВАНИЕ: {proxy_name}")
    logger.info(f"Сервер: {proxy_server}")
    
    # Дополнительная информация для резидентских
    if 'country' in proxy_config:
        logger.info(f"Страна: {proxy_config['country']}, Город: {proxy_config.get('city', 'N/A')}")
        logger.info(f"Ротация: {proxy_config.get('rotation', 'N/A')}")
    
    logger.info("=" * 80)
    
    results = {
        'proxy_name': proxy_name,
        'proxy_server': proxy_server,
        'tests': []
    }
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            
            # Формируем конфигурацию прокси для Playwright
            proxy_settings = {'server': proxy_config['server']}
            if 'username' in proxy_config and 'password' in proxy_config:
                proxy_settings['username'] = proxy_config['username']
                proxy_settings['password'] = proxy_config['password']
            
            context = await browser.new_context(proxy=proxy_settings)
            page = await context.new_page()
            
            # Тестируем каждый URL
            for url_name, url in TEST_URLS.items():
                logger.info(f"\n  Тест {url_name}...")
                test_result = await test_proxy_on_url(page, proxy_config, url_name, url)
                results['tests'].append(test_result)
                
                if test_result['success']:
                    logger.info(f"    ✓ Успешно ({test_result['load_time']}s)")
                    logger.info(f"    Заголовок: {test_result['title'][:60]}...")
                else:
                    logger.error(f"    ✗ Ошибка: {test_result['error']}")
            
            await browser.close()
            
        except Exception as e:
            logger.error(f"✗ Критическая ошибка: {e}")
            results['critical_error'] = str(e)
    
    return results


async def main():
    """
    Главная функция тестирования
    """
    logger.info("=" * 80)
    logger.info("ТЕСТИРОВАНИЕ ПРОКСИ НА РАЗНЫХ ИСТОЧНИКАХ")
    logger.info("=" * 80)
    logger.info(f"Тестовые URL: {', '.join(TEST_URLS.keys())}")
    logger.info("")
    
    # Собираем все прокси для тестирования
    all_proxies = []
    
    # Резидентские прокси (по 1 порту из каждого)
    for pool in RESIDENTIAL_PROXIES:
        if pool.get('enabled', True):
            import random
            port = random.randint(pool['port_range'][0], pool['port_range'][1])
            all_proxies.append({
                'name': f"{pool['name']}_test",
                'server': f"{pool['protocol']}://{pool['host']}:{port}",
                'username': pool['username'],
                'password': pool['password'],
                'country': pool.get('country'),
                'city': pool.get('city'),
                'rotation': pool.get('rotation'),
                'type': 'residential'
            })
    
    # Обычные прокси
    all_proxies.extend([p for p in PROXY_LIST if p.get('active', True)])
    
    logger.info(f"Всего прокси для тестирования: {len(all_proxies)}")
    logger.info("")
    
    # Тестируем каждый прокси
    all_results = []
    for idx, proxy in enumerate(all_proxies, 1):
        logger.info(f"\n>>> Прогресс: {idx}/{len(all_proxies)} <<<")
        result = await test_single_proxy(proxy)
        all_results.append(result)
        
        # Пауза между прокси
        if idx < len(all_proxies):
            await asyncio.sleep(2)
    
    # Итоговая статистика
    logger.info("")
    logger.info("=" * 80)
    logger.info("ИТОГОВАЯ СТАТИСТИКА")
    logger.info("=" * 80)
    
    for result in all_results:
        proxy_name = result['proxy_name']
        tests = result['tests']
        
        if 'critical_error' in result:
            logger.info(f"\n{proxy_name}: ✗ КРИТИЧЕСКАЯ ОШИБКА")
            continue
        
        success_count = sum(1 for t in tests if t['success'])
        total_count = len(tests)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        logger.info(f"\n{proxy_name}:")
        logger.info(f"  Успешно: {success_count}/{total_count} ({success_rate:.1f}%)")
        
        for test in tests:
            status = "✓" if test['success'] else "✗"
            logger.info(f"    {status} {test['url_name']}: {test.get('error', 'OK')}")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
