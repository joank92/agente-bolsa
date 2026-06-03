import os
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai

# ============================================================
# CONFIGURACIÓN
# ============================================================
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
NEWS_API_KEY    = os.environ.get("NEWS_API_KEY", "")
GMAIL_USER      = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASS  = os.environ.get("GMAIL_APP_PASS", "")
EMAIL_DESTINO   = os.environ.get("EMAIL_DESTINO", "")
# ============================================================

EMPRESAS_USA = {
    "MSFT": "Microsoft", "META": "Meta", "AMZN": "Amazon", "GOOGL": "Alphabet",
    "V": "Visa", "MA": "Mastercard", "SPGI": "S&P Global", "MCO": "Moody's",
    "MELI": "MercadoLibre", "BKNG": "Booking Holdings", "CPRT": "Copart",
    "TMDX": "TransMedics", "WCN": "Waste Connections", "MCD": "McDonald's",
    "AXP": "American Express", "ASTS": "AST SpaceMobile", "NVDA": "Nvidia",
}

EMPRESAS_INTL = {
    "CSU.TO":  ("Constellation Software", "CA"),
    "KRB.V":   ("Kraken Robotics", "CA"),
    "AIR.PA":  ("Airbus", "FR"),
    "7974.T":  ("Nintendo", "JP"),
    "DNP.WA":  ("Dino Polska", "PL"),
}

CRYPTO = {"BTC": "Bitcoin"}

TODAS_EMPRESAS = (
    list(EMPRESAS_USA.values()) +
    [v[0] for v in EMPRESAS_INTL.values()] +
    list(CRYPTO.values())
)

HEADERS_SEC = {"User-Agent": "agente-bolsa investigador@gmail.com"}


# ─────────────────────────────────────────────
# 1. MACRO
# ─────────────────────────────────────────────
def get_macro_data():
    """Obtiene datos macro vía NewsAPI."""
    queries = [
        "Federal Reserve interest rates inflation 2026",
        "ECB European Central Bank rates economy",
        "geopolitical risk trade war tariffs 2026",
        "US dollar DXY oil gold commodities",
        "recession GDP growth outlook 2026",
    ]
    noticias = []
    ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    for q in queries:
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={requests.utils.quote(q)}"
                f"&from={ayer}&language=en&sortBy=relevancy&pageSize=3&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    noticias.append(f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}")
        except Exception:
            continue
    return noticias


# ─────────────────────────────────────────────
# 2. NOTICIAS POR EMPRESA
# ─────────────────────────────────────────────
def get_noticias_empresas():
    """Busca noticias para cada empresa individualmente."""
    resultado = {}
    ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    todas = {**{t: n for t, n in EMPRESAS_USA.items()},
             **{t: v[0] for t, v in EMPRESAS_INTL.items()},
             **CRYPTO}

    for ticker, nombre in todas.items():
        try:
            q = requests.utils.quote(f'"{nombre}"')
            url = (
                f"https://newsapi.org/v2/everything?q={q}"
                f"&from={ayer}&language=en&sortBy=relevancy&pageSize=4&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                arts = r.json().get("articles", [])
                if arts:
                    resultado[nombre] = [
                        f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}"
                        for a in arts
                    ]
                else:
                    resultado[nombre] = []
        except Exception:
            resultado[nombre] = []
    return resultado


# ─────────────────────────────────────────────
# 3. INSIDERS
# ─────────────────────────────────────────────
def get_insiders_usa():
    """Form 4 de la SEC para empresas USA."""
    resultados = []
    hoy = datetime.now()
    hace_3_dias = (hoy - timedelta(days=3)).strftime("%Y-%m-%d")
    hoy_str = hoy.strftime("%Y-%m-%d")

    for ticker in EMPRESAS_USA.keys():
        try:
            url = (
                f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22"
                f"&dateRange=custom&startdt={hace_3_dias}&enddt={hoy_str}&forms=4"
            )
            r = requests.get(url, headers=HEADERS_SEC, timeout=10)
            if r.status_code != 200:
                continue
            hits = r.json().get("hits", {}).get("hits", [])
            for h in hits[:3]:
                src = h.get("_source", {})
                resultados.append(
                    f"{EMPRESAS_USA[ticker]} ({ticker}) | "
                    f"Fecha: {src.get('file_date','')} | "
                    f"Declarante: {src.get('display_names','')} | "
                    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=4&dateb=&owner=include&count=5"
                )
        except Exception:
            continue
    return resultados


