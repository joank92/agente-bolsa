import os
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
import yfinance as yf
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
    "BRK-B": "Berkshire Hathaway",
}

EMPRESAS_INTL = {
    "CSU.TO": ("Constellation Software", "CA"),
    "KRB.V":  ("Kraken Robotics", "CA"),
    "AIR.PA": ("Airbus", "FR"),
    "7974.T": ("Nintendo", "JP"),
    "DNP.WA": ("Dino Polska", "PL"),
}

CRYPTO = {"BTC": "Bitcoin"}

HEADERS_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ─────────────────────────────────────────────
# 1. MACRO
# ─────────────────────────────────────────────
def get_macro_data():
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
                resultado[nombre] = [
                    f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}"
                    for a in arts
                ] if arts else []
        except Exception:
            resultado[nombre] = []
    return resultado


# ─────────────────────────────────────────────
# 3. INSIDERS — OpenInsider
# ─────────────────────────────────────────────
def get_insiders_openinsider():
    resultados = []
    for ticker, nombre in EMPRESAS_USA.items():
        try:
            url = (
                f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh="
                f"&fd=3&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=3&xp=1&xs=1"
                f"&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999"
                f"&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h="
                f"&sortcol=0&cnt=10&action=1"
            )
            r = requests.get(url, headers=HEADERS_WEB, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            tabla = soup.find("table", {"class": "tinytable"})
            if not tabla:
                continue
            for fila in tabla.find_all("tr")[1:]:
                celdas = fila.find_all("td")
                if len(celdas) < 12:
                    continue
                tipo = celdas[6].get_text(strip=True)
                if tipo != "P":
                    continue
                fecha    = celdas[1].get_text(strip=True)
                insider  = celdas[4].get_text(strip=True)
                cargo    = celdas[5].get_text(strip=True)
                precio   = celdas[7].get_text(strip=True)
                cantidad = celdas[8].get_text(strip=True)
                valor    = celdas[9].get_text(strip=True)
                resultados.append(
                    f"🟢 COMPRA | {nombre} ({ticker}) | {fecha} | "
                    f"{insider} ({cargo}) | {cantidad} acciones a {precio} | "
                    f"Valor total: {valor}"
                )
        except Exception:
            continue
    return resultados if resultados else []


# ─────────────────────────────────────────────
# 5. EARNINGS PRÓXIMOS 15 DÍAS
# ─────────────────────────────────────────────
def get_earnings_proximos():
    resultados = []
    hoy = datetime.now().date()
    en_15_dias = hoy + timedelta(days=15)
    todos_tickers = list(EMPRESAS_USA.keys()) + list(EMPRESAS_INTL.keys())
    for ticker in todos_tickers:
        try:
            stock = yf.Ticker(ticker)
            cal = stock.calendar
            if cal is None:
                continue
            earnings_date = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if earnings_date is None:
                continue
            if isinstance(earnings_date, list):
                earnings_date = earnings_date[0] if earnings_date else None
            if earnings_date is None:
                continue
            if hasattr(earnings_date, 'date'):
                earnings_date = earnings_date.date()
            if hoy <= earnings_date <= en_15_dias:
                nombre = EMPRESAS_USA.get(ticker) or (EMPRESAS_INTL.get(ticker, (ticker,))[0])
                resultados.append(f"📅 {nombre} ({ticker}) — {earnings_date.strftime('%d/%m/%Y')}")
        except Exception:
            continue
    return resultados


# ─────────────────────────────────────────────
# 6. CAMBIOS DE ANALISTAS
# ─────────────────────────────────────────────
def get_cambios_analistas():
    resultados = []
    ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    todos_nombres = list(EMPRESAS_USA.values()) + [v[0] for v in EMPRESAS_INTL.values()]
    grupos = [todos_nombres[i:i+5] for i in range(0, len(todos_nombres), 5)]
    for grupo in grupos:
        nombres_query = " OR ".join([f'"{n}"' for n in grupo])
        q = f'({nombres_query}) AND ("price target" OR "target price" OR "upgrades" OR "downgrades" OR "raises target" OR "cuts target" OR "initiated" OR "outperform" OR "underperform")'
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={requests.utils.quote(q)}"
                f"&from={ayer}&language=en&sortBy=relevancy&pageSize=3&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    titulo = a.get('title', '')
                    fuente = a.get('source', {}).get('name', '')
                    desc   = a.get('description', '')
                    resultados.append(f"[{fuente}] {titulo} — {desc}")
        except Exception:
            continue
    return resultados


# ─────────────────────────────────────────────
# 7. DATOS FUNDAMENTALES
# ─────────────────────────────────────────────
def get_datos_fundamentales():
    resultados = []
    todos_tickers = {**EMPRESAS_USA, **{t: v[0] for t, v in EMPRESAS_INTL.items()}}
    for ticker, nombre in todos_tickers.items():
        try:
            info  = yf.Ticker(ticker).info
            precio        = info.get("regularMarketPrice") or info.get("currentPrice")
            pe_actual     = info.get("trailingPE")
            pe_forward    = info.get("forwardPE")
            precio_target = info.get("targetMeanPrice")
            moneda        = info.get("currency", "USD")
            if not precio:
                continue
            upside = ((precio_target - precio) / precio * 100) if precio_target else None
            linea = f"{nombre} ({ticker}) | {precio:.2f} {moneda}"
            if pe_actual:
                linea += f" | P/E {pe_actual:.1f}x"
            if pe_forward:
                linea += f" | Fwd {pe_forward:.1f}x"
            if precio_target:
                linea += f" | Target {precio_target:.2f}"
            if upside is not None:
                emoji = "🟢" if upside > 0 else "🔴"
                linea += f" | {emoji} {upside:+.1f}%"
            resultados.append((upside or 0, linea))
        except Exception:
            continue
    resultados.sort(key=lambda x: x[0], reverse=True)
    return [l for _, l in resultados]


# ─────────────────────────────────────────────
# GEMINI — GENERAR INFORME
# ─────────────────────────────────────────────
def generar_informe(macro, noticias_empresas, insiders, earnings, cambios_analistas, fundamentales):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
    fecha = datetime.now().strftime("%d/%m/%Y")

    noticias_texto = ""
    for empresa, arts in noticias_empresas.items():
        if arts:
            noticias_texto += f"\n### {empresa}\n"
            for a in arts:
                noticias_texto += f"  - {a}\n"
        else:
            noticias_texto += f"\n### {empresa}\n  - Sin noticias relevantes\n"

    macro_texto     = "\n".join(macro[:15]) if macro else "Sin datos macro."
    insiders_texto  = "\n".join(insiders) if insiders else ""
    earnings_texto  = "\n".join(earnings) if earnings else ""
    analistas_texto = "\n".join(cambios_analistas[:15]) if cambios_analistas else ""
    fund_texto      = "\n".join(fundamentales) if fundamentales else "Sin datos."

    prompt = f"""
Eres un analista de inversiones senior. Hoy es {fecha}.
Genera un informe diario en ESPAÑOL, conciso y orientado a decisiones de inversión.
Responde SOLO con HTML válido para email, sin markdown, sin bloques de código.

Cartera: Microsoft, Meta, Amazon, Alphabet, Constellation Software, Visa, Mastercard,
S&P Global, Moody's, Bitcoin, MercadoLibre, Booking Holdings, Copart, Dino Polska, Airbus, Nintendo,
Kraken Robotics, TransMedics, Berkshire Hathaway.
Watchlist: Waste Connections, McDonald's, American Express, AST SpaceMobile, Nvidia.

REGLAS DE FORMATO:
- Usa <h2> para títulos de sección
- Para cada empresa: <p><strong style="font-size:13px">Nombre Empresa</strong> <span style="font-size:11px">— descripción sin negrita</span></p>
- Texto normal: font-size 11px
- Sin bullets, usar párrafos
- Las secciones 3, 5 y 6 SOLO aparecen si hay datos reales, si no hay datos no escribas esa sección

ESTRUCTURA:
<h2>1. Resumen Macro</h2>
[tipos de interés, inflación, geopolítica, divisas, materias primas — implicaciones para la cartera]

<h2>2. Noticias por Empresa</h2>
[TODAS las empresas, nombre en negrita, descripción normal. Si no hay noticias: "Sin noticias relevantes"]

[Si hay insiders:]
<h2>3. Compras de Insiders</h2>
[empresa en negrita, detalle normal]

<h2>4. Señales a Vigilar</h2>
[breve, solo lo importante]

[Si hay earnings próximos:]
<h2>5. Earnings Próximos 15 Días</h2>
[empresa en negrita, fecha normal]

[Si hay cambios de analistas:]
<h2>6. Cambios de Analistas</h2>
[empresa en negrita, detalle del cambio normal]

<h2>7. Datos Fundamentales</h2>
[tabla con: empresa en negrita | precio | P/E | P/E Fwd | Target | Upside%, ordenado de mayor a menor upside]

=== MACRO ===
{macro_texto}

=== NOTICIAS ===
{noticias_texto}

=== INSIDERS ===
{insiders_texto if insiders_texto else "Sin compras."}

=== EARNINGS ===
{earnings_texto if earnings_texto else "Sin earnings próximos."}

=== CAMBIOS ANALISTAS ===
{analistas_texto if analistas_texto else "Sin cambios."}

=== FUNDAMENTALES ===
{fund_texto}
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

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 860px; margin: auto; padding: 20px; color: #222; font-size: 11px;">
    <h1 style="color:#1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom:8px; font-size:18px;">
        📊 Informe Diario de Cartera — {fecha}
    </h1>
    <div style="line-height:1.8;">
    {informe}
    </div>
    <hr>
    <p style="color:#aaa; font-size:10px;">Generado automáticamente · Agente de Bolsa</p>
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
    print("🌍 Macro...")
    macro = get_macro_data()
    print("📰 Noticias por empresa...")
    noticias = get_noticias_empresas()
    print("📋 Insiders (OpenInsider)...")
    insiders = get_insiders_openinsider()
    print("📅 Earnings próximos...")
    earnings = get_earnings_proximos()
    print("🎯 Cambios de analistas...")
    cambios = get_cambios_analistas()
    print("📊 Datos fundamentales (yfinance)...")
    fundamentales = get_datos_fundamentales()
    print("🤖 Generando informe con Gemini...")
    informe = generar_informe(macro, noticias, insiders, earnings, cambios, fundamentales)
    print("📧 Enviando email...")
    enviar_email(informe)
    print("✅ Completado.")


if __name__ == "__main__":
    main()
