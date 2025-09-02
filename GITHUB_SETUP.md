# GitHub Actions Setup Guide

## 🚀 Rychlé zprovoznění automatického newsletteru

**✅ HOTOVO**: GitHub Actions workflow soubory jsou vytvořené a připravené!

**⏰ Čas na dokončení**: 10-15 minut

### Krok 1: Nastavení GitHub Secrets

Jdi do svého GitHub repozitáře a nastav tyto secrets:

1. **Jdi na**: `Settings` → `Secrets and variables` → `Actions`
2. **Klikni na**: `New repository secret`
3. **Přidej tyto secrets**:

#### Povinné pro AI analýzu:
```
Name: ANTHROPIC_API_KEY
Value: [tvůj Claude API klíč z Anthropic]
```


### Krok 2: Získání API klíčů

#### Anthropic Claude API klíč:
1. Jdi na: https://console.anthropic.com/
2. Zaregistruj se / přihlas se
3. Jdi na `API Keys` sekci
4. Vytvoř nový API klíč
5. Zkopíruj klíč (začíná `sk-ant-...`)

### Krok 3: Povolení GitHub Actions

1. **Jdi na**: `Settings` → `Actions` → `General`
2. **Vyber**: "Allow all actions and reusable workflows"
3. **Klikni**: `Save`

### Krok 4: Testování

#### Manuální spuštění (doporučeno pro první test):
1. Jdi na `Actions` tab
2. Vyber `Daily Geopolitical Newsletter` workflow
3. Klikni `Run workflow`
4. Vyber `dry_run: true` pro první test
5. Klikni `Run workflow`

#### Automatické spouštění:
- Workflow se automaticky spustí každý den v 6:00 UTC (8:00 CET)
- Můžeš změnit čas v `.github/workflows/daily-newsletter.yml`

### Krok 5: Monitoring

#### Kontrola výsledků:
- **Logy**: `Actions` tab → vyber konkrétní run
- **Artefakty**: Stažení vygenerovaných newsletterů a logů
- **Chyby**: Automaticky se vytvoří GitHub issue při selhání

#### Co očekávat:
- **Úspěšný run**: 30-45 sekund
- **Sběr článků**: 400-500 článků z 19 zdrojů
- **Výstup**: HTML newsletter v artifacts
- **Velikost**: ~12KB profesionální newsletter

### Krok 6: Řešení problémů

#### Časté problémy:
1. **Chybějící API klíče**: Zkontroluj GitHub Secrets
2. **Síťové chyby**: Některé RSS zdroje mohou být dočasně nedostupné (normální)
3. **API limity**: Claude má rate limity, zkus později

#### Debug kroky:
1. Spusť s `dry_run: true` pro testování bez API volání
2. Zkontroluj logy v Actions tab
3. Stáhni artifacts pro detailní analýzu
4. Zkus lokální spuštění: `python test_complete_pipeline.py`

### Krok 7: Produkční nastavení

#### Pro plnou automatizaci:
1. Nastav všechny API klíče
2. Změň `DRY_RUN=false` v workflow (už je nastaveno)

#### Monitoring:
- Denní kontrola Actions tab
- Sledování automaticky vytvořených issues
- Pravidelná kontrola artifacts

## 🎯 Shrnutí kroků pro dnes:

1. ✅ **Nastav GitHub Secrets** (ANTHROPIC_API_KEY minimálně)
2. ✅ **Povol GitHub Actions**
3. ✅ **Spusť první test** s dry_run: true
4. ✅ **Zkontroluj výsledky** v Actions tab
5. ✅ **Nastav produkční režim** (dry_run: false)

**Časová náročnost**: 15-30 minut na kompletní nastavení

**Výsledek**: Plně automatický denní newsletter systém! 🎉
