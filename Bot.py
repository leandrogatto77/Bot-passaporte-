import os
import time
import logging
import schedule
import smtplib
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
BOOKING_URL = "https://prenotami.esteri.it/BookingCalendar?selectedService=Agendamento%20Primeiro%20%20Passaporte%20-%20Novas%20vagas%20adicionadas%20toda%20segunda-feira%20%C3%A0s%2016h"


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
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        try:
            # Passo 1: Acessa pagina principal
            log.info("Acessando pagina principal...")
            page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            log.info("URL: %s | Titulo: %s", page.url, page.title())

            # Passo 2: Clica no botao de login
            try:
                page.click("a:has-text('LOGIN')", timeout=10000)
                page.wait_for_load_state("networkidle", timeout=15000)
                log.info("URL apos LOGIN: %s", page.url)
            except Exception as e:
                log.warning("Botao LOGIN nao encontrado: %s", e)
                page.goto(BASE_URL + "/UserArea", wait_until="networkidle", timeout=30000)
                log.info("URL apos UserArea: %s", page.url)

            # Passo 3: Login no Keycloak
            log.info("URL antes do login: %s", page.url)
            page.fill("input[name='username']", EMAIL, timeout=15000)
            page.click("#kc-login")
            page.wait_for_load_state("networkidle", timeout=15000)
            log.info("URL apos username: %s", page.url)

            page.fill("input[name='password']", PASSWORD, timeout=15000)
            page.click("#kc-login")
            page.wait_for_load_state("networkidle", timeout=15000)
            log.info("URL apos senha: %s", page.url)

            # Passo 4: Vai direto para o calendario
            log.info("Acessando calendario de agendamento...")
            page.goto(BOOKING_URL, wait_until="networkidle", timeout=30000)
            log.info("URL calendario: %s", page.url)

            # Passo 5: Verifica se ha dia disponivel (verde)
            content = page.content()
            log.info("Titulo pagina: %s", page.title())

            dias_disponiveis = page.query_selector_all(".day.available, td.available, .green")
            log.info("Dias disponiveis encontrados: %d", len(dias_disponiveis))

            if not dias_disponiveis:
                log.warning("Sem vagas disponiveis.")
                return

            # Ha vaga!
            log.info("VAGA DISPONIVEL! Clicando no primeiro dia...")
            dias_disponiveis[0].click()
            time.sleep(2)

            # Clica no primeiro horario disponivel
            horarios = page.query_selector_all(".slot.available, .time-slot.available, input[type='radio']")
            log.info("Horarios disponiveis: %d", len(horarios))
            if horarios:
                horarios[0].click()
                time.sleep(1)

            log.info("VAGA ENCONTRADA E SELECIONADA!")
            notificar(
                "VAGA DE PASSAPORTE DISPONIVEL!",
                "O bot encontrou uma vaga!\n\nACESSE AGORA:\nhttps://prenotami.esteri.it/Services\n\nFinalize manualmente!"
            )

        except Exception as e:
            log.error("Erro: %s", e, exc_info=True)
        finally:
            context.close()
            browser.close()


def main():
    log.info("Bot iniciado.")

    # Roda imediatamente para teste
    log.info("Executando teste imediato...")
    tentar_agendar()

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
