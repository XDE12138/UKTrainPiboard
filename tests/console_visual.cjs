/* Run against the isolated tests/visual_review.py console, never private state. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');

async function main() {
  const args = process.argv.slice(2);
  const arg = (name, fallback) => args.includes(name) ? args[args.indexOf(name)+1] : fallback;
  const captureOnly = args.includes('--capture-only');
  const base = arg('--base', 'http://127.0.0.1:8081');
  if (!captureOnly && !base.startsWith('http://127.0.0.1:')) throw Error('Interactions require the isolated local server');
  const out = path.resolve(arg('--out-dir', '.visual-review/2026-11-11/after/console'));
  const runtime = path.resolve('.visual-review/2026-11-11/tmp');
  await fs.mkdir(out, {recursive:true});
  await fs.mkdir(runtime, {recursive:true});
  const context = await chromium.launchPersistentContext(path.join(runtime, 'chrome-profile'), {
    executablePath: process.env.PIBOARD_QA_BROWSER || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless:true, env:{...process.env, TMPDIR:runtime},
    args:['--disable-crash-reporter', '--disable-breakpad'],
  });
  const errors = [];
  try {
    for (const [width,height] of [[1440,900],[1024,768],[768,1024],[390,844],[320,740]]) {
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      await page.setViewportSize({width,height});
      await page.goto(base);
      await page.locator('.page-card').first().waitFor();
      await page.locator('#ws-badge.ok').waitFor();
      for (const id of ['content', 'sources', 'status', 'settings']) {
        await page.locator(`${width>640 ? '.sidebar' : '.bottom-nav'} [data-page="${id}"]`).click();
        await page.locator(`#page-${id}.active`).waitFor();
        if (id==='sources') await page.locator('[data-action="toggle-source"][data-source="weather"]').click();
        const overflow = await page.evaluate(() => {
          const root = document.querySelector('.content');
          return {body:document.body.scrollWidth>innerWidth, content:root.scrollWidth>root.clientWidth+1};
        });
        assert.deepEqual(overflow,{body:false,content:false},`${width}px ${id}: horizontal overflow`);
        if (!captureOnly) {
          const broken = await page.evaluate(() => [...document.querySelectorAll('.page.active .btn, .page.active .layout-card, .nav-item')]
            .filter(el=>el.getClientRects().length && (el.scrollWidth>el.clientWidth+1 || (innerWidth<=640 && el.getBoundingClientRect().height<44)))
            .map(el=>el.textContent.trim()));
          assert.deepEqual(broken,[],`${width}px ${id}: button text or target size`);
          assert.equal(await page.evaluate(()=>[...document.images].every(img=>img.complete && img.naturalWidth>0)),true,'local icons loaded');
        }
        await page.screenshot({path:path.join(out, `${width}-${id}.png`)});
        console.log(`PASS ${width}px ${id}, no horizontal overflow`);
        if (!captureOnly && id==='sources' && [1440,390].includes(width)) {
          for (const sid of ['mock','train','weather','calendar','custom']) {
            const toggle = page.locator(`[data-action="toggle-source"][data-source="${sid}"]`);
            if (await toggle.getAttribute('aria-expanded')!=='true') await toggle.click();
            const body = page.locator(`#source-body-${sid}`);
            assert.equal(await body.isVisible(),true);
            await body.locator('input,select').last().scrollIntoViewIfNeeded();
            await page.screenshot({path:path.join(out,`${width}-source-${sid}.png`)});
            await toggle.click();
          }
          console.log(`PASS ${width}px all five source forms`);
        }
      }
      if (!captureOnly && width===390) await interactions(page,out);
      await page.close();
    }
    if (!captureOnly) {
      const page = await context.newPage();
      await page.setViewportSize({width:390,height:844});
      await page.route('**/api/state', route=>route.fulfill({status:503,contentType:'application/json',body:'{"error":"设备暂时不可用"}'}));
      await page.goto(base);
      await page.locator('#notif.error').waitFor();
      assert.equal(await page.locator('#load-state.error').isVisible(),true);
      assert.equal(await page.getByRole('button',{name:'重新连接',exact:true}).isVisible(),true);
      await page.screenshot({path:path.join(out,'390-initial-error.png')});
      await page.close();
    }
    assert.deepEqual(errors, [], 'browser JavaScript errors');
  } finally { await context.close(); }
}

