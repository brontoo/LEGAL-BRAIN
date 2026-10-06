-- ==============================================================================
-- LEGAL-BRAIN — مخطط قاعدة المعرفة (Supabase / PostgreSQL + pgvector)
-- ==============================================================================
-- الغرض: إعادة بناء قاعدة المعرفة من الصفر. هذا الملف كان غائباً تماماً من
--        المستودع، مما جعل المشروع غير قابل لإعادة الإنتاج.
--
-- التنفيذ:
--     Supabase Dashboard → SQL Editor → الصق الملف كاملاً → Run
--     أو:  psql "$SUPABASE_DB_URL" -f schema.sql
--
-- آمن للتشغيل أكثر من مرة (idempotent): يستخدم IF NOT EXISTS و CREATE OR REPLACE.
--
-- ملاحظات معمارية:
--   * بُعد المتجه 1024 لأن النموذج intfloat/multilingual-e5-large ينتج 1024 بُعداً.
--   * النموذج e5 ينتج متجهات مُعيَّرة (normalized)، لذا المسافة الجيبية (cosine)
--     هي المقياس الصحيح — لذلك نستخدم عامل التشغيل <=> وفهرس vector_cosine_ops.
--   * النموذج يتطلب بادئة "passage: " عند التخزين و"query: " عند السؤال.
--     هذا مطبَّق بشكل صحيح في كل سكربتات الاستيعاب وفي legal_agent.py.
-- ==============================================================================


-- ------------------------------------------------------------------------------
-- ٠. الامتداد المطلوب
-- ------------------------------------------------------------------------------
create extension if not exists vector;


-- ------------------------------------------------------------------------------
-- ١. جدول التشريعات والأحكام  (legal_documents)
--    المصدر: html_ingester.py / ingest_documents.py / pdf_ingester.py
--    الوحدة: مادة قانونية واحدة لكل صف
-- ------------------------------------------------------------------------------
create table if not exists legal_documents (
    id            bigint generated always as identity primary key,
    document_name text        not null,
    document_type text,
    chunk_content text        not null,
    metadata      jsonb       not null default '{}'::jsonb,
    source_file   text,
    embedding     vector(1024),
    created_at    timestamptz not null default now()
);

comment on table  legal_documents is 'التشريعات الاتحادية والأحكام القضائية — وحدة التقطيع: المادة';
comment on column legal_documents.metadata is 'بيانات وصفية: article, source_file, document_type';


-- ------------------------------------------------------------------------------
-- ٢. جدول المذكرات والمسودات  (legal_drafts)
--    المصدر: drafts_ingester.py
--    الوحدة: مقطع 400 كلمة بتداخل 50 — للحفاظ على ترابط الأسلوب
-- ------------------------------------------------------------------------------
create table if not exists legal_drafts (
    id            bigint generated always as identity primary key,
    document_name text        not null,
    document_type text,
    chunk_content text        not null,
    metadata      jsonb       not null default '{}'::jsonb,
    source_file   text,
    embedding     vector(1024),
    created_at    timestamptz not null default now()
);

comment on table legal_drafts is 'مذكرات الدفاع واللوائح — تُستخدم لاستنساخ أسلوب الصياغة';


-- ------------------------------------------------------------------------------
-- ٣. جدول العقود والاتفاقيات  (legal_contracts)
--    المصدر: contracts_ingester.py
--    الوحدة: بند/مادة مستقلة
-- ------------------------------------------------------------------------------
create table if not exists legal_contracts (
    id            bigint generated always as identity primary key,
    document_name text        not null,
    document_type text,
    chunk_content text        not null,
    metadata      jsonb       not null default '{}'::jsonb,
    source_file   text,
    embedding     vector(1024),
    created_at    timestamptz not null default now()
);

comment on table legal_contracts is 'العقود والاتفاقيات والملاحق — وحدة التقطيع: البند/المادة';


-- ------------------------------------------------------------------------------
-- ٤. جدول الإنذارات  (legal_notices)
--    المصدر: notices_ingester.py
--    الوحدة: قسم مستقل (المنذر / الموضوع / الوقائع / الطلبات)
-- ------------------------------------------------------------------------------
create table if not exists legal_notices (
    id            bigint generated always as identity primary key,
    document_name text        not null,
    document_type text,
    chunk_content text        not null,
    metadata      jsonb       not null default '{}'::jsonb,
    source_file   text,
    embedding     vector(1024),
    created_at    timestamptz not null default now()
);

