import os
import re
import smtplib
import requests
import urllib.parse
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

QUERIES_EMPRESA = {
    "Microsoft":              "Microsoft MSFT",
    "Meta":                   "Meta Platforms",
    "Amazon":                 "Amazon AMZN",
    "Alphabet":               "Alphabet Google",
    "Visa":                   "Visa Inc payments",
    "Mastercard":             "Mastercard payments",
    "S&P Global":             "S&P Global SPGI",
    "Moody's":                "Moody's MCO",
    "MercadoLibre":           "MercadoLibre",
    "Booking Holdings":       "Booking Holdings",
    "Copart":                 "Copart auctions",
    "TransMedics":            "TransMedics organ",
    "Waste Connections":      "Waste Connections",
    "McDonald's":             "McDonald's MCD",
    "American Express":       "American Express AXP",
    "AST SpaceMobile":        "AST SpaceMobile",
    "Nvidia":                 "Nvidia chips",
    "Berkshire Hathaway":     "Berkshire Hathaway Buffett",
    "Constellation Software": "Constellation Software CSU",
    "Kraken Robotics":        "Kraken Robotics",
    "Airbus":                 "Airbus aerospace",
    "Nintendo":               "Nintendo Switch",
    "Dino Polska":            "Dino Polska",
    "Bitcoin":                "Bitcoin BTC",
}

HEADERS_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ─────────────────────────────────────────────
# GOOGLE NEWS RSS — nuevo motor de noticias gratuito
# ─────────────────────────────────────────────
def fetch_google_news(query, dias=3, max_items=6):
    """
    Descarga noticias de Google News RSS para una query.
    Devuelve lista de dicts con titulo, fuente, fecha, url, descripcion.
    """
    try:
        q_codificada = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={q_codificada}+when:{dias}d&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(url, headers=HEADERS_WEB, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")[:max_items]
        resultados = []
        for it in items:
            titulo  = it.find("title").get_text(strip=True) if it.find("title") else ""
            link    = it.find("link").get_text(strip=True)  if it.find("link") else ""
            pub     = it.find("pubDate").get_text(strip=True) if it.find("pubDate") else ""
            source  = it.find("source").get_text(strip=True) if it.find("source") else ""
            desc    = it.find("description").get_text(strip=True) if it.find("description") else ""
            # Limpiar HTML de descripcion
            desc_clean = BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)[:300]
            resultados.append({
                "titulo": titulo, "fuente": source, "fecha": pub,
                "url": link, "descripcion": desc_clean
            })
        return resultados
    except Exception:
        return []


# ─────────────────────────────────────────────
# 1. MACRO — combinando NewsAPI + Google News
# ─────────────────────────────────────────────
def get_macro_data():
    noticias = []
    queries_macro = [
        "Federal Reserve interest rates inflation",
        "ECB European Central Bank rates",
        "geopolitical risk trade tariffs",
        "US dollar oil gold commodities",
        "recession GDP growth outlook",
    ]
    # NewsAPI
    desde = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    for q in queries_macro:
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={urllib.parse.quote(q)}"
                f"&from={desde}&language=en&sortBy=publishedAt&pageSize=4&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    noticias.append(f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}")
        except Exception:
            continue
    # Google News RSS — añade volumen
    for q in queries_macro:
        for n in fetch_google_news(q, dias=3, max_items=4):
            noticias.append(f"[{n['fuente']}] {n['titulo']} — {n['descripcion']}")
    return noticias


# ─────────────────────────────────────────────
# 2. NOTICIAS POR EMPRESA — NewsAPI + Google News
# ─────────────────────────────────────────────
def get_noticias_empresas():
    resultado = {}
    desde = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    todas = (
        list(EMPRESAS_USA.values()) +
        [v[0] for v in EMPRESAS_INTL.values()] +
        list(CRYPTO.values())
    )

    for nombre in todas:
        items = []
        query = QUERIES_EMPRESA.get(nombre, nombre)

        # 1) NewsAPI
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={urllib.parse.quote(query)}"
                f"&from={desde}&language=en&sortBy=publishedAt&pageSize=4&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    items.append(f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}")
        except Exception:
            pass

        # 2) Google News RSS — sin límite de plan
        google = fetch_google_news(query, dias=3, max_items=5)
        for n in google:
            items.append(f"[{n['fuente']}] {n['titulo']} — {n['descripcion']}")

        # Deduplicar titulares parecidos
        vistos = set()
        items_unicos = []
        for it in items:
            clave = it[:80].lower()
            if clave not in vistos:
                vistos.add(clave)
                items_unicos.append(it)

        resultado[nombre] = items_unicos[:8]  # tope por empresa
    return resultado


