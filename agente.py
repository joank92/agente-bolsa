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

# ─────────────────────────────────────────────
# CARTERA
# ─────────────────────────────────────────────
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
    "PNG.V":  ("Kraken Robotics", "CA"),
    "AIR.PA": ("Airbus", "FR"),
    "7974.T": ("Nintendo", "JP"),
    "DNP.WA": ("Dino Polska", "PL"),
}
CRYPTO = {"BTC": "Bitcoin"}

# ─────────────────────────────────────────────
# WATCHLIST (punto 8)
# ─────────────────────────────────────────────
WATCHLIST = {
    "SAP":   "SAP SE", "AMD":   "AMD", "ORCL":  "Oracle",
    "TSM":   "Taiwan Semiconductor", "BABA":  "Alibaba",
    "FTNT":  "Fortinet", "PDD":   "PDD Holdings", "FICO":  "Fair Isaac",
    "IBKR":  "Interactive Brokers", "UBER":  "Uber", "BX":    "Blackstone",
    "UNH":   "UnitedHealth", "ROP":   "Roper Technologies", "LIN":   "Linde",
    "BN":    "Brookfield", "TMO":   "Thermo Fisher", "LMT":   "Lockheed Martin",
    "RACE":  "Ferrari", "BLK":   "BlackRock", "AAPL":  "Apple",
    "NVO":   "Novo Nordisk ADR", "ADP":   "ADP", "ORLY":  "O'Reilly Automotive",
    "NFLX":  "Netflix", "COST":  "Costco", "ODFL":  "Old Dominion",
    "WMT":   "Walmart", "ADBE":  "Adobe", "NOW":   "ServiceNow",
    "KKR":   "KKR", "TDG":   "TransDigm", "MSCI":  "MSCI",
    "KNSL":  "Kinsale Capital", "FDS":   "FactSet", "YUMC":  "Yum China",
    "KOF":   "Coca-Cola FEMSA", "HEI":   "Heico", "DPZ":   "Domino's Pizza",
    "POOL":  "Pool Corp", "AZO":   "AutoZone", "DHR":   "Danaher",
    "WM":    "Waste Management",
    # Nuevos añadidos
    "DOW":     "Dow Inc",
    "NDAQ":    "Nasdaq",
    "JD":      "JD.com",
    "EXP":     "Eagle Materials",
    "PEP":     "PepsiCo",
    "AVGO":    "Broadcom",
    # Internacionales
    "RMS.PA":  "Hermès",
    "MC.PA":   "LVMH",
    "MONC.MI": "Moncler",
    "WKL.AS":  "Wolters Kluwer",
    "CNR.TO":  "Canadian National Railway",
    "CCH.L":   "Coca-Cola HBC",
    "ENX.PA":  "Euronext",
    "TOI.V":   "Topicus.com",
    "ATD.TO":  "Couche-Tard",
    "ASML":    "ASML Holding",
    "ITX.MC":  "Inditex",
    "LSEG.L":  "London Stock Exchange Group",
    "1211.HK": "BYD",
    "0700.HK": "Tencent",
    "TEQ.TO":  "Technion",
    "JDG.L":   "Judges Scientific",
    "NOVO-B.CO":"Novo Nordisk (Copenhague)",
    "BZU.MI":  "Buzzi",
    "OEM-B.ST":"OEM International",
    "ACP.WA":  "Asseco Poland",
    "LOUP.PA": "LDC",
}

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

# Dominios financieros de calidad
DOMINIOS_FIN = "bloomberg.com,reuters.com,ft.com,wsj.com,cnbc.com,seekingalpha.com,marketwatch.com,barrons.com,economist.com,investors.com,fool.com"

HEADERS_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Traducción de grados de analistas al español
TRADUCCION_GRADO = {
    "buy":          "Comprar",
    "strong buy":   "Comprar fuerte",
    "outperform":   "Sobresperar",
    "overweight":   "Sobreponderar",
    "hold":         "Mantener",
    "neutral":      "Neutral",
    "market perform":"Rendimiento de mercado",
    "underperform": "Infraponderar",
    "underweight":  "Infraponderar",
    "sell":         "Vender",
    "strong sell":  "Vender fuerte",
    "reduce":       "Reducir",
    "accumulate":   "Acumular",
    "equal-weight": "Peso neutral",
    "equal weight": "Peso neutral",
    "in-line":      "En línea",
}

