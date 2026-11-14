-- Phase 2A additive retrieval, v1. MANUAL deployment only; never run on production automatically.
-- Preconditions: PostgreSQL >= 15, pgvector, existing public five legal_* tables / vector(1024).
-- Existing tables, text, metadata, vectors, HNSW indexes and match_legal_* RPCs are untouched.
-- Metadata is optional metadata.retrieval_v1; no backfill or authority promotion occurs.
begin;
set local search_path=public,extensions,pg_temp;
do $$
declare t text;
begin
 if current_setting('server_version_num')::integer<150000 then
  raise exception 'Phase 2A requires PostgreSQL 15 or newer for invoker-security views'; end if;
 if to_regprocedure('vector_norm(vector)') is null then
  raise exception 'Compatible pgvector with vector_norm(vector) required; no automatic extension upgrade'; end if;
 foreach t in array array['legal_documents','legal_drafts','legal_contracts','legal_notices','legal_poa'] loop
  if to_regclass('public.'||t) is null then raise exception 'Required existing knowledge table absent'; end if;
  if not exists(select 1 from pg_attribute where attrelid=to_regclass('public.'||t)
       and attname='embedding' and atttypmod=1024 and not attisdropped) then
   raise exception 'Existing embedding columns must be vector(1024); migration will not change them'; end if;
 end loop;
end $$;

create or replace function public.retrieval_normalize_v1(value text)
returns text language sql immutable parallel safe security invoker set search_path=public,extensions,pg_temp as $$
 select trim(regexp_replace(regexp_replace(
   translate(lower(normalize(coalesce(value,''), NFKC)),
             'أإآٱ٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','اااا01234567890123456789'),
   '[ً-ٰٟـ]','','g'),'[[:space:]]+',' ','g'));
$$;

create or replace function public.retrieval_date_v1(value text)
returns date language plpgsql immutable parallel safe security invoker set search_path=public,extensions,pg_temp as $$
begin
 if value is null or value='' then return null; end if;
 if value !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then return null; end if;
 return value::date;
exception when invalid_datetime_format or datetime_field_overflow then return null;
end $$;

create or replace function public.retrieval_metadata_valid_v1(meta jsonb)
returns boolean language plpgsql immutable parallel safe security invoker set search_path=public,extensions,pg_temp as $$
declare m jsonb:=coalesce(meta->'retrieval_v1','{}'::jsonb); key text; val text;
begin
 if (meta is not null and meta<>'null'::jsonb and jsonb_typeof(meta) is distinct from 'object') or jsonb_typeof(m) is distinct from 'object' then return false; end if;
 foreach key in array array['classification_verified','identity_verified','jurisdiction_verified','ai_generated'] loop
  if m ? key and jsonb_typeof(m->key) is distinct from 'boolean' then return false; end if;
 end loop;
 if m ? 'source_class' and (jsonb_typeof(m->'source_class') is distinct from 'string'
    or m->>'source_class' not in ('official_legislation','judicial_decision','administrative_regulatory',
       'contractual_evidence','drafting_precedent','internal_policy','external_commentary','unknown')) then return false; end if;
 if m ? 'jurisdiction' and m->'jurisdiction'<>'null'::jsonb then
  if jsonb_typeof(m->'jurisdiction') is distinct from 'object' then return false; end if;
  for key,val in select * from jsonb_each_text(m->'jurisdiction') loop
   if key not in ('governing_law','court_jurisdiction','regulatory_jurisdiction','contractual_choice_of_law',
       'subject_matter_jurisdiction','procedural_rules') or val is null or val not in
       ('uae_federal','abu_dhabi','dubai','sharjah','other_uae_emirates','adgm','difc','unknown') then return false; end if;
  end loop;
 end if;
 foreach key in array array['publication_date','effective_from','effective_to','verified_at','temporal_verified_through'] loop
  if m ? key and m->key <> 'null'::jsonb and (jsonb_typeof(m->key) is distinct from 'string'
      or (m->>key <> '' and public.retrieval_date_v1(m->>key) is null)) then return false; end if;
 end loop;
 foreach key in array array['instrument_id','issuing_authority','original_title','article_reference','clause_reference',
                            'language','amendment_version','source_document_id','content_checksum','official_url'] loop
  if m ? key and m->key <> 'null'::jsonb and (jsonb_typeof(m->key) is distinct from 'string'
      or length(m->>key)>case when key='official_url' then 2000 else 500 end) then return false; end if;
 end loop;
 if coalesce(m->>'official_url','')<>'' and m->>'official_url' !~ '^https://[^/@[:space:]]+([/?#].*)?$' then return false; end if;
 if public.retrieval_date_v1(m->>'effective_from')>public.retrieval_date_v1(m->>'effective_to') then return false; end if;
 return true;
