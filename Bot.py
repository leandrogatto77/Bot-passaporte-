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

logging.basicConfig(level=logging.INFO, format=”%(asctime)s [%(levelname)s] %(message)s”)
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

def notificar(mensagem):
try:
msg = MIMEText(mensagem)
msg[“Subject”] = “VAGA DE PASSAPORTE DISPONIVEL!”
msg[“From”] = GMAIL_USER
msg[“To”] = GMAIL_USER
with smtplib.SMTP_SSL(“smtp.gmail.com”, 465) as smtp:
smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
smtp.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
log.info(“E-mail enviado!”)
except Exception as e:
log.error(f”Erro ao enviar e-mail: {e}”)

def login(driver):
driver.get(BASE_URL)
wait = WebDriverWait(driver, 30)
wait.until(EC.element_to_be_clickable(
(By.XPATH, “//a[contains(@href,‘login’) or contains(text(),‘LOGIN’)]”)
)).click()
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
driver.get(f”{BASE_URL}/Services”)
time.sleep(3)

```
    btn = wait.until(EC.element_to_be_clickable((
        By.XPATH,
        "//tr[td[contains(text(),'Passaporte')] and td[contains(text(),'Primeiro Passaporte')]]//a[contains(text(),'RESERVAR')]"
    )))
    btn.click()
    time.sleep(3)

    try:
        popup = driver.find_element(
            By.XPATH,
            "//div[contains(text(),'All appointments for this service are currently booked')]"
        )
        if popup.is_displayed():
            driver.find_element(By.XPATH, "//button[contains(text(),'OK')]").click()
            log.warning("Sem vagas disponiveis.")
            return
    except Exception:
        pass

    log.info("VAGA DISPONIVEL!")
    notificar("Uma vaga foi encontrada! Acesse agora: https://prenotami.esteri.it/Services")

    for selector in ["btnConferma", "btnNext", "btnAvanti", "btnBook"]:
        try:
            driver.find_element(By.ID, selector).click()
            log.info(f"Clicou em {selector}")
            time.sleep(2)
            break
        except Exception:
            continue

except Exception as e:
    log.error(f"Erro: {e}", exc_info=True)
finally:
    driver.quit()
```

def main():
log.info(“Bot iniciado.”)
for horario in [“15:55”, “16:00”, “16:01”, “16:02”, “16:03”, “16:05”, “16:10”, “16:15”, “16:20”, “16:30”]:
schedule.every().monday.at(horario).do(tentar_agendar)
while True:
schedule.run_pending()
time.sleep(10)

if **name** == “**main**”:
main()