TRADUCCION_ACCION = {
    "up":       "Subida de recomendación",
    "down":     "Bajada de recomendación",
    "main":     "Mantenida",
    "init":     "Iniciada cobertura",
    "reit":     "Reiterada",
    "upgr":     "Subida de recomendación",
    "downgr":   "Bajada de recomendación",
}


def traducir_grado(g):
    if not g:
        return ""
    g_low = str(g).lower().strip()
    return TRADUCCION_GRADO.get(g_low, g)


def traducir_accion(a):
    if not a:
        return ""
    a_low = str(a).lower().strip()
    return TRADUCCION_ACCION.get(a_low, a)


# ═════════════════════════════════════════════
# GOOGLE NEWS RSS
# ═════════════════════════════════════════════
def fetch_google_news(query, dias=3, max_items=6):
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
            desc_clean = BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)[:300]
            resultados.append({"titulo": titulo, "fuente": source, "fecha": pub, "url": link, "descripcion": desc_clean})
        return resultados
    except Exception:
        return []


# ═════════════════════════════════════════════
# 1. MACRO — solo fuentes financieras de calidad
# ═════════════════════════════════════════════
def get_macro_data():
    noticias = []
    queries_macro = [
        "Federal Reserve interest rates inflation",
        "ECB European Central Bank rates",
        "geopolitical risk trade tariffs",
        "US dollar oil gold commodities",
        "recession GDP growth outlook",
    ]
    desde = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    # NewsAPI con dominios financieros premium
    for q in queries_macro:
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={urllib.parse.quote(q)}"
                f"&domains={DOMINIOS_FIN}"
                f"&from={desde}&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    noticias.append(f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}")
        except Exception:
            continue
    # Google News como complemento
    for q in queries_macro:
        for n in fetch_google_news(q, dias=3, max_items=3):
            noticias.append(f"[{n['fuente']}] {n['titulo']} — {n['descripcion']}")
    return noticias


# ═════════════════════════════════════════════
# 2. NOTICIAS POR EMPRESA — fuentes financieras
# ═════════════════════════════════════════════
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
        # NewsAPI con dominios financieros
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={urllib.parse.quote(query)}"
                f"&domains={DOMINIOS_FIN}"
                f"&from={desde}&language=en&sortBy=publishedAt&pageSize=4&apiKey={NEWS_API_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    items.append(f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}")
        except Exception:
            pass
        # Google News finance — buscar con sufijo "stock" o "earnings" para sesgo financiero
        for n in fetch_google_news(f"{query} stock", dias=3, max_items=4):
            items.append(f"[{n['fuente']}] {n['titulo']} — {n['descripcion']}")
        # Deduplicar
        vistos, items_unicos = set(), []
        for it in items:
            clave = it[:80].lower()
            if clave not in vistos:
                vistos.add(clave)
                items_unicos.append(it)
        resultado[nombre] = items_unicos[:6]
    return resultado


# ═════════════════════════════════════════════
# 3. INSIDERS — yfinance SIN filtros agresivos
# ═════════════════════════════════════════════
def get_insiders():
    resultados = []
    hoy = datetime.now().date()
    hace_30 = hoy - timedelta(days=30)
    for ticker, nombre in EMPRESAS_USA.items():
        try:
            stock = yf.Ticker(ticker)
            trans = stock.insider_transactions
            if trans is None or len(trans) == 0:
                continue
            for _, row in trans.iterrows():
                fecha_raw = row.get("Start Date") if "Start Date" in row else row.get("Date")
                if fecha_raw is None:
                    continue
                try:
                    fecha_date = fecha_raw.date() if hasattr(fecha_raw, "date") else datetime.strptime(str(fecha_raw)[:10], "%Y-%m-%d").date()
                except Exception:
                    continue
                if fecha_date < hace_30 or fecha_date > hoy:
                    continue

                texto = (str(row.get("Text", "")) + " " + str(row.get("Transaction", ""))).lower()
                # Filtrar SOLO ventas claras — todo lo demás se muestra
                if "sale" in texto or "sell" in texto or "disposition" in texto:
                    continue

                insider  = row.get("Insider", "")
                cargo    = row.get("Position", "")
                shares   = row.get("Shares", "")
                valor    = row.get("Value", "")
                trans_type = row.get("Transaction", "") or row.get("Text", "")

                resultados.append(
                    f"🟢 {nombre} ({ticker}) | {fecha_date.strftime('%d/%m/%Y')} | "
                    f"{insider} ({cargo}) | {trans_type} | {shares} acciones | Valor: {valor}"
                )
        except Exception:
            continue
    return resultados if resultados else ["Sin transacciones de insiders detectadas en los últimos 30 días."]


