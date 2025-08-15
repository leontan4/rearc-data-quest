# Rearc Data Quest – Data Pipeline Project
## Overview
This project implements the 4-part Rearc Data Quest challenge using AWS services, Python, Terraform, and S3.
The pipeline ingests public datasets, processes them into clean outputs, and stores results in S3, with automation via AWS Lambda and event triggers.

---

## Project Structure
```tree
.
├── build
│   ├── client_bls_lambda.zip
│   └── client_rearc_lambda.zip
├── Dockerfile
├── requirements.txt
├── src
│   ├── analytics
│   │   └── analytics_rearc_lambda.py
│   ├── analytics.ipynb
│   ├── archive
│   │   ├── analytics.py
│   │   ├── bls.py
│   │   └── census.py
│   └── functions
│       └── client_rearc_lambda.py
└── terraform
    ├── containers.tf
    ├── events.tf
    ├── iam.tf
    ├── main.tf
    ├── provider.tf
    └── variables.tf
```
## Pipeline Flow
### **Part 1 – Data Ingestion (BLS + Census data)**

- Public datasets are downloaded using Python and loaded into S3.
- Stored in S3 bucket:
  **S3 URI (Census)**: `s3://rearc-raw-bucket-dev/census/2025-08-15/census.json`
  **S3 URI (BLS)**: `s3://rearc-raw-bucket-dev/bls/pr/pr.data.0.Current`
  **S3 URI (Analytics)**: `s3://rearc-raw-bucket-dev/analytics/2025-08-15/bls_census_stats.parquet`

---

### **Part 2 – Lambda Clients**
- **AWS Lambda** fetches dataset updates from the Rearc API.
- Packaged in `client_rearc_lambda.zip` and deployed using Terraform (later was containerized with ECR).
- The original functions can be found in `../src/archive/bls.py` and `../src/archive/census.py`
- I combined the `census` and `bls` function into one lambda (will be explain in Part 4)

----

### **Part 3 – Data Analysis**
- Jupyter Notebook (`analytics.ipynb`) reads data from S3.
- Processes data using **Pandas/Numpy** and generates summary stats by merging BLS and Census data.
- It is then output to `s3://rearc-raw-bucket-dev/analytics/` as a praquet file.
- The python function can be found at `../src/archive/analytics.py`.
- The Jupyter Notebook is at `../src/analytics.ipynb`.
- The analysis also has a lambda function and will be explain further in Part 4.

---

### **Part 4 – Infrastructure as Code**
- **Terraform** provisions:
  - **Amazon S3**:  
  - Raw and processed data storage for `bls`, `census` and `analytics`.  
  - Optional bucket policy for public read access has been disabled and should have public access (Example image below).
  - <img width="1381" height="979" alt="image" src="https://github.com/user-attachments/assets/cf9cc221-af23-4d71-809c-4997ebae7eed" />
- **AWS Lambda Functions**:
  - For data retrieval, processing, and analytics tasks.  
  - Packaged as `.zip` initially and decided to built as container images (see `Dockerfile` for build process) to further automate the process and increase library memory limitation.
  - The other reason we use ECR is because lambda layer has a certain limitation such as layer size limit and runtime constraints. Heavy python libraries such as pandas, numpy or scikit-learn can easily exceed limit when packaged with dependencies.
  - Ingestion (BLS and Census) lambda function can be found in `../src/functions/client_rearc_lambda.py`
  - Analytics lambda function can be found in `../src/functions/analytics_rearc_lambda.py`.
- **AWS SQS**:  
  - Message queue for event-driven Lambda execution.
- **Amazon EventBridge**:  
  - Scheduled triggers for periodic Lambda runs.  
- **IAM Roles & Policies**:  
  - Grant least-privilege access to AWS services.  

**Deployment:**  
```bash
cd terraform
terraform init
terraform plan
terraform apply
  - S3 buckets
  - IAM roles/policies
  - Lambda functions
  - Event triggers (S3 → Lambda)
  - Bucket policy for public read
```

---

### **Future Improvements**
While the current implementation successfully completes all required parts of the project, we can potentiall enhance scalability, automation, and maintainability in future iterations for thisd pipeline:

1. **Automated CI/CD with AWS CodeBuild & CodePipeline**
- Set up a `CI/CD` pipeline that automatically builds, tests, and deploys new Lambda container images to ECR whenever changes are pushed to the GitHub repository.
- This would reduce manual deployment steps and improve developer productivity.

2. **Container Orchestration with Amazon EKS (Kubernetes)**
- Migrate heavy workloads to Kubernetes clusters on Amazon EKS for better scalability and load balancing.
- This is especially useful if multiple parallel processing jobs are required like extracting BLS and census data at the same time.

3. **Data Workflow Management with AWS Step Functions**
- Replace simple event triggers with Step Functions for more complex workflows, error handling, and retries between Lambda functions.
- This would improve resilience and make the pipeline easier to monitor and debug.
