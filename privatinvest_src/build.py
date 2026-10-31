"""Сборка посадочных страниц privateinvest.pro из pages.py.

Запуск из корня репозитория:  python3 privatinvest_src/build.py
Пишет privatinvest/<slug>/index.html, privatinvest/assets/site.css, privatinvest/sitemap.xml, privatinvest/404.html.
Стили и код Метрики берутся из privatinvest/index.html, чтобы страницы выглядели и считались так же, как главная.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pages import PAGES, GROUPS, UPDATED  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "privatinvest"
BASE = "https://privateinvest.pro"
BRAND = "Приватинвест"
LEGAL = ("Услуги по привлечению инвестиций оказывают операторы инвестиционных платформ, включённые в реестр Банка России; "
         "оператор конкретного проекта указывается в его описании и в договоре. Приватинвест отбирает, проверяет и сопровождает "
         "сделки, управляет залогом. Ставка указана по договору и не является гарантированной доходностью. Инвестиции через "
         "платформу высокорискованны и могут привести к потере вложенных средств полностью. Информация на сайте не является "
         "публичной офертой и индивидуальной инвестиционной рекомендацией.")

EXTRA_CSS = """
/* ---- посадочные страницы и статьи (privatinvest_src/build.py) ---- */
.crumbs{font-family:var(--f-mono);font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);display:flex;gap:8px;flex-wrap:wrap;padding-top:22px}
.crumbs a{text-decoration:none}.crumbs a:hover{color:var(--copper-deep)}
.lp-hero{padding-block:22px 34px;border-bottom:1px solid var(--hair)}
.lp-hero .wrap>div{display:grid;gap:18px;max-width:52em}
.lp-hero .lead{font-size:1.08rem}
.lp-hero .btns{display:flex;gap:10px;flex-wrap:wrap}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:6px}
.kpis div{border:1px solid var(--hair);background:var(--card);padding:12px 14px;border-radius:var(--r);display:grid;gap:2px}
.kpis b{font-family:var(--f-display);font-weight:700;font-size:1.6rem;line-height:1}
.kpis span{font-size:.8rem;color:var(--muted)}
@media (max-width:700px){.kpis{grid-template-columns:repeat(2,1fr)}}
.lp{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:40px;padding-block:36px}
@media (max-width:960px){.lp{grid-template-columns:1fr}}
.doc{display:grid;gap:34px;min-width:0}
.doc section{display:grid;gap:14px}
.doc h2{font-size:clamp(1.6rem,3.2vw,2.2rem)}
.doc h3{font-size:1.2rem}
.doc p,.doc li{font-size:1rem;max-width:44em}
.doc ul,.doc ol{margin:0;padding:0;list-style:none;display:grid;gap:9px}
.doc a{color:var(--copper-deep)}
.ticks li,.crosses li{padding-left:24px;position:relative}
.ticks li::before{content:"✓";position:absolute;left:0;color:var(--emerald);font-family:var(--f-mono);font-weight:700}
.crosses li::before{content:"✕";position:absolute;left:0;color:var(--bad);font-family:var(--f-mono);font-weight:700}
.steps-list{counter-reset:s}
.steps-list li{counter-increment:s;padding-left:40px;position:relative;min-height:28px}
.steps-list li::before{content:counter(s);position:absolute;left:0;top:-2px;font-family:var(--f-display);font-weight:700;font-size:1.5rem;color:var(--copper);line-height:1}
.cards3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
@media (max-width:760px){.cards3{grid-template-columns:1fr}}
.tile{display:grid;gap:4px;padding:14px;border:1px solid var(--hair);background:var(--card);border-radius:var(--r);text-decoration:none;color:var(--text)!important}
a.tile:hover{border-color:var(--copper)}
.tile b{font-family:var(--f-display);font-weight:700;font-size:1.2rem;text-transform:uppercase}
.tile span{font-size:.86rem;color:var(--muted)}
.calc-ex{border:1px solid var(--hair);display:grid;background:var(--card);border-radius:var(--r);max-width:36em}
.calc-ex div{display:flex;justify-content:space-between;gap:14px;padding:11px 14px;border-top:1px solid var(--hair);font-variant-numeric:tabular-nums}
.calc-ex div:first-child{border-top:0}
.calc-ex b{font-family:var(--f-display);font-size:1.25rem;text-align:right}
.cmp{overflow-x:auto;border:1px solid var(--hair);border-radius:var(--r);background:var(--card)}
.cmp table{border-collapse:collapse;width:100%;min-width:560px;font-size:.9rem}
.cmp th,.cmp td{padding:10px 12px;border-top:1px solid var(--hair);text-align:left;vertical-align:top}
.cmp thead th{border-top:0;font-family:var(--f-mono);font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:500}
.cmp td:first-child{font-weight:600}
.grid2-doc{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.grid2-doc>div{display:grid;gap:10px;align-content:start}
@media (max-width:760px){.grid2-doc{grid-template-columns:1fr}}
.faq-list{display:grid;gap:8px}
.aside{display:grid;gap:14px;align-content:start}
@media (min-width:961px){.aside{position:sticky;top:90px}}
.aside nav{display:grid;gap:2px}
.aside nav a{padding:7px 0;border-bottom:1px solid var(--hair);text-decoration:none;font-size:.9rem}
.aside nav a:hover{color:var(--copper-deep)}
.related{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
.art-list{display:grid;gap:12px}
.art-list a{display:grid;gap:4px;padding:16px;border:1px solid var(--hair);background:var(--card);border-radius:var(--r);text-decoration:none;color:var(--text)!important}
.art-list a:hover{border-color:var(--copper)}
.art-list b{font-family:var(--f-display);font-weight:700;font-size:1.35rem;text-transform:uppercase;line-height:1.05}
.art-list span{color:var(--muted);font-size:.9rem}
.lp-lead{border-top:1px solid var(--hair);background:var(--cream)}
.foot-nav{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:18px}
.foot-nav div{display:grid;gap:6px;align-content:start}
.foot-nav b{font-family:var(--f-mono);font-weight:500;font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:var(--band-muted)}
.foot-nav a{text-decoration:none;color:var(--band-text);font-size:.86rem}
.foot-nav a:hover{color:var(--copper)}
.top .nav a[aria-current]{color:var(--copper-deep);box-shadow:inset 0 -2px 0 var(--copper)}
"""

LEAD_JS = r"""// Форма заявки на посадочных страницах: тот же адрес и поля, что у формы на главной.
(function(){
  var API='https://check.kirpichinvest.ru/public/';
  var form=document.getElementById('lead-form');if(!form)return;
  var msg=document.getElementById('l-msg'),cta='';
  function syncRole(){var r=form.querySelector('input[name=role]:checked').value;
    form.querySelectorAll('[data-for]').forEach(function(el){el.hidden=el.dataset.for.split(' ').indexOf(r)<0})}
  form.addEventListener('change',function(e){if(e.target.name==='role')syncRole()});
  syncRole();
  document.addEventListener('click',function(e){
    var ld=e.target.closest('[data-lead]');if(!ld)return;e.preventDefault();
    var radio=form.querySelector('input[name=role][value="'+ld.dataset.lead+'"]');if(radio)radio.checked=true;syncRole();
    cta=ld.textContent.trim();if(window.piGoal)piGoal('form_open',{role:ld.dataset.lead});
    document.getElementById('s-lead').scrollIntoView({behavior:'smooth',block:'start'});
    setTimeout(function(){document.getElementById('l-name').focus({preventScroll:true})},400);
  });
  form.addEventListener('submit',function(e){
    e.preventDefault();
    var contact=document.getElementById('l-contact').value.trim();
    if(contact.replace(/\D/g,'').length<10&&contact.indexOf('@')<0){msg.textContent='Укажите телефон (10 цифр) или Telegram через @';return}
    if(!document.getElementById('l-consent').checked){msg.textContent='Отметьте согласие на обработку данных';return}
    var role=form.querySelector('input[name=role]:checked').value,fd=new FormData();
    fd.append('scenario',role);fd.append('name',document.getElementById('l-name').value.trim());fd.append('contact',contact);
    fd.append('consent','1');fd.append('website',document.getElementById('l-website').value);fd.append('page',location.href);
    try{var ft=JSON.parse(localStorage.getItem('pi_ft')||'{}');fd.append('utm',ft.utm||'');fd.append('referrer',ft.referrer||'');fd.append('landing',ft.landing||'')}catch(e){}
    fd.append('cta',(cta||'форма внизу страницы')+' · '+location.pathname);
    form.querySelectorAll('[data-for]').forEach(function(el){if(el.hidden)return;var i=el.querySelector('input');if(i&&i.value.trim())fd.append(i.name,i.value.trim())});
    var btn=document.getElementById('l-send');btn.disabled=true;msg.textContent='Отправляем…';
    fetch(API+'lead',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(j){
      if(j&&j.ok){msg.textContent='Заявка принята. Мы свяжемся с вами по указанному контакту.';if(window.piGoal){piGoal('lead_'+role);piGoal('lead')}form.reset();form.querySelector('input[value="'+role+'"]').checked=true;syncRole();cta=''}
      else{msg.textContent=(j&&j.error)||'Не получилось отправить, попробуйте ещё раз'}
    }).catch(function(){msg.textContent='Нет связи с сервером, попробуйте ещё раз через минуту'}).then(function(){btn.disabled=false});
  });
})();
"""


def esc(s):
    return html.escape(s, quote=True)


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def url(slug):
    return BASE + "/" + (slug + "/" if slug else "")


def href(slug):
    return "/" + (slug + "/" if slug else "")


def from_home():
    src = (SITE / "index.html").read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", src, re.S).group(1)
    m = re.search(r"(<script>\s*// первое касание.*?<!-- /Yandex\.Metrika counter -->)", src, re.S)
    if not m or "ym(113877734, 'init'" not in m.group(1):
        raise SystemExit("Не нашёл код Метрики в privatinvest/index.html")
    fonts = re.search(r'(<link rel="stylesheet" href="https://fonts\.googleapis\.com[^>]+>)', src).group(1)
    verif = re.search(r'(<meta name="yandex-verification"[^>]+>)', src).group(1)
    return css, m.group(1), fonts, verif


def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "</script>"


ORG = {"@type": "Organization", "@id": BASE + "/#org", "name": BRAND, "url": BASE + "/",
       "logo": BASE + "/icon-512.png",
       "description": "Отбор, проверка и сопровождение займов под залог недвижимости через операторов инвестиционных платформ из реестра Банка России."}


def header(cur):
    items = [("zaim-pod-zalog-nedvizhimosti", "Заёмщикам"), ("investicii-pod-zalog-nedvizhimosti", "Инвесторам"),
             ("brokeram", "Брокерам"), ("kak-my-proveryaem", "Проверка"), ("stati", "Статьи")]
    nav = "".join('<a href="%s"%s>%s</a>' % (href(s), ' aria-current="page"' if s == cur or cur.startswith(s + "/") else "", t)
                  for s, t in items)
    return ('<header class="top"><div class="wrap">'
            '<a class="logo" href="/"><b>Приватинвест</b><span>займы под залог · через платформы из реестра ЦБ</span></a>'
            '<nav class="nav" aria-label="Разделы"><a href="/">Витрина</a>' + nav + '</nav>'
            '<div class="top-actions"><a class="btn btn-sm" href="#s-lead" data-lead="%s">Оставить заявку</a></div>'
            '</div></header>')


def footer_nav():
    cols = []
    for title, slugs in GROUPS:
        links = "".join('<a href="%s">%s</a>' % (href(s), esc(PAGES[s]["menu"])) for s in slugs)
        cols.append("<div><b>%s</b>%s</div>" % (esc(title), links))
    return '<nav class="foot-nav" aria-label="Карта сайта"><div><b>Приватинвест</b><a href="/">Витрина заявок</a><a href="/#s-lead">Оставить заявку</a></div>' + "".join(cols) + "</nav>"


def footer():
    return ('<footer><div class="wrap">' + footer_nav() +
            '<p class="legal">' + LEGAL + '</p><p class="mono">Приватинвест · © 2026</p></div></footer>')


def lead_form(role):
    def r(v, label):
        return ('<label class="role-pick"><input type="radio" name="role" value="%s"%s> <b>%s</b></label>'
                % (v, " checked" if v == role else "", label))
    return ('<section class="sec lp-lead" id="s-lead"><div class="wrap">'
            '<div class="sec-head"><div><span class="eyebrow">Заявка</span><h2>Оставьте контакт, <em>мы перезвоним</em></h2></div>'
            '<p class="sub">Ответим в рабочее время, обычно в тот же день. Проверка и отказ бесплатны. Данные нужны только для связи по вашей заявке.</p></div>'
            '<form class="side-box" id="lead-form" novalidate>'
            '<div class="roles" role="radiogroup" aria-label="Кто вы">' + r("pi_borrow", "Мне нужен заём") + r("pi_invest", "Я инвестор") + r("pi_broker", "Я брокер") + '</div>'
            '<div class="form">'
            '<label class="field"><span>Имя</span><input id="l-name" name="name" autocomplete="name" maxlength="100"></label>'
            '<label class="field"><span>Телефон или Telegram</span><input id="l-contact" name="contact" autocomplete="tel" maxlength="100" required></label>'
            '<label class="field" data-for="pi_invest"><span>Сумма участия, ₽</span><input id="l-amount" name="Сумма участия" inputmode="numeric" placeholder="от 100 000" maxlength="20"></label>'
            '<label class="field" data-for="pi_broker pi_borrow"><span>Объект и город</span><input id="l-object" name="Объект" placeholder="квартира 60 м², Москва" maxlength="200"></label>'
            '<label class="field" data-for="pi_broker pi_borrow"><span>Сумма займа, ₽</span><input id="l-loan" name="Сумма займа" inputmode="numeric" placeholder="3 000 000" maxlength="20"></label>'
            '</div>'
            '<input type="text" name="website" id="l-website" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px" aria-hidden="true">'
            '<label class="stopf" style="font-size:.86rem"><span style="display:flex;gap:10px"><input type="checkbox" name="consent" value="1" id="l-consent"> Согласен на обработку персональных данных для связи по заявке</span></label>'
            '<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><button class="btn btn-copper" type="submit" id="l-send">Отправить</button>'
            '<span id="l-msg" class="mono" style="text-transform:none;letter-spacing:0" role="status"></span></div>'
            '</form></div></section>')


def faq_html(items):
    return '<div class="faq-list">' + "".join(
        "<details><summary>%s</summary><p>%s</p></details>" % (esc(q), a) for q, a in items) + "</div>"


def crumbs_for(p):
    trail = [("", "Главная")]
    if p["slug"].startswith("stati/"):
        trail.append(("stati", "Статьи"))
    trail.append((p["slug"], p["menu"]))
    return trail


def render(p, head_bits):
    css_link, metrika, fonts, verif = head_bits
    slug, role = p["slug"], p["role"]
    trail = crumbs_for(p)
    title_txt = strip_tags(p["h1"])
    cta = {"pi_borrow": "Оставить заявку на заём", "pi_invest": "Хочу участвовать", "pi_broker": "Передать клиента"}[role]

    ld = [ORG, {"@type": "WebSite", "@id": BASE + "/#site", "url": BASE + "/", "name": BRAND, "inLanguage": "ru", "publisher": {"@id": BASE + "/#org"}},
          {"@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": i + 1, "name": n, "item": url(s)} for i, (s, n) in enumerate(trail)]}]
    if p["kind"] == "article":
        ld.append({"@type": "Article", "headline": title_txt, "description": p["desc"], "inLanguage": "ru",
                   "datePublished": p["date"], "dateModified": p.get("modified", p["date"]),
                   "mainEntityOfPage": url(slug), "author": {"@id": BASE + "/#org"}, "publisher": {"@id": BASE + "/#org"},
                   "image": BASE + "/icon-512.png"})
    elif p["kind"] == "service":
        ld.append({"@type": "WebPage", "@id": url(slug), "url": url(slug), "name": p["title"], "description": p["desc"],
                   "inLanguage": "ru", "isPartOf": {"@id": BASE + "/#site"}, "about": {"@id": BASE + "/#org"}, "dateModified": UPDATED})
    faqs = list(p.get("faq") or [])
    for _, items in p.get("faq_groups") or []:
        faqs += items
    if faqs:
        ld.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}} for q, a in faqs]})

    crumbs = '<nav class="crumbs" aria-label="Навигация">' + ' <span>/</span> '.join(
        ('<a href="%s">%s</a>' % (href(s), esc(n)) if i < len(trail) - 1 else '<span aria-current="page">%s</span>' % esc(n))
        for i, (s, n) in enumerate(trail)) + "</nav>"
    kpis = ""
    if p.get("facts"):
        kpis = '<div class="kpis">' + "".join("<div><b>%s</b><span>%s</span></div>" % (esc(a), esc(b)) for a, b in p["facts"]) + "</div>"
    meta_line = ""
    if p["kind"] == "article":
        d = p["date"].split("-")
        meta_line = '<span class="mono">Опубликовано %s.%s.%s · Приватинвест</span>' % (d[2], d[1], d[0])
    hero = ('<section class="lp-hero"><div class="wrap">' + crumbs + '<div style="margin-top:14px">'
            '<span class="eyebrow">%s</span><h1>%s</h1><p class="lead">%s</p>%s%s'
            '<div class="btns"><a class="btn btn-copper" href="#s-lead" data-lead="%s">%s</a><a class="btn btn-ghost" href="/">Смотреть витрину</a></div>'
            '</div></div></section>') % (esc(p["eyebrow"]), p["h1"], p["lead"], meta_line, kpis, role, cta)

    body = []
    for h2, content in p.get("sections") or []:
        body.append("<section><h2>%s</h2>%s</section>" % (esc(h2), content.strip()))
    if p["kind"] == "hub":
        arts = [s for s in PAGES.values() if s["kind"] == "article"]
        body.append('<section><div class="art-list">' + "".join(
            '<a href="%s"><b>%s</b><span>%s</span></a>' % (href(a["slug"]), strip_tags(a["h1"]), esc(a["desc"])) for a in arts) + "</div></section>")
    if p.get("faq"):
        body.append("<section><h2>Частые вопросы</h2>%s</section>" % faq_html(p["faq"]))
    for gt, items in p.get("faq_groups") or []:
        body.append("<section><h2>%s</h2>%s</section>" % (esc(gt), faq_html(items)))
    if p.get("related"):
        body.append('<section><h2>Читайте также</h2><div class="related">' + "".join(
            '<a class="tile" href="%s"><b>%s</b><span>%s</span></a>' % (href(r), esc(PAGES[r]["menu"]), esc(PAGES[r]["desc"][:110].rsplit(" ", 1)[0] + "…"))
            for r in p["related"]) + "</div></section>")

    aside_links = []
    for gt, slugs in GROUPS[:2]:
        aside_links.append('<div class="side-box"><h3>%s</h3><nav>%s</nav></div>' % (esc(gt), "".join(
            '<a href="%s"%s>%s</a>' % (href(s), ' aria-current="page"' if s == slug else "", esc(PAGES[s]["menu"])) for s in slugs)))
    aside = ('<aside class="aside"><div class="side-box"><h3>Нужна консультация?</h3><p>Ответ за два рабочих дня, проверка бесплатно.</p>'
             '<a class="btn btn-copper btn-sm" href="#s-lead" data-lead="%s">%s</a></div>%s</aside>') % (role, cta, "".join(aside_links))

    og = "".join('<meta property="%s" content="%s">' % (k, esc(v)) for k, v in [
        ("og:type", "article" if p["kind"] == "article" else "website"), ("og:site_name", BRAND), ("og:locale", "ru_RU"),
        ("og:title", p["title"]), ("og:description", p["desc"]), ("og:url", url(slug)), ("og:image", BASE + "/icon-512.png")])

    return "\n".join([
        "<!doctype html>", '<html lang="ru">', "<head>", '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        '<meta name="robots" content="index,follow">',
        "<title>%s</title>" % esc(p["title"]),
        '<meta name="description" content="%s">' % esc(p["desc"]),
        '<link rel="canonical" href="%s">' % url(slug), og, verif,
        '<link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" href="/favicon.svg" type="image/svg+xml">',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="manifest" href="/site.webmanifest">',
        '<meta name="theme-color" content="#0E1A24">',
        metrika, fonts, css_link, jsonld({"@context": "https://schema.org", "@graph": ld}),
        "</head>", "<body>",
        header(slug) % role,
        "<main>", hero,
        '<div class="wrap lp"><article class="doc">' + "".join(body) + "</article>" + aside + "</div>",
        lead_form(role), "</main>", footer(),
        '<script src="/assets/lead.js?v=%s" defer></script>' % UPDATED.replace("-", ""),
        "</body>", "</html>", ""])


def page_404(head_bits):
    css_link, metrika, fonts, _ = head_bits
    links = "".join('<li><a href="%s">%s</a></li>' % (href(s), esc(PAGES[s]["menu"])) for s in GROUPS[0][1][:3] + GROUPS[1][1][:2])
    return "\n".join(["<!doctype html>", '<html lang="ru">', "<head>", '<meta charset="utf-8">',
                      '<meta name="viewport" content="width=device-width,initial-scale=1">', '<meta name="robots" content="noindex,follow">',
                      "<title>Страница не найдена · Приватинвест</title>", '<link rel="icon" href="/favicon.ico" sizes="any">',
                      metrika, fonts, css_link, "</head><body>", header("") % "pi_borrow",
                      '<main><section class="lp-hero"><div class="wrap"><div style="margin-top:22px"><span class="eyebrow">404</span>'
                      "<h1>Страница <em>не найдена</em></h1><p class=\"lead\">Возможно, адрес изменился. Начните с главной или с разделов ниже.</p>"
                      '<div class="btns"><a class="btn btn-copper" href="/">На главную</a></div></div></div></section>'
                      '<div class="wrap lp"><article class="doc"><ul class="ticks">' + links + "</ul></article></div></main>",
                      footer(), "</body></html>", ""])


def sitemap():
    rows = ['  <url><loc>%s/</loc><lastmod>%s</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>' % (BASE, UPDATED)]
    for s, p in PAGES.items():
        pr = "0.9" if p["kind"] == "service" else ("0.6" if p["kind"] == "hub" else "0.7")
        rows.append("  <url><loc>%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>" % (url(s), p.get("modified", p.get("date", UPDATED)), pr))
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"


def main():
    css, metrika, fonts, verif = from_home()
    (SITE / "assets").mkdir(exist_ok=True)
    (SITE / "assets" / "site.css").write_text(css.strip() + "\n" + EXTRA_CSS.lstrip(), encoding="utf-8")
    (SITE / "assets" / "lead.js").write_text(LEAD_JS, encoding="utf-8")
    bits = ('<link rel="stylesheet" href="/assets/site.css?v=%s">' % UPDATED.replace("-", ""), metrika, fonts, verif)
    for slug, p in PAGES.items():
        for k in p.get("related", []):
            assert k in PAGES, (slug, k)
        out = SITE / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(p, bits), encoding="utf-8")
    (SITE / "404.html").write_text(page_404(bits), encoding="utf-8")
    (SITE / "sitemap.xml").write_text(sitemap(), encoding="utf-8")
    print("pages:", len(PAGES))


if __name__ == "__main__":
    main()
