# Rearc Data Quest – Data Pipeline Project
## Overview
This project implements the 4-part Rearc Data Quest challenge using AWS services, Python, Terraform, and S3.
The pipeline ingests public datasets, processes them into clean outputs, and stores results in S3, with automation via AWS Lambda and event triggers.

## Project Structure

```tree
.
├── build
│   ├── client_bls_lambda.zip
│   └── client_rearc_lambda.zip
├── Dockerfile
├── layers
│   ├── analytics_layer.zip
│   └── api_layer.zip
├── requirements.txt
├── src
│   ├── __init__.py
│   ├── __pycache__
│   ├── analytics
│   │   └── analytics_rearc_lambda.py
│   ├── analytics.ipynb
│   ├── archive
│   │   ├── __init__.py
│   │   ├── analytics.py
│   │   ├── bls.py
│   │   └── census.py
│   └── functions
│       ├── __init__.py
│       └── client_rearc_lambda.py
└── terraform
    ├── containers.tf
    ├── events.tf
    ├── iam.tf
    ├── main.tf
    ├── provider.tf
    ├── terraform.tfstate
    ├── terraform.tfstate.backup
    ├── test
    └── variables.tf
```
