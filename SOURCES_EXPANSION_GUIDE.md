# 🚀 **GEOPOLITICAL DAILY - ROZŠÍŘENÍ ZDROJOVÉ BÁZE**

## 📊 **ANALÝZA SOUČASNÉ SITUACE**

### **Problém:**
- **16 zdrojů** s 24h filtrováním = nedostatek obsahu
- **4 problematické scrapery** často selhávají
- **Potřeba více perspektiv** pro komplexní analýzu

### **Řešení:**
- **Rozšíření na 50+ zdrojů** (RSS + scraping)
- **Zachování duplicit** pro různé perspektivy
- **Oprava problematických scraperů**

---

## 🎯 **ROZŠÍŘENÁ KONFIGURACE ZDROJŮ**

### **📡 TIER 1: ROZŠÍŘENÉ RSS FEEDY**

#### **📰 MAINSTREAM MEDIA (8 zdrojů):**
```json
{
  "name": "BBC World",
  "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
  "category": "mainstream",
  "weight": 0.8
},
{
  "name": "Reuters World",
  "url": "https://feeds.reuters.com/Reuters/worldNews",
  "category": "mainstream",
  "weight": 0.9
},
{
  "name": "Associated Press",
  "url": "https://feeds.apnews.com/rss/apf-worldnews",
  "category": "mainstream",
  "weight": 0.8
},
{
  "name": "Guardian International",
  "url": "https://www.theguardian.com/world/rss",
  "category": "mainstream",
  "weight": 0.8
},
{
  "name": "Al Jazeera English",
  "url": "https://www.aljazeera.com/xml/rss/all.xml",
  "category": "mainstream",
  "weight": 0.9
},
{
  "name": "Financial Times World",
  "url": "https://www.ft.com/world?format=rss",
  "category": "mainstream",
  "weight": 0.9
},
{
  "name": "NPR World",
  "url": "https://feeds.npr.org/1004/rss.xml",
  "category": "mainstream",
  "weight": 0.7
},
{
  "name": "DW News",
  "url": "https://rss.dw.com/xml/rss_en_all",
  "category": "mainstream",
  "weight": 0.8
}
```

#### **🔍 ANALYSIS & COMMENTARY (8 zdrojů):**
```json
{
  "name": "Foreign Affairs",
  "url": "https://www.foreignaffairs.com/rss.xml",
  "category": "analysis",
  "weight": 1.2
},
{
  "name": "War on the Rocks",
  "url": "https://warontherocks.com/feed/",
  "category": "analysis",
  "weight": 1.1
},
{
  "name": "The Diplomat",
  "url": "https://thediplomat.com/feed/",
  "category": "analysis",
  "weight": 1.1
},
{
  "name": "Foreign Policy Magazine",
  "url": "https://foreignpolicy.com/feed/",
  "category": "analysis",
  "weight": 1.2
},
{
  "name": "Politico Foreign",
  "url": "https://www.politico.com/rss/politics.xml",
  "category": "analysis",
  "weight": 1.0
},
{
  "name": "Economist World Politics",
  "url": "https://www.economist.com/world-politics/rss.xml",
  "category": "analysis",
  "weight": 1.0
},
{
  "name": "Defense One",
  "url": "https://www.defenseone.com/rss.xml",
  "category": "analysis",
  "weight": 1.1
},
{
  "name": "Jane's Defence",
  "url": "https://www.janes.com/rss/",
  "category": "analysis",
  "weight": 1.1
}
```

