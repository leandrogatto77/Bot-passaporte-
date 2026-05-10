import os
import time
import logging
import schedule
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EMAIL = os.environ["PRENOTA_EMAIL"]
PASSWORD = os.environ["PRENOTA_PASSWORD"]
BASE_URL = "https://prenotaonline.esteri.it"

def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=opts)

def login(driver):
    driver.get(f"{BASE_URL}/login")
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.ID, "email"))).send_keys(EMAIL)
    driver.find_element(By.ID, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    wait.until(EC.url_changes(f"{BASE_URL}/login"))

def tentar_agendar():
    log.info("=== Iniciando tentativa ===")
    driver = get_driver()
    try:
        login(driver)
        wait = WebDriverWait(driver, 20)
        driver.get(f"{BASE_URL}/vistaportal/pages/booking/BeginBookingNoOtp.aspx")
        Select(wait.until(EC.presence_of_element_located((By.ID, "ddlSede")))).select_by_visible_text("San Paolo")
        time.sleep(2)
        Select(wait.until(EC.presence_of_element_located((By.ID, "ddlCategoria")))).select_by_visible_text("Passaporti")
        time.sleep(2)
        Select(wait.until(EC.presence_of_element_located((By.ID, "ddlServizio")))).select_by_visible_text("Primo rilascio")
        time.sleep(2)
        driver.find_element(By.ID, "btnAvanti").click()
        time.sleep(3)
        try:
            slot = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".day.available, .slot-available")))
            slot.click()
            time.sleep(2)
            wait.until(EC.element_to_be_clickable((By.ID, "btnConferma"))).click()
            log.info("Agendamento CONFIRMADO!")
        except Exception:
            log.warning("Nenhuma vaga disponível.")
    except Exception as e:
        log.error(f"Erro: {e}", exc_info=True)
    finally:
        driver.quit()

def main():
    log.info("Bot iniciado.")
    schedule.every().monday.at("16:00").do(tentar_agendar)
    tentar_agendar()
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
