import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '_src'))
from lot_history import merge_history

class LifecycleTests(unittest.TestCase):
    def test_missing_is_not_sold_and_reappearance_restores_active(self):
        now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        row = dict(id='one_1', bidd_end='2027-01-01T00:00:00Z', label='Flat', description='PRIVATE', name='PRIVATE')
        first = merge_history([row], [], now)
        absent = merge_history([], first, now)
        self.assertEqual(absent[0]['status'], 'unavailable')
        self.assertNotIn('description', absent[0])
        self.assertNotIn('name', absent[0])
        self.assertEqual(merge_history([row], absent, now)[0]['status'], 'active')

    def test_expiry_and_meaningful_lastmod(self):
        now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        row = dict(id='two', price=10, bidd_end='2026-10-04T00:00:00Z')
        first = merge_history([row], [], now)
        unchanged = merge_history([row], first, datetime(2026, 10, 3, 12, tzinfo=timezone.utc))
        self.assertEqual(first[0]['lastmod'], unchanged[0]['lastmod'])
        ended = merge_history([], first, datetime(2026, 10, 5, tzinfo=timezone.utc))
        self.assertEqual(ended[0]['status'], 'ended')
        self.assertEqual(ended[0]['lastmod'], '2026-10-05')
        changed = merge_history([dict(row, price=20)], first, datetime(2026, 10, 4, tzinfo=timezone.utc))
        self.assertEqual(changed[0]['lastmod'], '2026-10-04')

    def test_invalid_id_fails(self):
        with self.assertRaises(ValueError):
            merge_history([{'id':'../escape'}], [], datetime.now(timezone.utc))

