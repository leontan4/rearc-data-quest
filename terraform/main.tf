locals {
  env              = "dev"
  lambda_image_uri = "${aws_ecr_repository.client_image["rearc"].repository_url}@${data.aws_ecr_image.shared.image_digest}"

  clientData = {
    rearc = {
      s3_bucket     = "rearc-raw-bucket"
      s3_bls_key    = "bls/pr"
      s3_census_key = "census/"
      bls_url       = "https://download.bls.gov/pub/time.series/pr/"
      census_url    = "https://honolulu-api.datausa.io/tesseract/data.jsonrecords?cube=acs_yg_total_population_1&drilldowns=Year%2CNation&locale=en&measures=Population"
    }
  }

  clientLambda = {
    ingestion = {
      function_name       = "rearc-ingestion"
      command             = "functions.client_rearc_lambda.handler"
      event_type          = "eventbridge"
      event_trigger       = true
      package_type        = "Image"
      event_name          = "rearc_daily_ingestion_trigger"
      description         = "Trigger lambda to extract data and load to S3 bucket"
      schedule_expression = "cron(0 14 * * ? *)"
    }

    analytics = {
      function_name = "rearc-analytics"
      command       = "analytics.analytics_rearc_lambda.handler"
      event_type    = "sqs"
      event_trigger = false
      package_type  = "Image"
    }
  }

  lambdaEventTrigger = {
    for lambda, clientData in local.clientLambda : lambda => clientData if clientData.event_trigger
  }

  lambdaSQSTrigger = {
    for lambda, clientData in local.clientLambda : lambda => clientData if !clientData.event_trigger
  }

  user_agent = join("", [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) ",
    "AppleWebKit/537.36 (KHTML, like Gecko) ",
    "Chrome/127.0.0.0 Safari/537.36 ",
    "(leon.tan004@gmail.com)",
  ])
}

# Creating S3 bucket
resource "aws_s3_bucket" "client_s3_bucket" {
  for_each = local.clientData
  bucket   = "${each.value.s3_bucket}-${local.env}"
  tags = {
    Name        = "${upper(each.key)} Bucket"
    Environment = local.env
  }
}

# Mking S3 bucket public
resource "aws_s3_bucket_public_access_block" "client_s3_public_access" {
  for_each                = local.clientData
  bucket                  = aws_s3_bucket.client_s3_bucket[each.key].id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = false
  restrict_public_buckets = false
}

# Define and setup lambda
resource "aws_lambda_function" "client_lambda" {
  for_each      = local.clientLambda
  function_name = each.value.function_name
  package_type  = each.value.package_type
  image_uri     = local.lambda_image_uri
  role          = aws_iam_role.client_iam_lambda_role[each.key].arn

  memory_size = 1024
  timeout     = 300

  architectures = ["arm64"]

  image_config {
    command = [
      each.value.command
    ]
  }

  ephemeral_storage {
    size = 1024
  }

  logging_config {
    log_format = "Text"
  }

  environment {
    variables = {
      "client_name" : each.key,
      "s3_bucket" : "${local.clientData.rearc.s3_bucket}-${local.env}"
      "s3_bls_key" : local.clientData.rearc.s3_bls_key
      "s3_census_key" : local.clientData.rearc.s3_census_key
      "bls_url" : local.clientData.rearc.bls_url
      "census_url" : local.clientData.rearc.census_url
      "user_agent" : local.user_agent
      "sns_topic_arn" : aws_sns_topic.client_notifications[each.key].arn
    }
  }
}

# Attaching CloudWatch permission to lambda to monitor logs
resource "aws_cloudwatch_log_group" "client_lambda_cloudwatch_log" {
  for_each          = local.clientLambda
  name              = "/aws/lambda/${aws_lambda_function.client_lambda[each.key].function_name}"
  retention_in_days = 14
}

# # Attaching Event Bridge trigger to lambda and load into S3 buckets
# # NOTE: statement_id should be unique if triggering for multiple lambdas
resource "aws_lambda_permission" "client_lambda_trigger" {
  for_each      = local.lambdaEventTrigger
  statement_id  = "AllowExecutionFromEventBridge-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.client_lambda[each.key].arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.client_event_rule[each.key].arn
}
