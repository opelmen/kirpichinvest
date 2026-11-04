const {chromium}=require('playwright');const fs=require('fs');
const logo='data:image/svg+xml;base64,'+fs.readFileSync('/mnt/project-files/brand/torggid/logo-light.svg').toString('base64');
const sizes={'4x5':[1080,1350],'4x3':[1440,1080],'1x1':[1080,1080]};
// focus: background-position по каждому фото
const imgs={'auto-msk-landcruiser':'30% 60%','auto-kazan-audi':'50% 45%','auto-krd-corolla':'85% 35%','flat-msk-borisovskie':'50% 40%','flat-mo-goluboe':'50% 45%','flat-krd-artezianskaya':'40% 50%','flat-krd-artezianskaya2':'50% 40%'};
(async()=>{const b=await chromium.launch();const p=await b.newPage();fs.mkdirSync('out',{recursive:true});
for(const [k,pos] of Object.entries(imgs)){const src='data:image/jpeg;base64,'+fs.readFileSync(k+'.jpg').toString('base64');
 for(const [sz,[w,h]] of Object.entries(sizes)){
  const html=`<html><body style="margin:0"><div style="position:relative;width:${w}px;height:${h}px;background:url(${src}) ${pos}/cover no-repeat"><div style="position:absolute;left:36px;top:36px;background:rgba(255,255,255,.94);border-radius:18px;padding:16px 20px;box-shadow:0 4px 18px rgba(0,0,0,.18)"><img src="${logo}" style="width:230px;display:block"></div></div></body></html>`;
  await p.setViewportSize({width:w,height:h});await p.setContent(html);await p.waitForTimeout(200);
  await p.screenshot({path:`out/${k}-${sz}.jpg`,type:'jpeg',quality:90});}}
await b.close();})();
