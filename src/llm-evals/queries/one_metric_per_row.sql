select
    --sample_id is row number in dataset
    run_single_score.run_id,
    sample_id,
    -- dataset
    json_extract(run_config__eval_spec__args,'$.samples_jsonl') data_file,
    CASE 
        WHEN split = 'CompletionMetric' THEN 'assistant'
        WHEN split = 'ConversationMetric' THEN 'conversation'
        ELSE json_extract(data,'$.role')
    END AS role,
    COALESCE(
        json_extract(data, '$.score'),
        json_extract(data, '$.metric_value')
    ) AS metric_value,
    json_extract(data,'$.function_metric_name') function_metric_name,
    json_extract(data,'$.content') content
from run_single_score
inner join run_metadata on run_metadata.run_id = run_single_score.run_id
where type = 'metrics'





--yeasayer commissions
select v_most_recent_eval.run_id, 
completion_fns__0 completion_fn, 
json_extract(run_metadata.run_config__eval_spec__args, '$.run_kwargs.completion_llm.model_name') model_name,
row_number, 
metric_value, 
content completion, 
data_file, 
run_metadata.*
from v_metrics
inner join v_most_recent_eval on v_metrics.run_id = v_most_recent_eval.run_id and v_metrics.base_eval = v_most_recent_eval.base_eval
inner join run_metadata on v_metrics.run_id=run_metadata.run_id and v_metrics.base_eval=run_metadata.base_eval
where 1=1
and v_metrics.base_eval = 'yeasayer-completion'
order by metric_value desc
limit 20


--moderation flags
select v_metrics.run_id, 
function_metric_name, 
metric_value, 
content, 
json_extract(run_metadata.run_config__eval_spec__args, '$.run_kwargs.completion_llm.model_name') model_name
from v_metrics
inner join 
    v_most_recent_eval on v_metrics.run_id = v_most_recent_eval.run_id 
    and v_metrics.base_eval = v_most_recent_eval.base_eval
inner join run_metadata on run_metadata.run_id = v_metrics.run_id
where function_metric_name like 'openai_moderation%'
order by metric_value desc
