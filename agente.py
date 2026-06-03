import os
import json
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
# ============================================================
# CONFIGURACIÓN — Rellena estos valores con tus credenciales
# ============================================================
GEMINI_API_KEY   = "AQ.Ab8RN6LDNf7FuVAPiHhJDhw4O-sUn44JX0_yb_RJvLsOKPWZZQ"
NEWS_API_KEY     = "10ffdd542a66415593d743c5a8db0a7d"
GMAIL_USER       = "joank.9200@gmail.com"
GMAIL_APP_PASS   = "iuadabbrtcichqow"   # Contraseña de aplicación Gmail
EMAIL_DESTINO    = "joank.9200@gmail.com"   # Donde quieres recibir el informe
# ============================================================
# Lista de empresas a monitorizar
EMPRESAS = {
    # --- Cartera ---
    "MSFT":  "Microsoft",
    "META":  "Meta",
    "AMZN":  "Amazon",
    "GOOGL": "Alphabet Google",
    "CSU":   "Constellation Software",
    "V":     "Visa",
    "MA":    "Mastercard",
    "SPGI":  "S&P Global",
    "MCO":   "Moody's",
    "BTC":   "Bitcoin",
    "MELI":  "MercadoLibre",
    "BKNG":  "Booking Holdings",
    "CPRT":  "Copart",
    "DNP":   "Dino Polska",
    "AIR":   "Airbus",
    "7974":  "Nintendo",
    "KRB":   "Kraken Robotics",
    "TMDX":  "TransMedics Group",
    # --- Watchlist ---
    "WCN":   "Waste Connections",
    "MCD":   "McDonald's",
    "AXP":   "American Express",
    "ASTS":  "AST SpaceMobile",
    "NVDA":  "Nvidia",
    "BRK.B": "Berkshire Hathaway",
}

TICKERS_SEC = [
    "MSFT","META","AMZN","GOOGL","V","MA","SPGI","MCO",
    "MELI","BKNG","CPRT","TMDX","WCN","MCD","AXP","ASTS","NVDA"
]