#### **🏛️ THINK TANKS (12 zdrojů):**
```json
{
  "name": "Brookings Institution",
  "url": "https://www.brookings.edu/feed/",
  "category": "think_tank",
  "weight": 1.3
},
{
  "name": "Council on Foreign Relations",
  "url": "https://www.cfr.org/feed/blog/",
  "category": "think_tank",
  "weight": 1.3
},
{
  "name": "CSIS",
  "url": "https://www.csis.org/rss.xml",
  "category": "think_tank",
  "weight": 1.2
},
{
  "name": "Carnegie Endowment",
  "url": "https://carnegieendowment.org/rss/",
  "category": "think_tank",
  "weight": 1.2
},
{
  "name": "Atlantic Council",
  "url": "https://www.atlanticcouncil.org/feed/",
  "category": "think_tank",
  "weight": 1.2
},
{
  "name": "RAND Corporation",
  "url": "https://www.rand.org/rss/",
  "category": "think_tank",
  "weight": 1.2
},
{
  "name": "Chatham House",
  "url": "https://www.chathamhouse.org/rss.xml",
  "category": "think_tank",
  "weight": 1.1
},
{
  "name": "Wilson Center",
  "url": "https://www.wilsoncenter.org/rss.xml",
  "category": "think_tank",
  "weight": 1.0
},
{
  "name": "Heritage Foundation",
  "url": "https://www.heritage.org/rss.xml",
  "category": "think_tank",
  "weight": 1.0
},
{
  "name": "PIIE",
  "url": "https://www.piie.com/rss.xml",
  "category": "think_tank",
  "weight": 1.0
},
{
  "name": "Stimson Center",
  "url": "https://www.stimson.org/rss.xml",
  "category": "think_tank",
  "weight": 0.9
},
{
  "name": "USIP",
  "url": "https://www.usip.org/rss.xml",
  "category": "think_tank",
  "weight": 0.9
}
```

#### **🌍 REGIONAL SOURCES (6 zdrojů):**
```json
{
  "name": "France 24 English",
  "url": "https://www.france24.com/en/rss",
  "category": "regional",
  "weight": 0.8
},
{
  "name": "RT News",
  "url": "https://www.rt.com/rss/",
  "category": "regional",
  "weight": 0.6
},
{
  "name": "South China Morning Post",
  "url": "https://www.scmp.com/rss/91/feed",
  "category": "regional",
  "weight": 1.0
},
{
  "name": "Asia Times",
  "url": "https://asiatimes.com/feed/",
  "category": "regional",
  "weight": 1.0
},
{
  "name": "Middle East Eye",
  "url": "https://www.middleeasteye.net/rss",
  "category": "regional",
  "weight": 0.9
},
{
  "name": "Al-Monitor",
  "url": "https://www.al-monitor.com/rss.xml",
  "category": "regional",
  "weight": 0.9
}
```

---

### **🌐 TIER 2: ROZŠÍŘENÉ WEB SCRAPING**

#### **📰 ANALYSIS SITES (8 zdrojů):**
```json
{
  "name": "Foreign Policy (Fixed)",
  "url": "https://foreignpolicy.com/latest/",
  "method": "basic",
  "category": "analysis",
  "weight": 1.2,
  "selectors": {
    "container": ".card--article, .post-item, article",
    "title": ".card__title, h2, h3, .headline",
    "link": "a",
    "summary": ".card__excerpt, .excerpt, .summary",
    "date": ".card__date, time, .date"
  }
},
{
  "name": "Politico Foreign Policy",
  "url": "https://www.politico.com/foreign-policy/",
  "method": "basic",
  "category": "analysis",
  "weight": 1.1,
  "selectors": {
    "container": ".story-card, article, .card",
    "title": "h2, h3, .headline",
    "link": "a",
    "summary": ".summary, .excerpt",
    "date": "time, .date"
  }
},
{
  "name": "Defense One (Fixed)",
  "url": "https://www.defenseone.com/",
  "method": "basic",
  "category": "analysis",
  "weight": 1.1,
  "selectors": {
    "container": ".river-well, article, .post-item",
    "title": "h3, h2, .headline",
    "link": "a",
    "summary": ".summary, .excerpt",
    "date": "time, .date"
  }
},
{
  "name": "The National Interest (Fixed)",
  "url": "https://nationalinterest.org/",
  "method": "basic",
  "category": "analysis",
  "weight": 1.0,
  "selectors": {
    "container": ".article-item, article, .post",
    "title": "h3, h2, .title",
    "link": "a",
    "summary": ".excerpt, .summary",
    "date": "time, .date"
  }
},
{
  "name": "RealClearWorld",
  "url": "https://www.realclearworld.com/",
  "method": "basic",
  "category": "analysis",
  "weight": 1.0,
  "selectors": {
    "container": ".article, .post-item",
    "title": "h2, h3, .headline",
    "link": "a",
    "summary": ".excerpt, .summary",
    "date": "time, .date"
  }
},
{
  "name": "World Politics Review",
  "url": "https://www.worldpoliticsreview.com/",
  "method": "basic",
  "category": "analysis",
  "weight": 1.0,
  "selectors": {
    "container": ".article-item, article",
    "title": "h2, h3",
    "link": "a",
    "summary": ".excerpt",
    "date": "time"
  }
},
{
  "name": "Geopolitical Monitor",
  "url": "https://www.geopoliticalmonitor.com/",
  "method": "basic",
  "category": "analysis",
  "weight": 0.9,
  "selectors": {
    "container": ".post-item, article",
    "title": "h2, h3",
    "link": "a",
    "summary": ".excerpt",
    "date": "time"
  }
},
{
  "name": "Eurasianet",
  "url": "https://eurasianet.org/",
  "method": "basic",
  "category": "regional",
  "weight": 0.9,
  "selectors": {
    "container": ".article-item, article",
    "title": "h2, h3",
    "link": "a",
    "summary": ".excerpt",
    "date": "time"
  }
}
```

