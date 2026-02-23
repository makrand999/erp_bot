"""
verify.py
Attempts to log in with given credentials.
Returns True if login succeeds, False otherwise.
"""

from playwright.async_api import async_playwright
import asyncio

async def verify_login(username: str, password: str) -> bool:
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto('https://erp.mit.asia/login.htm')
            await page.get_by_role('textbox', name='Enter username').fill(username)
            await page.get_by_role('textbox', name='Enter password').fill(password)
            await page.get_by_role('button', name='Login').click()
            await page.wait_for_load_state('load')

            current_url = page.url
            return 'login.htm?failure=true' not in current_url

    except Exception as e:
        print(f'[verify] Error: {e}')
        return False

"""
async def main():
    
    data = await verify_login("makrand.shinde@mit.asia","261224")
    print(data)

if __name__ == "__main__" :

    asyncio.run(main())
"""
