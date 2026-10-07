kirpichinvest.ru — сайт о покупке жилья с торгов (СПб и ЛО).

Для полной карты рабочего пространства, концепции продуктов, статуса сборщика лотов и SEO/GEO-плана см. PROJECT_HANDOFF_RU.md. Перед любой работой также прочитайте AGENTS.md и постоянный журнал в _project/00_План и журнал/.

Как устроено:
- _src/ — исходники: шаблоны (templates), статьи (content/*.md), стили и шрифты (static), сборщик build.py.
- При push в main и 3 раза в день GitHub Actions берёт свежие лоты с https://check.kirpichinvest.ru/public/lots.json,
  собирает сайт в _site/ и выкладывает на Beget (public_html).
- Заявки с форм уходят в сервис check.kirpichinvest.ru (/public/lead) → Telegram и раздел «Заявки» в админке.
- check/ — редирект в сервис проверки заявок.
- _src/semantics.py / semantics.csv — семантическое ядро (частотность снять в Вордстате).
- _src/config.json (необязательно) — реквизиты, цены, счётчик Метрики: SITE_INN, SITE_OGRNIP, PRICE_BUY, PRICE_CHECK, METRIKA_ID.
