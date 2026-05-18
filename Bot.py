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
LOGIN_URL = "https://prenotami.esteri.it/Home/Login"


def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=opts)


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
    log.info("Acessando LOGIN_URL: %s", LOGIN_URL)
    driver.get(LOGIN_URL)
    time.sleep(3)
    log.info("URL apos carregar: %s", driver.current_url)
    log.info("Titulo da pagina: %s", driver.title)

    inputs = driver.find_elements(By.TAG_NAME, "input")
    log.info("Inputs encontrados: %d", len(inputs))
    for inp in inputs:
        log.info("Input - id=%s name=%s type=%s",
                 inp.get_attribute("id"),
                 inp.get_attribute("name"),
                 inp.get_attribute("type"))

    wait = WebDriverWait(driver, 30)

    try:
        field = driver.find_element(By.NAME, "username")
        field.send_keys(EMAIL)
        driver.find_element(By.ID, "kc-login").click()
        log.info("Clicou Next no Keycloak.")
        time.sleep(2)
        log.info("URL apos Next: %s", driver.current_url)
        wait.until(EC.presence_of_element_located((By.NAME, "password")))
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.ID, "kc-login").click()
        log.info("Clicou Login no Keycloak.")
    except Exception as e:
        log.warning("Keycloak falhou: %s", e)
        try:
            inputs2 = driver.find_elements(By.TAG_NAME, "input")
            log.info("Inputs apos falha: %d", len(inputs2))
            for inp in inputs2:
                log.info("Input2 - id=%s name=%s type=%s",
                         inp.get_attribute("id"),
                         inp.get_attribute("name"),
                         inp.get_attribute("type"))
            driver.find_element(By.CSS_SELECTOR, "input[type='email'], input[type='text']").send_keys(EMAIL)
            driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(PASSWORD)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']").click()
            log.info("Login via formulario padrao.")
        except Exception as e2:
            log.error("Formulario padrao falhou: %s", e2)
            raise

    time.sleep(3)
    log.info("URL final apos login: %s", driver.current_url)


def tentar_agendar():
    log.info("=== Iniciando tentativa ===")
    driver = get_driver()
    try:
        login(driver)
        wait = WebDriverWait(driver, 20)
        driver.get(BASE_URL + "/Services")
        time.sleep(3)
        log.info("Pagina Services. URL: %s", driver.current_url)

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
    # TESTE - hoje segunda 17:05 UTC (14:05 Brasilia)
    schedule.every().monday.at("17:05").do(tentar_agendar)
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
