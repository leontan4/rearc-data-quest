import json, boto3, requests
from datetime import date
from requests import Session
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
S3_BUCKET = "rearc-raw-bucket-dev"
S3_PREFIX = f"census/{date.today().isoformat()}/census.json"
API_URL = "https://honolulu-api.datausa.io/tesseract/data.jsonrecords?cube=acs_yg_total_population_1&drilldowns=Year%2CNation&locale=en&measures=Population"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36 "
    "(leon.tan004@gmail.com)"
)

def make_session() -> Session:
    """Create and configure a requests.Session for Census"""
    # Initial params for header later
    params = {
        "User-Agent": USER_AGENT,
    }

    session = requests.Session()
    session.headers.update(params)

    return session

def get_population(session: Session) -> dict:
    """Extract  census api date"""
    res = session.get(API_URL, timeout=20)
    res.raise_for_status()
    return res.json()

def validate_payload(payload: dict) -> dict:
    """Validate census api data"""
    if not isinstance(payload, dict):
        raise ValueError("Payload is not a dictionary")

    if "data" not in payload or not payload["data"]:
        raise ValueError("No data found in payload")
    return payload

def import_to_s3(s3_bucket: str, s3_key: str, payload: dict) -> None:

    try:
        obj = s3.head_object(Bucket=s3_bucket, Key=s3_key)
        print(f"Census data exist in {s3_bucket}")
        return
    except ClientError as e:
        print(f"Payload does not exists in {s3_bucket}")

    body = json.dumps(payload).encode("utf-8")

    s3.put_object(
        Bucket=s3_bucket,
        Key=s3_key,
        Body=body,
        ContentType="application/json"
    )
    print("Successfully uploaded census data")

def main():
    session = make_session()
    payload = get_population(session)
    validate_payload(payload)
    import_to_s3(S3_BUCKET, S3_PREFIX, payload)

if __name__ == "__main__":
    main()