# ═════════════════════════════════════════════
# 5. EARNINGS — múltiples métodos + scraping Yahoo
# ═════════════════════════════════════════════
def scrape_yahoo_earnings(ticker):
    """Intenta obtener fecha de earnings desde Yahoo Finance vía scraping."""
    try:
        url = f"https://finance.yahoo.com/calendar/earnings?symbol={ticker}"
        r = requests.get(url, headers=HEADERS_WEB, timeout=10)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        # Yahoo muestra las fechas en una tabla
        tabla = soup.find("table")
        if not tabla:
            return None
        filas = tabla.find_all("tr")
        for fila in filas[1:3]:  # primera fila de datos
            celdas = fila.find_all("td")
            if len(celdas) >= 3:
                fecha_text = celdas[2].get_text(strip=True)
                try:
                    # Formato típico: "Jul 23, 2026, 4:00 PM EDT"
                    fecha = datetime.strptime(fecha_text.split(",")[0] + "," + fecha_text.split(",")[1], "%b %d, %Y")
                    return fecha.date()
                except Exception:
                    continue
        return None
    except Exception:
        return None


def get_earnings_calendario():
    proximos = []
    reportados = []
    hoy = datetime.now().date()
    en_30 = hoy + timedelta(days=30)
    hace_7 = hoy - timedelta(days=7)

    tickers_cartera = list(EMPRESAS_USA.keys()) + list(EMPRESAS_INTL.keys())
    nombres_cartera = {**EMPRESAS_USA, **{t: v[0] for t, v in EMPRESAS_INTL.items()}}

    for ticker in tickers_cartera:
        nombre = nombres_cartera.get(ticker, ticker)
        fechas_encontradas = []

        try:
            stock = yf.Ticker(ticker)

            # Método 1: calendar
            try:
                cal = stock.calendar
                if cal and isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed:
                        if isinstance(ed, list):
                            for e in ed:
                                if hasattr(e, 'date'):
                                    fechas_encontradas.append(e.date())
                        elif hasattr(ed, 'date'):
                            fechas_encontradas.append(ed.date())
            except Exception:
                pass

            # Método 2: earnings_dates
            try:
                ed_df = stock.earnings_dates
                if ed_df is not None and len(ed_df) > 0:
                    for idx in ed_df.index:
                        if hasattr(idx, 'date'):
                            fechas_encontradas.append(idx.date())
            except Exception:
                pass

            # Método 3: scraping Yahoo si no hay nada
            if not fechas_encontradas:
                yahoo_date = scrape_yahoo_earnings(ticker)
                if yahoo_date:
                    fechas_encontradas.append(yahoo_date)
        except Exception:
            continue

        for f in fechas_encontradas:
            if hoy <= f <= en_30:
                linea = f"📅 {nombre} ({ticker}) — {f.strftime('%d/%m/%Y')}"
                if linea not in proximos:
                    proximos.append(linea)
            elif hace_7 <= f < hoy:
                linea = f"✅ {nombre} ({ticker}) — reportó el {f.strftime('%d/%m/%Y')}"
                if linea not in reportados:
                    reportados.append(linea)

    return proximos, reportados