# ─────────────────────────────────────────────
# 3. INSIDERS — OpenInsider — ÚLTIMOS 30 DÍAS
# ─────────────────────────────────────────────
def get_insiders_openinsider():
    resultados = []
    for ticker, nombre in EMPRESAS_USA.items():
        try:
            # daysago=30 → últimos 30 días
            url = (
                f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh="
                f"&fd=30&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=30&xp=1&xs=1"
                f"&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999"
                f"&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h="
                f"&sortcol=0&cnt=20&action=1"
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
    return resultados if resultados else ["Sin compras de insiders detectadas en los últimos 30 días."]


# ─────────────────────────────────────────────
# 5. EARNINGS — Próximos 30 días + Reportados últimos 7 días
# ─────────────────────────────────────────────
def get_earnings_calendario():
    proximos = []
    reportados = []
    hoy = datetime.now().date()
    en_30_dias = hoy + timedelta(days=30)
    hace_7_dias = hoy - timedelta(days=7)

    todos_tickers = list(EMPRESAS_USA.keys()) + list(EMPRESAS_INTL.keys())
    for ticker in todos_tickers:
        try:
            stock = yf.Ticker(ticker)
            cal = stock.calendar
            if cal is None or not isinstance(cal, dict):
                continue
            earnings_date = cal.get("Earnings Date")
            if earnings_date is None:
                continue
            if isinstance(earnings_date, list):
                earnings_date = earnings_date[0] if earnings_date else None
            if earnings_date is None:
                continue
            if hasattr(earnings_date, 'date'):
                earnings_date = earnings_date.date()

            nombre = EMPRESAS_USA.get(ticker) or (EMPRESAS_INTL.get(ticker, (ticker,))[0])
            if hoy <= earnings_date <= en_30_dias:
                proximos.append(f"📅 {nombre} ({ticker}) — {earnings_date.strftime('%d/%m/%Y')}")
            elif hace_7_dias <= earnings_date < hoy:
                reportados.append(f"✅ {nombre} ({ticker}) — reportó el {earnings_date.strftime('%d/%m/%Y')}")
        except Exception:
            continue

    return proximos, reportados


# ─────────────────────────────────────────────
# 6. CAMBIOS DE ANALISTAS — ÚLTIMOS 15 DÍAS
# ─────────────────────────────────────────────
def get_cambios_analistas():
    resultados = []
    desde = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
    todos_nombres = list(EMPRESAS_USA.values()) + [v[0] for v in EMPRESAS_INTL.values()]

    # 1) NewsAPI
    grupos = [todos_nombres[i:i+5] for i in range(0, len(todos_nombres), 5)]
    for grupo in grupos:
        nombres_query = " OR ".join([f'"{n}"' for n in grupo])
        q = f'({nombres_query}) AND ("price target" OR "raises target" OR "cuts target" OR "upgrades" OR "downgrades" OR "outperform" OR "underperform" OR "initiated" OR "reiterate")'
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={urllib.parse.quote(q)}"
                f"&from={desde}&language=en&sortBy=relevancy&pageSize=5&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    resultados.append(
                        f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}"
                    )
        except Exception:
            continue

    # 2) Google News RSS — busca por cada empresa
    for nombre in todos_nombres:
        q_analista = f'{nombre} price target OR upgrade OR downgrade'
        for n in fetch_google_news(q_analista, dias=15, max_items=2):
            resultados.append(f"[{n['fuente']}] {n['titulo']} — {n['descripcion']}")

    # Deduplicar
    vistos, unicos = set(), []
    for r in resultados:
        clave = r[:80].lower()
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(r)
    return unicos[:25]


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
            linea = f"**{nombre} ({ticker})** | Precio: {precio:.2f} {moneda}"
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
def generar_informe(macro, noticias_empresas, insiders, earnings_proximos, earnings_reportados, cambios_analistas, fundamentales):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
    fecha = datetime.now().strftime("%d/%m/%Y")

    noticias_texto = ""
    for empresa, arts in noticias_empresas.items():
        noticias_texto += f"\n### {empresa}\n"
        if arts:
            for a in arts:
                noticias_texto += f"  - {a}\n"
        else:
            noticias_texto += "  - (sin artículos recientes)\n"

    macro_texto       = "\n".join(macro[:30]) if macro else "Sin datos macro disponibles."
    insiders_texto    = "\n".join(insiders)
    earn_prox_texto   = "\n".join(earnings_proximos) if earnings_proximos else "Sin earnings en los próximos 30 días."
    earn_rep_texto    = "\n".join(earnings_reportados) if earnings_reportados else "Ninguna empresa de la lista ha reportado en los últimos 7 días."
    analistas_texto   = "\n".join(cambios_analistas) if cambios_analistas else "Sin cambios detectados."
    fund_texto        = "\n".join(fundamentales) if fundamentales else "Sin datos."

    prompt = f"""
Eres un analista de inversiones senior con amplio conocimiento del mercado. Hoy es {fecha}.
Genera un informe diario de seguimiento de cartera en ESPAÑOL, redactado de forma fluida, útil y orientado a la toma de decisiones.

El inversor tiene en cartera: Microsoft, Meta, Amazon, Alphabet, Constellation Software, Visa, Mastercard,
S&P Global, Moody's, Bitcoin, MercadoLibre, Booking Holdings, Copart, Dino Polska, Airbus, Nintendo,
Kraken Robotics, TransMedics, Berkshire Hathaway.
También monitoriza: Waste Connections, McDonald's, American Express, AST SpaceMobile, Nvidia.

REGLAS DE REDACCIÓN:
- Usa los artículos proporcionados como fuente principal y resúmelos con criterio inversor
- Si en los artículos no hay noticias específicas de una empresa concreta hoy, puedes apoyarte en tu conocimiento del contexto sectorial o de la situación reciente de la empresa para aportar un comentario útil de una línea
- NO inventes hechos concretos (cifras específicas, contratos, fechas, declaraciones literales) que no estén en los datos
- Sí puedes hablar del contexto general que ya conoces: ciclo del sector, posicionamiento competitivo, dinámica reciente del valor, catalizadores conocidos
- El objetivo es que CADA empresa tenga al menos un comentario útil cada día, evitando repetir "Sin noticias relevantes"

Genera 7 secciones:

## 1. RESUMEN MACRO
Análisis sustancioso de tipos de interés (Fed/BCE), inflación, geopolítica, divisas y materias primas.
Cada subtema con su nombre en negrita y un análisis concreto basado tanto en los artículos como en el contexto macro general.
Ejemplo: **Tipos de interés:** ...
Termina con una línea sobre implicaciones para la cartera.

## 2. NOTICIAS POR EMPRESA
Lista TODAS las empresas. Formato: **Nombre:** comentario.
- Si hay artículos: resume con criterio inversor.
- Si no hay artículos relevantes pero sí contexto reciente conocido del valor o sector: aporta un comentario breve (1 línea) sobre la situación o catalizador pendiente.
- Solo en casos donde realmente no haya nada útil que decir: "Sin novedades destacadas."
Integra varias noticias de una misma empresa en un párrafo coherente.

## 3. COMPRAS DE INSIDERS (últimos 30 días)
Lista todas las compras detectadas. Empresa en negrita.
Si no hay: "Sin compras de insiders en los últimos 30 días."

## 4. SEÑALES A VIGILAR
Riesgos y catalizadores importantes. Breve.

## 5. CALENDARIO DE RESULTADOS
Subsección A: **Próximos 30 días** — empresas con earnings programados, con fecha.
Subsección B: **Reportados en los últimos 7 días** — empresas que ya presentaron. Si tienes información en las noticias sobre sus resultados (EPS, ingresos, guidance), añádela.

## 6. CAMBIOS DE ANALISTAS (últimos 15 días)
Cambios de precio objetivo o recomendación. Indica analista/banco, empresa, cambio, nuevo target.
Si no hay nada: "Sin cambios relevantes en los últimos 15 días."

## 7. DATOS FUNDAMENTALES
Reproduce los datos del bloque FUNDAMENTALES tal cual, uno por línea. Ya están ordenados por upside.

Sé directo. Sin relleno.

=== DATOS MACRO ===
{macro_texto}

=== NOTICIAS POR EMPRESA ===
{noticias_texto}

=== INSIDERS (30 días) ===
{insiders_texto}

=== EARNINGS PRÓXIMOS 30 DÍAS ===
{earn_prox_texto}

=== EARNINGS REPORTADOS ÚLTIMOS 7 DÍAS ===
{earn_rep_texto}

=== CAMBIOS ANALISTAS (15 días) ===
{analistas_texto}

=== FUNDAMENTALES ===
{fund_texto}
"""
    response = model.generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────
