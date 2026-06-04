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
    "MELI": "MercadoLibre", "BKNG": "Booking Holdings", "CPRT": "Copart",
    "TMDX": "TransMedics",
}
EMPRESAS_INTL = {
    "CSU.TO":  ("Constellation Software", "CA"),
    "PNG.V":   ("Kraken Robotics", "CA"),
    "AIR.PA":  ("Airbus", "FR"),
    "7974.T":  ("Nintendo", "JP"),
    "DNP.WA":  ("Dino Polska", "PL"),
}

# ─────────────────────────────────────────────
# WATCHLIST WIDE MOAT (Morningstar)
# ─────────────────────────────────────────────
WATCHLIST_WIDE_MOAT = {
    "AOS": "A.O. Smith",
    "ABLZF": "ABB",
    "ABBV": "AbbVie",
    "ACN": "Accenture",
    "ADBE": "Adobe",
    "AVIFY": "Advanced Inforvice PCL",
    "A": "Agilent Technologies",
    "AIQUF": "Air Liquide",
    "APD": "Air Products and Chemicals",
    "ABNB": "Airbnb",
    "AIPUY": "Airports Of Thailand",
    "ALFVF": "Alfa Laval AB",
    "BABAF": "Alibaba",
    "ALLE": "Allegion",
    "ALEGF": "Allegro.EU",
    "MO": "Altria",
    "AMZN": "Amazon.com",
    "ABEV": "Ambev",
    "AME": "AMETEK",
    "AMGN": "Amgen",
    "APH": "Amphenol",
    "ADI": "Analog Devices",
    "BUDFF": "Anheuser-Busch InBev/NV",
    "ANSS": "Ansys",
    "ANZGF": "ANZ",
    "AAPL": "Apple",
    "AMAT": "Applied Materials",
    "EMBVF": "Arca ContinentalB de CV",
    "ANET": "Arista Networks",
    "ARM": "ARM",
    "ASMXF": "ASM International",
    "ASMLF": "ASML",
    "ASAZY": "Assa Abloy AB",
    "AZNCF": "AstraZeneca",
    "ASXFF": "ASX",
    "ATLCY": "Atlas Copco AB",
    "ACKDF": "Auckland International Airport",
    "ATDRF": "Auto Trader",
    "ADSK": "Autodesk",
    "ADP": "Automatic Data Processing",
    "AZO": "AutoZone",
    "BAESF": "BAE Systems",
    "BAIDF": "Baidu",
    "BK": "Bank of New York Mellon",
    "BAC": "Bank of America",
    "BESVF": "BEmiconductor Industries",
    "BRBR": "BellRing Brands",
    "BIO.B": "Bio-Rad Laboratories",
    "BLK": "BlackRock",
    "BA": "Boeing",
    "BMBLF": "Brambles",
    "BMY": "Bristol-Myers Squibb",
    "BTAFF": "British American Tobacco",
    "AVGO": "Broadcom",
    "BR": "Broadridge Financial Solutions",
    "BAM": "Brookfield Asset Management",
    "BF.A": "Brown-Forman",
    "DOOO": "BRP Shs Subord.Voting",
    "BVRDF": "Bureau Veritas",
    "CHRW": "C.H. Robinson Worldwide",
    "CDNS": "Cadence Design Systems",
    "CNI": "Canadian National Railway",
    "CP": "Canadian Pacific Kansas City",
    "CKHGY": "Capitec Bank",
    "CSL": "Carlisle Companies",
    "CAT": "Caterpillar",
    "CBOE": "Cboe Global Markets",
    "SCHW": "Charles Schwab",
    "CHE": "Chemed",
    "LNG": "Cheniere Energy",
    "CQP": "Cheniere Energy Partners LP",
    "CMG": "Chipotle Mexican Grill",
    "CTAS": "Cintas",
    "CSCO": "Cisco Systems",
    "CCKRF": "Clicks",
    "CLX": "Clorox",
    "CME": "CME",
    "KO": "Coca-Cola",
    "COCSF": "Coca-Cola FemsaB de CVries L",
    "CHEOF": "Cochlear",
    "CL": "Colgate-Palmolive",
    "CLPBF": "Coloplast AS",
    "CBAUF": "Commonwealth Bank of Australia",
    "CFRHF": "Compagnie Financiere Richemont",
    "CMSQF": "Computershare",
    "STZ": "Constellation Brands",
    "CTVA": "Corteva",
    "CSGP": "CoStar",
    "COST": "Costco Wholesale",
    "CSX": "CSX",
    "DAIUF": "Daifuku",
    "DHR": "Danaher",
    "DUAVF": "Dassault Aviation",
    "DASTF": "Dassault Systemes",
    "DE": "Deere &",
    "DETRF": "Deterra Royalties",
    "DBOEF": "Deutsche Boerse",
    "DGEAF": "Diageo",
    "DLMAF": "Dollarama",
    "DPZ": "Domino's Pizza",
    "DSMFF": "DSM Firmenich",
    "ETN": "Eaton",
    "ECL": "Ecolab",
    "EDNMY": "Edenred",
    "EKTAY": "Elekta AB",
    "LLY": "Eli Lilly and",
    "EMR": "Emerson Electric",
    "EMSHF": "Ems-Chemie",
    "EDVGF": "Endeavour",
    "EPD": "Enterprise Products Partners LP",
    "EPOAY": "Epiroc AB (Representing",
    "EPIPF": "Epiroc AB Share B",
    "EFX": "Equifax",
    "ESLOF": "Essilorluxottica",
    "ETSY": "Etsy",
    "EXLS": "ExlService",
    "EXPD": "Expeditors International of Washington",
    "EXPGF": "Experian",
    "FICO": "Fair Isaac",
    "FANUF": "Fanuc",
    "FRCOY": "Fast Retailing",
    "FAST": "Fastenal",
    "RACE": "Ferrari",
    "FER": "Ferrovial",
    "FNCHF": "FINEOS Chess Depository Interest",
    "FTNT": "Fortinet",
    "FNV": "Franco-Nevada",
    "IT": "Gartner",
    "GE": "GE Aerospace",
    "GEHC": "GE HealthCare Technologies",
    "GEAGF": "GEA",
    "GBERF": "Geberit",
    "GD": "General Dynamics",
    "GILD": "Gilead Sciences",
    "GVDBF": "Givaudan",
    "GGG": "Graco",
    "GLAXF": "GSK",
    "GWRE": "Guidewire Software",
    "HLNCF": "Haleon",
    "HSYDF": "Harmonicive Systems",
    "HINKF": "Heineken",
    "HESAF": "Hermes International",
    "HLT": "Hilton Worldwide",
    "HON": "Honeywell International",
    "HKXCF": "Hong Kong Exchanges and Clearing",
    "HSHZY": "Hoshizaki",
    "HLI": "Houlihan Lokey",
    "HWM": "Howmet Aerospace",
    "HOCPF": "Hoya",
    "HUBB": "Hubbell",
    "HII": "Huntington Ingalls Industries",
    "IEX": "IDEX",
    "IDXX": "IDEXX Laboratories",
    "ITW": "Illinois Tool Works",
    "IMBBF": "Imperial Brands",
    "IDEXY": "Industria De Diseno Textil",
    "IBKR": "Interactive Brokers",
    "ICE": "Intercontinental Exchange",
    "ICHGF": "InterContinental Hotels",
    "IFF": "International Flavors & Fragrances",
    "IKTSF": "Intertek",
    "INTU": "Intuit",
    "ISRG": "Intuitive Surgical",
    "IVTBF": "Investment AB Latour",
    "ITT": "ITT",
    "JKHY": "Jack Henry & Associates",
    "JHX": "James Hardie Industries",
    "OSCUF": "Japan Exchange",
    "JAPAF": "Japan Tobacco",
    "JDCMF": "JD.com",
    "JNJ": "Johnson & Johnson",
    "JPM": "JPMorgan Chase &",
    "JBARF": "Julius Baer Gruppe",
    "KAOCF": "Kao",
    "KVUE": "Kenvue",
    "KEYS": "Keysight Technologies",
    "KIKOF": "Kikkoman",
    "KLAC": "KLA",
    "KNYJY": "KONE Oyj",
    "NSKFF": "Kongsberg Gruppen ASA",
    "RYLPF": "Koninklijke Philips",
    "KUBTF": "Kubota",
    "LRLCF": "L'Oreal",
    "LRCX": "Lam Research",
    "LSTR": "Landstar System",
    "LTOUF": "Larsen & Toubro",
    "LFCBY": "Lifco AB",
    "LIN": "Linde",
    "LMT": "Lockheed Martin",
    "LDNXF": "London Stock Exchange",
    "LOW": "Lowe's Companies",
    "LVMHF": "Lvmh Moet Hennessy Louis Vuitton",
    "YAHOF": "LY",
    "MANH": "Manhattan Associates",
    "MKTX": "MarketAxess",
    "MAR": "Marriott International",
    "MAS": "Masco",
    "MKC": "McCormick &",
    "MLSPF": "Melrose Industries",
    "MRK": "Merck &",
    "MCHP": "Microchip Technology",
    "MDLZ": "Mondelez International",
    "MPWR": "Monolithic Power Systems",
    "MSI": "Motorola Solutions",
    "MSCI": "MSCI",
    "MTUAF": "MTU Aero Engines",
    "MRAAF": "Murata Manufacturing",
    "NCTKF": "Nabtesco",
    "NAUBF": "National Australia Bank",
    "NSRGF": "Nestle",
    "NYT": "New York Times",
    "NXGPF": "Next",
    "NKE": "Nike",
    "NURAF": "Nomura Research Institute",
    "NDSN": "Nordson",
    "NSC": "Norfolk Southern",
    "NTRS": "Northern Trust",
    "NOC": "Northrop Grumman",
    "NVSEF": "Novartis",
    "NONOF": "Novo Nordisk AS",
    "NVZMY": "Novonesis (Novozymes) B",
    "NXPI": "NXPmiconductors",
    "ORLY": "O'Reilly Automotive",
    "OBIIF": "OBIC",
    "OMRNF": "OMRON",
    "ORCL": "Oracle",
    "OCLCF": "Oracle Japan",
    "OLCLF": "Oriental Land",
    "OTIS": "Otis Worldwide",
    "PANW": "Palo Alto Networks",
    "PAYX": "Paychex",
    "PEP": "PepsiCo",
    "PDRDF": "Pernod Ricard",
    "PFE": "Pfizer",
    "PM": "Philip Morris International",
    "PII": "Polaris",
    "PMRTY": "Pop Mart International",
    "PTAUY": "Port of Tauranga",
    "PG": "Procter & Gamble",
    "PBCRF": "PT Bank Central Asia Tbk",
    "RPGRF": "REA",
    "RBGPF": "Reckitt Benckiser",
    "RICFY": "Recordati SpA",
    "RLXXF": "RELX",
    "RSG": "Republicrvices",
    "RNMBF": "Rheinmetall",
    "RHHBF": "Roche",
    "ROK": "Rockwell Automation",
    "ROL": "Rollins",
    "ROP": "Roper Technologies",
    "ROST": "Ross Stores",
    "RY": "Royal Bank of Canada",
    "RGLD": "Royal Gold",
    "RTX": "RTX",
    "SAABY": "Saab AB",
    "SAFRF": "Safran",
    "CRM": "Salesforce",
    "SDVKF": "Sandvik AB",
    "SNYNF": "Sanofi",
    "SAP": "SAP",
    "SARTF": "Sartorius",
    "SDMHF": "Sartorius Stedim Biotech",
    "SHLRF": "Schindler",
    "SBGSF": "Schneider Electric",
    "NOW": "ServiceNow",
    "SGSOF": "SGS",
    "SHW": "Sherwin-Williams",
    "SHMDF": "Shimano",
    "SHOP": "Shopify",
    "SMAWF": "Siemens",
    "SMMNY": "Siemens Healthineers",
    "SPXCF": "Singapore Exchange",
    "SMGKF": "Smiths",
    "SNEJF": "Sony",
    "SCCO": "Southern Copper",
    "SPXSF": "Spirax",
    "SBUX": "Starbucks",
    "STT": "State Street",
    "SYK": "Stryker",
    "SYIEF": "Symrise",
    "SNPS": "Synopsys",
    "SYY": "Sysco",
    "TSM": "Taiwanmiconductor Manufacturing",
    "THNOF": "Technology One",
    "TCTZF": "Tencent",
    "TER": "Teradyne",
    "TXN": "Texas Instruments",
    "TXRH": "Texas Roadhouse",
    "THLEF": "Thales",
    "CPB": "The Campbell's",
    "DSGX": "The Descartes Systems",
    "EL": "The Estee Lauder Companies",
    "HSY": "The Hershey",
    "HD": "The Home Depot",
    "LTRCF": "The Lottery",
    "TD": "The Toronto-Dominion Bank",
    "DIS": "The Walt Disney",
    "TMO": "Thermo Fisher Scientific",
    "TJX": "TJX Companies",
    "TOELF": "Tokyo Electron",
    "TSCO": "Tractor Supply",
    "TW": "Tradeweb Markets",
    "TDG": "TransDigm",
    "TRU": "TransUnion",
    "TRAUF": "Transurban",
    "TYL": "Tyler Technologies",
    "USB": "U.S. Bancorp",
    "UNCHF": "Unicharm",
    "UNLYF": "Unilever",
    "UNP": "Union Pacific",
    "UPS": "United Parcelrvice",
    "UMGNF": "Universal Music",
    "VACNY": "VAT",
    "VEEV": "Veeva Systems",
    "VLTO": "Veralto",
    "OEZVY": "Verbund",
    "VRSN": "VeriSign",
    "VRSK": "Verisk Analytics",
    "GWW": "W.W. Grainger",
    "WMT": "Walmart",
    "WRTBF": "Wartsila",
    "WM": "Waste Management",
    "WAT": "Waters",
    "WEGZY": "Weg",
    "WFC": "Wells Fargo &",
    "WFAFF": "Wesfarmers",
    "WST": "West Pharmaceuticalrvices",
    "WEBNF": "Westpac Banking",
    "WPM": "Wheaton Precious Metals",
    "WOLTF": "Wolters Kluwer",
    "WOLWF": "Woolworths",
    "WDAY": "Workday",
    "YASKF": "YASKAWA Electric",
    "YUM": "Yum Brands",
    "YUMC": "Yum China",
    "ZBH": "Zimmer Biomet",
    "ZTS": "Zoetis",
    "SATLF": "Zozo",
}

