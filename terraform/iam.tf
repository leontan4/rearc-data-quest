# Lambda IAM policy document creation
data "aws_iam_policy_document" "lambda_policy_document" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

# Creating Lambda IAM role
resource "aws_iam_role" "client_iam_lambda_role" {
  for_each           = local.clientLambda
  name               = "${each.key}_iam_lambda_role"
  assume_role_policy = data.aws_iam_policy_document.lambda_policy_document.json
}

# CloudWatch IAM policy document creation
data "aws_iam_policy_document" "lambda_cloudwatch_policy" {
  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["arn:aws:logs:*:*:*"]
  }
}

# Defining CloudWatch permission for lambda logs
resource "aws_iam_role_policy" "client_s3_lambda_logging" {
  for_each = local.clientLambda
  name     = "s3_lambda_cloudwatch_logging"
  role     = aws_iam_role.client_iam_lambda_role[each.key].name
  policy   = data.aws_iam_policy_document.lambda_cloudwatch_policy.json
}

# S3 IAM policy document creation
# Providing full S3 access to lambda, example: ["create", "put", "delete", "read", "write"]
data "aws_iam_policy_document" "s3_bucket_lambda_policy_document" {
  for_each = local.clientLambda

  statement {
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]
    resources = [
      aws_s3_bucket.client_s3_bucket["rearc"].arn,
      "${aws_s3_bucket.client_s3_bucket["rearc"].arn}/*"
    ]
  }
}

# Providing S3 access to lambda
resource "aws_iam_role_policy" "s3_lambda_role_policy" {
  for_each = local.clientLambda
  name     = "${each.key}_s3_lambda_role"
  role     = aws_iam_role.client_iam_lambda_role[each.key].id
  policy   = data.aws_iam_policy_document.s3_bucket_lambda_policy_document[each.key].json
}

# SNS Publish Policy for Lambda
data "aws_iam_policy_document" "client_lambda_sns_policy" {
  for_each = local.clientLambda
  statement {
    effect  = "Allow"
    actions = ["sns:Publish"]
    resources = [
      aws_sns_topic.client_notifications[each.key].arn
    ]
  }
}

# Attach the SNS Policy to Lambda Role
resource "aws_iam_role_policy" "client_lambda_sns_publish_policy" {
  for_each = local.clientLambda
  name     = "${each.key}_lambda_sns_publish_policy"
  role     = aws_iam_role.client_iam_lambda_role[each.key].id
  policy   = data.aws_iam_policy_document.client_lambda_sns_policy[each.key].json
}

# SQS notification policy from S3 to SQS
data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "client_s3_sqs_policy" {
  for_each = local.lambdaSQSTrigger
  statement {
    sid     = "AllowS3SendMessage"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    resources = [
      aws_sqs_queue.client_sqs_events[each.key].arn
    ]

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values = [
        aws_s3_bucket.client_s3_bucket["rearc"].arn
      ]
    }
  }
}

resource "aws_sqs_queue_policy" "client_queue_policy" {
  for_each  = local.lambdaSQSTrigger
  queue_url = aws_sqs_queue.client_sqs_events[each.key].id
  policy    = data.aws_iam_policy_document.client_s3_sqs_policy[each.key].json
}


data "aws_iam_policy_document" "client_analytics_lambda_sqs_document" {
  for_each = local.lambdaSQSTrigger

  statement {
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ChangeMessageVisibility",
      "sqs:GetQueueUrl"
    ]
    resources = [aws_sqs_queue.client_sqs_events[each.key].arn]
  }
}

resource "aws_iam_role_policy" "client_analytics_lambda_sqs_policy" {
  for_each = local.lambdaSQSTrigger
  name     = "${each.key}_lambda_sqs_policy"
  role     = aws_iam_role.client_iam_lambda_role["analytics"].id
  policy   = data.aws_iam_policy_document.client_analytics_lambda_sqs_document[each.key].json
}