end $$;

create or replace function public.retrieval_eligible_v1(meta jsonb, family text, filters jsonb)
returns boolean language plpgsql immutable parallel safe security invoker set search_path=public,extensions,pg_temp as $$
declare m jsonb:=coalesce(meta->'retrieval_v1','{}'::jsonb); source text; key text; wanted text; actual text;
 unknown_found boolean:=false; when_date date:=public.retrieval_date_v1(filters->>'as_of');
begin
 if not public.retrieval_metadata_valid_v1(meta) then return false; end if;
 if coalesce((m->>'ai_generated')::boolean,false) then return false; end if;
 -- An unverified non-authority declaration may exclude a row but never promote it.
 source:=coalesce(m->>'source_class','unknown');
 if family='legislation' and source not in ('unknown','official_legislation','judicial_decision','administrative_regulatory') then return false;
 elsif family='drafts' and source not in ('unknown','drafting_precedent') then return false;
 elsif family in ('contracts','notices','poa') and source not in ('unknown','contractual_evidence') then return false; end if;
 source:=case when coalesce((m->>'classification_verified')::boolean,false) then coalesce(m->>'source_class','unknown') else 'unknown' end;
 if source='unknown' then unknown_found:=true;
 elsif family='legislation' and source not in ('official_legislation','judicial_decision','administrative_regulatory') then return false;
 elsif family='drafts' and source<>'drafting_precedent' then return false;
 elsif family in ('contracts','notices','poa') and source<>'contractual_evidence' then return false; end if;
 if family='legislation' and (not coalesce((m->>'identity_verified')::boolean,false)
      or coalesce(m->>'official_url','')='' or public.retrieval_date_v1(m->>'verified_at') is null) then unknown_found:=true; end if;
 if not exists(select 1 from jsonb_each_text(coalesce(filters->'jurisdiction','{}')) e where e.value<>'unknown') then unknown_found:=true; end if;
 for key,wanted in select * from jsonb_each_text(coalesce(filters->'jurisdiction','{}')) loop
  if wanted='unknown' then continue; end if;
  actual:=coalesce(m->'jurisdiction'->>key,'unknown');
  if coalesce((m->>'jurisdiction_verified')::boolean,false) and actual<>'unknown' and actual<>wanted then return false; end if;
  if not coalesce((m->>'jurisdiction_verified')::boolean,false) or actual='unknown' then unknown_found:=true; end if;
 end loop;
 if when_date is not null and (when_date<public.retrieval_date_v1(m->>'effective_from')
      or when_date>public.retrieval_date_v1(m->>'effective_to')) then return false; end if;
 if family='legislation' and (when_date is null or public.retrieval_date_v1(m->>'effective_from') is null
      or public.retrieval_date_v1(m->>'verified_at') is null or public.retrieval_date_v1(m->>'temporal_verified_through') is null
      or public.retrieval_date_v1(m->>'temporal_verified_through')<when_date) then unknown_found:=true; end if;
 return not unknown_found or coalesce(filters->>'unknown_policy','research_lead')='research_lead';