# Sobrescribir WATCHLIST con la lista específica del usuario
# Punto 5: solo estas empresas (cartera + watchlist seleccionada)
WATCHLIST_USUARIO = {
    # — Cartera (replicada para que aparezca también en watchlist) —
    "MSFT":   "Microsoft",
    "META":   "Meta",
    "AMZN":   "Amazon",
    "GOOGL":  "Alphabet",
    "CSU.TO": "Constellation Software",
    "MA":     "Mastercard",
    "V":      "Visa",
    "SPGI":   "S&P Global",
    "MCO":    "Moody's",
    "MELI":   "MercadoLibre",
    "BKNG":   "Booking Holdings",
    "CPRT":   "Copart",
    "DNP.WA": "Dino Polska",
    "AIR.PA": "Airbus",
    "7974.T": "Nintendo",
    "PNG.V":  "Kraken Robotics",
    "TMDX":   "TransMedics",
    # — Watchlist específica —
    "AXP":    "American Express",
    "ASTS":   "AST SpaceMobile",
    "NVDA":   "Nvidia",
    "MCD":    "McDonald's",
    "WCN":    "Waste Connections",
    "ROL":    "Rollins",
    "MSCI":   "MSCI",
    "BRK-B":  "Berkshire Hathaway",
    "TOI.V":  "Topicus.com",
    "BABA":   "Alibaba",
    "0700.HK":"Tencent",
    "TDG":    "TransDigm",
    "NFLX":   "Netflix",
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
    "UBER":   "Uber",
}

