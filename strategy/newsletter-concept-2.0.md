# Geopolitical Daily 2.0 — koncept a strategie

*Nezávislý průzkum trhu a návrh nového konceptu newsletteru. Srpen 2026.*

> **TL;DR:** Současný produkt ztrácí odběratele, protože kombinuje pět prokázaných churn-driverů najednou: hutný akademický jazyk, rigidní repetitivní formát bez šířky záběru, viditelně úzké zdrojování (které působí zaujatě), anonymní „AI-generated" framing a povinnou denní frekvenci bez volby. Trh přitom ukazuje jasnou, nikým neobsazenou mezeru: **multi-perspektivní geopolitický brief na globální ose (Západ / Čína / Rusko / regionální / Global South)** — tedy mechaniku Ground News, ale aplikovanou na osu, kterou Ground News, Tangle ani AllSides nepokrývají (všichni jedou americkou levici/pravici). Doporučuji přestavět produkt na tento koncept: úzké zdrojování se tím promění z ostudy v samotný produkt („kdo o události mluví jak") a AI-native výroba se stane férově přiznanou výhodou místo skrývaného stigmatu.

---

## 1. Diagnóza: proč se noví odběratelé do pár dní odhlašují

Analýza posledních 8 vydání (17.–24. 8. 2026) a kódu pipeline:

