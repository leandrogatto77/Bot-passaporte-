import os
import time
import logging
import schedule
import smtplib
import requests
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


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


def login():
    session = requests.Session()
    session.headers.update(HEADERS)

    # Passo 1: Acessa pagina principal para pegar cookies
    log.info("Acessando pagina principal...")
    resp = session.get(BASE_URL, timeout=30)
    log.info("Status pagina principal: %d", resp.status_code)
    log.info("URL final: %s", resp.url)

    # Passo 2: Acessa UserArea para ser redirecionado ao IAM
    log.info("Acessando UserArea...")
    resp = session.get(BASE_URL + "/UserArea", timeout=30, allow_redirects=True)
    log.info("Status UserArea: %d", resp.status_code)
    log.info("URL apos UserArea: %s", resp.url)

    # Passo 3: Pega a URL do IAM e extrai o form
    iam_url = resp.url
    log.info("IAM URL: %s", iam_url)

    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form")
    if not form:
        log.error("Formulario de login nao encontrado!")
        log.info("Conteudo da pagina: %s", resp.text[:500])
        return None

    # Passo 4: Preenche e envia o formulario de username
    action = form.get("action", iam_url)
    if not action.startswith("http"):
        from urllib.parse import urljoin
        action = urljoin(iam_url, action)

    dados = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        value = inp.get("value", "")
        if name:
            dados[name] = value

    dados["username"] = EMAIL
    log.info("Enviando username para: %s", action)
    resp = session.post(action, data=dados, timeout=30, allow_redirects=True)
    log.info("Status apos username: %d | URL: %s", resp.status_code, resp.url)

    # Passo 5: Preenche e envia o formulario de senha
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form")
    if not form:
        log.error("Formulario de senha nao encontrado!")
        log.info("Conteudo: %s", resp.text[:500])
        return None

    action = form.get("action", resp.url)
    if not action.startswith("http"):
        from urllib.parse import urljoin
        action = urljoin(resp.url, action)

    dados = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        value = inp.get("value", "")
        if name:
            dados[name] = value

    dados["password"] = PASSWORD
    log.info("Enviando senha para: %s", action)
    resp = session.post(action, data=dados, timeout=30, allow_redirects=True)
    log.info("Status apos senha: %d | URL: %s", resp.status_code, resp.url)

    if "prenotami.esteri.it" in resp.url and "UserArea" in resp.url:
        log.info("Login realizado com sucesso!")
        return session
    elif "prenotami.esteri.it" in resp.url:
        log.info("Redirecionado para prenotami: %s", resp.url)
        return session
    else:
        log.error("Login falhou. URL final: %s", resp.url)
        return None


def tentar_agendar():
    log.info("=== Iniciando tentativa ===")
    try:
        session = login()
        if not session:
            log.error("Sessao nao criada.")
            return

        # Acessa Services
        log.info("Acessando Services...")
        resp = session.get(BASE_URL + "/Services", timeout=30)
        log.info("Status Services: %d | URL: %s", resp.status_code, resp.url)

        soup = BeautifulSoup(resp.text, "html.parser")

        # Procura pelo link RESERVAR do Passaporte
        links = soup.find_all("a", string=lambda t: t and "RESERVAR" in t)
        log.info("Links RESERVAR encontrados: %d", len(links))

        link_passaporte = None
        for link in links:
            tr = link.find_parent("tr")
            if tr and "Passaporte" in tr.get_text() and "Primeiro" in tr.get_text():
                link_passaporte = link
                break

        if not link_passaporte:
            log.warning("Link RESERVAR do Passaporte nao encontrado.")
            return

        href = link_passaporte.get("href", "")
        if not href.startswith("http"):
            href = BASE_URL + href

        log.info("Acessando link RESERVAR: %s", href)
        resp = session.get(href, timeout=30, allow_redirects=True)
        log.info("Status RESERVAR: %d | URL: %s", resp.status_code, resp.url)

        if "currently booked" in resp.text or "All appointments" in resp.text:
            log.warning("Sem vagas disponiveis.")
            return

        log.info("VAGA DISPONIVEL!")
        notificar(
            "VAGA DE PASSAPORTE DISPONIVEL!",
            "Acesse agora: https://prenotami.esteri.it/Services"
        )

    except Exception as e:
        log.error("Erro: %s", e, exc_info=True)


def main():
    log.info("Bot iniciado.")
    # TESTE - 18:10 UTC (15:10 Brasilia)
    schedule.every().monday.at("18:10").do(tentar_agendar)
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
