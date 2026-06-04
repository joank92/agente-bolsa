import os
import re
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
    return resultados if resultados else ["Sin compras de insiders detectadas en las últimas 72h."]


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
    return resultados if resultados else ["Sin earnings confirmados en los próximos 15 días."]


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
        q = f'({nombres_query}) AND ("price target" OR "target price" OR "upgrades" OR "downgrades" OR "raises target" OR "cuts target" OR "outperform" OR "underperform")'
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={requests.utils.quote(q)}"
                f"&from={ayer}&language=en&sortBy=relevancy&pageSize=3&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    resultados.append(
                        f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}"
                    )
        except Exception:
            continue
    return resultados


# ─────────────────────────────────────────────
# 7. DATOS FUNDAMENTALES — ORDENADOS POR UPSIDE
# ─────────────────────────────────────────────
def get_datos_fundamentales():
    resultados = []
    todos_tickers = {**EMPRESAS_USA, **{t: v[0] for t, v in EMPRESAS_INTL.items()}}
    for ticker, nombre in todos_tickers.items():
        try:
            info          = yf.Ticker(ticker).info
            precio        = info.get("regularMarketPrice") or info.get("currentPrice")
            pe_actual     = info.get("trailingPE")
            pe_forward    = info.get("forwardPE")
            precio_target = info.get("targetMeanPrice")
            moneda        = info.get("currency", "USD")
            if not precio:
                continue
            upside = ((precio_target - precio) / precio * 100) if precio_target else None
            linea = f"{nombre} ({ticker}) | Precio: {precio:.2f} {moneda}"
            if pe_actual:
                linea += f" | P/E: {pe_actual:.1f}x"
            if pe_forward:
                linea += f" | P/E Fwd: {pe_forward:.1f}x"
            if precio_target:
                linea += f" | Target: {precio_target:.2f}"
            if upside is not None:
                emoji = "🟢" if upside > 0 else "🔴"
                linea += f" | Upside: {emoji} {upside:+.1f}%"
            resultados.append((upside if upside is not None else -999, linea))
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
            noticias_texto += f"\n### {empresa}\n  - Sin noticias\n"

    macro_texto      = "\n".join(macro[:15]) if macro else "Sin datos macro disponibles."
    insiders_texto   = "\n".join(insiders)
    earnings_texto   = "\n".join(earnings)
    analistas_texto  = "\n".join(cambios_analistas[:15]) if cambios_analistas else "Sin cambios detectados."
    fund_texto       = "\n".join(fundamentales) if fundamentales else "Sin datos disponibles."

    # Mismo prompt que la v3 que funcionaba bien, con secciones 5,6,7 añadidas
    prompt = f"""
Eres un analista de inversiones senior. Hoy es {fecha}.
Genera un informe diario de seguimiento de cartera en ESPAÑOL, estructurado, conciso y orientado a la toma de decisiones.

El inversor tiene en cartera: Microsoft, Meta, Amazon, Alphabet, Constellation Software, Visa, Mastercard,
S&P Global, Moody's, Bitcoin, MercadoLibre, Booking Holdings, Copart, Dino Polska, Airbus, Nintendo,
Kraken Robotics, TransMedics, Berkshire Hathaway.
También monitoriza: Waste Connections, McDonald's, American Express, AST SpaceMobile, Nvidia.

Genera el informe con EXACTAMENTE estas 7 secciones, usando los nombres de sección como aparecen:

## 1. RESUMEN MACRO
Tipos de interés, inflación, geopolítica, divisas, materias primas. Qué implica para la cartera.
Usa los datos proporcionados. Sé directo y analítico. Aporta análisis, no solo titulares.

## 2. NOTICIAS POR EMPRESA
Lista TODAS las empresas de cartera y watchlist.
- Si hay noticias: resúmelas con criterio inversor, destaca lo relevante con detalle
- Si no hay noticias: escribe simplemente "Sin noticias relevantes"
No omitas ninguna empresa. Para cada empresa pon su nombre como subtítulo en formato:
**Nombre de la empresa**: descripción

## 3. COMPRAS DE INSIDERS
Compras reales de directivos detectadas. Indica empresa, directivo, cargo, cantidad, precio y valor total.
Si no hay datos: "Sin transacciones detectadas en las últimas 72h"

## 4. SEÑALES A VIGILAR
Riesgos, catalizadores próximos o niveles fundamentales a tener en cuenta esta semana.

## 5. EARNINGS PRÓXIMOS 15 DÍAS
Solo empresas de la lista con earnings confirmados en los próximos 15 días. Indica fecha exacta.

## 6. CAMBIOS DE ANALISTAS
Solo si hay cambios de precio objetivo o recomendación en las últimas 24h.
Si no hay nada: "Sin cambios de analistas detectados."

## 7. DATOS FUNDAMENTALES
Reproduce los datos tal cual están en la sección FUNDAMENTALES, uno por línea, sin modificar el formato.
YA ESTÁN ORDENADOS de mayor a menor upside potencial.

Sé directo. Sin relleno. Sin frases vacías.

=== DATOS MACRO ===
{macro_texto}

=== NOTICIAS POR EMPRESA ===
{noticias_texto}

=== INSIDERS ===
{insiders_texto}

=== EARNINGS ===
{earnings_texto}

=== CAMBIOS ANALISTAS ===
{analistas_texto}

=== FUNDAMENTALES ===
{fund_texto}
"""
    response = model.generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────
# EMAIL — formato compacto con negritas
# ─────────────────────────────────────────────
def markdown_a_html(texto):
    """Conversor sencillo de markdown a HTML para email."""
    html = texto
    # Cabeceras
    html = re.sub(r'^## (.+)$', r'<h2 style="font-size:14px; color:#1a1a2e; margin-top:18px; margin-bottom:6px;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3 style="font-size:12px; color:#333; margin-top:10px; margin-bottom:4px;">\1</h3>', html, flags=re.MULTILINE)
    # Negritas markdown **xxx**
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    # Saltos de línea
    html = html.replace('\n', '<br>')
    return html


def enviar_email(informe):
    fecha = datetime.now().strftime("%d/%m/%Y")
    asunto = f"📊 Informe Diario de Cartera — {fecha}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_DESTINO

    parte_texto = MIMEText(informe, "plain", "utf-8")
    informe_html = markdown_a_html(informe)

    html = f"""
    <html>
    <body style="font-family: Arial, Helvetica, sans-serif; max-width: 820px; margin: auto; padding: 16px; color: #222; font-size: 11px; line-height: 1.55;">
    <h1 style="color:#1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom:6px; font-size:16px; margin-bottom:14px;">
        📊 Informe Diario de Cartera — {fecha}
    </h1>
    <div>
    {informe_html}
    </div>
    <hr style="margin-top:20px;">
    <p style="color:#aaa; font-size:9px;">Generado automáticamente · Agente de Bolsa</p>
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
    print("📅 Earnings próximos 15 días...")
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