comment on table legal_notices is 'الإنذارات القانونية والعدلية — وحدة التقطيع: القسم';


-- ------------------------------------------------------------------------------
-- ٥. جدول الوكالات  (legal_poa)
--    المصدر: poa_ingester.py
--    الوحدة: صلاحية مستقلة
-- ------------------------------------------------------------------------------
create table if not exists legal_poa (
    id            bigint generated always as identity primary key,
    document_name text        not null,
    document_type text,
    chunk_content text        not null,
    metadata      jsonb       not null default '{}'::jsonb,
    source_file   text,
    embedding     vector(1024),
    created_at    timestamptz not null default now()
);

comment on table legal_poa is 'الوكالات والتوكيلات والتفويضات — وحدة التقطيع: الصلاحية';


-- ==============================================================================
-- ٥-ب. ترقية قاعدة بيانات موجودة (Top-up for an existing database)
-- ==============================================================================
-- ⚠️ مهم: عبارات `create table if not exists` أعلاه **لا تضيف أعمدة** إلى جدول
--    موجود بالفعل — إن كان الجدول موجوداً فإن العبارة كلها تُتجاهل. لذا إن كانت
--    قاعدة بياناتك أُنشئت قبل هذا الملف، فلن تُضاف الأعمدة الناقصة تلقائياً.
--
--    هذه الكتلة تكمّل النقص بأمان، وهي idempotent: لا تفعل شيئاً إن كان العمود
--    موجوداً. لا تحذف بيانات ولا تُغيّر نوع أي عمود.
--
-- لماذا source_file؟ لأن contracts_ingester.py كان يفحص وجود الملف عبر
-- source_file قبل الرفع دون أن يكتبه، فأُصلح ليكتبه. فإن لم يكن العمود موجوداً
-- في legal_contracts سيفشل الإدخال بخطأ "column source_file does not exist".
--
-- ⚠️ وسبب إضافة document_type وcreated_at هنا: ظهور خطأ حقيقي عند تنفيذ
--    القسم ١١ — `column "created_at" does not exist` في legal_drafts.
--    فالكتلة كانت تنقص عمودين تحتاجهما دالّتا الأرشيف، ولم يكن أحد يعلم حتى
--    شُغِّلتا. والقاعدة: كل عمود في `create table` أعلاه يجب أن يقابله
--    `add column if not exists` هنا — وإلا بقي النقص صامتاً في قواعد قديمة.

alter table legal_documents add column if not exists source_file   text;
alter table legal_drafts    add column if not exists source_file   text;
alter table legal_contracts add column if not exists source_file   text;
alter table legal_notices   add column if not exists source_file   text;
alter table legal_poa       add column if not exists source_file   text;

alter table legal_documents add column if not exists document_type text;
alter table legal_drafts    add column if not exists document_type text;
alter table legal_contracts add column if not exists document_type text;
alter table legal_notices   add column if not exists document_type text;
alter table legal_poa       add column if not exists document_type text;

-- ⚠️ وملاحظة صريحة عن `default now()`: الصفوف الموجودة **ستأخذ كلها وقت تنفيذ
--    هذا الأمر**. فعمود «أُضيف في» يكون دقيقاً للصفوف المرفوعة **بعد** التعديل،
--    ويُظهر وقت التعديل للقديمة. وهذا أفضل من غياب العمود، وأصدق من اختلاق تاريخ.
alter table legal_documents add column if not exists created_at timestamptz not null default now();
alter table legal_drafts    add column if not exists created_at timestamptz not null default now();
alter table legal_contracts add column if not exists created_at timestamptz not null default now();
alter table legal_notices   add column if not exists created_at timestamptz not null default now();
alter table legal_poa       add column if not exists created_at timestamptz not null default now();


-- ==============================================================================
-- ٦. الفهارس
-- ==============================================================================
-- ملاحظة: أعمدة source_file مُضافة إلى الجداول الخمسة لأن كل سكربتات الاستيعاب
--        تفحص وجود الملف قبل الرفع (idempotency). كانت contracts_ingester.py
--        تبحث عن source_file دون أن تكتبه، فتكرّر العقود في كل تشغيل.
--        (تم إصلاح الجانب البرمجي أيضاً في contracts_ingester.py)

