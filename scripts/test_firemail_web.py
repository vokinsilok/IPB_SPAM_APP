"""
Тест автоматического подтверждения через веб-интерфейс Firemail
"""
import asyncio
import logging
import sys
from playwright.async_api import async_playwright
from firemail_web_confirmer import confirm_email_via_firemail_web

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_firemail_web():
    # Тестовые данные
    test_email = "whitaker2106@firemail.de"
    test_password = "IVO$dpm3M@jI"
    
    if len(sys.argv) > 2:
        test_email = sys.argv[1]
        test_password = sys.argv[2]
    
    print("=" * 80)
    print(f"ТЕСТ АВТОПОДТВЕРЖДЕНИЯ ЧЕРЕЗ ВЕБ-ИНТЕРФЕЙС")
    print(f"Email: {test_email}")
    print("=" * 80)
    
    async with async_playwright() as p:
        # Запускаем браузер (не headless чтобы видеть процесс)
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        
        try:
            link = await confirm_email_via_firemail_web(
                browser,
                test_email,
                test_password,
                max_attempts=3,
                wait_seconds=5
            )
            
            print("\n" + "=" * 80)
            if link:
                print("✓✓✓ УСПЕХ!")
                print(f"Ссылка подтверждения: {link}")
            else:
                print("✗✗✗ НЕУДАЧА")
                print("Ссылка не найдена")
            print("=" * 80)
            
            return link
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_firemail_web())
