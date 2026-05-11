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
format=”%(asctime)s [%(levelname)s] %(message)s”
)
log = logging.getLogger(**name**)

EMAIL = os.environ[“PRENOTA_EMAIL”]
PASSWORD = os.environ[“PRENOTA_PASSWORD”]
GMAIL_USER = os.environ[“GMAIL_USER”]
GMAIL_APP_PASSWORD = os.environ[“GMAIL_APP_PASSWORD”]
BASE_URL = “https://prenotami.esteri.it”

def get_driver():
opts = Options()
opts.add_argument(”–headless”)
opts.add_argument(”–no-sandbox”)
opts.add_argument(”–disable-dev-shm-usage”)
opts.add_argument(”–disable-gpu”)
opts.add_argument(”–window-size=1920,1080”)
return webdriver.Chrome(options=opts)

def notificar(assunto, mensagem):
try:
msg = MIMEText(mensagem)
msg[“Subject”] = assunto
msg[“From”] = GMAIL_USER
msg[“To”] = GMAIL_USER
with smtplib.SMTP_SSL(“smtp.gmail.com”, 465) as smtp:
smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
smtp.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
log.info(“E-mail enviado!”)
except Exception as e:
log.error(“Erro ao enviar e-mail: %s”, e)

def login(driver):
driver.get(BASE_URL)
wait = WebDriverWait(driver, 30)
xpath_login = “//a[contains(@href,‘login’) or contains(text(),‘LOGIN’)]”
wait.until(EC.element_to_be_clickable((By.XPATH, xpath_login))).click()
wait.until(EC.presence_of_element_located((By.NAME, “username”)))
driver.find_element(By.NAME, “username”).send_keys(EMAIL)
driver.find_element(By.ID, “kc-login”).click()
wait.until(EC.presence_of_element_located((By.NAME, “password”)))
driver.find_element(By.NAME, “password”).send_keys(PASSWORD)
driver.find_element(By.ID, “kc-login”).click()
wait.until(EC.url_contains(“prenotami.esteri.it”))
log.info(“Login realizado com sucesso.”)

def tentar_agendar():
log.info(”=== Iniciando tentativa ===”)
driver = get_driver()
try:
login(driver)
wait = WebDriverWait(driver, 20)
driver.get(BASE_URL + “/Services”)
time.sleep(3)

```
    # Clica no RESERVAR do Primeiro Passaporte
    botoes = driver.find_elements(By.XPATH, "//a[contains(text(),'RESERVAR')]")
    clicou = False
    for botao in botoes:
        try:
            linha = botao.find_element(By.XPATH, "./ancestor::tr")
            texto = linha.text
            if "Passaporte" in texto and "Primeiro" in texto:
                botao.click()
                clicou = True
                break
        except Exception:
            continue

    if not clicou:
        log.warning("Botao RESERVAR do Passaporte nao encontrado.")
        return

    time.sleep(3)

    # Verifica popup de sem vagas
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

    # Ha vaga! Tenta clicar no primeiro slot verde disponivel
    log.info("VAGA DISPONIVEL! Tentando selecionar slot...")
    slot_selecionado = False
    try:
        slots = driver.find_elements(
            By.CSS_SELECTOR, ".day.available, .slot-available, td.green, td.available"
        )
        if slots:
            slots[0].click()
            slot_selecionado = True
            log.info("Slot selecionado!")
            time.sleep(2)
    except Exception as e:
        log.warning("Nao conseguiu selecionar slot: %s", e)

    # Notifica o usuario para finalizar manualmente
    if slot_selecionado:
        assunto = "ACAO NECESSARIA - Vaga de Passaporte Selecionada!"
        mensagem = (
            "O bot encontrou e selecionou uma vaga de passaporte!\n\n"
            "ACESSE AGORA e finalize o agendamento:\n"
            "https://prenotami.esteri.it/Services\n\n"
            "Voce precisara:\n"
            "1. Inserir o codigo recebido por e-mail/SMS\n"
            "2. Aceitar a Politica\n"
            "3. Clicar em AVANCAR\n\n"
            "ATENCAO: A vaga pode expirar em poucos minutos!"
        )
    else:
        assunto = "ACAO NECESSARIA - Vaga de Passaporte Disponivel!"
        mensagem = (
            "O bot detectou uma vaga de passaporte disponivel!\n\n"
            "ACESSE AGORA e finalize o agendamento manualmente:\n"
            "https://prenotami.esteri.it/Services\n\n"
            "Selecione o slot disponivel, insira o codigo e confirme.\n\n"
            "ATENCAO: A vaga pode expirar em poucos minutos!"
        )

    notificar(assunto, mensagem)

except Exception as e:
    log.error("Erro: %s", e, exc_info=True)
finally:
    driver.quit()
```

def main():
log.info(“Bot iniciado.”)
horarios = [“15:55”, “16:00”, “16:01”, “16:02”, “16:03”,
“16:05”, “16:10”, “16:15”, “16:20”, “16:30”]
for horario in horarios:
schedule.every().monday.at(horario).do(tentar_agendar)
while True:
schedule.run_pending()
time.sleep(10)

if **name** == “**main**”:
main()