-- فهارس المتجهات — HNSW يتفوق على IVFFlat في الاسترجاع ويحتاج pgvector >= 0.5
create index if not exists legal_documents_embedding_idx
    on legal_documents using hnsw (embedding vector_cosine_ops);
create index if not exists legal_drafts_embedding_idx
    on legal_drafts    using hnsw (embedding vector_cosine_ops);
create index if not exists legal_contracts_embedding_idx
    on legal_contracts using hnsw (embedding vector_cosine_ops);
create index if not exists legal_notices_embedding_idx
    on legal_notices   using hnsw (embedding vector_cosine_ops);
create index if not exists legal_poa_embedding_idx
    on legal_poa       using hnsw (embedding vector_cosine_ops);

-- فهارس منع التكرار والفلترة
create index if not exists legal_documents_doc_name_idx on legal_documents (document_name);
create index if not exists legal_drafts_doc_name_idx    on legal_drafts    (document_name);
create index if not exists legal_contracts_source_idx   on legal_contracts (source_file);
create index if not exists legal_notices_source_idx     on legal_notices   (source_file);
create index if not exists legal_poa_source_idx         on legal_poa       (source_file);


-- ==============================================================================
-- ٧. دوال البحث الدلالي (RPC) — تستدعيها legal_agent.py
-- ==============================================================================
-- كل دالة تُرجع نفس الشكل الذي يتوقّعه legal_agent.py و ask_brain.py:
--     document_name, chunk_content, similarity  (+ document_type, metadata, id)
--
-- العتبات المستخدمة في الكود:
--     التشريعات 0.75  (أعلى — الدقة القانونية لا تحتمل اجتهاداً)
--     البقية    0.70
-- لذلك العتبة مُمرَّرة كوسيط ولا تُثبَّت هنا.
-- ==============================================================================

create or replace function match_legal_documents(
    query_embedding vector(1024),
    match_threshold float default 0.75,
    match_count     int   default 5
)
returns table (
    id            bigint,
    document_name text,
    document_type text,
    chunk_content text,
    metadata      jsonb,
    similarity    float
)
language sql
stable
as $$
    select
        d.id,
        d.document_name,
        d.document_type,
        d.chunk_content,
        d.metadata,
        1 - (d.embedding <=> query_embedding) as similarity
    from legal_documents d
    where d.embedding is not null
      and 1 - (d.embedding <=> query_embedding) > match_threshold
    order by d.embedding <=> query_embedding
    limit match_count;
$$;


create or replace function match_legal_drafts(
    query_embedding vector(1024),
    match_threshold float default 0.70,
    match_count     int   default 2
)
returns table (
    id            bigint,
    document_name text,
    document_type text,
    chunk_content text,
    metadata      jsonb,
    similarity    float
)
language sql
stable
as $$
    select
        d.id, d.document_name, d.document_type, d.chunk_content, d.metadata,
        1 - (d.embedding <=> query_embedding) as similarity
    from legal_drafts d
    where d.embedding is not null
      and 1 - (d.embedding <=> query_embedding) > match_threshold
    order by d.embedding <=> query_embedding
    limit match_count;
$$;


create or replace function match_legal_contracts(
    query_embedding vector(1024),
    match_threshold float default 0.70,
    match_count     int   default 4
)
returns table (
    id            bigint,
    document_name text,
    document_type text,
    chunk_content text,
    metadata      jsonb,
    similarity    float
)
language sql
stable
as $$
    select
        d.id, d.document_name, d.document_type, d.chunk_content, d.metadata,
        1 - (d.embedding <=> query_embedding) as similarity
    from legal_contracts d
    where d.embedding is not null
      and 1 - (d.embedding <=> query_embedding) > match_threshold
    order by d.embedding <=> query_embedding
    limit match_count;
$$;


create or replace function match_legal_notices(
    query_embedding vector(1024),
    match_threshold float default 0.70,
    match_count     int   default 3
)
returns table (
    id            bigint,
    document_name text,
    document_type text,
    chunk_content text,
    metadata      jsonb,
    similarity    float
)
language sql
stable
as $$
    select
        d.id, d.document_name, d.document_type, d.chunk_content, d.metadata,
        1 - (d.embedding <=> query_embedding) as similarity
    from legal_notices d
    where d.embedding is not null
      and 1 - (d.embedding <=> query_embedding) > match_threshold
    order by d.embedding <=> query_embedding
    limit match_count;