| Problém | Důkaz z produktu | Co na to výzkum |
|---|---|---|
| **Repetitivní formát bez šířky** | Každý den přesně 4 příběhy, všechny v identické šabloně (Why This Matters / What Others Are Missing / What to Watch). Žádné quick hits, žádný pocit „jsem v obraze o celém světě". | Všichni úspěšní hráči (1440, International Intrigue, Semafor, Espresso) kombinují **1 hloubkový příběh + mnoho krátkých položek**. Čistá hloubka bez šířky u denního briefu nefunguje. |
| **Akademický jazyk** | Věty o 40–70 slovech („…signals the maximum-pressure campaign is reaching an inflection point with direct risk to global oil supply and Hormuz shipping lanes"). Prompt explicitně žádá registr „senior geopolitical analyst". | Masové zpravodajství cílí na čitelnost 6.–9. třídy (BBC ~6,3; NYT ~8–9 Flesch-Kincaid). Axios Smart Brevity je postavená na eye-trackingu: čtenář dá textu milisekundy. Hustota, ne délka, je to, co čtenáře vyhání (GetApp 2024: délku uvádí jen ~4 % odhlášených). |
| **Viditelně úzké zdroje → dojem zaujatosti** | Za 8 vydání jen ~15 různých domén; foreignpolicy.com 12×, scmp.com 8×, meduza.io 7×. Příběhy citují 2–3 domény, často tutéž dvakrát (24. 8.: al-monitor.com 2× u jednoho příběhu). Prompt přímo přikazuje „weight think tanks and specialist outlets above wire services". Newsletter navíc přebírá kritiku jednoho outletu jako vlastní stanovisko. | Vítězné produkty dělají z transparentnosti zdrojů **viditelný trust signál** (Ground News bias bar, DailyChatter „syntéza 20+ zdrojů" jako celá brand promise). Holé domény bez odkazů jsou pravý opak. |
| **Nevysvětlená skóre** | Čipy „9/10 82%" bez jakékoli legendy. | Žádný ze zkoumaných úspěšných konkurentů nezobrazuje skóre bez zdůvodnění — buď řadí umístěním, nebo je „proč" viditelná věta prózy. |
| **Anonymní AI framing** | Patička: „generated using AI analysis … contact our editorial team" (tým neexistuje). Žádný autor, žádná persona. | Reuters Institute DNR 2025: 54 % lidí je nekomfortních se zprávami „primárně od AI", ale 34 % je v pohodě s „AI-assisted, human-primary". Osobní jméno odesílatele zvyšuje open rate (+3,8 %, MailerLite 2025); Economist v A/B testu vyhrál s bylines proti instituční značce. Současná patička je nejhorší možná kombinace. |
| **Povinný daily bez volby** | Jediná frekvence: denně. | **Frekvence je důvod č. 1 odhlašování (46,4 % — 3× víc než druhý důvod; GetApp 2024).** Denní kadence zvyšuje churn ~40 % proti týdenní. Preference center s volbou frekvence snižuje odhlášení o 20–40 % (Mailfloss/Digioh 2026). |
| **Chybí sběr e-mailů a onboarding** | Publikované stránky **neobsahují žádný e-mailový formulář** (Buttondown form se renderuje jen se secretem `BUTTONDOWN_USERNAME`; v `docs/` není). Jediné CTA je „Subscribe via RSS". Žádná welcome sekvence. | Welcome e-maily mají 51–69 % open rate (vs. 20–40 % běžných sendů); vícedílná welcome série zvedá engagement až o 51 %. Nejlevnější retenční páka vůbec — a dnes je na nule. |
| **Nula vizuálů** | Žádná mapa, graf, obrázek. | Mapy/číselné sekce („Hard Numbers" u GZERO) jsou standardní retenční prvek. |

**Souhrn:** SEO přivádí obecné zájemce o světové dění, ale produkt je wonk-brief psaný jazykem think-tanku, který navíc nepůsobí důvěryhodně (anonymní AI, neproklikatelné úzké zdroje, pseudoskóre) a nedává volbu frekvence. Churn do pár dní je přesně to, co tahle kombinace podle výzkumu produkuje.

---

## 2. Co říká trh

### 2.1 Vítězné formáty (denní world-news briefy)

| Produkt | Velikost | Formát | Čím vyhrává |
|---|---|---|---|
| **1440 Daily Digest** | 4M+ subs | Need to Know (1–3 top) → In the Know (grid krátkých) → trivia | Neutralita jako brand („facts without motives"), šířka, 5 min |
| **International Intrigue** | 100k+ (8,5k→82k za rok 2023) | Deep dive + roundup, ~5 min | „Cheeky cheatsheet" — osobnost + kredibilita ex-diplomatů, plain language |
| **DailyChatter** | 400k+ | Syntéza 20+ zdrojů | Nonpartisan positioning jako celá brand promise |
| **Semafor Flagship** | 180k+ | **Semaform**: The News → Reporter's View → Room for Disagreement → **The View From** → Notable | Strukturální oddělení faktů a názoru; „View From" = jediný mainstream náznak globální perspektivy |
| **GZERO Daily** | nezveřejněno | Quick Take + Hard Numbers + satira (Puppet Regime) | Čísla + delight prvek |
| **Tangle** | 500k free / 75k paid | Left says / Right says / My take, 1 téma denně | Skutečný, adresný autorský hlas |
| **Ground News** | 2,7M downloads | Bias bar (L/C/R %), **Blindspot report** | Coverage-transparentnost jako produkt |

**Společné ingredience vítězů:** (1) pevné, pojmenované sekce v každém vydání; (2) mix hloubky a šířky — 1 deep dive + quick hits; (3) hovorový jazyk místo think-tank prózy; (4) pojmenovaný lidský hlas; (5) delight prvek navíc (trivia, satira, mapa); (6) oddělení faktů od názoru **strukturou**, ne tvrzením; (7) viditelný trust signál (bias bar, bylines) místo nevysvětleného čísla; (8) ~5 minut, ráno, stejný čas.

### 2.2 Kde je mezera (a kde ne)

**Přeplněno — nesoutěžit čelně:**
- „Vše za 5 minut" obecné roundupy — 1440 má 4M+ a totální mindshare.
- US left/right bias-comparison — Ground News, Tangle, AllSides, Flip Side, Verity; kategorie se konsoliduje.
- Paywallovaná expertní analýza (Foreign Policy a spol.) — saturováno, jiné publikum.

**Mezera, kterou nikdo nedrží:** Všechny multi-perspektivní produkty organizují perspektivy na **americké domácí ose levice/pravice — i u mezinárodních témat**. Nikdo systematicky neukazuje, jak tutéž událost rámují **západní média vs. čínská vs. ruská vs. regionální vs. Global South**. Přitom akademický výzkum potvrzuje, že rozdíly v rámování jsou reálné a čitelné (srovnání 4 997 článků CGTN vs. 4 975 VOA k Ukrajině: „geopolitics-first" vs. „humanitarian-solidarity" framing, Journal of Media 2025; obdobně Wozniak et al. 2026 pro Global South). Semafor to dělá jednou větou u jednoho příběhu; Ground News na to nemá zdrojovou základnu mimo US/UK.

A druhá poznámka k mezeře: geopolitika se dnes dělí na „dense/credible" a „broad/shallow". Skoro nikdo nekombinuje geopolitickou hloubku s řemeslem pop-newsletteru. International Intrigue je nejblíž — ale stojí na kredenciálech lidských ex-diplomatů, které automatizovaný produkt mít nemůže. Automat potřebuje **náhradní trust signál: radikální transparentnost zdrojů a výroby**. Tu má AI-native pipeline zadarmo — stačí ji přestat schovávat.

---

## 3. Tři koncepty a doporučení

### Koncept A — „Every side of the story": globální multi-perspektivní brief ⭐ DOPORUČENO

Mechanika Ground News (coverage-transparentnost, blindspoty) aplikovaná na **globální osu perspektiv** místo US left/right, v ~5minutovém denním/týdenním e-mailu psaném plain language.

- Hlavní příběh dne se **stane produktem tím, jak je pokrytý**: „31 outletů o tom píše; západní média zdůrazňují X (citace Reuters), čínská státní média rámují jako Y (citace Global Times), regionální zdroje řeší Z (citace Al-Monitor), a tady je, co skoro nikdo nepokrývá."
- **Řeší přesně tvůj problém se SCMP:** dva příběhy po sobě zdrojované jen z SCMP jsou dnes bug; v konceptu A je „co píše SCMP vs. co píší ostatní" feature. Úzká perspektiva přestane být skrytá vada a stane se explicitním obsahem.
- **AI přestává být stigma:** „Žádná redakce na světě nečte denně 100+ zdrojů v pěti perspektivách. Naše pipeline ano — a každý zdroj vidíš." AI-native výroba je tu poctivě přiznaná konkurenční výhoda (v souladu s Reuters daty: „AI-assisted, human-curated" framing, pojmenovaná osoba jako editor/odesílatel).
- Obhajitelný moat: vyžaduje globální zdrojovou základnu + clustering + framing-extraction pipeline — přesně to, co už z poloviny máš a co je pro tebe zábavné stavět.
- Riziko: náročnější pipeline (řešitelné, viz §5); citace státních médií vyžadují jasné labelování (viz §7).

### Koncept B — Plain-language 5-min world brief (klon 1440/II)

Přepsat jazyk, přidat quick hits, zůstat u kurátorského briefu. Nejnižší náklad, ale nulová diferenciace: soutěžíš přímo s 1440 (4M subs) a II (lidští diplomaté), bez jejich distribuce a kredenciálů. SEO trickle 1–2 subs/týdně to nezmění. **Samo o sobě nedoporučuji — ale jazyková a formátová disciplína z B je povinná součást A.**

### Koncept C — Datový „signals" brief (indikátory, pravděpodobnosti, mapy)

Denní dashboard světa: eskalační indexy, GDELT trendy, pravděpodobnosti z predikčních trhů, mapa dne. Výrazné, ale úzké publikum (analytici, tráderi) a bez příběhu to je studené. **Nedoporučuji jako celek — ale sekce „Signals" (3 čísla + Polymarket/Metaculus pravděpodobnost u „What to Watch") přebíráme do A jako delight/retenční prvek.**