class BuildTests(unittest.TestCase):
    def test_paginated_catalog_and_retained_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copytree(ROOT / '_src', base / '_src')
            (base / '_src/data/market.json').unlink(missing_ok=True)  # тест прежнего фида Залог-Деска
            rows = [dict(id=f'test_{i}', city='moskva', region='77', address='Москва, Тестовая улица, дом 1', price=1000000, area=40, bidd_end='2099-01-01T00:00:00Z') for i in range(65)]
            rows[1]['bidd_type'] = 'Реализация имущества должников'
            data = base / '_src/data'
            rows[0].update(city='sankt-peterburg', region='47', address='Ленинградская область, Гатчинский район, г. Гатчина, Тестовая улица, дом 1')
            (data/'lot_history.json').write_text('[]')
            (data/'lots.json').write_text(json.dumps(rows))
            def build():
                subprocess.run([sys.executable, str(base/'_src/build.py')], check=True, capture_output=True)
            build()
            site = base/'_site'
            self.assertIn('noindex', (site/'torgi/doli/index.html').read_text())
            index = (site/'sitemap.xml').read_text()
            self.assertIn('<sitemapindex', index)
            for part in ('sitemap-pages.xml', 'sitemap-catalog.xml', 'sitemap-lots-1.xml'):
                self.assertIn(f'https://torggid.ru/{part}', index)
            catalog = (site/'sitemap-catalog.xml').read_text()
            self.assertNotIn('https://torggid.ru/torgi/doli/', catalog)
            self.assertNotIn('/page/2/', catalog)  # страницы 2+ только по ссылкам, не из карты
            self.assertNotIn('noindex', (site/'torgi/page/2/index.html').read_text())
            if (site/'torgi/do-3-mln/page/2/index.html').exists():
                self.assertIn('noindex', (site/'torgi/do-3-mln/page/2/index.html').read_text())
            self.assertNotIn('/torgi/lot/', catalog)
            self.assertIn('https://torggid.ru/torgi/lot/test_0/', (site/'sitemap-lots-1.xml').read_text())
            self.assertIn('https://torggid.ru/stati/', (site/'sitemap-pages.xml').read_text())
            self.assertIn('Clean-param', (site/'robots.txt').read_text())
            self.assertIn('https://torggid.ru/sitemap-yandex.xml', (site/'robots.txt').read_text())
            yandex = (site/'sitemap-yandex.xml').read_text()
            self.assertIn('https://torggid.ru/torgi/moskva/', yandex)
            self.assertIn('https://torggid.ru/stati/', yandex)
            self.assertNotIn('/torgi/lot/', yandex)
            self.assertNotIn('name="yandex"', (site/'torgi/lot/test_0/index.html').read_text())  # полная карточка в миллионнике
            self.assertIn('Факты для цитирования', (site/'llms.txt').read_text())
            self.assertIn('Состав права нужно проверить', (site/'torgi/do-1-mln/index.html').read_text())
            self.assertIn('/byudzhet/', (site/'index.html').read_text())
            self.assertTrue((site/'torgi/sankt-peterburg/gatchinskiy-rayon/index.html').exists())
            self.assertTrue((site/'torgi/page/2/index.html').exists())
            page2 = (site/'torgi/page/2/index.html').read_text()
            self.assertIn('rel="canonical" href="https://torggid.ru/torgi/page/2/"', page2)
            self.assertEqual(page2.count('class="lot"'), 5)
            self.assertIn('/torgi/page/2/', (site/'torgi/index.html').read_text())
            moskva = (site/'torgi/moskva/index.html').read_text()
            self.assertIn('aria-label="Другие города"', moskva)
            self.assertIn('href="/torgi/sankt-peterburg/"', moskva.split('aria-label="Другие города"')[1].split('</nav>')[0])
            # посадочные под рекламу: подборка сохраняется «Охотником» в платформе, ссылки в платформу без utm (Метрика не рвёт визит)
            self.assertIn('/?city=moskva&amp;follow=1&amp;from=catalog_follow', moskva)
            self.assertIn('/?category=flat&amp;category=room&amp;category=share&amp;category=house&amp;price_max=1&amp;follow=1', (site/'torgi/do-1-mln/index.html').read_text())
            self.assertNotIn('utm_', moskva.replace('utm_source","utm_medium', '').split('<script>')[0])
            self.assertIn('tg_acq=', moskva)
            self.assertIn('https://max.ru/id780108433761_biz', moskva)  # канал в Max рядом с Telegram
            self.assertIn('<a href="/torgi/moskva/">Москва</a>', (site/'torgi/lot/test_5/index.html').read_text())  # город в крошках карточки
            rows[1]['status'] = 'ignored'  # Build derives lifecycle from source/deadline.
            rows[1]['bidd_type'] = 'Аренда'
            (data/'lots.json').write_text(json.dumps(rows[1:]))
            build()
            self.assertIn('noindex', (site/'torgi/do-1-mln/index.html').read_text())
            self.assertNotIn('https://torggid.ru/torgi/do-1-mln/', (site/'sitemap-catalog.xml').read_text())
            card = (site/'torgi/lot/test_0/index.html').read_text()
            self.assertIn('Результат торгов и факт продажи не подтверждены', card)
            self.assertNotIn('Получить отчёт', card)
            self.assertIn('/torgi/arhiv/', (site/'torgi/index.html').read_text())
            self.assertEqual(len(list((site/'torgi/lot').glob('*/index.html'))),65)

    def test_market_feed_whole_country(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copytree(ROOT / '_src', base / '_src')
            data = base / '_src/data'
            (data/'lot_history.json').write_text('[]')
            row = dict(source='mets', source_url='https://m-ets.ru/x', kind='bankruptcy', stage='repeat', procedure='Публичное предложение',
                       category='flat', title='Квартира', address='Республика Татарстан, г. Альметьевск, ул. Ленина, д. 5', city=None, region='16',
                       area=40.5, rooms=1, price=2_000_000, price_start=2_500_000, market_price=3_000_000, market_conf='medium', discount_pct=33.3,
                       risks=[dict(key='minors', title='Несовершеннолетние', level='high')], own_time='4–11 мес.',
                       bidd_end='2099-01-01T00:00:00+00:00', first_seen='2026-10-09T00:00:00+00:00')
            rows = [dict(row, id='gistorgi:21000000000000000001_1', source='gistorgi', kind='arrest', category='land', city='kazan')]
            rows += [dict(row, id=f'mets:{i}') for i in range(3)]
            rows.append(dict(row, id='mets:9', discount_pct=55.0, suspect=True))
            rows.append(dict(row, id='mets:10', address='г. Казань, Иванов Иван Иванович, ул. Ленина, д. 7', market_conf='low'))
            (data/'market.json').write_text(json.dumps({'lots': rows}, ensure_ascii=False))
            subprocess.run([sys.executable, str(base/'_src/build.py')], check=True, capture_output=True)
            site = base/'_site'
            self.assertIn('по всей России', (site/'torgi/index.html').read_text())
            region = (site/'torgi/tatarstan/index.html').read_text()
            self.assertIn('Недвижимость с торгов в Татарстане', region)
            self.assertIn('FAQPage', region)  # у региона свои вопросы с цифрами каталога, как у города
            # запрос «торги по банкротству <регион> официальный сайт» (GSC 25.10): площадки региона с числом лотов и ссылками
            self.assertIn('Какой официальный сайт торгов по банкротству в Татарстане?', region)
            self.assertIn('Где проходят торги по банкротству и аресту в Татарстане', region)
            self.assertIn('<a href="https://m-ets.ru/" rel="nofollow noopener" target="_blank">МЭТС</a>', region)
            self.assertIn('все площадки, актуальные лоты', region.split('<title>')[1].split('</title>')[0])
            self.assertNotIn('Где проходят торги', (site/'torgi/tatarstan/povtornye-torgi/index.html').read_text())  # только на главной странице региона
            self.assertIn('ItemList', region)
            self.assertNotIn('follow=1', region)  # регион платформа не фильтрует: без «Следить», только поиск на карте
            self.assertIn('/?category=land&amp;follow=1', (site/'torgi/zemlya/index.html').read_text())
            deal = dict(row, id='mets:20', city='kazan', address='г. Казань, ул. Баумана, д. 5', risks=[], discount_pct=25.0, market_price=2_700_000)
            rows2 = rows + [dict(deal, id=f'mets:2{i}', price_drops=2, price_was=2_500_000) for i in range(3)] + [dict(deal, id='mets:30', category='share')] + [
                dict(deal, id='mets:31', city='moskva', region='77', address='г. Москва, ул. Профсоюзная, д. 12', discount_pct=20.0)] + [
                dict(deal, id='mets:32', category='commercial', title='Нежилое здание', land=dict(kind='building', status='lease', cad='16:50:1:2', area=900.0))]
            (data/'market.json').write_text(json.dumps({'lots': rows2}, ensure_ascii=False))
            subprocess.run([sys.executable, str(base/'_src/build.py')], check=True, capture_output=True)
            board = (site/'index.html').read_text().split('class="board"')[1].split('class="more"')[0]
            self.assertIn('Дешевле рынка', board)
            self.assertIn('/torgi/lot/mets-20/', board)
            self.assertNotIn('/torgi/lot/mets-30/', board)  # доля на витрину не попадает
            self.assertNotIn('/torgi/lot/mets-0/', board)  # серьёзный риск (несовершеннолетние) — тоже
            self.assertLess(board.index('/torgi/lot/mets-31/'), board.index('/torgi/lot/mets-22/'))  # третий лот Казани — после других городов
            self.assertTrue((site/'torgi/vygodnye/index.html').exists())
            deal_card = (site/'torgi/lot/mets-20/index.html').read_text()
            self.assertIn('Полная карточка: фото, документы, аналоги', deal_card)
            self.assertIn('Цена ниже рынка, чистота не проверена', deal_card)  # без проверки жильцов и арестов «выгодно» не пишем
            self.assertIn('<b>Жильцы и дети</b> <span class="st">нет данных</span>', deal_card)  # о чём молчит извещение — отдельной строкой со статусом
            self.assertIn('?start=ask_mets-20', deal_card)
            kazan = (site/'torgi/kazan/index.html').read_text()
            self.assertIn('Цена снижалась 2 раза: 2,5 млн', kazan)  # история снижения цены в каталоге
            self.assertIn('Банкротное имущество</span>', kazan)
            # телефон только в подвале и разметке (John, 31.10.2026), в теле карточки его нет
            self.assertNotIn('995', deal_card.split('<main')[1].split('<footer')[0])
            self.assertIn('595-54-00', deal_card.split('<footer')[1])
            self.assertIn('повторные торги: цена уже снижена', deal_card)  # повторные — плюс, не риск
            bld = (site/'torgi/lot/mets-32/index.html').read_text()
            self.assertIn('<th>Земельный участок</th><td>не продают, участок в аренде (КН 16:50:1:2, 900 м²)', bld)  # участок под зданием
            similar = deal_card.split('<h2>Похожие лоты</h2>')[1]
            self.assertNotIn('/torgi/lot/mets-30/', similar)  # доля к квартире в похожие не попадает
            ym = __import__('datetime').date.today().strftime('%Y-%m')
            idx = (site/'analitika'/ym/'index.html').read_text()
            self.assertIn('Индекс торгов ТоргГид', idx)
            self.assertIn('"@type": "Dataset"', idx)
            self.assertIn('Татарстан', idx)
            self.assertNotIn('Ленина', idx)  # в индексе только агрегаты, без адресов
            csv = (site/'analitika'/ym/'indeks.csv').read_text(encoding='utf-8-sig')
            self.assertIn('лотов в продаже;', csv)
            self.assertIn('площадка: МЭТС;', csv)
            self.assertIn(f'/analitika/{ym}/', (site/'analitika/index.html').read_text())
            self.assertIn(f'https://torggid.ru/analitika/{ym}/', (site/'sitemap-pages.xml').read_text())
            llms = (site/'llms.txt').read_text()
            self.assertIn('Индекс торгов ТоргГид', llms)
            self.assertIn('Все регионы России', llms)
            self.assertIn('## Услуги и цены', llms)
            self.assertIn('Пн–Пт', llms)
            graph = json.loads((site/'index.html').read_text().split('<script type="application/ld+json">')[1].split('</script>')[0])['@graph']
            org = next(x for x in graph if 'RealEstateAgent' in x['@type'])
            self.assertEqual(org['areaServed'], {'@type': 'Country', 'name': 'Россия'})
            self.assertIn('Торггид', org['alternateName'])
            self.assertTrue(any(x['@type'] == 'WebSite' for x in graph))
            self.assertEqual(org['founder']['@id'], 'https://torggid.ru/avtor/ilya-smirnov/#person')
            author = (site/'avtor/ilya-smirnov/index.html').read_text()
            self.assertIn('ProfilePage', author)
            self.assertIn('https://torggid.ru/avtor/ilya-smirnov/', (site/'sitemap-pages.xml').read_text())
            self.assertIn('/avtor/ilya-smirnov/', (site/'stati/zadatok-na-torgah/index.html').read_text())
            self.assertNotIn('16 городах-миллионниках', (site/'index.html').read_text().split('<footer>')[1])
            self.assertIn('<a href="/torgi/tatarstan/">Татарстан</a>', (site/'torgi/lot/mets-0/index.html').read_text())
            card = (site/'torgi/lot/mets-0/index.html').read_text()
            self.assertIn('Цена ниже рынка, но серьёзный риск', card)
            self.assertNotIn('Выгодно', card)
            self.assertIn('Извещение и документы на МЭТС', card)
            self.assertIn('/lot/mets%3A0', card)
            self.assertIn('RealEstateListing', card)
            sus = (site/'torgi/lot/mets-9/index.html').read_text()
            self.assertIn('сверьте с объявлениями', sus)
            self.assertNotIn('дисконт 55%', sus)  # громкий процент при подозрительной скидке не выносим
            self.assertIn('Цена сейчас', card)  # публичное предложение
            self.assertIn('<b>Аресты и залоги</b> <span class="st">нет данных</span>', card)  # о чём молчит извещение — строкой со статусом
            self.assertIn('Банкротное имущество', card)
            self.assertNotIn('повторные торги</', card.split('На что обратить')[-1][:200])
            self.assertIn('/torgi/lot/mets-0/', (site/'torgi/tatarstan/povtornye-torgi/index.html').read_text())  # фасет по-прежнему собирается
            home = (site/'index.html').read_text()
            self.assertIn('Все торги недвижимостью в России', home)
            self.assertNotIn('Земельный участок', home.split('class="board"')[1].split('</div>')[0])
            self.assertTrue((site/'torgi/lot/21000000000000000001_1/index.html').exists())  # адреса ГИС Торги прежние
            self.assertIn('Земельный участок', (site/'torgi/zemlya/index.html').read_text())
            land = (site/'torgi/lot/21000000000000000001_1/index.html').read_text()
            self.assertIn('Земля: оценка вручную', land)  # оценка по квартирам к земле не применяется
            self.assertNotIn('Выгодно', land)
            self.assertIn('?buy=1', card)  # отчёт ведёт сразу к покупке в приложении
            low = (site/'torgi/lot/mets-10/index.html').read_text()
            self.assertNotIn('Иванов', low)  # ФИО должника из строки адреса убрано
            self.assertIn('Ориентир по городу', low)

if __name__ == '__main__':
    unittest.main()


class AutoSectionTests(unittest.TestCase):
    def test_make_slug_is_ascii(self):
        import importlib
        sys.path.insert(0, str(ROOT / '_src'))
        af = importlib.import_module('auto_feed')
        self.assertEqual(af.slug('Kögel'), 'kogel')  # выкладка 25.10 упала на /auto/marka/kögel/
        self.assertEqual(af.slug('Citroën'), 'citroen')
        self.assertEqual(af.slug('Škoda'), 'skoda')
        self.assertEqual(af.slug('ГАЗ'), 'gaz')
        self.assertEqual(af.slug('Тайга'), 'tayga')
        self.assertEqual(af.slug('Mercedes-Benz'), 'mercedes-benz')
        for m in ('Kögel', 'Hyundai Heavy', 'Chevrolet Niva'):
            self.assertTrue(af.slug(m).isascii())

    def test_auto_pages_from_vehicles_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copytree(ROOT / '_src', base / '_src')
            data = base / '_src/data'
            (data/'lot_history.json').write_text('[]')
            (data/'auto_history.json').write_text('[]')  # на сервере лежит живая история техники
            (data/'market.json').unlink(missing_ok=True)
            (data/'lots.json').write_text('[]')
            row = dict(source='gistorgi_auto', source_url='https://torgi.gov.ru/new/public/lots/lot/1', kind='arrest', procedure='Аукцион',
                       stage=None, title='Renault Logan 2020, VIN •••', descr='Легковой автомобиль Renault Logan, 2020 года, цвет серый. Хранится по адресу организатора.',
                       region='35', vtype='car', make='Renault', model='Logan', year=2020, has_vin=True, mileage_km=85000, hours=None,
                       purpose=None, pledge_mentioned=False, price=227000, price_start=227000, price_was=None, price_drops=0,
                       bidd_end='2099-01-01T00:00:00+00:00', first_seen='2026-10-20T00:00:00+00:00',
                       photo='https://torgi.gov.ru/new/image/1.jpg', photos=['https://torgi.gov.ru/new/image/1.jpg', 'https://torgi.gov.ru/new/image/2.jpg'], photos_count=9)
            rows = [dict(row, id=f'gistorgi_auto:{i}_1') for i in range(5)]
            rows += [dict(row, id=f'mets:{i}', source='mets', kind='bankruptcy', region='16', vtype='truck', make='КАМАЗ', model='65115', year=2012,
                          has_vin=False, mileage_km=None, pledge_mentioned=True, price=900000, price_was=1200000, price_drops=2) for i in range(4)]
            rows.append(dict(row, id='gistorgi_auto:9_1', vtype='special', make=None, model=None, year=None, region='2', price=None, photo=None, photos=[], photos_count=0,
                             descr='Экскаватор. Должник Иванов Иван Иванович, ИНН 1234567890.'))
            (data/'vehicles.json').write_text(json.dumps({'lots': rows}, ensure_ascii=False))
            subprocess.run([sys.executable, str(base/'_src/build.py')], check=True, capture_output=True)
            site = base/'_site'
            index = (site/'auto/index.html').read_text()
            self.assertIn('<h1>Автомобили и техника с торгов по всей России</h1>', index)
            self.assertIn('href="/auto/legkovye/"', index)
            self.assertIn('href="/auto/marka/renault/"', index)
            self.assertIn('href="/auto/vologodskaya-oblast/"', index)
            self.assertIn('href="/auto/snizhennaya-cena/"', index)
            self.assertIn('aria-current="page"', index.split('<nav class="nav">')[1].split('</nav>')[0])  # «Авто» в меню ведёт на раздел
            self.assertTrue((site/'auto/tatarstan/gruzovye/index.html').exists())
            self.assertTrue((site/'auto/marka/kamaz/index.html').exists())
            self.assertFalse((site/'auto/marka/index.html').exists())
            car = (site/'auto/lot/gistorgi_auto-0_1/index.html').read_text()
            self.assertIn('Renault Logan, 2020 с торгов в Вологодской области', car)
            self.assertIn('"@type": "Car"', car)
            self.assertIn('85 000 км', car)
            self.assertIn('VIN есть', car)
            self.assertIn('<meta property="og:image" content="https://torgi.gov.ru/new/image/1.jpg">', car)
            self.assertIn('https://app.torggid.ru/auto/gistorgi_auto%3A0_1?from=site_auto_check', car)
            self.assertIn('Похожие машины с торгов', car)
            truck = (site/'auto/lot/mets-0/index.html').read_text()
            self.assertIn('Грузовой автомобиль КАМАЗ 65115, 2012', truck)
            self.assertIn('упомянут залог', truck.lower())
            self.assertIn('1 200 000 ₽ → 900 000 ₽', truck)
            self.assertIn('"@type": "Vehicle"', truck)
            spec = (site/'auto/lot/gistorgi_auto-9_1/index.html').read_text()
            self.assertNotIn('Иванов', spec)  # ПДн из пересказа не выводим даже если выгрузка их пропустила
            self.assertIn('Спецтехника с торгов в Башкортостане', spec)
            self.assertIn('https://torggid.ru/sitemap-auto.xml', (site/'sitemap.xml').read_text())
            self.assertIn('https://torggid.ru/auto/legkovye/', (site/'sitemap-auto.xml').read_text())
            self.assertIn('https://torggid.ru/auto/lot/mets-0/', (site/'sitemap-auto-lots-1.xml').read_text())
            self.assertNotIn('/auto/lot/', (site/'sitemap-auto.xml').read_text())
            self.assertIn('https://torggid.ru/auto/', (site/'llms.txt').read_text())
            self.assertIn('Техника с торгов: 10 лотов', (site/'llms.txt').read_text())
            hist = json.loads((data/'auto_history.json').read_text())
            self.assertEqual(len(hist), 10)
            self.assertNotIn('excerpt_raw', hist[0])
            # лот ушёл из выгрузки: карточка остаётся, но noindex и в архиве
            (data/'vehicles.json').write_text(json.dumps({'lots': rows[1:]}, ensure_ascii=False))
            subprocess.run([sys.executable, str(base/'_src/build.py')], check=True, capture_output=True)
            gone = (site/'auto/lot/gistorgi_auto-0_1/index.html').read_text()
            self.assertIn('noindex', gone)
            self.assertIn('Результат торгов и факт продажи не подтверждены', gone)
            self.assertTrue((site/'auto/arhiv/index.html').exists())
            self.assertNotIn('https://torggid.ru/auto/lot/gistorgi_auto-0_1/', (site/'sitemap-auto-lots-1.xml').read_text())


class NoticeExcerptTests(unittest.TestCase):
    def test_excerpt_drops_personal_data(self):
        import importlib, sys
        sys.path.insert(0, str(ROOT / '_src'))
        build = importlib.import_module('build')
        text = ("Квартира, назначение жилое, общая площадь 45,2 кв. м, этаж 3. Должник Иванов Иван Иванович, ИНН 7701234567. "
                "Обременение: ипотека в пользу банка. Осмотр по согласованию, тел. +7 999 123-45-67. Петров П.П. является собственником помещения.")
        out = build.notice_excerpt(text)
        self.assertIn('общая площадь 45,2', out)
        self.assertIn('ипотека', out)
        for bad in ('Иванов', 'ИНН', '+7', 'Петров'):
            self.assertNotIn(bad, out)
        self.assertLessEqual(len(build.notice_excerpt(text * 20)), 502)
        self.assertEqual(build.notice_excerpt(None), '')