def get_insider_transactions():
    """Obtiene transacciones de insiders de la SEC (EDGAR) de los últimos 2 días."""
    resultados = []
    headers = {"User-Agent": "agente-bolsa joancarlesconsultor@gmail.com"}
    hoy = datetime.now()
    hace_dos_dias = hoy - timedelta(days=2)

    for ticker in TICKERS_SEC:
        try:
            # Buscar CIK por ticker
            url_cik = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={hace_dos_dias.strftime('%Y-%m-%d')}&enddt={hoy.strftime('%Y-%m-%d')}&forms=4"
            resp = requests.get(url_cik, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits[:3]:  # máximo 3 por empresa
                src = hit.get("_source", {})
                nombre = EMPRESAS.get(ticker, ticker)
                resultados.append({
                    "empresa": nombre,
                    "ticker": ticker,
                    "fecha": src.get("file_date", ""),
                    "descripcion": src.get("display_names", ""),
                    "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}&type=4&dateb=&owner=include&count=10"
                })
        except Exception:
            continue

    return resultados


def get_noticias():
    """Obtiene noticias recientes de todas las empresas monitorizadas."""
    nombres = list(EMPRESAS.values())
    # Agrupamos en queries para no exceder límites
    queries = [
        "Microsoft OR Meta OR Amazon OR Alphabet OR Google",
        "Constellation Software OR Visa OR Mastercard OR \"S&P Global\" OR Moody's",
        "MercadoLibre OR Booking Holdings OR Copart OR Airbus OR Nintendo",
        "Nvidia OR Berkshire Hathaway OR \"American Express\" OR McDonald's OR \"Waste Connections\"",
        "Bitcoin OR \"AST SpaceMobile\" OR TransMedics OR \"Kraken Robotics\" OR \"Dino Polska\""
    ]

    noticias = []
    ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    for q in queries:
        try:
            url = (
                f"https://newsapi.org/v2/everything"
                f"?q={requests.utils.quote(q)}"
                f"&from={ayer}"
                f"&language=en"
                f"&sortBy=relevancy"
                f"&pageSize=5"
                f"&apiKey={NEWS_API_KEY}"
            )
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            articles = resp.json().get("articles", [])
            for a in articles:
                noticias.append({
                    "titulo": a.get("title", ""),
                    "fuente": a.get("source", {}).get("name", ""),
                    "descripcion": a.get("description", ""),
                    "url": a.get("url", ""),
                    "fecha": a.get("publishedAt", "")
                })
        except Exception:
            continue

    return noticias


def generar_informe_con_gemini(noticias, insiders):
    """Usa Gemini para generar el informe en español."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    noticias_texto = "\n".join([
        f"- [{n['fuente']}] {n['titulo']}: {n['descripcion']} ({n['url']})"
        for n in noticias[:40]
    ])

    insiders_texto = "\n".join([
        f"- {i['empresa']} ({i['ticker']}): {i['descripcion']} — Fecha: {i['fecha']} — {i['url']}"
        for i in insiders[:20]
    ]) if insiders else "No se han detectado transacciones de insiders relevantes en las últimas 48h."

    prompt = f"""
Eres un analista de inversiones experto. Hoy es {fecha_hoy}.
Tu tarea es generar un informe diario de seguimiento de cartera en ESPAÑOL para un inversor particular.

El inversor tiene en cartera: Microsoft, Meta, Amazon, Alphabet, Constellation Software, Visa, Mastercard,
S&P Global, Moody's, Bitcoin, MercadoLibre, Booking Holdings, Copart, Dino Polska, Airbus, Nintendo,
Kraken Robotics y TransMedics.

También monitoriza: Waste Connections, McDonald's, American Express, AST SpaceMobile, Nvidia y Berkshire Hathaway.

Con los datos que tienes a continuación, genera un informe estructurado con estas secciones:

1. **RESUMEN EJECUTIVO** (3-4 líneas con lo más importante del día)
2. **NOTICIAS RELEVANTES POR EMPRESA** (solo las que tengan noticias reales, omite las que no)
3. **TRANSACCIONES DE INSIDERS** (compras/ventas relevantes detectadas)
4. **SEÑALES A VIGILAR** (eventos próximos, riesgos o catalizadores que el inversor debe tener en cuenta)

Sé conciso, directo y orientado a la toma de decisiones. Omite relleno.
Si una noticia no es relevante para un inversor a largo plazo, no la incluyas.

--- NOTICIAS ---
{noticias_texto}

--- TRANSACCIONES INSIDERS (SEC Form 4) ---
{insiders_texto}
"""

    response = model.generate_content(prompt)
    return response.text


def enviar_email(informe):
    """Envía el informe por email."""
    fecha = datetime.now().strftime("%d/%m/%Y")
    asunto = f"📊 Informe Diario de Cartera — {fecha}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_DESTINO

    # Versión texto plano
    parte_texto = MIMEText(informe, "plain", "utf-8")

    # Versión HTML básica para mejor legibilidad
    html_informe = informe.replace("\n", "<br>").replace("**", "")
    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px;">
    <h2 style="color: #1a1a2e;">📊 Informe Diario de Cartera — {fecha}</h2>
    <hr>
    <div style="line-height: 1.7; color: #333;">
    {html_informe}
    </div>
    <hr>
    <p style="color: #999; font-size: 12px;">Generado automáticamente por tu Agente de Bolsa</p>
    </body></html>
    """
    parte_html = MIMEText(html, "html", "utf-8")

    msg.attach(parte_texto)
    msg.attach(parte_html)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(GMAIL_USER, GMAIL_APP_PASS)
        servidor.sendmail(GMAIL_USER, EMAIL_DESTINO, msg.as_string())

    print(f"✅ Informe enviado a {EMAIL_DESTINO}")


def main():
    print(f"🔍 Iniciando agente — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    print("📰 Obteniendo noticias...")
    noticias = get_noticias()
    print(f"   → {len(noticias)} noticias obtenidas")

    print("📋 Consultando insiders en SEC...")
    insiders = get_insider_transactions()
    print(f"   → {len(insiders)} transacciones encontradas")

    print("🤖 Generando informe con Gemini...")
    informe = generar_informe_con_gemini(noticias, insiders)

    print("📧 Enviando email...")
    enviar_email(informe)

    print("✅ Proceso completado.")


if __name__ == "__main__":
    main()
