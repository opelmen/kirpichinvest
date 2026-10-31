# приватинвест.про — макет сайта-агрегатора залоговых заявок

Статический макет (один файл `index.html`): первый экран, витрина, блоки для инвестора, брокера и
заёмщика, три кабинета и вкладка «Концепция». Все объекты, суммы и люди вымышлены.
Дизайн — «цифровой» стиль сайта партнёра (см. `/mnt/project-files/partner-zaloginvest/` в проекте).

Выкладка: workflow `.github/workflows/privatinvest.yml` копирует папку на Beget тем же SSH-ключом,
что и торггид, в `~/privateinvest.pro/public_html` (на Beget домен заведён как privateinvest.pro).
Запускается при изменении `privatinvest/**` и вручную (workflow_dispatch). Страница открыта для поисковиков (решение John 29.10.2026). Есть robots.txt и sitemap.xml; Метрика 113877734 (стандартный код в <head>, цели через piGoal), Вебмастер подтверждается meta yandex-verification в <head>.

## SEO-страницы (31.10.2026)
Посадочные страницы и статьи (`/zaim-pod-zalog-*/`, `/investicii-pod-zalog-nedvizhimosti/`, `/brokeram/`, `/stati/…`) собираются
скриптом `python3 privatinvest_src/build.py` из `privatinvest_src/pages.py`; HTML не править руками, править pages.py и пересобирать
(workflow падает, если собранное не закоммичено). Стили и код Метрики скрипт берёт из `index.html` → `assets/site.css`.
Форма заявки на страницах (`assets/lead.js`) шлёт в тот же `/public/lead`, в `cta` дописывается адрес страницы.
`sitemap.xml` и `404.html` тоже генерируются. `<32 hex>.txt` в корне — ключ IndexNow: после выкладки workflow отправляет все адреса
из sitemap в Яндекс. Тот же шаг проверяет, что каждая страница отдаёт 200 и свой canonical.