**Doporučení: A + jazyk a struktura z B + sekce Signals z C.** Pracovní positioning: *„The world's news from every side — Western, Chinese, Russian, and the Global South, in one 5-minute brief."* Rebrand (volitelně, fáze 2+): kandidáti „Parallax", „Vantage", „Worldsides"; do té doby stačí nový tagline u stávající značky.

---

## 4. Nový formát vydání (konkrétně)

Cíl: ~5 minut, čitelnost Flesch-Kincaid ≤ 9. třída, pevné pojmenované sekce, každý zdroj proklikatelný s názvem outletu a labelem perspektivy.

```
Subject: 🌍 Iran's oil threat — and what Beijing's papers won't say

THE BIG STORY  ─────────────────────────────
Iran threatens to shut down Gulf oil exports
• What happened: 2–4 odrážky, každá ≤ 20 slov, prostý jazyk.
• Why it matters: 2 krátké věty (ne jedna 60slovná).

HOW THE WORLD COVERS IT
▓▓▓▓▓▓▓▓░░ 31 outlets · 58 % Western · 19 % regional · 13 % state media (labeled)
🇺🇸🇪🇺 Western (18): sankce jako páka, riziko pro Hormuz.
   „…" — Reuters | „…" — FT
🇨🇳 Chinese state (3): americký unilateralismus destabilizuje region.
   „…" — Global Times [state-affiliated]
🇷🇺 Russian (2): …  „…" — TASS [state-affiliated]
🌍 Regional Gulf/Iran (5): …  „…" — Al-Monitor
⚠ BLINDSPOT: Indická a africká média událost téměř nepokrývají —
   přitom Indie odebírá 35 % íránské ropy.

WHAT TO WATCH: Polymarket dává „US–Iran vojenský střet do konce
roku" 23 % (↑5 b. tento týden).

ALSO TODAY  ────────────────────────────────
6–8 položek po jedné větě s odkazem, tag regionu.
(Tohle dodává pocit „jsem v obraze", který dnes chybí.)

SIGNALS  ───────────────────────────────────
Tři čísla dne s jednořádkovým kontextem (GDELT trend, cena
komodity, pravděpodobnost z predikčního trhu).

THE MAP  ───────────────────────────────────
Statická mapka k big story (Mapbox Static API / open-source).

Patička: „Drafted with AI, curated and reviewed by [jméno].
Every source is linked above. Delivery: daily | weekly digest →"
```