end $$;

create or replace function public.retrieval_filters_valid_v1(filters jsonb)
returns boolean language plpgsql immutable parallel safe security invoker set search_path=public,extensions,pg_temp as $$
declare key text; val text;
begin
 if jsonb_typeof(filters) is distinct from 'object' then return false; end if;
 if exists(select 1 from jsonb_object_keys(filters) k where k not in ('jurisdiction','as_of','unknown_policy')) then return false; end if;
 if coalesce(filters->>'unknown_policy','research_lead') not in ('exclude','research_lead') then return false; end if;
 if filters ? 'as_of' and filters->'as_of'<>'null'::jsonb and public.retrieval_date_v1(filters->>'as_of') is null then return false; end if;
 if jsonb_typeof(coalesce(filters->'jurisdiction','{}')) is distinct from 'object' then return false; end if;
 for key,val in select * from jsonb_each_text(coalesce(filters->'jurisdiction','{}')) loop
  if key not in ('governing_law','court_jurisdiction','regulatory_jurisdiction','contractual_choice_of_law',
       'subject_matter_jurisdiction','procedural_rules') or val is null or val not in
       ('uae_federal','abu_dhabi','dubai','sharjah','other_uae_emirates','adgm','difc','unknown') then return false; end if;
 end loop;
 return true;
end $$;

-- Exact identifier matching requires ALL requested references in one source row.
-- Structured metadata or bounded word/number source-text matches; this is not legal verification.
create or replace function public.retrieval_exact_v1(title text, body text, meta jsonb, refs jsonb)
returns boolean language plpgsql immutable parallel safe security invoker set search_path=public,extensions,pg_temp as $$
declare ref jsonb; kind text; value text; pattern text; content text:=public.retrieval_normalize_v1(title||E'\n'||body);
 m jsonb:=coalesce(meta->'retrieval_v1','{}'); structured text;
begin
 if jsonb_typeof(refs)<>'array' or jsonb_array_length(refs)=0 then return false; end if;
 for ref in select * from jsonb_array_elements(refs) loop
  kind:=ref->>'kind'; value:=ref->>'value';
  if value is null or value !~ '^[0-9]+([./][0-9]+)*(:[0-9]{4})?$' then return false; end if;
  if kind in ('article','clause') and value like '%:%' then return false; end if;
  structured:=public.retrieval_normalize_v1(case when kind='article' then m->>'article_reference'
    when kind='clause' then m->>'clause_reference' else m->>'instrument_id' end);
  if coalesce((m->>'identity_verified')::boolean,false) and public.retrieval_date_v1(m->>'verified_at') is not null and structured=(case when kind in ('article','clause') then value else kind||':'||value end) then continue; end if;
  pattern:=case kind when 'article' then '(article[[:space:]]+|المادة[[:space:]]*)'
     when 'clause' then '(clause[[:space:]]+|البند[[:space:]]*)'
     when 'law' then '((?<!decree-)(?<!decree )law[[:space:]]+no\.?[[:space:]]*|القانون[[:space:]]+رقم[[:space:]]*|قانون[[:space:]]+رقم[[:space:]]*)'
     when 'decree_law' then '(decree[- ]law[[:space:]]+(no\.?[[:space:]]*)?|مرسوم[[:space:]]+بقانون[[:space:]]+(رقم[[:space:]]*)?)'
     when 'regulation' then '(regulation[[:space:]]+no\.?[[:space:]]*|لائحة[[:space:]]+رقم[[:space:]]*)'
     else null end;
  if pattern is null or content !~ ('(^|[^[:alnum:]_])'||pattern||replace(replace(value,'.','\.'),':','[[:space:]]+(of|لسنة)[[:space:]]+')||'(?![[:alnum:]_]|[./][0-9])') then return false; end if;
 end loop;
 return true;
end $$;

