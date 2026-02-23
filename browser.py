"""
browser.py
Scrapes attendance for a given user using Playwright.

Returns: { subject_name: { "present": int, "total": int } }
"""

import re
from playwright.async_api import async_playwright
import asyncio


async def scrape_attendance(username: str, password: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
       
        try:
            await page.goto('https://erp.mit.asia/login.html')
            await _perform_login(page, username, password)
            await page.wait_for_load_state('load')
            await page.goto(
                'https://erp.mit.asia/studentCourseFileNew.htm?shwA=%2700A%27'
            )
            await page.wait_for_load_state('load')

            # If redirected to login, authenticate again
            if 'login.htm' in page.url:
                await _perform_login(page, username, password)
                await page.goto('https://erp.mit.asia/studentCourseFileNew.htm?shwA=%2700A%27')
                await page.wait_for_load_state('load')

            # Wait for table
            await page.wait_for_selector('#attendanceDiv table tbody tr', timeout=15000)

            rows = page.locator('#attendanceDiv table tbody tr')
            count = await rows.count()
            attendance = {}

            for i in range(count):
                row = rows.nth(i)
                cell_count = await row.locator('td').count()
                if cell_count < 3:
                    continue

                course = (await row.locator('td').nth(1).inner_text()).strip()
                raw = (await row.locator('td').nth(2).locator('a').inner_text()).strip()

                # Parse "7/7" format
                match = re.search(r'(\d+)\s*/\s*(\d+)', raw)
                if match:
                    attendance[course] = {
                        'present': int(match.group(1)),
                        'total': int(match.group(2)),
                    }

            return attendance

        finally:
            await browser.close()


async def _perform_login(page, username: str, password: str) -> None:
    await page.get_by_role('textbox', name='Enter username').fill(username)
    await page.get_by_role('textbox', name='Enter password').fill(password)
    await page.get_by_role('button', name='Login').click()
    await page.wait_for_load_state('load')
"""
async def main():
    # Call the function and await the result
    data = await scrape_attendance("makrand.shinde@mit.asia", "261224")
    print(data)

if __name__ == "__main__":
    # This starts the event loop and runs your async code
    asyncio.run(main())
"""