# Reemplazar la WATCHLIST (eliminar la lista enorme de Wide Moat)
WATCHLIST = WATCHLIST_USUARIO

# Set de tickers para el punto 6 (todas las del usuario son candidatas)
TICKERS_WIDE_MOAT = set(WATCHLIST_USUARIO.keys())

# Combinar con la watchlist anterior del usuario (incluir RACE, KKR, etc. que también son wide moat)
WATCHLIST = WATCHLIST_WIDE_MOAT

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
    """Descarga info + upgrades_downgrades de un ticker. Devuelve dict."""
    ticker, nombre = ticker_nombre
    resultado = {
        "ticker": ticker, "nombre": nombre,
        "info": None, "upgrades": None, "error": None
    }
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
    """Descarga datos en paralelo para todos los tickers."""
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
# 3. CAMBIOS DE ANALISTAS (30 días)
# ═════════════════════════════════════════════
def procesar_cambios_analistas(datos_descargados):
    cambios_por_ticker = {}
    hoy = datetime.now().date()
    hace_30 = hoy - timedelta(days=30)

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
            if fecha_date < hace_30 or fecha_date > hoy:
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
    """Devuelve flechita según la acción original."""
    a = str(accion_raw).lower().strip()
    if "up" in a or "upgr" in a:
        return "⬆️"
    if "down" in a or "downgr" in a:
        return "⬇️"
    if "main" in a or "reit" in a:
        return "➖"
    if "init" in a:
        return "🆕"
    return ""


