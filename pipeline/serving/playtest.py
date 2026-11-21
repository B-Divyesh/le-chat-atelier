"""Play the world-model game in real Firefox like a user: hold keys, cross edges, screenshot what a player sees."""
import asyncio, sys, time, urllib.parse
from playwright.async_api import async_playwright
OUT = sys.argv[1]
async def play(page, prompt, plan, tag):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto("http://127.0.0.1:8090/game?prompt=" + urllib.parse.quote(prompt))
    t0 = time.time()
    while time.time() - t0 < 60:
        if int(await page.inner_text("#sFrame") or 0) > 0: break
        await asyncio.sleep(0.5)
    start_s = time.time() - t0
    await page.screenshot(path=f"{OUT}/{tag}-0-start.png")
    f0, t1, shots = int(await page.inner_text("#sFrame")), time.time(), 1
    for key, secs in plan:
        await page.keyboard.down(key); await asyncio.sleep(secs); await page.keyboard.up(key)
        await page.screenshot(path=f"{OUT}/{tag}-{shots}-{key}.png"); shots += 1
    frames = int(await page.inner_text("#sFrame")) - f0; dur = time.time() - t1
    story = await page.eval_on_selector_all("#log p", "ps => ps.slice(0, 6).map(p => p.textContent)")
    print(f"[{tag}] world ready in {start_s:.1f}s | {frames} frames in {dur:.0f}s = {frames/dur:.2f} fps | step {await page.inner_text('#sMs')} | {await page.inner_text('#sTok')}")
    print(f"[{tag}] errors: {errors[:3] or 'none'}")
    for line in story: print(f"[{tag}]   story: {line[:150]}")
    await page.close()  # like a user closing the tab: stop this game before the next one
async def main():
    async with async_playwright() as p:
        b = await p.firefox.launch(headless=True)
        page = await b.new_page(viewport={"width": 1400, "height": 900})
        await play(page, "Le Chat survives a haunted cheese dungeon full of ghost rats",
                   [("ArrowRight", 9), ("ArrowUp", 4), ("ArrowLeft", 5)], "surv")
        page2 = await b.new_page(viewport={"width": 1400, "height": 900})
        await play(page2, "Le Chat leaps across rooftop platforms collecting golden fish",
                   [("ArrowRight", 5), ("ArrowUp", 2), ("ArrowRight", 6)], "plat")
        await b.close()
asyncio.run(main())
