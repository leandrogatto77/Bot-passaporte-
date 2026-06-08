import os
import time
import logging
import schedule
import smtplib
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


def aguardar_keycloak(page, max_tentativas=10):
    for i in range(max_tentativas):
        url = page.url
        log.info("Tentativa %d | URL: %s", i+1, url)
        if "iam.esteri.it" in url and "validate.perfdrive" not in url and "botmanager" not in url:
            # Verifica se o campo username esta presente
            inputs = page.query_selector_all("input")
            nomes = [inp.get_attribute("name") for inp in inputs]
            log.info("Inputs: %s", nomes)
            if "username" in nomes:
                log.info("Keycloak carregado com sucesso!")
                return True
        log.info("Aguardando Keycloak... (%d/10)", i+1)
        time.sleep(5)
    return False


def tentar_agendar():
    log.info("=== Iniciando tentativa ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-extensions",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        try:
            # Passo 1: Pagina principal
            log.info("Acessando pagina principal...")
            try:
                page.goto(BASE_URL, wait_until="commit", timeout=60000)
            except PlaywrightTimeout:
                log.warning("Timeout na pagina principal — continuando.")
            time.sleep(5)
            log.info("URL: %s | Titulo: %s", page.url, page.title())

            # Passo 2: Clica no botao LOGIN
            try:
                page.click("a:has-text('LOGIN')", timeout=5000)
                log.info("Clicou LOGIN.")
            except Exception:
                log.info("Botao LOGIN nao encontrado, indo para UserArea...")
                try:
                    page.goto(BASE_URL + "/UserArea", wait_until="commit", timeout=60000)
                except PlaywrightTimeout:
                    log.warning("Timeout no UserArea — continuando.")

            # Passo 3: Aguarda Keycloak carregar (com retry)
            log.info("Aguardando Keycloak...")
            keycloak_ok = aguardar_keycloak(page, max_tentativas=12)

            if not keycloak_ok:
                log.error("Keycloak nao carregou apos 60 segundos.")
                return

            # Passo 4: Preenche login
            page.fill("input[name='username']", EMAIL)
            time.sleep(1)
            page.click("#kc-login")
            time.sleep(8)
            log.info("URL apos username: %s", page.url)

            page.wait_for_selector("input[name='password']", timeout=30000)
            page.fill("input[name='password']", PASSWORD)
            time.sleep(1)
            page.click("#kc-login")
            time.sleep(8)
            log.info("URL apos senha: %s", page.url)

            # Passo 5: Acessa Services
            log.info("Acessando Services...")
            try:
                page.goto(BASE_URL + "/Services", wait_until="commit", timeout=60000)
            except PlaywrightTimeout:
                log.warning("Timeout no Services — continuando.")
            time.sleep(5)
            log.info("Services URL: %s", page.url)

            # Passo 6: Clica no RESERVAR do Passaporte
            rows = page.query_selector_all("tr")
            log.info("Linhas: %d", len(rows))
            clicou = False
            for row in rows:
                texto = row.inner_text()
                if "Passaporte" in texto and "Primeiro" in texto:
                    btn = row.query_selector("a:has-text('RESERVAR')")
                    if btn:
                        btn.click()
                        clicou = True
                        log.info("Clicou RESERVAR.")
                        break

            if not clicou:
                log.warning("Botao RESERVAR nao encontrado.")
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
    log.info("Executando teste imediato...")
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