def formatear_cambios_para_seccion(cambios_por_ticker, datos_descargados, solo_cartera_tickers=None):
    """Formato mejorado: incluye flechita + precio objetivo de consenso de la empresa."""
    lineas = []
    # Ordenar por fecha más reciente primero
    todos_cambios = []
    for ticker, cambios in cambios_por_ticker.items():
        if solo_cartera_tickers and ticker not in solo_cartera_tickers:
            continue
        for c in cambios:
            todos_cambios.append((c, ticker))
    todos_cambios.sort(key=lambda x: x[0]["fecha"], reverse=True)

    for c, ticker in todos_cambios:
        flecha = emoji_cambio(c.get("accion_raw", c.get("accion", "")))
        # Precio objetivo de consenso (de yfinance.info)
        target_consenso = ""
        if ticker in datos_descargados and datos_descargados[ticker].get("info"):
            tgt = datos_descargados[ticker]["info"].get("targetMeanPrice")
            if tgt:
                target_consenso = f" | Target consenso: {tgt:.2f}"

        cambio_txt = ""
        if c["desde"] and c["hasta"]:
            cambio_txt = f"{c['desde']} → {c['hasta']}"
        elif c["hasta"]:
            cambio_txt = c["hasta"]

        linea = f"{flecha} **{c['nombre']} ({ticker})** | {c['fecha'].strftime('%d/%m/%Y')} | {c['firma']}"
        if cambio_txt:
            linea += f" | {cambio_txt}"
        linea += target_consenso
        lineas.append(linea)

    return lineas if lineas else ["Sin cambios de analistas en los últimos 30 días."]