$$;


create or replace function match_legal_poa(
    query_embedding vector(1024),
    match_threshold float default 0.70,
    match_count     int   default 3
)
returns table (
    id            bigint,
    document_name text,
    document_type text,
    chunk_content text,
    metadata      jsonb,
    similarity    float
)
language sql
stable
as $$
    select
        d.id, d.document_name, d.document_type, d.chunk_content, d.metadata,
        1 - (d.embedding <=> query_embedding) as similarity
    from legal_poa d
    where d.embedding is not null
      and 1 - (d.embedding <=> query_embedding) > match_threshold
    order by d.embedding <=> query_embedding
    limit match_count;
$$;


-- ==============================================================================
-- ٨. الأمان — Row Level Security
-- ==============================================================================
-- الواجهة الأمامية (Next.js) لا تتصل بـ Supabase إطلاقاً؛ كل الوصول يمر عبر
-- خادم FastAPI باستخدام SUPABASE_KEY. لذلك:
--
--   * إن كانت SUPABASE_KEY هي anon key  → فعّل RLS أدناه.
--   * إن كانت service_role key          → يتجاوز RLS تلقائياً (الوضع الحالي).
--
-- التوصية: فعّل RLS وامنع كل الوصول العام، لأن الخادم بمفتاح service_role
-- لا يتأثر. هذا يحمي أرشيفك إن تسرّب الـ anon key يوماً ما.
--
-- ⚠️ لا تُنفّذ هذا القسم قبل التأكد من أن SUPABASE_KEY = service_role،
--    وإلا سيتوقف الاستيعاب والبحث عن العمل.
-- ------------------------------------------------------------------------------
-- alter table legal_documents enable row level security;
-- alter table legal_drafts    enable row level security;
-- alter table legal_contracts enable row level security;
-- alter table legal_notices   enable row level security;
-- alter table legal_poa       enable row level security;
--
-- revoke all on legal_documents from anon, authenticated;
-- revoke all on legal_drafts    from anon, authenticated;
-- revoke all on legal_contracts from anon, authenticated;
-- revoke all on legal_notices   from anon, authenticated;
-- revoke all on legal_poa       from anon, authenticated;


-- ==============================================================================
-- ٩. التحقق بعد التنفيذ
-- ==============================================================================
-- يجب أن تظهر 6 جداول (5 لقاعدة المعرفة + 1 للتصحيحات) و5 دوال:

-- select table_name from information_schema.tables
--  where table_schema = 'public'
--    and table_name in ('legal_documents','legal_drafts','legal_contracts',
--                       'legal_notices','legal_poa','draft_revisions')
--  order by table_name;

-- select routine_name from information_schema.routines
--  where routine_schema = 'public' and routine_name like 'match_legal_%'
--  order by routine_name;

-- عدد المقاطع في كل جدول (يجب أن يكون > 0 بعد تشغيل سكربتات الاستيعاب):
-- select 'legal_documents' as t, count(*) from legal_documents
-- union all select 'legal_drafts',    count(*) from legal_drafts
-- union all select 'legal_contracts', count(*) from legal_contracts
-- union all select 'legal_notices',   count(*) from legal_notices
-- union all select 'legal_poa',       count(*) from legal_poa;

-- عدد التصحيحات المحفوظة (يبدأ من صفر ويزيد مع كل مسودّة تعتمدها):
-- select count(*) as revisions,
--        round(avg(edit_ratio)::numeric, 3) as avg_edit_ratio
--   from draft_revisions;


-- ==============================================================================
-- ١٠. تصحيحات المحامي  (draft_revisions)
-- ==============================================================================
-- ⚠️ هذا الجدول **ليس جزءاً من قاعدة المعرفة**، ولا يدخل الاسترجاع إطلاقاً.
--
-- الغرض: جمع أزواج (ما كتبه النموذج ← ما اعتمده المحامي)، لأنها المادة الخام
--        لتقليد أسلوب صاحب المكتب. وكل تصحيح لا يُسجَّل يضيع، فيبقى الأسلوب
--        في الموجّه تخميناً لا تعلّماً.
--
-- ⚠️ ولا يوجد عمود embedding هنا **عن قصد**، وهو أهمّ قرار في هذا القسم:
--    المسودّة المولَّدة قد تحوي مادة قانونية مؤلَّفة. ولو أُضمّنت ودخلت
--    الاسترجاع، لعادت في جولة لاحقة كـ«سياق موثوق» فتصير الهلوسة حقيقة
--    مؤرشفة. وهي أسوأ من الهلوسة العابرة، لأنها تترسّخ وتتكرّر.
--    الحقيقة ما قاله المحامي، لا ما قاله النموذج.
--
-- المصدر: POST /revisions في main.py
-- القياس: revisions.py (نسبة التعديل على مستوى الكلمات)
-- ------------------------------------------------------------------------------

