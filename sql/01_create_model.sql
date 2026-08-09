DROP VIEW IF EXISTS daily_metrics;
DROP VIEW IF EXISTS group_summary;

CREATE VIEW daily_metrics AS
SELECT
    event_date,
    experiment_group,
    pageviews,
    clicks,
    enrollments,
    payments,
    1.0 * clicks / pageviews AS click_through_rate,
    CASE WHEN enrollments IS NOT NULL THEN 1.0 * enrollments / clicks END AS gross_conversion,
    CASE WHEN payments IS NOT NULL THEN 1.0 * payments / clicks END AS net_conversion,
    CASE WHEN payments IS NOT NULL THEN 1.0 * payments / enrollments END AS retention
FROM experiment_daily;

CREATE VIEW group_summary AS
SELECT
    experiment_group,
    SUM(pageviews) AS pageviews,
    SUM(clicks) AS clicks,
    SUM(CASE WHEN enrollments IS NOT NULL THEN pageviews ELSE 0 END) AS mature_pageviews,
    SUM(CASE WHEN enrollments IS NOT NULL THEN clicks ELSE 0 END) AS mature_clicks,
    SUM(enrollments) AS enrollments,
    SUM(payments) AS payments,
    1.0 * SUM(clicks) / SUM(pageviews) AS click_through_rate,
    1.0 * SUM(enrollments) / SUM(CASE WHEN enrollments IS NOT NULL THEN clicks ELSE 0 END) AS gross_conversion,
    1.0 * SUM(payments) / SUM(CASE WHEN payments IS NOT NULL THEN clicks ELSE 0 END) AS net_conversion,
    1.0 * SUM(payments) / SUM(enrollments) AS retention
FROM experiment_daily
GROUP BY experiment_group;