# ═════════════════════════════════════════════
# 6. CAMBIOS DE ANALISTAS — TRADUCIDOS AL ESPAÑOL
# ═════════════════════════════════════════════
def get_cambios_analistas():
    resultados = []
    hoy = datetime.now().date()
    hace_15 = hoy - timedelta(days=15)

    tickers_cartera = list(EMPRESAS_USA.keys()) + list(EMPRESAS_INTL.keys())
    nombres_cartera = {**EMPRESAS_USA, **{t: v[0] for t, v in EMPRESAS_INTL.items()}}

    for ticker in tickers_cartera:
        try:
            stock = yf.Ticker(ticker)
            ud = stock.upgrades_downgrades
            if ud is None or len(ud) == 0:
                continue
            nombre = nombres_cartera.get(ticker, ticker)
            for idx, row in ud.iterrows():
                try:
                    fecha_date = idx.date() if hasattr(idx, 'date') else datetime.strptime(str(idx)[:10], "%Y-%m-%d").date()
                except Exception:
                    continue
                if fecha_date < hace_15 or fecha_date > hoy:
                    continue
                firma = row.get("Firm", "")
                desde_g = traducir_grado(row.get("FromGrade", ""))
                hasta_g = traducir_grado(row.get("ToGrade", ""))
                accion  = traducir_accion(row.get("Action", ""))

                if desde_g and hasta_g:
                    linea = f"📊 {nombre} ({ticker}) | {fecha_date.strftime('%d/%m/%Y')} | {firma} | {accion}: {desde_g} → {hasta_g}"
                elif hasta_g:
                    linea = f"📊 {nombre} ({ticker}) | {fecha_date.strftime('%d/%m/%Y')} | {firma} | {accion}: {hasta_g}"
                else:
                    linea = f"📊 {nombre} ({ticker}) | {fecha_date.strftime('%d/%m/%Y')} | {firma} | {accion}"
                resultados.append(linea)
        except Exception:
            continue

    # Complemento Google News (sólo si yfinance da poco)
    if len(resultados) < 5:
        nombres_lista = list(EMPRESAS_USA.values()) + [v[0] for v in EMPRESAS_INTL.values()]
        for nombre in nombres_lista[:10]:
            q = f"{nombre} price target upgrade"
            for n in fetch_google_news(q, dias=15, max_items=1):
                resultados.append(f"[{n['fuente']}] {n['titulo']} — {n['descripcion']}")

    # Deduplicar
    vistos, unicos = set(), []
    for r in resultados:
        clave = r[:80].lower()
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(r)
    return unicos[:30]


# ═════════════════════════════════════════════
# 7 y 8. FUNDAMENTALES
# ═════════════════════════════════════════════
def get_datos_fundamentales(tickers_dict):
    resultados = []
    for ticker, nombre in tickers_dict.items():
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


def get_fundamentales_cartera():
    tickers = {**EMPRESAS_USA, **{t: v[0] for t, v in EMPRESAS_INTL.items()}}
    return get_datos_fundamentales(tickers)


def get_fundamentales_watchlist():
    return get_datos_fundamentales(WATCHLIST)


