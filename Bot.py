import os
import time
import logging
import schedule
import smtplib
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

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


def get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


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


def login(driver):
    # Acessa a pagina principal e clica no botao de login
    log.info("Acessando pagina principal: %s", BASE_URL)
    driver.get(BASE_URL)
    time.sleep(5)
    log.info("URL: %s", driver.current_url)
    log.info("Titulo: %s", driver.title)

    wait = WebDriverWait(driver, 30)

    # Clica no botao de login da pagina principal
    try:
        botao_login = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'LOGIN') or contains(@href,'login') or contains(@href,'Login')]")
        ))
        log.info("Botao login encontrado: %s", botao_login.text)
        botao_login.click()
        time.sleep(5)
        log.info("URL apos clicar login: %s", driver.current_url)
    except Exception as e:
        log.warning("Botao login nao encontrado: %s", e)
        # Tenta ir direto para UserArea que redireciona para login
        driver.get(BASE_URL + "/UserArea")
        time.sleep(5)
        log.info("URL apos UserArea: %s", driver.current_url)

    # Agora deve estar no IAM (Keycloak)
    log.info("URL antes do login: %s", driver.current_url)

    try:
        wait.until(EC.presence_of_element_located((By.NAME, "username")))
        driver.find_element(By.NAME, "username").send_keys(EMAIL)
        driver.find_element(By.ID, "kc-login").click()
        log.info("Clicou Next.")
        time.sleep(3)
        wait.until(EC.presence_of_element_located((By.NAME, "password")))
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.ID, "kc-login").click()
        log.info("Clicou Login.")
    except Exception as e:
        log.error("Login falhou: %s | URL: %s", e, driver.current_url)
        raise

    time.sleep(3)
    log.info("URL final: %s", driver.current_url)


def tentar_agendar():
    log.info("=== Iniciando tentativa ===")
    driver = get_driver()
    try:
        login(driver)
        wait = WebDriverWait(driver, 20)
        driver.get(BASE_URL + "/Services")
        time.sleep(3)
        log.info("Services URL: %s", driver.current_url)

        botoes = driver.find_elements(By.XPATH, "//a[contains(text(),'RESERVAR')]")
        log.info("Botoes RESERVAR: %d", len(botoes))
        clicou = False
        for botao in botoes:
            try:
                linha = botao.find_element(By.XPATH, "./ancestor::tr")
                texto = linha.text
                if "Passaporte" in texto and "Primeiro" in texto:
                    botao.click()
                    clicou = True
                    log.info("Clicou RESERVAR Passaporte.")
                    break
            except Exception:
                continue

        if not clicou:
            log.warning("Botao RESERVAR nao encontrado.")
            return

        time.sleep(3)

        sem_vagas = False
        try:
            elementos = driver.find_elements(
                By.XPATH, "//div[contains(text(),'currently booked')]"
            )
            if elementos and elementos[0].is_displayed():
                sem_vagas = True
                driver.find_elements(
                    By.XPATH, "//button[contains(text(),'OK')]"
                )[0].click()
        except Exception:
            pass

        if sem_vagas:
            log.warning("Sem vagas disponiveis.")
            return

        log.info("VAGA DISPONIVEL!")
        notificar(
            "VAGA DE PASSAPORTE DISPONIVEL!",
            "Acesse agora: https://prenotami.esteri.it/Services"
        )

    except Exception as e:
        log.error("Erro: %s", e, exc_info=True)
    finally:
        driver.quit()


def main():
    log.info("Bot iniciado.")
    # TESTE - 17:35 UTC (14:35 Brasilia)
    schedule.every().monday.at("17:35").do(tentar_agendar)
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
