# ---- Tiggers lambda and unloads daily data into s3 bucket ----
resource "aws_cloudwatch_event_rule" "client_event_rule" {
  for_each            = local.lambdaEventTrigger
  name                = "${each.value.event_name}-${local.env}"
  description         = each.value.description
  schedule_expression = each.value.schedule_expression
}

resource "aws_cloudwatch_event_target" "client_event_target" {
  for_each = local.lambdaEventTrigger
  rule     = aws_cloudwatch_event_rule.client_event_rule[each.key].id
  arn      = aws_lambda_function.client_lambda[each.key].arn
}

resource "aws_sns_topic" "client_notifications" {
  for_each = local.clientLambda
  name     = "data-${each.key}-rearc"
}

resource "aws_sns_topic_subscription" "client_email" {
  for_each  = local.clientLambda
  topic_arn = aws_sns_topic.client_notifications[each.key].arn
  protocol  = "email"
  endpoint  = "leon.tan004@gmail.com"
}

# SQS Queue to from S3
# Dead letter queue
resource "aws_sqs_queue" "client_dlq_events" {
  for_each = local.lambdaSQSTrigger
  name     = "rearc-${each.key}-dlq-events"
}

# Main queue
resource "aws_sqs_queue" "client_sqs_events" {
  for_each                   = local.lambdaSQSTrigger
  name                       = "rearc-${each.key}-sqs-events-${local.env}"
  visibility_timeout_seconds = 360
  message_retention_seconds  = 345600
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.client_dlq_events[each.key].arn
    maxReceiveCount     = 5
  })
}

# S3 -> SQS notification (filters ensure ONLY the census JSON triggers)
resource "aws_s3_bucket_notification" "client_s3_sqs" {
  for_each = local.clientData
  bucket   = aws_s3_bucket.client_s3_bucket[each.key].id

  queue {
    queue_arn     = aws_sqs_queue.client_sqs_events["analytics"].arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = each.value.s3_census_key
    filter_suffix = ".json"
  }

  depends_on = [aws_sqs_queue_policy.client_queue_policy["analytics"]]
}

resource "aws_lambda_event_source_mapping" "census_sqs_to_analytics" {
  for_each                           = local.lambdaSQSTrigger
  event_source_arn                   = aws_sqs_queue.client_sqs_events[each.key].arn
  function_name                      = aws_lambda_function.client_lambda["analytics"].arn
  enabled                            = true
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5
}