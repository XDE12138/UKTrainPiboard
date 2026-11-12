/* Local human-review tool checks. No Pi or external URL is contacted. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('playwright');

async function main(){
  const root=path.resolve('.visual-review/2026-11-11-fonts');
  await fs.mkdir(path.join(root,'tmp'),{recursive:true});
  const context=await chromium.launchPersistentContext(path.join(root,'browser-profile'),{
    executablePath:process.env.PIBOARD_QA_BROWSER||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless:true,env:{...process.env,TMPDIR:path.join(root,'tmp')},
    args:['--disable-crash-reporter','--disable-breakpad'],
  });
  const errors=[];
  try{
    for(const [width,height] of [[1440,900],[1024,768],[390,844]]){
      const page=await context.newPage();
      page.on('pageerror',e=>errors.push(e.message));
      await page.setViewportSize({width,height});
      await page.goto('http://127.0.0.1:8092/');
      await page.waitForSelector('body[data-ready=true]');
      assert.equal(await page.locator('#selected-title').textContent(),'字符 S');
      const metadata=await page.evaluate(()=>{
        const d=JSON.parse(document.getElementById('font-data').textContent);
        return {changed:d.changed.map(item=>item.char),count:d.characters.length,
          stable:d.sizes.every(size=>d.characters.every(ch=>d.before.glyphs[size][ch].rect.slice(2).join(',')===d.after.glyphs[size][ch].rect.slice(2).join(',')))};
      });
      assert.deepEqual(metadata,{changed:['0','N','S','V','W'],count:108,stable:true});
      const pixels=()=>page.evaluate(()=>{
        const read=id=>{const c=document.getElementById(id);return Array.from(c.getContext('2d').getImageData(0,0,c.width,c.height).data).join(',')};
        return read('before-native')===read('after-native');
      });
      assert.equal(await pixels(),false,'large S raster changes');
      await page.screenshot({path:path.join(root,`review-${width}.png`),fullPage:width===390});
      await page.getByRole('radio',{name:'小',exact:true}).check();
      assert.equal(await pixels(),true,'small S is preserved');
      await page.getByRole('button',{name:'查看 N',exact:true}).click();
      assert.equal(await pixels(),false,'small N raster changes');
      assert.equal(await page.locator(':focus').getAttribute('data-char'),'N','glyph selection retains focus');
      await page.getByRole('combobox',{name:'点阵放大'}).selectOption('8');
      assert.equal(await page.locator('#after-zoom').getAttribute('width'),'120');
      await page.getByRole('button',{name:'全部',exact:true}).click();
      assert.equal(await page.locator('#glyph-list button').count(),108);
      await page.getByRole('searchbox',{name:'查找字符'}).fill('s');
      assert.equal(await page.locator('#glyph-list button').count(),2);
      await page.getByRole('searchbox',{name:'查找字符'}).fill('');
      await page.getByRole('button',{name:'查看 日',exact:true}).click();
      assert.equal(await pixels(),true,'Chinese raster is preserved');
      await page.getByRole('radio',{name:'特大',exact:true}).check();
      await page.getByRole('combobox',{name:'点阵放大'}).selectOption('4');
      await page.getByRole('button',{name:'词句',exact:true}).click();
      await page.getByRole('textbox',{name:'输入核查词句'}).fill('SWANSEA 08:35 UK');
      assert.equal(await page.locator('#invalid').isVisible(),false);
      assert.ok(await page.locator('.sample-row').count()>=10);
      await page.getByRole('combobox',{name:'词句倍率'}).selectOption('2');
      assert.equal(await page.locator('.sample-row').first().locator('canvas').first().getAttribute('height'),'126');
      await page.screenshot({path:path.join(root,`words-${width}.png`)});
      if(width===1440){
        await page.getByRole('combobox',{name:'词句倍率'}).selectOption('1');
        const checks=await page.evaluate(()=>JSON.parse(document.getElementById('font-data').textContent).boards.word_checks);
        for(let i=0;i<checks.after.length;i++){
          const check=checks.after[i];
          await page.locator(`input[name=size][value=${check.size}]`).check();
          await page.getByRole('textbox',{name:'输入核查词句'}).fill(check.text);
          const rasters=await page.locator('.sample-row').first().locator('canvas').evaluateAll(async canvases=>{
            return Promise.all(canvases.map(async c=>{
              const rgba=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
              const rgb=new Uint8Array(c.width*c.height*3);
              for(let s=0,d=0;s<rgba.length;s+=4){rgb[d++]=rgba[s];rgb[d++]=rgba[s+1];rgb[d++]=rgba[s+2];}
              const hash=await crypto.subtle.digest('SHA-256',rgb);
              return {width:c.width,height:c.height,hash:[...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,'0')).join('')};
            }));
          });
          for(const [index,phase] of ['before','after'].entries()){
            const expected=checks[phase][i];
            assert.deepEqual(rasters[index],{width:expected.width,height:expected.height,hash:expected.rgb_sha256},`${phase} ${check.size} ${check.text}: exact pygame word pixels`);
          }
        }
        console.log('PASS 24 before/after whole-string rasters match actual pygame RGB hashes');
      }
      await page.getByRole('textbox',{name:'输入核查词句'}).fill('Ω');
      assert.equal(await page.locator('#invalid').isVisible(),true);
      await page.getByRole('button',{name:'整屏',exact:true}).click();
      await page.waitForFunction(()=>document.getElementById('after-board').complete);
      assert.equal(await page.locator('#after-board').evaluate(el=>el.naturalWidth),600);
      assert.equal(await page.getByRole('radio',{name:'小',exact:true}).isDisabled(),true);
      await page.screenshot({path:path.join(root,`board-${width}.png`),fullPage:width===1440});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'no page-level horizontal overflow');
      console.log(`PASS ${width}px: actual raster comparison, four-size metadata, focus, filters, zoom, mixed-script samples and overflow`);
      await page.close();
    }
    assert.deepEqual(errors,[]);
  }finally{await context.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1});