def get_insiders_canada():
    """SEDI canadiense para CSU y Kraken vía scraping básico."""
    resultados = []
    empresas = {"Constellation Software": "CSU", "Kraken Robotics": "KRB"}
    for nombre, ticker in empresas.items():
        try:
            url = f"https://www.sedi.ca/sedi/SVTFileViewer?event=DISPLAY&lang=EN&search=BASICFILEISSUER&issuerId=&issuerName={requests.utils.quote(nombre)}&transactionFromDate=&transactionToDate=&insider=&filingType=4"
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and nombre.lower() in r.text.lower():
                resultados.append(
                    f"{nombre} ({ticker}) | Consultar SEDI: https://www.sedi.ca"
                )
        except Exception:
            continue
    return resultados


def get_insiders_europa_japon():
    """Noticias de insiders para empresas europeas y japonesas."""
    resultados = []
    empresas_buscar = [
        ("Airbus", "AIR.PA", "Airbus insider transaction AMF"),
        ("Nintendo", "7974.T", "Nintendo insider transaction TDnet"),
        ("Dino Polska", "DNP.WA", "Dino Polska insider transaction ESPI"),
    ]
    ayer = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    for nombre, ticker, query in empresas_buscar:
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={requests.utils.quote(query)}"
                f"&from={ayer}&language=en&sortBy=relevancy&pageSize=2&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                arts = r.json().get("articles", [])
                for a in arts:
                    resultados.append(
                        f"{nombre} ({ticker}) | [{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('url','')}"
                    )
        except Exception:
            continue
    return resultados


def get_todos_insiders():
    insiders = []
    insiders += get_insiders_usa()
    insiders += get_insiders_canada()
    insiders += get_insiders_europa_japon()
    return insiders


# ─────────────────────────────────────────────
# 5. CALENDARIO DE RESULTADOS
# ─────────────────────────────────────────────
def get_calendario_resultados():
    """Busca próximas presentaciones de resultados vía NewsAPI."""
    hoy = datetime.now()
    en_dos_semanas = (hoy + timedelta(days=14)).strftime("%Y-%m-%d")
    hoy_str = hoy.strftime("%Y-%m-%d")

    nombres_busqueda = " OR ".join([
        f'"{n}"' for n in [
            "Microsoft", "Meta", "Amazon", "Alphabet", "Visa", "Mastercard",
            "MercadoLibre", "Nvidia", "Booking", "Copart", "TransMedics",
            "Nintendo", "Airbus", "Constellation Software", "Dino Polska",
            "Waste Connections", "McDonald's", "American Express", "Berkshire"
        ]
    ])

    resultados = []
    queries = [
        "earnings date results Q2 2026 " + "Microsoft OR Meta OR Amazon OR Alphabet OR Nvidia OR Visa OR Mastercard",
        "earnings date results Q2 2026 " + "MercadoLibre OR Booking OR Copart OR TransMedics OR \"Waste Connections\" OR McDonald's",
        "earnings results 2026 Nintendo OR Airbus OR \"Constellation Software\" OR \"Dino Polska\" OR \"Kraken Robotics\"",
        "earnings calendar Q2 2026 \"American Express\" OR Berkshire OR \"AST SpaceMobile\" OR \"S&P Global\" OR Moody's",
    ]

    for q in queries:
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={requests.utils.quote(q)}"
                f"&from={hoy_str}&language=en&sortBy=relevancy&pageSize=4&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    resultados.append(
                        f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')} ({a.get('url','')})"
                    )
        except Exception:
            continue
    return resultados


