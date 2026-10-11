# Раскладывает исследование SEO/GEO от 11.10.2026 по папке проекта D:\Кирпичи\_project.
# Запуск из корня репозитория (D:\Кирпичи). Ничего не удаляет, ветку не переключает, в git не коммитит.
$ErrorActionPreference = "Stop"
# Вывод git в UTF-8, иначе кириллица в файлах испортится
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$Branch = "claude/seo-geo-research-rdazms"
${Stamp} = "2026-10-11"

$Root = (git rev-parse --show-toplevel 2>$null)
if (-not $Root) { throw "Запустите скрипт из папки репозитория D:\Кирпичи (там, где .git)." }
$Root = $Root -replace "/", "\"
$Project = Join-Path $Root "_project"
if (-not (Test-Path $Project)) { throw "Нет папки _project в $Root" }
Write-Host "Репозиторий: $Root"

# 1. Файлы исследования из ветки
Write-Host "1/4 Беру файлы из ветки $Branch..."
# ветку уже забрала команда запуска (git fetch)
$Dest = Join-Path $Project "seo\${Stamp}"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$Files = (git ls-tree --name-only "origin/$Branch" docs/seo/) | Where-Object { $_ -notlike "*.ps1" }
$Utf8 = New-Object System.Text.UTF8Encoding($false)
foreach ($f in $Files) {
    $name = Split-Path $f -Leaf
    $raw = & git --no-pager show "origin/${Branch}:$f"
    [System.IO.File]::WriteAllLines((Join-Path $Dest $name), $raw, $Utf8)
    Write-Host "   $name"
}
Write-Host "   Разложено в $Dest"

# 2. Папка журнала: битое имя -> нормальное
Write-Host "2/4 Проверяю папку журнала..."
$Good = Join-Path $Project "00_План и журнал"
if (Test-Path -LiteralPath $Good) {
    Write-Host "   Папка '00_План и журнал' уже есть, переименование не нужно."
} else {
    $cands = @(Get-ChildItem -LiteralPath $Project -Directory | Where-Object { $_.Name -like "00_*" })
    if ($cands.Count -eq 1) {
        Rename-Item -LiteralPath $cands[0].FullName -NewName "00_План и журнал"
        Write-Host "   Переименовал '$($cands[0].Name)' -> '00_План и журнал'"
    } else {
        throw "Не нашёл единственную папку 00_* в _project (нашёл $($cands.Count)). Переименуйте руками в '00_План и журнал' и запустите снова."
    }
}
$Log = Join-Path $Good "ACTION_LOG.md"
$State = Join-Path $Good "CURRENT_STATE.md"
foreach ($p in @($Log, $State)) { if (-not (Test-Path -LiteralPath $p)) { throw "Нет файла $p" } }

# 3. Бэкап журнала
Write-Host "3/4 Бэкап журнала..."
$Bak = Join-Path $Project "backups\${Stamp}_seo"
New-Item -ItemType Directory -Force -Path $Bak | Out-Null
Copy-Item -LiteralPath $Log, $State -Destination $Bak -Force
Write-Host "   $Bak"

# 4. Записи в журнал
Write-Host "4/4 Дописываю журнал..."
$LogEntry = @"

## ${Stamp} · SEO и GEO: исследование, ядро, первый PR

- Тред «SEO и GEO продвижение» (облако). Файлы: ``_project/seo/${Stamp}/`` (README.md, 00_yadro.md … 06_plan-deystviy.md, semantika-torggid.csv: 1085 запросов, 195 кластеров, вся Россия + авто; CHTO_SDELAT_JOHN.md: шаги для John; wordstat-snyat.txt: 36 запросов на съём).
- Учтён прежний план от 03.10.2026 (``_project/seo/SEO_GEO_MASTER_PLAN.md``, ``research/``): 35 замеров Вордстата перенесены в ядро, панели 48 GEO-вопросов и 80 запросов для позиций учтены в файлах 04 и 06. Главная цифра: «квартиры с торгов» по России ≈ 8 100 показов в месяц, с Москвой 600, другие города 18–107.
- kirpichinvest, ветка ``claude/seo-geo-research-rdazms``, PR #10 (черновик, ждёт пачку): индекс карт сайта, llms.txt с блоком «Факты для цитирования», ItemList и полный RealEstateListing, FAQ и статистика регионов, Clean-param, ``_src/semantics.py`` с частотностью WS. 12 тестов проходят. Не деплоить отдельно.
- Очеловечивание: 10 статей сайта и все документы seo/ проходят stop-slop-ru («ЧИСТО»).
- Не подключились из контейнера: jsonseo (Вордстат), se-ranking, seocrawl, serpzilla, exa, прямой доступ к torggid.ru и tbankrot.ru (сеть 403). Как открыть: ``06_plan-deystviy.md``.
- Нужно от John: PR #10 в пачку; Bing Webmaster; регион и 5xx в Яндекс Вебмастере; доснять Вордстат (36 запросов) или открыть сеть; решение по /auto/; цены на услуги. Подробно: ``CHTO_SDELAT_JOHN.md``.
"@
$StateEntry = @"

## SEO и GEO (обновлено ${Stamp})

Исследование от ${Stamp}: ``_project/seo/${Stamp}/`` (копия в проекте Claude, папка seo/). Первая пачка правок в PR #10 kirpichinvest (ветка ``claude/seo-geo-research-rdazms``), ждёт деплой пачкой. Ядро: ``_src/semantics.py`` в репозитории, 35 запросов с частотностью Вордстата от 03.10.2026, остальное без частотности. Следующие шаги по неделям: ``06_plan-deystviy.md``; что нужно от John: ``CHTO_SDELAT_JOHN.md``. Открытые решения: раздел /auto/ следующим; цены на услуги; Bing Webmaster.
"@
[System.IO.File]::AppendAllText($Log, $LogEntry, $Utf8)
[System.IO.File]::AppendAllText($State, $StateEntry, $Utf8)
Write-Host "   ACTION_LOG.md и CURRENT_STATE.md дополнены."
Write-Host ""
Write-Host "Готово. Дальше по списку: $Dest\CHTO_SDELAT_JOHN.md (шаги 2–7)."