---

## 📈 **OČEKÁVANÉ VÝSLEDKY**

### **Před rozšířením:**
- **16 zdrojů** → **24-48 článků** → **10-15 po deduplikaci**

### **Po rozšíření:**
- **50+ zdrojů** → **150-200 článků** → **zachování duplicit pro různé perspektivy**

### **Kvalitativní výhody:**
- ✅ **Různé perspektivy** na stejné události
- ✅ **Geografické pokrytí** (USA, EU, Asie, Blízký východ)
- ✅ **Typy zdrojů**: Mainstream, think tanks, regional, analysis
- ✅ **Jazykové pokrytí**: Převážně angličtina s regionálními zdroji

---

## 🛠️ **IMPLEMENTACE**

### **Krok 1: Aktualizace sources.json**
```bash
# Nahraďte obsah sources.json novou konfigurací výše
```

### **Krok 2: Testování**
```bash
# Spusťte pipeline v DRY_RUN módu
python -m src.main_pipeline

# Zkontrolujte logy pro nové zdroje
tail -f logs/geodaily_$(date +%Y%m%d).log
```

### **Krok 3: Optimalizace**
- **Opravte problematické scrapery** podle selectorů výše
- **Přidejte retry logiku** pro nové zdroje
- **Monitorujte výkon** v dashboardu

---

## 🎯 **STRATEGIE DEDUPLIKACE**

### **Současný přístup:**
- **Agresivní deduplikace** - odstraňuje podobné články
- **Problém**: Ztrácí se různé perspektivy na stejnou událost

### **Doporučený přístup:**
- **Zachovat duplicity** pro různé perspektivy
- **Pouze technické duplicity** (stejný URL, stejný obsah)
- **Zachovat redakční duplicity** (různé analýzy stejné události)

### **Výhody zachování duplicit:**
- ✅ **Různé perspektivy** na geopolitické události
- ✅ **Rozmanitost názorů** v newsletteru
- ✅ **Lepší pokrytí** komplexních témat
- ✅ **Bohatší obsah** pro čtenáře

---

## 📊 **MONITORING A ÚDRŽBA**

### **Dashboard Metrics:**
- **Počet zdrojů** po kategorii
- **Úspěšnost sběru** po zdroji
- **Četnost aktualizací** RSS vs scraping
- **Kvalita obsahu** po zdroji

### **Údržba:**
- **Měsíční kontrola** nefunkčních zdrojů
- **Aktualizace selectorů** pro scrapery
- **Přidávání nových zdrojů** podle potřeby
- **Vyvažování vah** pro optimální pokrytí

---

## 🚀 **DALŠÍ ROZŠÍŘENÍ**

### **Pokročilé zdroje:**
- **Twitter/X API** pro real-time geopolitické diskuze
- **Telegram kanály** pro regionální perspektivy
- **Academic journals** pro hloubkové analýzy
- **Government briefings** a oficiální komuniké

### **AI-enhanced zdroje:**
- **Automated sentiment analysis** z RSS feeds
- **Cross-reference validation** mezi zdroji
- **Trend detection** napříč zdroji
- **Source credibility scoring**

---

**Tato rozšířená konfigurace poskytne bohatý, rozmanitý obsah s různými perspektivami na geopolitické události!** 🌍📈