create table if not exists draft_revisions (
    id              bigint generated always as identity primary key,
    created_at      timestamptz not null default now(),
    session_id      text,            -- جلسة الواجهة، لتتبّع مسار المسودّة
    doc_type        text,            -- نوع المستند المطلوب
    prompt          text,            -- الوقائع التي أدخلها المحامي
    generated_text  text not null,   -- ما أنتجه النموذج
    corrected_text  text not null,   -- ما اعتمده المحامي فعلاً
    edit_ratio      real,            -- نسبة الكلمات المتغيّرة (0.0 – 1.0)
    word_count      int              -- طول النسخة المعتمدة (للفلترة والتقارير)
);

-- ترتيب زمني معكوس: أحدث التصحيحات أولاً
create index if not exists draft_revisions_created_idx
    on draft_revisions (created_at desc);

-- فلترة «الأزواج الأكثر تعديلاً» — وهي الأغنى بالدروس عن الأسلوب
create index if not exists draft_revisions_ratio_idx
    on draft_revisions (edit_ratio);


-- ==============================================================================
-- ١١. دوالّ الأرشيف — يقرأها `GET /archive/overview` و`GET /archive/documents`
-- ==============================================================================
-- ⚠️ لماذا دوالّ SQL لا استعلامات من الخادم؟
--
-- لأن الواجهة كانت تعرض أرقاماً **مكتوبة بخط اليد** (١٢٤٨ مستنداً و٨٥٣٠ سنداً)
-- لا أصل لها. والبديل الحقيقي يحتاج شيئين لا يوفّرهما PostgREST:
--
--   ١) `count(distinct document_name)` — وPostgREST لا يدعم DISTINCT.
--   ٢) `group by` لتجميع المقاطع في مستند واحد — ولا يدعمه أيضاً.
--
-- وكان يمكن جلب كل الأسماء إلى بايثون وجمعها فيه، لكنه يعني تنزيل آلاف الصفوف
-- في كل فتح للصفحة. فالعمل يُنفَّذ حيث البيانات ✅
--
-- ⚠️ وهي `security invoker` لا `security definer` عن قصد: الخادم يستخدم مفتاح
--    `service_role` وهو يتجاوز RLS أصلاً، فلا حاجة إلى رفع الصلاحية. و
--    `security definer` بلا داعٍ **ثغرة تصعيد امتيازات** لا مكسب.
-- ------------------------------------------------------------------------------

create or replace function archive_overview()
returns table (
    family_key   text,
    documents    bigint,
    chunks       bigint,
    latest_added timestamptz
)
language sql
stable
as $$
    select 'legislation'::text, count(distinct document_name), count(*), max(created_at)
      from legal_documents
    union all
    select 'drafts'::text,      count(distinct document_name), count(*), max(created_at)
      from legal_drafts
    union all
    select 'contracts'::text,   count(distinct document_name), count(*), max(created_at)
      from legal_contracts
    union all
    select 'notices'::text,     count(distinct document_name), count(*), max(created_at)
      from legal_notices
    union all
    select 'poa'::text,         count(distinct document_name), count(*), max(created_at)
      from legal_poa;
$$;

comment on function archive_overview() is
    'عدد المستندات والمقاطع لكل عائلة من العائلات الخمس — للوحة القيادة';