# ═════════════════════════════════════════════
# GEMINI — INFORME
# ═════════════════════════════════════════════
def generar_informe(macro, noticias_empresas, insiders, earnings_proximos, earnings_reportados, cambios_analistas, fund_cartera, fund_watchlist):
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

    macro_texto       = "\n".join(macro[:30]) if macro else "Sin datos macro."
    insiders_texto    = "\n".join(insiders)
    earn_prox_texto   = "\n".join(earnings_proximos) if earnings_proximos else "Sin earnings en los próximos 30 días."
    earn_rep_texto    = "\n".join(earnings_reportados) if earnings_reportados else "Ninguna empresa ha reportado en los últimos 7 días."
    analistas_texto   = "\n".join(cambios_analistas) if cambios_analistas else "Sin cambios detectados."
    fund_cart_texto   = "\n".join(fund_cartera) if fund_cartera else "Sin datos."
    fund_watch_texto  = "\n".join(fund_watchlist) if fund_watchlist else "Sin datos."

    prompt = f"""
Eres un analista de inversiones senior. Hoy es {fecha}.
Genera un informe diario en ESPAÑOL, redactado de forma fluida y útil, orientado a la toma de decisiones.

Cartera: Microsoft, Meta, Amazon, Alphabet, Constellation Software, Visa, Mastercard,
S&P Global, Moody's, Bitcoin, MercadoLibre, Booking Holdings, Copart, Dino Polska, Airbus, Nintendo,
Kraken Robotics, TransMedics, Berkshire Hathaway.
Cartera ampliada: Waste Connections, McDonald's, American Express, AST SpaceMobile, Nvidia.

REGLAS:
- Usa los artículos como fuente principal
- Si no hay artículo específico puedes apoyarte en contexto sectorial conocido para 1 línea útil
- NO inventes hechos concretos no presentes en los datos
- Cada empresa debe tener al menos un comentario útil

Genera EXACTAMENTE estas 8 secciones:

## 1. RESUMEN MACRO
Análisis sustancioso de tipos de interés (Fed/BCE), inflación, geopolítica, divisas, materias primas.
Cada subtema con su nombre en negrita y análisis concreto. Termina con implicación para la cartera.

## 2. NOTICIAS POR EMPRESA
Lista TODAS las empresas. Formato: **Nombre:** comentario.
Resume con criterio inversor. Si no hay artículos pero conoces contexto: aporta una línea breve.

## 3. TRANSACCIONES DE INSIDERS (últimos 30 días)
Lista las transacciones detectadas tal como vienen, agrupadas por empresa.
Marca con 🟢 las compras claras y describe el contexto si es posible.
Si la lista dice "Sin transacciones": refléjalo.

## 4. SEÑALES A VIGILAR
Identifica riesgos y catalizadores reales: earnings próximos, cambios de analistas relevantes, factores macro.
NUNCA escribas "no hay nada que vigilar".

## 5. CALENDARIO DE RESULTADOS
**Próximos 30 días:** lista con fechas.
**Reportados últimos 7 días:** lista con comentario si hay info en las noticias.

## 6. CAMBIOS DE ANALISTAS (últimos 15 días)
Lista los cambios. Los grados YA están traducidos al español (Comprar, Mantener, Vender, Sobresperar, etc).
Indica banco, empresa, acción y cambio.

## 7. DATOS FUNDAMENTALES — CARTERA
Reproduce el bloque FUNDAMENTALES CARTERA tal cual, uno por línea. Ya ordenados por upside.

## 8. DATOS FUNDAMENTALES — WATCHLIST
Reproduce el bloque FUNDAMENTALES WATCHLIST tal cual, uno por línea. Ya ordenados por upside.
NO comentes estas empresas, solo los datos.

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

=== FUNDAMENTALES CARTERA ===
{fund_cart_texto}

=== FUNDAMENTALES WATCHLIST ===
{fund_watch_texto}
"""
    response = model.generate_content(prompt)
    return response.text


# ═════════════════════════════════════════════
# EMAIL
# ═════════════════════════════════════════════
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


# ═════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════
def main():
    print(f"🔍 Iniciando agente — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("🌍 Macro (fuentes financieras + Google News)...")
    macro = get_macro_data()
    print(f"   → {len(macro)} items")
    print("📰 Noticias por empresa...")
    noticias = get_noticias_empresas()
    con_n = sum(1 for v in noticias.values() if v)
    total_n = sum(len(v) for v in noticias.values())
    print(f"   → {con_n}/{len(noticias)} empresas ({total_n} artículos)")
    print("📋 Insiders 30 días...")
    insiders = get_insiders()
    print(f"   → {len(insiders)} registros")
    print("📅 Earnings (calendar + earnings_dates + scraping Yahoo)...")
    earnings_prox, earnings_rep = get_earnings_calendario()
    print(f"   → {len(earnings_prox)} próximos / {len(earnings_rep)} reportados")
    print("🎯 Cambios de analistas (yfinance)...")
    cambios = get_cambios_analistas()
    print(f"   → {len(cambios)} cambios")
    print("📊 Fundamentales cartera...")
    fund_cartera = get_fundamentales_cartera()
    print(f"   → {len(fund_cartera)} empresas")
    print("📈 Fundamentales watchlist...")
    fund_watchlist = get_fundamentales_watchlist()
    print(f"   → {len(fund_watchlist)} empresas")
    print("🤖 Generando informe con Gemini...")
    informe = generar_informe(macro, noticias, insiders, earnings_prox, earnings_rep, cambios, fund_cartera, fund_watchlist)
    print("📧 Enviando email...")
    enviar_email(informe)
    print("✅ Completado.")


if __name__ == "__main__":
    main()
