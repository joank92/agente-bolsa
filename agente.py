import os
import re
import smtplib
import requests
import urllib.parse
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
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
    "MELI": "Mercado Libre", "BKNG": "Booking Holdings", "CPRT": "Copart",
    "TMDX": "TransMedics",
    "UBER": "Uber", "NFLX": "Netflix", "MBGL": "Mobility Global",
}
EMPRESAS_INTL = {
    "CSU.TO":  ("Constellation Software", "CA"),
    "PNG.V":   ("Kraken Robotics", "CA"),
    "TOI.V":   ("Topicus.com", "CA"),
    "AIR.PA":  ("Airbus", "FR"),
    "7974.T":  ("Nintendo", "JP"),
    "DNP.WA":  ("Dino Polska", "PL"),
}

# WATCHLIST del usuario (cartera + selección adicional)
WATCHLIST_USUARIO = {
    # — Cartera (replicada para que aparezca también en watchlist) —
    "MSFT":   "Microsoft",
    "META":   "Meta",
    "AMZN":   "Amazon",
    "GOOGL":  "Alphabet",
    "CSU.TO": "Constellation Software",
    "TOI.V":  "Topicus.com",
    "MA":     "Mastercard",
    "V":      "Visa",
    "SPGI":   "S&P Global",
    "MCO":    "Moody's",
    "MELI":   "Mercado Libre",
    "BKNG":   "Booking Holdings",
    "CPRT":   "Copart",
    "DNP.WA": "Dino Polska",
    "AIR.PA": "Airbus",
    "7974.T": "Nintendo",
    "PNG.V":  "Kraken Robotics",
    "TMDX":   "TransMedics",
    "UBER":   "Uber",
    "NFLX":   "Netflix",
    "MBGL":   "Mobility Global",
    # — Watchlist específica —
    "AXP":    "American Express",
    "ASTS":   "AST SpaceMobile",
    "NVDA":   "Nvidia",
    "MCD":    "McDonald's",
    "WCN":    "Waste Connections",
    "ROL":    "Rollins",
    "MSCI":   "MSCI",
    "BRK-B":  "Berkshire Hathaway",
    "BABA":   "Alibaba",
    "0700.HK":"Tencent",
    "TDG":    "TransDigm",
    "SAP":    "SAP",
    "FICO":   "Fair Isaac",
    "TSM":    "Taiwan Semi",
    "AMD":    "AMD",
    "ASML":   "ASML",
    "LIN":    "Linde",
    "DPZ":    "Domino's Pizza",
    "AVGO":   "Broadcom",
    "AAPL":   "Apple",
    "ORLY":   "O'Reilly Auto",
    "AZO":    "AutoZone",
    "KO":     "Coca-Cola",
    "PG":     "Procter & Gamble",
    "JNJ":    "Johnson & Johnson",
    "CNI":    "Canadian National Rail",
    "WM":     "Waste Management",
    "NSRGY":  "Nestlé",
    "PLD":    "Prologis",
    "WALMEX.MX":"Walmex",
    "KNSL":   "Kinsale Capital",
    "WKL.AS": "Wolters Kluwer",
    "ACP.WA": "Asseco Poland",
    "NOW":    "ServiceNow",
    "YUMC":   "Yum China",
    "RMS.PA": "Hermès",
}

WATCHLIST = WATCHLIST_USUARIO
TICKERS_WIDE_MOAT = set(WATCHLIST_USUARIO.keys())

DOMINIOS_FIN = "bloomberg.com,reuters.com,ft.com,wsj.com,cnbc.com,seekingalpha.com,marketwatch.com,barrons.com,economist.com,investors.com,fool.com"
HEADERS_WEB  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

TRADUCCION_GRADO = {
    "buy":"Comprar","strong buy":"Comprar fuerte","outperform":"Sobresperar",
    "overweight":"Sobreponderar","hold":"Mantener","neutral":"Neutral",
    "market perform":"Rend. mercado","underperform":"Infraponderar",
    "underweight":"Infraponderar","sell":"Vender","strong sell":"Vender fuerte",
    "reduce":"Reducir","accumulate":"Acumular","equal-weight":"Peso neutral",
    "equal weight":"Peso neutral","in-line":"En línea","perform":"Rend. neutral",
}
TRADUCCION_ACCION = {
    "up":"⬆️ Subida","down":"⬇️ Bajada","main":"Mantenida",
    "init":"Inicio cobertura","reit":"Reiterada",
}