create or replace function archive_documents(
    search_term   text default null,
    family_filter text default null,
    max_rows      int  default 200
)
returns table (
    document_name text,
    document_type text,
    family_key    text,
    chunks        bigint,
    added_at      timestamptz
)
language sql
stable
as $$
    with combined as (
        select document_name, document_type, 'legislation'::text as family_key, created_at
          from legal_documents
        union all
        select document_name, document_type, 'drafts'::text, created_at
          from legal_drafts
        union all
        select document_name, document_type, 'contracts'::text, created_at
          from legal_contracts
        union all
        select document_name, document_type, 'notices'::text, created_at
          from legal_notices
        union all
        select document_name, document_type, 'poa'::text, created_at
          from legal_poa
    )
    select
        combined.document_name,
        max(combined.document_type)  as document_type,
        combined.family_key,
        count(*)                     as chunks,
        min(combined.created_at)     as added_at
    from combined
    where (
            coalesce(search_term, '') = ''
            or combined.document_name ilike '%' || search_term || '%'
            or combined.document_type ilike '%' || search_term || '%'
          )
      and (
            coalesce(family_filter, '') = ''
            or combined.family_key = family_filter
          )
    group by combined.document_name, combined.family_key
    -- ⚠️ والاسم فاصلٌ ثانٍ لا زينة: التواريخ في أربع عائلات **متطابقة** (وقت
    --    إضافة العمود بـ`alter table`)، فالترتيب بالتاريخ وحده **غير حتميّ** —
    --    قد تُعاد صفوف مختلفة في كل نداء مع أن البيانات لم تتغيّر. والفاصل
    --    يجعل النتيجة ثابتة، وهو شرط أي قائمة تُقرأ مرتين.
    order by min(combined.created_at) desc, combined.document_name
    -- ⚠️ سقف صريح: بلا `least` يستطيع أي نداء طلب الأرشيف كله في صفّ واحد
    limit least(greatest(coalesce(max_rows, 200), 1), 500);
$$;

comment on function archive_documents(text, text, int) is
    'قائمة مستندات الأرشيف مجموعةً بالاسم — لصفحة الأرشيف والمكتبة';


-- ------------------------------------------------------------------------------
-- التحقّق بعد التنفيذ
-- ------------------------------------------------------------------------------
-- يجب أن تعيد خمسة صفوف (واحد لكل عائلة)، والأعداد أصفار إن كان الأرشيف فارغاً:
--
--   select * from archive_overview();
--
-- ويجب أن تعيد مستنداتك مجموعةً، وكل صفّ بعدد مقاطعه:
--
--   select * from archive_documents(max_rows => 10);
--
-- والبحث والتصفية:
--
--   select * from archive_documents(search_term => 'إيجار');
--   select * from archive_documents(family_filter => 'legislation');
-- ------------------------------------------------------------------------------


-- ==============================================================================
-- ١٢. البحث في المقاطع — يقرأها `GET /archive/chunks`
-- ==============================================================================
-- ⚠️ لماذا دالّة جديدة وقد وُجدت `archive_documents`؟
--
-- لأن تلك تجمع **بالاسم** فتُعيد صفّاً واحداً لكل مستند (`group by
-- document_name`). وهذه تُعيد **المقاطع نفسها** — وهو ما يفتحه المحامي لقراءته.
--
-- ⚠️ وثلاث حالات في دالّة واحدة، والفصل بينها مقصود:
--
--   ① `document_filter` مُعطى  → **كل مقاطع مستند واحد**، مرتّبة بترتيب فقراته.
--      وهذا «فتح المستند» الذي طلبه المستخدم.
--   ② `search_term` مُعطى      → بحث نصّي في المتن وفي اسم المستند.
--   ③ لا هذا ولا ذاك           → أحدث المقاطع.
--
-- ⚠️ **والبحث نصّي لا دلالي، وهو اختيار لا نقص.**
--    البحث الدلالي يحتاج تحميل نموذج التضمين (٢.٢ غ.ب) وتشفير السؤال — وهو
--    متاح في **أدوات الوكيل الخمس** حيث يُحتاج فعلاً. أما هنا فالمحامي يبحث عن
--    **نصّ بعينه**: «أين وردت المادة ٤٨؟» — والبحث النصّي أدقّ في هذا وأسرع
--    (بلا نموذج، بلا انتظار). وإضافة الدلالي هنا تحتاج دالّة سادسة وتمثيلاً
--    لكل جدول — وتُترك لخطوة تالية إن احتيجت.
--
-- ⚠️ و`chunk_index` يُقرأ من `metadata` بـ**تحويل آمن**: لو كانت القيمة غير
--    رقمية لانهارت الدالّة كلها عند أول صفّ مخالف. والقيد `~` يمنع ذلك.
-- ------------------------------------------------------------------------------

