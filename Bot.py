import os
import time
import logging
import schedule
import smtplib
import asyncio
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

EMAIL = os.environ["PRENOTA_EMAIL"]
PASSWORD = os.environ["PRENOTA_PASSWORD"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
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


def tentar_agendar():
    log.info("=== Iniciando tentativa ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )

        # Remove webdriver flag
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page = context.new_page()

        try:
            log.info("Acessando pagina principal...")
            page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            log.info("URL: %s", page.url)
            log.info("Titulo: %s", page.title())

            # Clica no botao de login
            log.info("Procurando botao de login...")
            try:
                page.click("a:has-text('LOGIN')", timeout=10000)
                page.wait_for_load_state("networkidle", timeout=15000)
                log.info("URL apos login click: %s", page.url)
            except Exception as e:
                log.warning("Botao LOGIN nao encontrado: %s", e)
                log.info("Tentando UserArea...")
                page.goto(BASE_URL + "/UserArea", wait_until="networkidle", timeout=30000)
                log.info("URL apos UserArea: %s", page.url)

            # Preenche username no Keycloak
            log.info("URL antes do login: %s", page.url)
            try:
                page.fill("input[name='username']", EMAIL, timeout=15000)
                page.click("#kc-login")
                page.wait_for_load_state("networkidle", timeout=15000)
                log.info("URL apos username: %s", page.url)

                page.fill("input[name='password']", PASSWORD, timeout=15000)
                page.click("#kc-login")
                page.wait_for_load_state("networkidle", timeout=15000)
                log.info("URL apos senha: %s", page.url)
            except Exception as e:
                log.error("Login falhou: %s | URL: %s", e, page.url)
                raise

            log.info("Login realizado. URL: %s", page.url)

            # Acessa Services
            page.goto(BASE_URL + "/Services", wait_until="networkidle", timeout=30000)
            log.info("Services URL: %s", page.url)

            # Clica no RESERVAR do Passaporte
            try:
                rows = page.query_selector_all("tr")
                clicou = False
                for row in rows:
                    texto = row.inner_text()
                    if "Passaporte" in texto and "Primeiro" in texto:
                        btn = row.query_selector("a:has-text('RESERVAR')")
                        if btn:
                            btn.click()
                            clicou = True
                            log.info("Clicou RESERVAR Passaporte.")
                            break

                if not clicou:
                    log.warning("Botao RESERVAR nao encontrado.")
                    return

                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(2)

            except Exception as e:
                log.error("Erro ao clicar RESERVAR: %s", e)
                return

            # Verifica sem vagas
            content = page.content()
            if "currently booked" in content or "All appointments" in content:
                log.warning("Sem vagas disponiveis.")
                return

            log.info("VAGA DISPONIVEL!")
            notificar(
                "VAGA DE PASSAPORTE DISPONIVEL!",
                "Acesse agora: https://prenotami.esteri.it/Services\n\nFINALIZE MANUALMENTE!"
            )

        except Exception as e:
            log.error("Erro: %s", e, exc_info=True)
        finally:
            context.close()
            browser.close()


def main():
    log.info("Bot iniciado.")
    # TESTE - 19:10 UTC (16:10 Brasilia)
    schedule.every().monday.at("19:10").do(tentar_agendar)
    # Horarios reais toda segunda (Brasilia 16h = 19h UTC)
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