def traducir_grado(g):
    if not g: return ""
    return TRADUCCION_GRADO.get(str(g).lower().strip(), g)


def traducir_accion(a):
    if not a: return ""
    return TRADUCCION_ACCION.get(str(a).lower().strip(), a)


# ═════════════════════════════════════════════
# GOOGLE NEWS RSS
# ═════════════════════════════════════════════
def fetch_google_news(query, dias=3, max_items=6):
    try:
        q = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={q}+when:{dias}d&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(url, headers=HEADERS_WEB, timeout=10)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")[:max_items]
        out = []
        for it in items:
            titulo  = it.find("title").get_text(strip=True) if it.find("title") else ""
            source  = it.find("source").get_text(strip=True) if it.find("source") else ""
            desc    = it.find("description").get_text(strip=True) if it.find("description") else ""
            desc_clean = BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)[:300]
            out.append({"titulo": titulo, "fuente": source, "descripcion": desc_clean})
        return out
    except Exception:
        return []


# ═════════════════════════════════════════════
# 1. MACRO
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
    for q in queries_macro:
        try:
            url = (f"https://newsapi.org/v2/everything?q={urllib.parse.quote(q)}"
                   f"&domains={DOMINIOS_FIN}&from={desde}&language=en"
                   f"&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}")
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    noticias.append(f"[{a.get('source',{}).get('name','')}] {a.get('title','')} — {a.get('description','')}")
        except Exception:
            continue
    for q in queries_macro:
        for n in fetch_google_news(q, dias=3, max_items=3):
            noticias.append(f"[{n['fuente']}] {n['titulo']} — {n['descripcion']}")
    return noticias


# ═════════════════════════════════════════════
# DESCARGA EN PARALELO DE DATOS YFINANCE
# ═════════════════════════════════════════════
def descargar_datos_ticker(ticker_nombre):
    ticker, nombre = ticker_nombre
    resultado = {"ticker": ticker, "nombre": nombre, "info": None, "upgrades": None, "error": None}
    try:
        stock = yf.Ticker(ticker)
        resultado["info"] = stock.info
        try:
            resultado["upgrades"] = stock.upgrades_downgrades
        except Exception:
            resultado["upgrades"] = None
    except Exception as e:
        resultado["error"] = str(e)
    return resultado


def descargar_todos_los_datos(tickers_cartera, tickers_watchlist):
    lista = []
    for t, n in tickers_cartera.items():
        lista.append((t, n))
    for t, n in tickers_watchlist.items():
        if t not in tickers_cartera:
            lista.append((t, n))

    print(f"   Descargando {len(lista)} tickers en paralelo...")
    datos = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        for resultado in executor.map(descargar_datos_ticker, lista):
            datos[resultado["ticker"]] = resultado
    return datos


