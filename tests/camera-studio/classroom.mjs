import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import path from 'node:path';
export async function classroom(url) {
  const dependencies=createRequire(path.resolve(process.env.CAMERA_TEST_DEPS,'package.json'));
  const { chromium }=dependencies('playwright-core');
  const browser=await chromium.launch({channel:'chrome',headless:true,timeout:30000});
  try{
    const page=await browser.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);
    await page.locator('#entry-continue').waitFor();
    assert.match(await page.locator('#entry-title').textContent(),/已有课堂工位/);
    await page.locator('#entry-practice').click();
    await page.waitForFunction(()=>document.querySelector('#entry-title')?.textContent==='独立练习');
    await page.locator('#entry-practice').click();
    const options=page.locator('#isp-demo-tabs button');
    assert.equal(await options.count(),5);
    for(const item of await options.all()){
      await item.click();
      assert.equal(await item.getAttribute('aria-pressed'),'true');
    }
    await page.locator('#entry-continue').click();
    await page.waitForURL(url);await page.locator('#entry-continue').click();
    assert.ok((await page.locator('#step-title').textContent()).trim());
    assert.deepEqual(errors,[]);
    console.log('Verified resume, independent practice, five ISP samples and return to original station');
  }finally{await browser.close();}
}