async function interactions(page,out) {
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.locator('.bottom-nav [data-page="sources"]').click();
  const source = page.locator('[data-action="toggle-source"][data-source="calendar"]');
  await source.focus();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Shift+Tab');
  assert.equal(await source.evaluate(el=>getComputedStyle(el).outlineStyle),'solid');
  await page.keyboard.press('Enter');
  assert.equal(await source.getAttribute('aria-expanded'), 'true');
  assert.equal(await page.locator('[data-source="calendar"] .chevron').evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
  assert.equal(await page.locator('#field_source_calendar_ical_url').getAttribute('type'), 'password');
  const field = page.locator('#field_source_calendar_lookahead_days');
  await field.fill('5');
  const scroll = await page.locator('.content').evaluate(el => el.scrollTop);
  await page.locator('.bottom-nav [data-page="settings"]').click();
  assert.equal(await page.locator('.content').evaluate(el=>el.scrollTop),0);
  await page.locator('.bottom-nav [data-page="sources"]').click();
  assert.equal(await field.inputValue(),'5');
  assert.equal(await page.locator('.content').evaluate(el=>el.scrollTop),scroll);
  await page.locator('.bottom-nav [data-page="content"]').click();
  const custom = page.locator('[data-card="custom"]');
  await custom.getByRole('button',{name:'添加一行'}).click();
  assert.equal(await page.locator(':focus').getAttribute('class'),'row-left');
  await custom.locator('.row-left').last().fill('项目进度 Review');
  await custom.locator('.row-right').last().fill('11:30');
  await page.screenshot({path:path.join(out,'390-custom-edit.png')});
  const save = custom.getByRole('button',{name:'保存并刷新'});
  await page.route('**/api/source/custom/config?wait=1',async route=>{
    await new Promise(resolve=>setTimeout(resolve,350));
    await route.continue();
  });
  await save.scrollIntoViewIfNeeded();
  const before = await save.boundingBox();
  await save.click();
  await page.waitForFunction(()=>document.querySelector('[data-card="custom"] [aria-busy="true"]'));
  const during = await save.boundingBox();
  assert.equal(during.width,before.width,'button width stays stable during save');
  await page.locator('#notif.success').waitFor();
  await page.unroute('**/api/source/custom/config?wait=1');
  await page.route('**/api/source/custom/config?wait=1',route=>route.fulfill({status:502,contentType:'application/json',body:'{"error":"刷新失败，请稍后重试。"}'}));
  await custom.locator('.row-left').last().fill('Keep this edit');
  await save.click();
  await page.locator('#notif.error').waitFor();
  assert.equal(await custom.locator('.row-left').last().inputValue(),'Keep this edit');
  const toast = await page.locator('#notif').boundingBox();
  const nav = await page.locator('.bottom-nav').boundingBox();
  assert.ok(toast.y+toast.height<=nav.y,'notification clears mobile navigation');
  await page.screenshot({path:path.join(out,'390-save-error.png')});
  await page.unroute('**/api/source/custom/config?wait=1');
  await page.locator('.bottom-nav [data-page="settings"]').click();
  const toggle = page.getByRole('switch');
  await toggle.check();
  assert.equal(await page.locator('#animation-state').textContent(),'开启连续动画');
  await toggle.uncheck();
  assert.equal(await page.locator('#animation-state').textContent(),'关闭（低功耗）');
  await page.getByRole('button',{name:'双栏',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'双栏',exact:true}).getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('[id^="slot_"]').count(),2);
  await page.getByRole('button',{name:'系统状态',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[data-app="system_status"]').getAttribute('aria-pressed')==='true');
  await page.getByRole('button',{name:'展示看板',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[data-app="uk_station"]').getAttribute('aria-pressed')==='true');
  console.log('PASS keyboard accordion, masking, scroll restoration, editing, stable save, error retention, toast placement, layout selection, reduced motion');
}

main().catch(error=>{console.error(error);process.exitCode=1});
