resource "aws_sns_topic" "alerts" {
    name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
    topic_arn = aws_sns_topic.alerts.arn
    protocol = "email"
    endpoint = var.aws_email
}

resource "aws_cloudwatch_metric_alarm" "amb_5xx" {
    alarm_name = "${var.project_name}-high-5xx"
    comparison_operator = "GreaterThanThreshold"
    evaluation_periods = 2
    metric_name = "HTTPCode_Target_5XX_Count"
    namespace = "AWS/ApplicationELB"
    period = 300
    statistic = "Sum"
    threshold = 10
    alarm_description = "More than 10 5xx errors in 5 minutes"

    dimensions = {
        LoadBalancer = aws_lb.main.arn_suffix
    }

    alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ecs_app_running" {
    alarm_name = "${var.project_name}-app-not-running"
    comparison_operator = "LessThanThreshold"
    evaluation_periods = 2
    metric_name = "RunningTaskCount"
    namespace = "ECS/ContainerInsights"
    period = 60
    statistic = "Average"
    threshold = 1
    alarm_description = "App service has no running tasks"

    dimensions = {
        ClusterName = aws_ecs_cluster.main.name 
        ServiceName = aws_ecs_service.app.name 
    }

    alarm_actions = [aws_sns_topic.alerts.arn]
}