# ═════════════════════════════════════════════
# 4 y 5. FUNDAMENTALES
# ═════════════════════════════════════════════
def procesar_fundamentales(datos_descargados, tickers_filtro):
    """Devuelve lista de dicts con todos los datos solo para tickers del filtro."""
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
            rec_mean      = info.get("recommendationMean")  # 1=Strong Buy, 5=Strong Sell
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


def formatear_linea_fundamental(d):
    linea = f"**{d['nombre']} ({d['ticker']})** | Precio: {d['precio']:.2f} {d['moneda']}"
    if d['pe_actual']:
        linea += f" | P/E: {d['pe_actual']:.1f}x"
    if d['pe_forward']:
        linea += f" | P/E Fwd: {d['pe_forward']:.1f}x"
    if d['target']:
        linea += f" | Target: {d['target']:.2f}"
    if d['upside'] is not None:
        emoji = "🟢" if d['upside'] > 0 else "🔴"
        linea += f" | Upside: {emoji} {d['upside']:+.1f}%"
    return linea


def formatear_seccion_fundamentales(datos, top_n=None):
    ordenados = sorted(datos, key=lambda x: x['upside'] if x['upside'] is not None else -999, reverse=True)
    if top_n:
        ordenados = ordenados[:top_n]
    return [formatear_linea_fundamental(d) for d in ordenados]


