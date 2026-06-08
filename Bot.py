import os
import re
import time
import logging
import schedule
import smtplib
import requests
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

EMAIL = os.environ["PRENOTA_EMAIL"]
PASSWORD = os.environ["PRENOTA_PASSWORD"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
CAPTCHA_API_KEY = os.environ["CAPTCHA_API_KEY"]
BASE_URL = "https://prenotami.esteri.it"


def notificar(assunto, mensagem):
    try:
        msg = MIMEText(mensagem)
        msg["Subject"] = assunto
        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_USER
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        log.info("E-mail enviado!")
    except Exception as e:
        log.error("Erro ao enviar e-mail: %s", e)


def detectar_captcha(page):
    html = page.content()

    # Verifica hCaptcha
    if "hcaptcha.com" in html or "h-captcha" in html:
        match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
        if match:
            return "hcaptcha", match.group(1)

    # Verifica reCAPTCHA v2
    if "recaptcha" in html.lower():
        match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
        if match:
            return "recaptcha_v2", match.group(1)
        # Tenta via iframe
        match = re.search(r'google\.com/recaptcha.*?[?&]k=([^&"\']+)', html)
        if match:
            return "recaptcha_v2", match.group(1)

    # Verifica Turnstile
    if "turnstile" in html.lower() or "challenges.cloudflare" in html:
        match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
        if match:
            return "turnstile", match.group(1)

    return None, None


def resolver_captcha(tipo, sitekey, page_url):
    log.info("Resolvendo %s | sitekey: %s", tipo, sitekey)
    try:
        if tipo == "hcaptcha":
            data = {
                "key": CAPTCHA_API_KEY,
                "method": "hcaptcha",
                "sitekey": sitekey,
                "pageurl": page_url,
                "json": 1
            }
        elif tipo == "turnstile":
            data = {
                "key": CAPTCHA_API_KEY,
                "method": "turnstile",
                "sitekey": sitekey,
                "pageurl": page_url,
                "json": 1
            }
        else:
            data = {
                "key": CAPTCHA_API_KEY,
                "method": "userrecaptcha",
                "googlekey": sitekey,
                "pageurl": page_url,
                "json": 1
            }

        resp = requests.post("https://2captcha.com/in.php", data=data, timeout=30)
        result = resp.json()
        log.info("2captcha in: %s", result)
        if result.get("status") != 1:
            log.error("Erro ao enviar: %s", result)
            return None

        captcha_id = result["request"]
        for i in range(24):
            time.sleep(5)
            resp = requests.get("https://2captcha.com/res.php", params={
                "key": CAPTCHA_API_KEY,
                "action": "get",
                "id": captcha_id,
                "json": 1
            }, timeout=30)
            result = resp.json()
            if result.get("status") == 1:
                log.info("Captcha resolvido!")
                return result["request"]
            elif result.get("request") != "CAPCHA_NOT_READY":
                log.error("Erro: %s", result)
                return None
            log.info("Aguardando... (%d/24)", i+1)

        return None
    except Exception as e:
        log.error("Erro 2captcha: %s", e)
        return None


def injetar_token(page, tipo, token):
    try:
        if tipo == "hcaptcha":
            page.evaluate(f"""
                document.querySelectorAll('[name="h-captcha-response"]').forEach(el => el.value = '{token}');
                document.querySelectorAll('[name="g-recaptcha-response"]').forEach(el => el.value = '{token}');
            """)
        else:
            page.evaluate(f"""
                document.querySelectorAll('[name="g-recaptcha-response"]').forEach(el => el.innerHTML = '{token}');
            """)
        log.info("Token %s injetado.", tipo)
    except Exception as e:
        log.warning("Erro ao injetar token: %s", e)


def goto_ignorando_timeout(page, url):
    try:
        page.goto(url, wait_until="commit", timeout=60000)
    except PlaywrightTimeout:
        log.warning("Timeout: %s", url)
    time.sleep(5)
    log.info("URL: %s", page.url)


def tentar_agendar():
    log.info("=== Iniciando tentativa ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7"}
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        try:
            goto_ignorando_timeout(page, BASE_URL)

            try:
                page.click("a:has-text('LOGIN')", timeout=5000)
            except Exception:
                goto_ignorando_timeout(page, BASE_URL + "/UserArea")
            time.sleep(5)
            log.info("URL apos LOGIN: %s", page.url)

            # Detecta e resolve captcha
            tipo, sitekey = detectar_captcha(page)
            log.info("Captcha detectado: tipo=%s sitekey=%s", tipo, sitekey)
            if tipo and sitekey:
                token = resolver_captcha(tipo, sitekey, page.url)
                if token:
                    injetar_token(page, tipo, token)
                    time.sleep(2)
                    # Tenta submeter o form apos injetar token
                    try:
                        page.click("button[type='submit'], input[type='submit']", timeout=3000)
                        time.sleep(5)
                    except Exception:
                        pass
                else:
                    log.error("Captcha nao resolvido.")
                    return

            # Aguarda username
            for i in range(12):
                inputs = page.query_selector_all("input")
                nomes = [inp.get_attribute("name") for inp in inputs]
                log.info("T%d | Inputs: %s | URL: %s", i+1, nomes, page.url)
                if "username" in nomes:
                    break
                time.sleep(5)
            else:
                log.error("Username nao apareceu.")
                return

            page.fill("input[name='username']", EMAIL)
            time.sleep(1)
            page.click("#kc-login")
            time.sleep(8)
            log.info("URL apos username: %s", page.url)

            tipo, sitekey = detectar_captcha(page)
            if tipo and sitekey:
                token = resolver_captcha(tipo, sitekey, page.url)
                if token:
                    injetar_token(page, tipo, token)
                    time.sleep(2)

            page.wait_for_selector("input[name='password']", timeout=30000)
            page.fill("input[name='password']", PASSWORD)
            time.sleep(1)
            page.click("#kc-login")
            time.sleep(8)
            log.info("URL apos senha: %s", page.url)

            goto_ignorando_timeout(page, BASE_URL + "/Services")

            rows = page.query_selector_all("tr")
            clicou = False
            for row in rows:
                if "Passaporte" in row.inner_text() and "Primeiro" in row.inner_text():
                    btn = row.query_selector("a:has-text('RESERVAR')")
                    if btn:
                        btn.click()
                        clicou = True
                        log.info("Clicou RESERVAR.")
                        break

            if not clicou:
                log.warning("RESERVAR nao encontrado.")
                return

            time.sleep(3)
            content = page.content()
            if "currently booked" in content or "All appointments" in content:
                log.warning("Sem vagas.")
                return

            log.info("VAGA DISPONIVEL!")
            notificar(
                "VAGA DE PASSAPORTE DISPONIVEL!",
                "Acesse agora:\nhttps://prenotami.esteri.it/Services\n\nFinalize manualmente!"
            )

        except Exception as e:
            log.error("Erro: %s", e, exc_info=True)
        finally:
            context.close()
            browser.close()


def main():
    log.info("Bot iniciado.")
    tentar_agendar()

    horarios_utc = [
        "18:55", "19:00", "19:01", "19:02", "19:03",
        "19:05", "19:10", "19:15", "19:20", "19:30"
    ]
    for horario in horarios_utc:
        schedule.every().monday.at(horario).do(tentar_agendar)

    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    main()