def markdown_a_html(texto):
    html = texto
    html = re.sub(r'^## (.+)$', r'<h2 style="font-size:14px; color:#1a1a2e; margin-top:18px; margin-bottom:6px;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3 style="font-size:12px; color:#333; margin-top:10px; margin-bottom:4px;">\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
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
    <div>{informe_html}</div>
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
    print("🌍 Macro (NewsAPI + Google News)...")
    macro = get_macro_data()
    print(f"   → {len(macro)} items")
    print("📰 Noticias por empresa (NewsAPI + Google News)...")
    noticias = get_noticias_empresas()
    con_n = sum(1 for v in noticias.values() if v)
    total_n = sum(len(v) for v in noticias.values())
    print(f"   → {con_n}/{len(noticias)} empresas con noticias ({total_n} artículos)")
    print("📋 Insiders últimos 30 días...")
    insiders = get_insiders_openinsider()
    print(f"   → {len(insiders)} registros")
    print("📅 Earnings...")
    earnings_prox, earnings_rep = get_earnings_calendario()
    print(f"   → {len(earnings_prox)} próximos / {len(earnings_rep)} reportados")
    print("🎯 Cambios de analistas (últimos 15 días)...")
    cambios = get_cambios_analistas()
    print(f"   → {len(cambios)} cambios")
    print("📊 Datos fundamentales...")
    fundamentales = get_datos_fundamentales()
    print(f"   → {len(fundamentales)} empresas")
    print("🤖 Generando informe con Gemini...")
    informe = generar_informe(macro, noticias, insiders, earnings_prox, earnings_rep, cambios, fundamentales)
    print("📧 Enviando email...")
    enviar_email(informe)
    print("✅ Completado.")


if __name__ == "__main__":
    main()
