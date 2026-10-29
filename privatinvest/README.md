# приватинвест.про — макет сайта-агрегатора залоговых заявок

Статический макет (один файл `index.html`): первый экран, витрина, блоки для инвестора, брокера и
заёмщика, три кабинета и вкладка «Концепция». Все объекты, суммы и люди вымышлены.
Дизайн — «цифровой» стиль сайта партнёра (см. `/mnt/project-files/partner-zaloginvest/` в проекте).

Выкладка: workflow `.github/workflows/privatinvest.yml` копирует папку на Beget тем же SSH-ключом,
что и торггид, в `~/privateinvest.pro/public_html` (на Beget домен заведён как privateinvest.pro).
Запускается при изменении `privatinvest/**` и вручную (workflow_dispatch). Страница открыта для поиска (29.10.2026), есть robots.txt и sitemap.xml. Номер Метрики и код Вебмастера — в `window.PI_CFG` в начале index.html.
