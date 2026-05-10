import os
import time
import logging
import schedule
import requests
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EMAIL = os.environ["PRENOTA_EMAIL"]
PASSWORD = os.environ["PRENOTA_PASSWORD"]
WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE", "")
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "")
BASE_URL = "https://prenotami.esteri.it"

def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=opts)

def notificar(mensagem):
    if not WHATSAPP_PHONE or not CALLMEBOT_APIKEY:
        log.warning("WhatsApp não configurado ainda.")
        return
    try:
        texto = urllib.parse.quote(mensagem)
        url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={texto}&apikey={CALLMEBOT_APIKEY}"
        requests.get(url, timeout=10)
        log.info("WhatsApp enviado!")
    except Exception as e:
        log.error(f"Erro ao enviar WhatsApp: {e}")

def login(driver):
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 30)
    wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//a[contains(@href,'login') or contains(text(),'LOGIN')]")
    )).click()
    wait.until(EC.presence_of_element_located((By.NAME, "username")))
    driver.find_element(By.NAME, "username").send_keys(EMAIL)
    driver.find_element(By.ID, "kc-login").click()
    wait.until(EC.presence_of_element_located((By.NAME, "password")))
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.ID, "kc-login").click()
    wait.until(EC.url_contains("prenotami.esteri.it"))
    log.info("Login realizado com sucesso.")

def tentar_agendar():
    log.info("=== Iniciando tentativa ===")
    driver = get_driver()
    try:
        login(driver)
        wait = WebDriverWait(driver, 20)

        driver.get(f"{BASE_URL}/Services")
        time.sleep(3)

        # Clica no RESERVAR do​​​​​​​​​​​​​​​​