# ═════════════════════════════════════════════
# 3. CAMBIOS DE ANALISTAS (15 días)
# ═════════════════════════════════════════════
def procesar_cambios_analistas(datos_descargados):
    cambios_por_ticker = {}
    hoy = datetime.now().date()
    hace_15 = hoy - timedelta(days=15)

    for ticker, d in datos_descargados.items():
        ud = d.get("upgrades")
        if ud is None or len(ud) == 0:
            continue
        nombre = d["nombre"]
        cambios = []
        for idx, row in ud.iterrows():
            try:
                fecha_date = idx.date() if hasattr(idx, 'date') else datetime.strptime(str(idx)[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            if fecha_date < hace_15 or fecha_date > hoy:
                continue
            firma     = row.get("Firm", "")
            desde_g   = traducir_grado(row.get("FromGrade", ""))
            hasta_g   = traducir_grado(row.get("ToGrade", ""))
            accion_raw = row.get("Action", "")
            accion    = traducir_accion(accion_raw)
            cambios.append({
                "fecha": fecha_date, "firma": firma,
                "desde": desde_g, "hasta": hasta_g, "accion": accion,
                "accion_raw": accion_raw,
                "nombre": nombre, "ticker": ticker
            })
        if cambios:
            cambios_por_ticker[ticker] = cambios
    return cambios_por_ticker


def emoji_cambio(accion_raw):
    a = str(accion_raw).lower().strip()
    if "up" in a or "upgr" in a: return "⬆️"
    if "down" in a or "downgr" in a: return "⬇️"
    if "main" in a or "reit" in a: return "➖"
    if "init" in a: return "🆕"
    return ""


def formatear_cambios_para_seccion(cambios_por_ticker, datos_descargados, solo_cartera_tickers=None):
    lineas = []
    tickers_validos = []
    for ticker in cambios_por_ticker.keys():
        if solo_cartera_tickers and ticker not in solo_cartera_tickers:
            continue
        tickers_validos.append(ticker)
    tickers_validos.sort(key=lambda t: cambios_por_ticker[t][0]["nombre"])

    for ticker in tickers_validos:
        cambios = cambios_por_ticker[ticker]
        nombre = cambios[0]["nombre"]
        target_consenso = ""
        if ticker in datos_descargados and datos_descargados[ticker].get("info"):
            tgt = datos_descargados[ticker]["info"].get("targetMeanPrice")
            if tgt:
                try:
                    target_consenso = f" — Target consenso: {float(tgt):.2f}"
                except Exception:
                    pass

        lineas.append(f"\n### {nombre} ({ticker}){target_consenso}")

        cambios_ord = sorted(cambios, key=lambda c: c["fecha"], reverse=True)
        for c in cambios_ord:
            flecha = emoji_cambio(c.get("accion_raw", c.get("accion", "")))
            cambio_txt = ""
            if c["desde"] and c["hasta"]:
                cambio_txt = f"{c['desde']} → {c['hasta']}"
            elif c["hasta"]:
                cambio_txt = c["hasta"]

            linea = f"  {flecha} {c['fecha'].strftime('%d/%m/%Y')} | {c['firma']}"
            if cambio_txt:
                linea += f" | {cambio_txt}"
            lineas.append(linea)

    return lineas if lineas else ["Sin cambios de analistas en los últimos 15 días."]


# ═════════════════════════════════════════════
# 4 y 5. FUNDAMENTALES
# ═════════════════════════════════════════════
def procesar_fundamentales(datos_descargados, tickers_filtro):
    resultados = []
    for ticker, d in datos_descargados.items():
        if ticker not in tickers_filtro:
            continue
        info = d.get("info")
        if not info:
            continue
        try:
            precio        = info.get("regularMarketPrice") or info.get("currentPrice")
            pe_actual     = info.get("trailingPE")
            pe_forward    = info.get("forwardPE")
            precio_target = info.get("targetMeanPrice")
            moneda        = info.get("currency", "USD")
            rec_mean      = info.get("recommendationMean")
            num_analistas = info.get("numberOfAnalystOpinions") or 0

            if not precio:
                continue

            upside = ((precio_target - precio) / precio * 100) if precio_target else None

            resultados.append({
                "ticker": ticker, "nombre": d["nombre"],
                "precio": precio, "pe_actual": pe_actual, "pe_forward": pe_forward,
                "target": precio_target, "moneda": moneda, "upside": upside,
                "rec_mean": rec_mean, "num_analistas": num_analistas
            })
        except Exception:
            continue
    return resultados


def _f(v):
    if v is None: return None
    try: return float(v)
    except (TypeError, ValueError): return None


def formatear_linea_fundamental(d):
    precio    = _f(d.get('precio'))
    pe_actual = _f(d.get('pe_actual'))
    pe_fwd    = _f(d.get('pe_forward'))
    target    = _f(d.get('target'))
    upside    = _f(d.get('upside'))
    moneda    = d.get('moneda', 'USD')

    linea = f"**{d['nombre']} ({d['ticker']})** | Precio: {precio:.2f} {moneda}" if precio else f"**{d['nombre']} ({d['ticker']})**"
    if pe_actual: linea += f" | P/E: {pe_actual:.1f}x"
    if pe_fwd: linea += f" | P/E Fwd: {pe_fwd:.1f}x"
    if target: linea += f" | Target: {target:.2f}"
    if upside is not None:
        emoji = "🟢" if upside > 0 else "🔴"
        linea += f" | Upside: {emoji} {upside:+.1f}%"
    return linea


def formatear_seccion_fundamentales(datos, top_n=None):
    ordenados = sorted(datos, key=lambda x: _f(x.get('upside')) if _f(x.get('upside')) is not None else -999, reverse=True)
    if top_n:
        ordenados = ordenados[:top_n]
    return [formatear_linea_fundamental(d) for d in ordenados]


# ═════════════════════════════════════════════
# 6. TOP 10 OPORTUNIDADES
# ═════════════════════════════════════════════
def get_top_oportunidades(datos_cartera, datos_watchlist, cambios_por_ticker, top=10, min_upside=25):
    vistos = set()
    todos = []
    for d in datos_cartera + datos_watchlist:
        if d['ticker'] in vistos:
            continue
        vistos.add(d['ticker'])
        todos.append(d)

    elegibles = []
    for d in todos:
        if d['ticker'] not in TICKERS_WIDE_MOAT:
            continue
        upside = _f(d.get('upside'))
        if upside is None or upside < min_upside:
            continue
        rec_mean = _f(d.get('rec_mean'))
        num_an   = _f(d.get('num_analistas', 0)) or 0
        if rec_mean is None or rec_mean > 2.5:
            continue
        if num_an < 3:
            continue
        elegibles.append(d)

    elegibles.sort(key=lambda x: _f(x.get('upside')) or 0, reverse=True)
    top_n = elegibles[:top]

    salida = []
    for i, d in enumerate(top_n, 1):
        precio = _f(d.get('precio')) or 0
        target = _f(d.get('target')) or 0
        upside = _f(d.get('upside')) or 0
        rm     = _f(d.get('rec_mean'))
        moneda = d.get('moneda', 'USD')

        rec_texto = ""
        if rm is not None:
            if rm <= 1.5: rec_label = "Comprar fuerte"
            elif rm <= 2.0: rec_label = "Comprar"
            elif rm <= 2.5: rec_label = "Comprar/Mantener"
            else: rec_label = "Mantener"
            rec_texto = f" | Consenso: {rec_label} ({rm:.2f}/5, {d.get('num_analistas',0)} analistas)"

        linea = f"{i}. **{d['nombre']} ({d['ticker']})** | Precio: {precio:.2f} {moneda} | "
        linea += f"Target: {target:.2f} | Upside: 🟢 {upside:+.1f}%{rec_texto}"

        cambios = cambios_por_ticker.get(d['ticker'], [])
        if cambios:
            cambio_reciente = max(cambios, key=lambda c: c['fecha'])
            detalle = f"\n   → 📢 Movimiento reciente: {cambio_reciente['firma']} ({cambio_reciente['fecha'].strftime('%d/%m/%Y')})"
            if cambio_reciente['accion']:
                detalle += f" — {cambio_reciente['accion']}"
            if cambio_reciente['hasta']:
                detalle += f" → {cambio_reciente['hasta']}"
            linea += detalle
        salida.append(linea)

    return salida if salida else [f"Ninguna empresa Wide Moat cumple los criterios actuales (upside ≥{min_upside}%, consenso favorable, ≥3 analistas)."]


# ═════════════════════════════════════════════
# GEMINI — INFORME
# ═════════════════════════════════════════════
def generar_informe(macro, cambios_analistas, fund_cartera_fmt, fund_watchlist_fmt, top_oportunidades):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
    fecha = datetime.now().strftime("%d/%m/%Y")

    macro_texto       = "\n".join(macro[:30]) if macro else "Sin datos macro."
    analistas_texto   = "\n".join(cambios_analistas)
    fund_cart_texto   = "\n".join(fund_cartera_fmt) if fund_cartera_fmt else "Sin datos."
    fund_watch_texto  = "\n".join(fund_watchlist_fmt) if fund_watchlist_fmt else "Sin datos."
    top_texto         = "\n".join(top_oportunidades)

    prompt = f"""
Eres un analista de inversiones senior. Hoy es {fecha}.
Genera un informe diario en ESPAÑOL.

Cartera: Microsoft, Meta, Amazon, Alphabet, Constellation Software, Topicus, Visa, Mastercard,
S&P Global, Moody's, Mercado Libre, Booking Holdings, Copart, Dino Polska, Airbus, Nintendo,
Kraken Robotics, TransMedics, Uber, Netflix, Mobility Global.

Genera EXACTAMENTE estas 6 secciones:

## 1. RESUMEN MACRO
Análisis sustancioso de tipos (Fed/BCE), inflación, geopolítica, divisas y materias primas.
Cada subtema con su nombre en negrita y análisis concreto. Termina con implicaciones para la cartera.

## 2. SEÑALES A VIGILAR
Riesgos y catalizadores reales basados en macro y contexto de la cartera. NUNCA "no hay nada".

## 3. CAMBIOS DE ANALISTAS (últimos 15 días)
Reproduce la lista tal cual, manteniendo el agrupamiento por empresa (cada empresa con su cabecera ### y luego sus cambios debajo).
NO reordenes, NO mezcles empresas. Los grados YA están en español.

## 4. DATOS FUNDAMENTALES — CARTERA
Reproduce el bloque tal cual.

## 5. DATOS FUNDAMENTALES — WATCHLIST (TOP 50 por upside)
Reproduce el bloque tal cual.

## 6. TOP 10 OPORTUNIDADES WIDE MOAT (≥25% upside + consenso favorable)
Reproduce el bloque tal cual, conservando numeración 1-10 y movimientos recientes.

Sé directo. Sin relleno.

=== DATOS MACRO ===
{macro_texto}

=== CAMBIOS ANALISTAS (15 días) ===
{analistas_texto}

=== FUNDAMENTALES CARTERA ===
{fund_cart_texto}

=== FUNDAMENTALES WATCHLIST (TOP 50) ===
{fund_watch_texto}

=== TOP OPORTUNIDADES ===
{top_texto}
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

    print("🌍 Macro...")
    macro = get_macro_data()
    print(f"   → {len(macro)} items")

    tickers_cartera = {**EMPRESAS_USA, **{t: v[0] for t, v in EMPRESAS_INTL.items()}}

    print("⏳ Descargando datos de yfinance...")
    datos = descargar_todos_los_datos(tickers_cartera, WATCHLIST)
    print(f"   → {len(datos)} tickers procesados")

    print("🎯 Procesando cambios de analistas...")
    cambios_dict = procesar_cambios_analistas(datos)
    cambios_fmt  = formatear_cambios_para_seccion(cambios_dict, datos, solo_cartera_tickers=set(tickers_cartera.keys()))
    print(f"   → {sum(len(v) for v in cambios_dict.values())} cambios totales")

    print("📊 Procesando fundamentales cartera...")
    datos_cartera = procesar_fundamentales(datos, set(tickers_cartera.keys()))
    fund_cartera_fmt = formatear_seccion_fundamentales(datos_cartera)
    print(f"   → {len(datos_cartera)} empresas")

    print("📈 Procesando fundamentales watchlist...")
    datos_watchlist = procesar_fundamentales(datos, set(WATCHLIST.keys()))
    fund_watchlist_fmt = formatear_seccion_fundamentales(datos_watchlist, top_n=50)
    print(f"   → {len(datos_watchlist)} empresas procesadas (top 50 mostradas)")

    print("🏆 Top 10 oportunidades Wide Moat (≥25% upside)...")
    top = get_top_oportunidades(datos_cartera, datos_watchlist, cambios_dict, top=10, min_upside=25)
    print(f"   → {len(top)} oportunidades identificadas")

    print("🤖 Generando informe con Gemini...")
    informe = generar_informe(macro, cambios_fmt, fund_cartera_fmt, fund_watchlist_fmt, top)

    print("📧 Enviando email...")
    enviar_email(informe)

    print("✅ Completado.")


if __name__ == "__main__":
    main()