create or replace function archive_chunks(
    search_term     text default null,
    family_filter   text default null,
    document_filter text default null,
    max_rows        int  default 50
)
returns table (
    id            bigint,
    document_name text,
    document_type text,
    family_key    text,
    chunk_content text,
    source_file   text,
    chunk_index   int,
    created_at    timestamptz
)
language sql
stable
as $$
    with combined as (
        select id, document_name, document_type, 'legislation'::text as family_key,
               chunk_content, source_file, created_at,
               case when metadata->>'chunk_index' ~ '^[0-9]+$'
                    then (metadata->>'chunk_index')::int end as chunk_index
          from legal_documents
        union all
        select id, document_name, document_type, 'drafts'::text,
               chunk_content, source_file, created_at,
               case when metadata->>'chunk_index' ~ '^[0-9]+$'
                    then (metadata->>'chunk_index')::int end
          from legal_drafts
        union all
        select id, document_name, document_type, 'contracts'::text,
               chunk_content, source_file, created_at,
               case when metadata->>'chunk_index' ~ '^[0-9]+$'
                    then (metadata->>'chunk_index')::int end
          from legal_contracts
        union all
        select id, document_name, document_type, 'notices'::text,
               chunk_content, source_file, created_at,
               case when metadata->>'chunk_index' ~ '^[0-9]+$'
                    then (metadata->>'chunk_index')::int end
          from legal_notices
        union all
        select id, document_name, document_type, 'poa'::text,
               chunk_content, source_file, created_at,
               case when metadata->>'chunk_index' ~ '^[0-9]+$'
                    then (metadata->>'chunk_index')::int end
          from legal_poa
    )
    select combined.id, combined.document_name, combined.document_type,
           combined.family_key, combined.chunk_content, combined.source_file,
           combined.chunk_index, combined.created_at
    from combined
    where (
            coalesce(document_filter, '') = ''
            or combined.document_name = document_filter
          )
      and (
            coalesce(family_filter, '') = ''
            or combined.family_key = family_filter
          )
      and (
            coalesce(search_term, '') = ''
            -- ⚠️ وعند «فتح مستند» **يُلغى البحث النصّي**: فالمستخدم يريد
            --    المستند كاملاً بفقراته، لا فقراته التي فيها الكلمة فقط.
            or coalesce(document_filter, '') <> ''
            or combined.chunk_content ilike '%' || search_term || '%'
            or combined.document_name ilike '%' || search_term || '%'
          )
    order by
        -- داخل المستند: بترتيب الفقرات. وفي البحث: هذا التعبير `null` للجميع
        -- فلا يؤثّر في الترتيب، ويبقى الترتيب بالأحدث.
        case when coalesce(document_filter, '') <> '' then combined.chunk_index end
            nulls last,
        combined.created_at desc nulls last,
        combined.document_name,
        combined.id
    limit least(greatest(coalesce(max_rows, 50), 1), 200);
$$;

comment on function archive_chunks(text, text, text, int) is
    'المقاطع نفسها: فتح مستند بفقراته، أو بحث نصّي في المتن — لصفحة الأرشيف';


-- ------------------------------------------------------------------------------
-- التحقّق بعد التنفيذ
-- ------------------------------------------------------------------------------
-- المادة ٤٨ في التشريعات (أو أي نصّ تعرفه):
--
--   select document_name, chunk_content
--     from archive_chunks(search_term => 'المادة', max_rows => 5);
--
-- وفتح مستند بعينه — يجب أن تعود فقراته **مرتّبة**:
--
--   select chunk_index, left(chunk_content, 60)
--     from archive_chunks(document_filter => 'اسم المستند كما يظهر في الجدول');
--
-- ⚠️ وإن كان البحث النصّي بطيئاً على أرشيفك، فهذا متوقّع: **مسح كامل بلا
--    فهرس**. والعلاج فهرس ثلاثي الحروف (يُضيف مساحة على القرص):
--
--      create extension if not exists pg_trgm;
--      create index if not exists legal_documents_content_trgm
--          on legal_documents using gin (chunk_content gin_trgm_ops);
--      -- ويتكرّر لكل جدول من الخمسة
-- ------------------------------------------------------------------------------
