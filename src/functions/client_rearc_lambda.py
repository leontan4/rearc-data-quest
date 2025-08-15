import os, boto3, requests, logging, json
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional, Any
from requests import Session
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin
from email.utils import parsedate_to_datetime
from requests.exceptions import RequestException
from botocore.exceptions import ClientError

# CONFIG
UTC_DATE      = datetime.now(timezone.utc).date().isoformat()
S3_BUCKET     = os.environ.get("s3_bucket")
S3_BLS        = os.environ.get("s3_bls_key")
S3_CENSUS_KEY = os.environ.get("s3_census_key")
S3_CENSUS     = f"{S3_CENSUS_KEY}{UTC_DATE}/census.json"
BLS_URL       = os.environ.get("bls_url")
CENSUS_URL    = os.environ.get("census_url")
USER_AGENT    = os.environ.get("user_agent")

# Initiate s3
s3_client = boto3.client("s3")
sns_client = boto3.client("sns")

# Initiate logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def handler(event, context) -> Dict[str, Any]:
    res = []

    try:
        # BLS session
        bls_session = create_session(True)
        bls_res = import_to_s3(session=bls_session)
        res.append({"BLS": bls_res})

        # Census session
        census_session = create_session(False)
        payload = get_population(census_session)
        validate_payload(payload)
        census_res = import_to_s3(payload=payload)
        res.append({"Census": census_res})

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Import for BLS and census are complete",
                "results": res
            })
        }

    except Exception as err:
        logger.error(f"Handler failed: {err}")

        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Handler failed",
                "error": str(err)
            })
        }

def create_session(is_bls: bool) -> Session:
    """Create and configure a requests.Session for Census or BLS"""

    # Initial params for header later
    params = {
        "User-Agent": USER_AGENT,
        "Referer": BLS_URL if is_bls else ""
    }

    session = requests.Session()
    session.headers.update(params)

    return session

def check_source(session: Session, url: str) -> Tuple[Optional[int], Optional[datetime]]:
    """Check size to compare if there are any changes or not"""

    response = session.head(url, timeout=10)
    response.raise_for_status()

    # If there are changes in content then we assign size to something, else return None
    size = response.headers.get("Content-Length")
    size = int(size) if size and size.isdigit() else None

    # If there are changes in dates then we assigned changes in lm, else return None
    last = response.headers.get("Last-Modified")
    last = (parsedate_to_datetime(last) if last else None)

    return size, last

def get_population(session: Session) -> dict:
    """Extract census api date"""
    res = session.get(CENSUS_URL, timeout=20)
    res.raise_for_status()
    return res.json()

def validate_payload(payload: dict) -> dict:
    """Validate census api data"""
    if not isinstance(payload, dict):
        raise ValueError("Payload is not a dictionary")

    if "data" not in payload or not payload["data"]:
        raise ValueError("No data found in payload")
    return payload

def import_to_s3(*, session: Session = None, payload: dict = None) -> Dict[str, Any]:
    """Upload census or bls files to S3 bucket"""

    try:
        if payload:
            try:
                obj = s3_client.head_object(Bucket=S3_BUCKET, Key=S3_CENSUS)
                logger.info(f"Census data exists in {S3_BUCKET}")
            except ClientError as e:
                logger.info(f"Payload does not exists in {S3_BUCKET}")

            body = json.dumps(payload).encode("utf-8")

            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=S3_CENSUS,
                Body=body,
                ContentType="application/json"
            )
            logger.info("Successfully uploaded census data")
            return {
                "statusCode": 200,
                "body": "Census data uploaded"
            }

        elif session:
            response = session.get(BLS_URL, timeout=20)
            response.raise_for_status()
            soup = bs(response.text, "html.parser")

            seen_file = set()
            stats = {
                "uploaded": 0,
                "skipped": 0,
                "deleted": 0,
                "errors": 0,
            }

            for links in soup.select("a[href]"):
                href = links["href"]

                if not href.startswith("/pub/time.series/pr/pr."):
                    continue

                file_name = href.split("/")[-1]
                file_url = urljoin(BLS_URL, file_name)
                s3_key = f"{S3_BLS}/{file_name}"
                seen_file.add(file_name)

                # Retrieving size and last modified from source
                try:
                    src_size, src_last = check_source(session, file_url)
                except RequestException as e:
                    logger.error("Size and last modified not retrieved")
                    stats["errors"] += 1
                    continue

                # Retrieving size and last modified from S3
                try:
                    obj = s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
                    dst_size = obj["ContentLength"]
                    dst_last = obj["LastModified"]

                    if ((src_size is not None and dst_size == src_size) or
                        (src_last and dst_last and src_last <= dst_last)):
                        logger.info(f"No changes for {file_name}")
                        stats["skipped"]+= 1
                        continue
                except ClientError as e:
                    logger.info(f"{file_name} not found in {S3_BUCKET}")
                    stats["errors"] += 1

                try:
                    with session.get(file_url, stream=True, timeout=20) as res:
                        res.raise_for_status()
                        s3_client.upload_fileobj(res.raw, S3_BUCKET, s3_key)
                        stats["uploaded"] += 1
                        logger.info(f"Uploading {file_name} to {S3_BUCKET}")

                except RequestException as e:
                    logger.error(f"Not able to upload file: {e}")
                    stats["errors"] += 1

            delete_files(seen_file, stats)
            return {
                "statusCode": 200,
                "body": "BLS files uploaded"
            }
        else:
            return {
                "statusCode": 400,
                "body": "No payload or session provided"
            }

    except Exception as err:
        err_message = f"Error importing files into S3 bucket: {err}"
        logger.error(err_message)

        try:
            sns_params = {
                'TopicArn': os.environ.get("sns_topic_arn"),
                'Message': f"{err_message}: {err}",
                'Subject': "Importing BLS Data to S3"
            }

            sns_result = sns_client.publish(
                TopicArn=os.environ.get("sns_topic_arn"),
                Message=err_message,
                Subject="Importing BLS/Census Data to S3"
            )
            logger.info(f"SNS notification sent: {sns_result}")

        except Exception as sns_err:
            logger.error(f"Failed to send SNS notification: {sns_err}")

            return {
                'statusCode': 500,
                'body': f"Failed to send SNS notification: {sns_err}"
            }

        return {
            "statusCode": 500,
            "body": err_message
        }

def delete_files(seen_file: set, stats: dict) -> None:
    """Delete from S3 if source does not match"""

    files_to_delete = []

    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_BLS)

        for obj in response.get("Contents", []):
            key = obj["Key"]
            file_name = key.split("/")[-1]

            if file_name not in seen_file:
                files_to_delete.append({"Key": key})

        if files_to_delete:
            s3_client.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": files_to_delete})
            for obj in files_to_delete:
                logger.info(f"DELETED: {obj['Key']}")
                stats["deleted"] += 1

    except ClientError as e:
        logger.error(f"Error in deleting files: {e}")
        stats["errors"] += 1

def list_source_files(is_bls: bool) -> None:
    """Return existing files in S3"""
    s3_key = S3_BLS if is_bls else S3_CENSUS_KEY

    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=s3_key)

        for prefix in response.get("Contents", []):
            logger.info(prefix["Key"])

    except Exception as e:
        logger.info(f"Error listing s3 objects: {e}")