# ─────────────────────────────────────────────
# GEMINI — GENERAR INFORME
# ─────────────────────────────────────────────
def generar_informe(macro, noticias_empresas, insiders, calendario):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    fecha = datetime.now().strftime("%d/%m/%Y")

    # Formatear noticias por empresa
    noticias_texto = ""
    for empresa, arts in noticias_empresas.items():
        if arts:
            noticias_texto += f"\n### {empresa}\n"
            for a in arts:
                noticias_texto += f"  - {a}\n"
        else:
            noticias_texto += f"\n### {empresa}\n  - Sin noticias\n"

    macro_texto = "\n".join(macro[:15]) if macro else "Sin datos macro disponibles."
    insiders_texto = "\n".join(insiders[:25]) if insiders else "Sin transacciones de insiders detectadas."
    calendario_texto = "\n".join(calendario[:20]) if calendario else "Sin información de calendario de resultados."

    prompt = f"""
Eres un analista de inversiones senior. Hoy es {fecha}.
Genera un informe diario de seguimiento de cartera en ESPAÑOL, estructurado, conciso y orientado a la toma de decisiones.

El inversor tiene en cartera: Microsoft, Meta, Amazon, Alphabet, Constellation Software, Visa, Mastercard,
S&P Global, Moody's, Bitcoin, MercadoLibre, Booking Holdings, Copart, Dino Polska, Airbus, Nintendo,
Kraken Robotics y TransMedics.
También monitoriza: Waste Connections, McDonald's, American Express, AST SpaceMobile, Nvidia y Berkshire Hathaway.

Genera el informe con EXACTAMENTE estas 5 secciones:

---
## 1. RESUMEN MACRO
Tipos de interés, inflación, geopolítica, divisas, materias primas. Qué implica para la cartera.
Usa los datos proporcionados. Sé directo y analítico.

## 2. NOTICIAS POR EMPRESA
Lista TODAS las empresas de cartera y watchlist. 
- Si hay noticias: resúmelas con criterio inversor, destaca lo relevante
- Si no hay noticias: escribe simplemente "Sin noticias relevantes"
No omitas ninguna empresa.

## 3. TRANSACCIONES DE INSIDERS
Compras y ventas detectadas. Si hay Form 4 de la SEC u otras fuentes, analiza si es compra o venta y el importe si está disponible.
Si no hay datos: "Sin transacciones detectadas en las últimas 72h"

## 4. SEÑALES A VIGILAR
Riesgos, catalizadores próximos, niveles técnicos o fundamentales a tener en cuenta esta semana.

## 5. CALENDARIO DE RESULTADOS
Presentaciones de resultados de la semana actual y la próxima para las empresas monitorizadas.
Indica fecha si está disponible. Si no hay datos concretos, indica qué empresas reportan aproximadamente en este período.
---

Sé directo. Sin relleno. Sin frases vacías.

=== DATOS MACRO ===
{macro_texto}

=== NOTICIAS POR EMPRESA ===
{noticias_texto}

=== INSIDERS ===
{insiders_texto}

=== CALENDARIO RESULTADOS ===
{calendario_texto}
"""

    response = model.generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────
def enviar_email(informe):
    fecha = datetime.now().strftime("%d/%m/%Y")
    asunto = f"📊 Informe Diario de Cartera — {fecha}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_DESTINO

    parte_texto = MIMEText(informe, "plain", "utf-8")

    html_body = informe.replace("## ", "<h2>").replace("\n---\n", "<hr>").replace("\n", "<br>")
    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 860px; margin: auto; padding: 20px; color: #222;">
    <h1 style="color:#1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom:8px;">
        📊 Informe Diario de Cartera — {fecha}
    </h1>
    <div style="line-height:1.8;">{html_body}</div>
    <hr>
    <p style="color:#aaa; font-size:11px;">Generado automáticamente · Agente de Bolsa</p>
    </body></html>
    """
    parte_html = MIMEText(html, "html", "utf-8")

    msg.attach(parte_texto)
    msg.attach(parte_html)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASS)
        s.sendmail(GMAIL_USER, EMAIL_DESTINO, msg.as_string())

    print(f"✅ Informe enviado a {EMAIL_DESTINO}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print(f"🔍 Iniciando agente — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    print("🌍 Obteniendo datos macro...")
    macro = get_macro_data()
    print(f"   → {len(macro)} items macro")

    print("📰 Obteniendo noticias por empresa...")
    noticias = get_noticias_empresas()
    con_noticias = sum(1 for v in noticias.values() if v)
    print(f"   → {con_noticias}/{len(noticias)} empresas con noticias")

    print("📋 Consultando insiders...")
    insiders = get_todos_insiders()
    print(f"   → {len(insiders)} registros encontrados")

    print("📅 Buscando calendario de resultados...")
    calendario = get_calendario_resultados()
    print(f"   → {len(calendario)} eventos encontrados")

    print("🤖 Generando informe con Gemini...")
    informe = generar_informe(macro, noticias, insiders, calendario)

    print("📧 Enviando email...")
    enviar_email(informe)

    print("✅ Completado.")


if __name__ == "__main__":
    main()
