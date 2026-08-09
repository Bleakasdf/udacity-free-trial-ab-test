-- 1. Randomization health: metrics measured before the screener.
SELECT experiment_group, pageviews, clicks, click_through_rate
FROM group_summary
ORDER BY experiment_group;

-- 2. Mature funnel: only dates with a complete 14-day payment outcome.
SELECT experiment_group, mature_pageviews, mature_clicks, enrollments, payments
FROM group_summary
ORDER BY experiment_group;

-- 3. Decision metrics.
SELECT experiment_group, gross_conversion, net_conversion, retention
FROM group_summary
ORDER BY experiment_group;

-- 4. Daily evidence for stability checks.
SELECT event_date, experiment_group, gross_conversion, net_conversion
FROM daily_metrics
WHERE enrollments IS NOT NULL
ORDER BY event_date, experiment_group;
