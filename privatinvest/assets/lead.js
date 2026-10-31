// Форма заявки на посадочных страницах: тот же адрес и поля, что у формы на главной.
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