-- Expression indexes do not rewrite original passages or existing metadata.
create index if not exists legal_documents_lexical_v1_idx on public.legal_documents using gin (to_tsvector('simple'::regconfig, public.retrieval_normalize_v1(document_name||' '||chunk_content)));
create index if not exists legal_documents_article_reference_v1_idx on public.legal_documents (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,article_reference}'));
create index if not exists legal_documents_clause_reference_v1_idx on public.legal_documents (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,clause_reference}'));
create index if not exists legal_documents_instrument_id_v1_idx on public.legal_documents (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,instrument_id}'));
create index if not exists legal_drafts_lexical_v1_idx on public.legal_drafts using gin (to_tsvector('simple'::regconfig, public.retrieval_normalize_v1(document_name||' '||chunk_content)));
create index if not exists legal_drafts_article_reference_v1_idx on public.legal_drafts (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,article_reference}'));
create index if not exists legal_drafts_clause_reference_v1_idx on public.legal_drafts (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,clause_reference}'));
create index if not exists legal_drafts_instrument_id_v1_idx on public.legal_drafts (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,instrument_id}'));
create index if not exists legal_contracts_lexical_v1_idx on public.legal_contracts using gin (to_tsvector('simple'::regconfig, public.retrieval_normalize_v1(document_name||' '||chunk_content)));
create index if not exists legal_contracts_article_reference_v1_idx on public.legal_contracts (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,article_reference}'));
create index if not exists legal_contracts_clause_reference_v1_idx on public.legal_contracts (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,clause_reference}'));
create index if not exists legal_contracts_instrument_id_v1_idx on public.legal_contracts (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,instrument_id}'));
create index if not exists legal_notices_lexical_v1_idx on public.legal_notices using gin (to_tsvector('simple'::regconfig, public.retrieval_normalize_v1(document_name||' '||chunk_content)));
create index if not exists legal_notices_article_reference_v1_idx on public.legal_notices (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,article_reference}'));
create index if not exists legal_notices_clause_reference_v1_idx on public.legal_notices (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,clause_reference}'));
create index if not exists legal_notices_instrument_id_v1_idx on public.legal_notices (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,instrument_id}'));
create index if not exists legal_poa_lexical_v1_idx on public.legal_poa using gin (to_tsvector('simple'::regconfig, public.retrieval_normalize_v1(document_name||' '||chunk_content)));
create index if not exists legal_poa_article_reference_v1_idx on public.legal_poa (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,article_reference}'));
create index if not exists legal_poa_clause_reference_v1_idx on public.legal_poa (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,clause_reference}'));
create index if not exists legal_poa_instrument_id_v1_idx on public.legal_poa (public.retrieval_normalize_v1(metadata#>>'{retrieval_v1,instrument_id}'));

create or replace view public.retrieval_chunks_v1 with (security_invoker=true) as
select 'legislation'::text as family, id, document_name, document_type, chunk_content, metadata, embedding from public.legal_documents
union all
select 'drafts'::text as family, id, document_name, document_type, chunk_content, metadata, embedding from public.legal_drafts
union all
select 'contracts'::text as family, id, document_name, document_type, chunk_content, metadata, embedding from public.legal_contracts
union all
select 'notices'::text as family, id, document_name, document_type, chunk_content, metadata, embedding from public.legal_notices
union all
select 'poa'::text as family, id, document_name, document_type, chunk_content, metadata, embedding from public.legal_poa;

create or replace function public.hybrid_semantic_v1(p_family text, p_embedding vector(1024),
 p_threshold double precision default 0.70, p_limit integer default 30, p_filters jsonb default '{}')
returns table(id bigint,document_name text,document_type text,chunk_content text,metadata jsonb,similarity double precision)
language plpgsql stable security invoker set search_path=public,extensions,pg_temp as $$
begin
 if p_family not in ('legislation','drafts','contracts','notices','poa') or p_family is null
   or p_limit is null or p_limit not between 1 and 100 or p_threshold is null or p_threshold not between -1 and 1
   or p_embedding is null or vector_dims(p_embedding)<>1024 or vector_norm(p_embedding)=0
   or not public.retrieval_filters_valid_v1(p_filters) then raise invalid_parameter_value using message='Invalid hybrid search parameters'; end if;
 return query select d.id,d.document_name,d.document_type,d.chunk_content,d.metadata,1-(d.embedding<=>p_embedding)
 from public.retrieval_chunks_v1 d where d.family=p_family and d.embedding is not null
 and public.retrieval_eligible_v1(d.metadata,p_family,p_filters) and 1-(d.embedding<=>p_embedding)>p_threshold
 order by d.embedding<=>p_embedding,d.id limit p_limit;
end $$;

create or replace function public.hybrid_lexical_v1(p_family text,p_query text,p_references jsonb default '[]',
 p_limit integer default 30,p_filters jsonb default '{}')
returns table(id bigint,document_name text,document_type text,chunk_content text,metadata jsonb,lexical_score real,exact_match boolean)
language plpgsql stable security invoker set search_path=public,extensions,pg_temp as $$
declare q tsquery; ref jsonb; article text; clause text; instrument text;
begin
 if p_family not in ('legislation','drafts','contracts','notices','poa') or p_family is null
   or p_query is null or length(p_query)>20000 or p_limit is null or p_limit not between 1 and 100
   or not public.retrieval_filters_valid_v1(p_filters) or jsonb_typeof(p_references) is distinct from 'array'
   or jsonb_array_length(p_references)>16 then raise invalid_parameter_value using message='Invalid hybrid search parameters'; end if;
 for ref in select * from jsonb_array_elements(p_references) loop
  if jsonb_typeof(ref) is distinct from 'object' or ref->>'kind' is null or ref->>'value' is null
    or ref->>'kind' not in ('article','clause','law','decree_law','regulation')
    or ref->>'value' !~ '^[0-9]+([./][0-9]+)*(:[0-9]{4})?$' then raise invalid_parameter_value using message='Invalid exact reference'; end if;
  if ref->>'kind' in ('article','clause') and ref->>'value' like '%:%' then raise invalid_parameter_value using message='Invalid exact reference'; end if;
  case ref->>'kind' when 'article' then article:=ref->>'value'; when 'clause' then clause:=ref->>'value';
     else instrument:=(ref->>'kind')||':'||(ref->>'value'); end case;
 end loop;
 if trim(p_query)='' then return; end if;
 select websearch_to_tsquery('simple',coalesce(string_agg(term,' OR '),'')) into q from
   (select m[1] as term from regexp_matches(public.retrieval_normalize_v1(p_query),'[[:alnum:]_]+','g') m limit 32) tokens;
 return query select d.id,d.document_name,d.document_type,d.chunk_content,d.metadata,
    ts_rank_cd(to_tsvector('simple',public.retrieval_normalize_v1(d.document_name||' '||d.chunk_content)),q),
    public.retrieval_exact_v1(d.document_name,d.chunk_content,d.metadata,p_references)
 from public.retrieval_chunks_v1 d where d.family=p_family
 and public.retrieval_eligible_v1(d.metadata,p_family,p_filters)
 and (to_tsvector('simple',public.retrieval_normalize_v1(d.document_name||' '||d.chunk_content))@@q
   or (coalesce(d.metadata#>>'{retrieval_v1,identity_verified}','false')='true' and public.retrieval_date_v1(d.metadata#>>'{retrieval_v1,verified_at}') is not null and ((article is not null and public.retrieval_normalize_v1(d.metadata#>>'{retrieval_v1,article_reference}')=article)
   or (clause is not null and public.retrieval_normalize_v1(d.metadata#>>'{retrieval_v1,clause_reference}')=clause)
   or (instrument is not null and public.retrieval_normalize_v1(d.metadata#>>'{retrieval_v1,instrument_id}')=instrument))))
 order by 7 desc,6 desc,d.id limit p_limit;
end $$;

create or replace function public.hybrid_metadata_audit_v1(p_family text)
returns jsonb language plpgsql stable security invoker set search_path=public,extensions,pg_temp as $$
declare result jsonb;
begin
 if p_family is null or p_family not in ('legislation','drafts','contracts','notices','poa') then raise invalid_parameter_value using message='Invalid family'; end if;
 select jsonb_build_object('records',count(*),
 'known_jurisdiction',count(*) filter(where metadata#>>'{retrieval_v1,jurisdiction,governing_law}' in ('uae_federal','abu_dhabi','dubai','sharjah','other_uae_emirates','adgm','difc')),
 'unknown_jurisdiction',count(*) filter(where coalesce(metadata#>>'{retrieval_v1,jurisdiction,governing_law}','unknown') not in ('uae_federal','abu_dhabi','dubai','sharjah','other_uae_emirates','adgm','difc')),
 'with_source_url',count(*) filter(where coalesce(metadata#>>'{retrieval_v1,official_url}','')<>''),
 'without_source_url',count(*) filter(where coalesce(metadata#>>'{retrieval_v1,official_url}','')=''),
 'with_instrument_id',count(*) filter(where coalesce(metadata#>>'{retrieval_v1,instrument_id}','')<>''),
 'with_temporal_metadata',count(*) filter(where coalesce(metadata#>>'{retrieval_v1,effective_from}','')<>''),
 'manual_review',count(*) filter(where not public.retrieval_metadata_valid_v1(metadata)
  or coalesce(metadata#>>'{retrieval_v1,classification_verified}','false')<>'true'
  or coalesce(metadata#>>'{retrieval_v1,identity_verified}','false')<>'true'
  or coalesce(metadata#>>'{retrieval_v1,jurisdiction_verified}','false')<>'true'
  or public.retrieval_date_v1(metadata#>>'{retrieval_v1,verified_at}') is null)) into result
 from public.retrieval_chunks_v1 where family=p_family;
 return result;
end $$;

-- No new public/anonymous/authenticated data policies or grants. Preserve base-table RLS.
revoke all on public.retrieval_chunks_v1 from public;
revoke all on function public.hybrid_semantic_v1(text,vector,double precision,integer,jsonb) from public;
revoke all on function public.hybrid_lexical_v1(text,text,jsonb,integer,jsonb) from public;
revoke all on function public.hybrid_metadata_audit_v1(text) from public;
revoke all on function public.retrieval_normalize_v1(text) from public;
revoke all on function public.retrieval_date_v1(text) from public;
revoke all on function public.retrieval_metadata_valid_v1(jsonb) from public;
revoke all on function public.retrieval_eligible_v1(jsonb,text,jsonb) from public;
revoke all on function public.retrieval_filters_valid_v1(jsonb) from public;
revoke all on function public.retrieval_exact_v1(text,text,jsonb,jsonb) from public;
do $$ begin
 if exists(select 1 from pg_roles where rolname='service_role') then
  grant select on public.retrieval_chunks_v1 to service_role;
  grant execute on function public.retrieval_normalize_v1(text) to service_role;
  grant execute on function public.retrieval_date_v1(text) to service_role;
  grant execute on function public.retrieval_metadata_valid_v1(jsonb) to service_role;
  grant execute on function public.retrieval_eligible_v1(jsonb,text,jsonb) to service_role;
  grant execute on function public.retrieval_filters_valid_v1(jsonb) to service_role;
  grant execute on function public.retrieval_exact_v1(text,text,jsonb,jsonb) to service_role;

  grant execute on function public.hybrid_semantic_v1(text,vector,double precision,integer,jsonb) to service_role;
  grant execute on function public.hybrid_lexical_v1(text,text,jsonb,integer,jsonb) to service_role;
  grant execute on function public.hybrid_metadata_audit_v1(text) to service_role;
 end if;
end $$;
commit;