Pravidla psaní (nový prompt): věty ≤ 20 slov; žádný think-tank žargon („inflection point", „strategic calculus"); u perspektiv **citovat doslovné formulace outletů, ne parafráze** (mitigace LLM framing-bias, viz §5); skóre 1–10 zrušit z UI úplně — prioritu vyjadřuje pořadí a plocha. Interní skóring může zůstat pro výběr.

---

## 5. Nová pipeline

Dnešek: 32 RSS → title-similarity dedup (0,85) → jeden Claude call vybere a napíše 4 příběhy. Nový tok:

1. **Collect** — rozšíření na ~80–120 zdrojů (viz §6). Stávající kolektor stačí, jen víc feedů + nová metadata.
2. **Embed + cluster** — `all-MiniLM-L6-v2` (CPU, zdarma, sekundy na tomto objemu) → HDBSCAN. Nahrazuje title-similarity dedup; články o téže události se sejdou napříč jazykovým stylem outletů. *Feasibility: triviální (ověřeno — standardní produkční pattern).*
3. **Event selection** — skóre události = velikost clusteru × **diverzita perspektiv** × váhy zdrojů × novost vůči 7denní historii. Tvrdá pravidla: big story vyžaduje ≥ 5 outletů ze ≥ 3 os; žádný příběh nesmí citovat jednu doménu 2×; quick hits musí pokrýt ≥ 4 regiony.
4. **Perspective extraction** — 1 Claude call na big story (+ případně 1 na blindspot dne): vstup = úryvky článků clusteru s labely os, výstup = citace + jednovětné shrnutí rámování per osa + co chybí. Model **cituje, neparafrázuje** — výzkum (arXiv 2505.05406, Springer 2026) ukazuje, že LLM jinak vnáší vlastní rámování.
5. **Composition** — 1 Claude call složí vydání (big story, also today, signals) v plain language. **Readability gate:** Flesch-Kincaid > 9 → automatický retry s instrukcí zjednodušit. (Deterministická kontrola, `textstat`, zdarma.)
6. **Enrich** — Polymarket API (zdarma, bez klíče) / Metaculus pro pravděpodobnost k „What to Watch"; GDELT Doc API pro trend-číslo do Signals; statická mapa.
7. **Render + publish** — e-mail-safe HTML (existuje) + web; Buttondown API.
8. **Archive + metrics** — stávající archiver; nově logovat i coverage-statistiky (kolik outletů/os na událost) — je to zároveň obsah („31 outlets covered this").

**Náklady:** embeddings 0 $; ~2–3 Claude cally/den (odhad ~60–120k input + ~8k output tokenů denně ≈ 0,30–0,55 $/den ≈ 9–16 $/měs při Sonnet cenách 3/15 $ za MTok) — bezpečně v limitu 30 $/měs, s rezervou na týdenní digest a experimenty. Vše běží dál v GitHub Actions.

---

## 6. Rozšíření zdrojů: z 32 na ~100

Bottleneck není technika (OPML kolekce jako `plenaryapp/awesome-rss-feeds` pokrývají 250+ feedů po zemích; velcí nezápadní hráči mají anglické RSS), ale **editorské otagování**. Nové schéma per zdroj v `sources.json`:

```json
{ "name": "Global Times", "perspective": "chinese_state",
  "state_affiliated": true, "reliability_tier": 3, "weight": 0.6 }
```

- `perspective` (osa): `western_mainstream`, `western_analysis`, `chinese_state`, `chinese_diaspora`, `russian_state`, `russian_exile`, `indian`, `gulf`, `israeli`, `turkish`, `iranian_state`, `african`, `latam`, `sea_pacific`, `intl_org`…
- `state_affiliated`: seed z Wikidata „state media" entit (SPARQL, zdarma) + ruční kontrola.
- `reliability_tier`: seed z MBFC open datasetů (GitHub scrapes) + ruční review. AllSides/Ad Fontes API jsou enterprise-gated — nepotřebujeme je; u globální osy si mapping stejně musíme vlastnit.

**Kandidáti k přidání (výběr):** wire/mainstream: AP, DW, NHK World, France24 (je), CBC/ABC AU; Asie: Xinhua EN, Global Times, CGTN, Nikkei Asia, Korea Herald/Yonhap, Straits Times, Times of India, The Hindu, Dawn (PK); Rusko: TASS EN (state, labelovat) — pozn. RT je v EU sankcionovaná, vynechat a rámování ruského státu brát z TASS/MID prohlášení přes GDELT; Blízký východ: Al Arabiya, Anadolu, Haaretz, Jerusalem Post, Tehran Times (state); Afrika: Daily Maverick, Premium Times, The East African; LatAm: MercoPress, Buenos Aires Herald, Folha EN. Stávajících 32 zůstává. Validace: existující `scripts/validate_sources.py` + týdenní health workflow už běží.

**Zásada:** státní média se **necitují jako zdroj pravdy, ale jako data o rámování** — vždy s labelem `[state-affiliated]`, vždy vedle ostatních os, nikdy jako jediný zdroj faktu. Přesně tak z toho dělá přednost Ground News („kdo to říká a kdo to neříká je informace sama o sobě").

---

## 7. Retenční mechanika (Buttondown, quick wins)

1. **E-mailový formulář na web** — dnes na publikovaných stránkách chybí (secret `BUTTONDOWN_USERNAME` se nepropisuje). Fix + formulář i na index a každé vydání. Bez toho je všechno ostatní jedno.
2. **Volba frekvence: daily vs. weekly digest** — přes Buttondown tagy + automations (nativní toggle nemá, jde to složit). Týdenní digest = „best of + biggest blindspots of the week". Řeší důvod č. 1 churnu; nabídnout **už při signup** a znovu v každé patičce („too many emails? switch to weekly").
3. **Welcome sekvence (3 e-maily):** (1) okamžitě: co čekat, ukázkové vydání, volba frekvence; (2) den 3: „jak číst perspective grid" + nejlepší blindspot měsíce; (3) den 10: mikro-survey (Buttondown surveys: nadprůměrná response) — „co ti chybí?".
4. **Osobní odesílatel a persona** — e-maily chodí od „[jméno] — Geopolitical Daily", patička „drafted with AI, curated by [jméno]". Nikdy anonymní „editorial team".
5. **Subject lines** s napětím perspektiv („X happened — and Beijing's papers won't say Y") místo generických titulků.
6. **Sdílitelné blindspot karty** — perspective grid je přirozeně virální formát; napojit na existující X-thread generátor (`src/social/`) jako růstový kanál.

**KPI:** 14denní retence nové kohorty (cíl > 60 %), open rate (cíl > 40 % — osobní newslettery běžně 35–50 %), CTR na zdroje, poměr volby weekly vs. daily, response na day-10 survey. Vše měřitelné v Buttondown analytics.

---

## 8. Roadmap

| Fáze | Rozsah | Obsah |
|---|---|---|
| **0 — Quick wins** (≤ 1 týden) | jen konfig + šablony + prompt | Formulář na web; welcome sekvence; volba daily/weekly; nový writing-prompt (plain language, věty ≤ 20 slov) + readability gate; proklikatelné zdroje s názvy; skrýt skóre; persona v patičce („AI-drafted, human-curated by [jméno]"); zákaz duplicitní domény v jednom příběhu. **Tohle samo o sobě by mělo zastavit většinu okamžitého churnu.** |
| **1 — Šířka a základ** (2–4 týdny) | pipeline | +40–60 zdrojů s perspective/state labely; embeddings + HDBSCAN místo title-dedup; event selection s diversity pravidly; formát „Big story + Also today (6–8) + 1 delight prvek". |
| **2 — Diferenciace** (4–8 týdnů) | produkt | Perspective grid s citacemi a coverage-statistikou; Blindspot dne; Signals (Polymarket/GDELT); mapa dne; sdílitelné karty do X threads; případný rebrand + landing page postavená na „every side of the story". |
| **3 — Růst** (průběžně) | marketing | SEO stránky per událost s perspective gridem (unikátní obsah, který nikdo jiný nemá → lepší SEO než generické shrnutí); referral; cross-promo s podobnými newslettery; weekly „Blindspot Report" jako samostatný lead magnet. |

**Rizika a mitigace:** LLM vnáší vlastní rámování → citovat, ne parafrázovat; sekundárně namátkový lidský audit. Státní média eticky/právně → labelovat, RT vynechat (EU sankce), nikdy jediný zdroj faktu. Rozpočet → cost controller existuje, odhad je ⅓–½ limitu. Komplexita pro jednoho člověka → fáze jsou samostatně shippovatelné; po fázi 0 lze měřit a případně zastavit.

---

## 9. Proč tohle bude fungovat (shrnutí evidence)

1. **Odstraňuje všech pět diagnostikovaných churn-driverů** doloženými opatřeními (frekvence → volba; jazyk → readability gate; důvěra → persona + linkované zdroje; formát → hloubka+šířka; skóre → pryč).
2. **Obsazuje ověřenou mezeru:** multi-perspektivnost prokazatelně táhne (Ground News 2,7M downloads, Tangle 500k), globální osu nikdo nedrží a framing-rozdíly jsou akademicky doložené.
3. **Mění dvě největší slabiny v přednosti:** úzké/biased zdrojování → transparentní „kdo o tom mluví jak"; AI výroba → přiznaná superschopnost („čteme 100+ zdrojů v 5 perspektivách denně — každý vidíš").
4. **Je levné a proveditelné sólo:** embeddings zdarma, Polymarket/GDELT zdarma, Claude náklady ~⅓ současného limitu, vše v existující GitHub Actions infrastruktuře, fáze 0 je otázka dnů.
