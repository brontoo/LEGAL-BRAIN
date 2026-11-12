"""Production UI smoke with fictional browser-intercepted API responses only.

Requires optional Playwright + Chromium; run against a local next start server.
"""
import argparse
import json
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',default='http://127.0.0.1:13000')
    args=parser.parse_args()
    if urlparse(args.base_url).hostname not in ('127.0.0.1','localhost'):
        parser.error('Only a local test server is supported')
    names=('عقد افتراضي ألف','عقد افتراضي باء')
    documents=[dict(document_name=name,document_type='خدمات',family='contracts',family_label='العقود',chunks=1,added_at='2026-01-01') for name in names]
    revision_requests=[]
    generation_requests=[]
    def api(route):
        assert 'authorization' not in route.request.headers, 'Backend token reached browser requests'
        path=urlparse(route.request.url).path
        query=parse_qs(urlparse(route.request.url).query)
        if path.endswith('/archive/overview'):
            payload={'families':[{'key':'contracts','label':'العقود','documents':2,'chunks':2,'latest_added':'2026-01-01'}]}
        elif path.endswith('/archive/documents'):
            payload={'documents':documents,'count':2,'limit':200,'truncated':False}
        elif path.endswith('/archive/chunks'):
            selected=query.get('document',[names[0]])[0]
            payload={'chunks':[{'id':names.index(selected)+1,'document_name':selected,'document_type':'خدمات','family':'contracts','family_label':'العقود','content':('هذا نص افتراضي لاختبار واجهة المستند. '+selected+' ')*30,'source_file':'fictional.txt','chunk_index':1,'created_at':'2026-01-01'}], 'count':1,'limit':200,'truncated':False}
        elif path.endswith('/generate'):
            generation_requests.append(route.request.post_data_json)
            frames=[{'type':'done','document':'هذه مسودة افتراضية لاختبار الواجهة وتتطلب مراجعة المحامي.','skill_diagnostics':{'advisory_only':True}}]
            route.fulfill(status=200,content_type='text/event-stream',body=''.join('data: '+json.dumps(f,ensure_ascii=False)+'\n\n' for f in frames))
            return
        elif path.endswith('/revisions'):
            revision_requests.append(route.request.post_data_json)
            payload={'id':'fictional-revision','edit_ratio':0.1,'word_count':12}
        else:
            payload={}
        route.fulfill(status=200,content_type='application/json',body=json.dumps(payload,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
        context.route('**/api/**',api)
        page=context.new_page()
        errors=[]
        external_fonts=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda req:external_fonts.append(req.url) if 'fonts.googleapis.com' in req.url or 'fonts.gstatic.com' in req.url else None)
        for path in ('/','/chat','/credits','/workspace','/library'):
            response=page.goto(args.base_url+path)
            assert response.status==200,(path,response.status)
            expect(page.locator('html')).to_have_attribute('lang','ar')
            expect(page.locator('html')).to_have_attribute('dir','rtl')
            assert 'dark' in page.locator('html').get_attribute('class')
        grid=page.get_by_role('button',name='عرض شبكة',exact=True)
        grid.click()
        expect(grid).to_have_attribute('aria-pressed','true')
        page.reload()
        expect(page.get_by_role('button',name='عرض شبكة',exact=True)).to_have_attribute('aria-pressed','true')
        page.get_by_role('button',name=names[0],exact=False).first.click()
        panel=page.get_by_role('dialog')
        expect(panel).to_be_visible()
        expect(panel).to_contain_text(names[0])
        page.keyboard.press('Escape')
        expect(panel).to_be_hidden()
        page.get_by_role('button',name=names[1],exact=False).first.click()
        expect(page.get_by_role('dialog')).to_contain_text(names[1])
        expect(page.get_by_role('dialog')).to_contain_text('هذا نص افتراضي')
        page.get_by_role('button',name='أغلق اللوحة').click()
        page.set_viewport_size({'width':390,'height':844})
        page.reload()
        expect(page.get_by_role('button',name='عرض قائمة',exact=True)).to_be_visible()
        page.set_viewport_size({'width':1440,'height':1000})
        page.goto(args.base_url+'/workspace')
        page.get_by_placeholder('مثال: مطالبة مالية بقيمة 20,000 درهم عن فواتير غير مسددة...').fill('طلب افتراضي لاختبار واجهة الصياغة فقط')
        page.get_by_role('button',name='ابدأ الصياغة',exact=False).click()
        expect(page.get_by_role('button',name='عدّل واحفظ نسختك',exact=False)).to_be_visible(timeout=15000)
        page.get_by_role('button',name='عدّل واحفظ نسختك',exact=False).click()
        page.get_by_role('textbox',name='نسختك المعتمدة من المستند').fill('نسخة افتراضية معدلة لاختبار حفظ التصحيح فقط.')
        page.get_by_role('button',name='احفظ التصحيح',exact=True).click()
        expect(page.get_by_text('حُفظ تصحيحك.',exact=True)).to_be_visible()
        assert generation_requests and revision_requests
        assert revision_requests[0]['session_id']
        await_fonts=page.evaluate('document.fonts.ready.then(() => document.fonts.status)')
        assert await_fonts=='loaded'
        assert not external_fonts,external_fonts
        assert not errors,errors
        browser.close()
    print('PASSED: production navigation, Arabic/RTL, local fonts, stored view hydration, document panels, mobile library controls, desktop SSE and revision session')


if __name__=='__main__': main()
