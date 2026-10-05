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

alter table legal_documents add column if not exists source_file text;
alter table legal_drafts    add column if not exists source_file text;
alter table legal_contracts add column if not exists source_file text;
alter table legal_notices   add column if not exists source_file text;
alter table legal_poa       add column if not exists source_file text;


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