# ═════════════════════════════════════════════
# 6. TOP 10 OPORTUNIDADES (Wide Moat + ≥25% upside + rec favorable)
# ═════════════════════════════════════════════
def get_top_oportunidades(datos_cartera, datos_watchlist, cambios_por_ticker, top=10, min_upside=25):
    """
    Filtros:
    - Ticker debe estar en TICKERS_WIDE_MOAT
    - upside >= min_upside
    - recommendationMean <= 2.5 (consenso favorable, sin Sells significativos)
    - número mínimo de analistas: 3 para que sea fiable
    """
    todos = datos_cartera + datos_watchlist

    elegibles = []
    for d in todos:
        # Filtro 1: Wide Moat
        if d['ticker'] not in TICKERS_WIDE_MOAT:
            continue
        # Filtro 2: upside
        if d['upside'] is None or d['upside'] < min_upside:
            continue
        # Filtro 3: recomendación favorable
        rec_mean = d.get('rec_mean')
        num_an   = d.get('num_analistas', 0)
        if rec_mean is None or rec_mean > 2.5:
            continue
        if num_an < 3:  # mínimo 3 analistas para fiabilidad
            continue
        elegibles.append(d)

    # Ordenar por upside descendente
    elegibles.sort(key=lambda x: x['upside'], reverse=True)
    top_n = elegibles[:top]

    salida = []
    for i, d in enumerate(top_n, 1):
        rec_texto = ""
        if d.get('rec_mean'):
            rm = d['rec_mean']
            if rm <= 1.5: rec_label = "Comprar fuerte"
            elif rm <= 2.0: rec_label = "Comprar"
            elif rm <= 2.5: rec_label = "Comprar/Mantener"
            else: rec_label = "Mantener"
            rec_texto = f" | Consenso: {rec_label} ({rm:.2f}/5, {d.get('num_analistas',0)} analistas)"

        linea = f"{i}. **{d['nombre']} ({d['ticker']})** | Precio: {d['precio']:.2f} {d['moneda']} | "
        linea += f"Target: {d['target']:.2f} | Upside: 🟢 {d['upside']:+.1f}%{rec_texto}"
        if d.get('pe_forward'):
            linea += f" | P/E Fwd: {d['pe_forward']:.1f}x"

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
# GEMINI — INFORME (6 secciones)
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

Cartera: Microsoft, Meta, Amazon, Alphabet, Constellation Software, Visa, Mastercard,
S&P Global, Moody's, MercadoLibre, Booking Holdings, Copart, Dino Polska, Airbus, Nintendo,
Kraken Robotics, TransMedics, Berkshire Hathaway. Cartera ampliada: Waste Connections,
McDonald's, American Express, AST SpaceMobile, Nvidia.

Genera EXACTAMENTE estas 6 secciones:

## 1. RESUMEN MACRO
Análisis sustancioso de tipos (Fed/BCE), inflación, geopolítica, divisas y materias primas.
Cada subtema con su nombre en negrita y análisis concreto. Termina con implicaciones para la cartera.

## 2. SEÑALES A VIGILAR
Riesgos y catalizadores reales basados en macro y contexto de la cartera. NUNCA "no hay nada".

## 3. CAMBIOS DE ANALISTAS (últimos 30 días)
Reproduce la lista tal cual. Los grados YA están en español.

## 4. DATOS FUNDAMENTALES — CARTERA
Reproduce el bloque tal cual.

## 5. DATOS FUNDAMENTALES — WATCHLIST (TOP 50 por upside)
Reproduce el bloque tal cual.

## 6. TOP 10 OPORTUNIDADES WIDE MOAT (≥25% upside + consenso favorable)
Reproduce el bloque tal cual, conservando numeración 1-10 y movimientos recientes.

Sé directo. Sin relleno.

=== DATOS MACRO ===
{macro_texto}

=== CAMBIOS ANALISTAS (30 días) ===
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

    # Preparar todos los tickers
    tickers_cartera = {**EMPRESAS_USA, **{t: v[0] for t, v in EMPRESAS_INTL.items()}}

    print("⏳ Descargando datos de yfinance (cartera + watchlist en paralelo)...")
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
