# import boto3, requests, logging
# from requests import Session
# from bs4 import BeautifulSoup as bs
# from urllib.parse import urljoin
# from email.utils import parsedate_to_datetime
# from requests.exceptions import RequestException
# from botocore.exceptions import ClientError
#
# # CONFIG
# S3_BUCKET = "rearc-raw-bucket-dev"
# S3_PREFIX = "bls/pr"
# BASE_URL = "https://download.bls.gov/pub/time.series/pr/"
# USER_AGENT = (
#     "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
#     "AppleWebKit/537.36 (KHTML, like Gecko) "
#     "Chrome/127.0.0.0 Safari/537.36 "
#     "(leon.tan004@gmail.com)"
# )
#
# # Initiate s3
# s3 = boto3.client("s3")
#
# # Initiate logger
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(levelname)s - %(message)s"
# )
# logger = logging.getLogger(__name__)
#
# def check_source(session: Session, url: str):
#     """Check size to compare if there are any changes or not"""
#     response = session.head(url, timeout=10)
#     response.raise_for_status()
#
#     # If there are changes in content then we assign size to something, else return None
#     size = response.headers.get("Content-Length")
#     size = int(size) if size and size.isdigit() else None
#
#     # If there are changes in dates then we assigned changes in lm, else return None
#     last = response.headers.get("Last-Modified")
#     last = (parsedate_to_datetime(last) if last else None)
#
#     return size, last
#
# def make_session() -> Session:
#     """Create and configure a requests.Session for BLS fetching"""
#
#     # Initial params for header later
#     params = {
#         "User-Agent": USER_AGENT,
#         "Referer": BASE_URL
#     }
#
#     session = requests.Session()
#     session.headers.update(params)
#
#     return session
#
# def import_to_s3(session: Session, s3_bucket: str, key: str) -> str:
#     """Upload files to S3 bucket"""
#     response = session.get(BASE_URL, timeout=20)
#     response.raise_for_status()
#     soup = bs(response.text, "html.parser")
#
#     seen_file = set()
#     stats = {
#         "uploaded": 0,
#         "skipped": 0,
#         "deleted": 0,
#         "errors": 0,
#     }
#
#     for links in soup.select("a[href]"):
#         href = links["href"]
#
#         if not href.startswith("/pub/time.series/pr/pr."):
#             continue
#
#         file_name = href.split("/")[-1]
#         file_url = urljoin(BASE_URL, file_name)
#         s3_key = f"{key}/{file_name}"
#         seen_file.add(file_name)
#
#         # Retrieving size and last modified from source
#         try:
#             src_size, src_last = check_source(session, file_url)
#         except RequestException as e:
#             print("Size and last modified not retrieved")
#             stats["errors"] += 1
#             continue
#
#         # Retrieving size and last modified from S3
#         try:
#             obj = s3.head_object(Bucket=s3_bucket, Key=s3_key)
#             dst_size = obj["ContentLength"]
#             dst_last = obj["LastModified"]
#
#             if ((src_size is not None and dst_size == src_size) or
#                 (src_last and dst_last and src_last <= dst_last)):
#                 print(f"There are no changes")
#                 stats["skipped"]+= 1
#                 continue
#         except ClientError as e:
#             print(f"{file_name} not found in {s3_bucket}")
#             stats["errors"] += 1
#
#         try:
#             with session.get(file_url, stream=True, timeout=20) as res:
#                 res.raise_for_status()
#                 s3.upload_fileobj(res.raw, s3_bucket, s3_key)
#                 stats["uploaded"] += 1
#                 print(f"Uploading {file_name} to {s3_bucket}")
#         except RequestException as e:
#             print(f"Not able to upload file: {e}")
#             stats["errors"] += 1
#             continue
#
#     delete_files(s3_bucket, s3_key, seen_file, stats)
#
#     return "File successfully uploaded to S3"
#
# def delete_files(s3_bucket: str, s3_key: str, seen_file: set, stats: dict) -> None:
#     """Delete from S3 if source does not match"""
#
#     files_to_delete = []
#
#     try:
#         response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=s3_key)
#
#         for obj in response.get("Contents", []):
#             key = obj["Key"]
#             file_name = key.split("/")[-1]
#
#             if file_name not in seen_file:
#                 files_to_delete.append({"Key": key})
#
#         if files_to_delete:
#             s3.delete_objects(Bucket=s3_bucket, Delete={"Objects": files_to_delete})
#             for obj in files_to_delete:
#                 print(f"DELETED: {obj['Key']}")
#                 stats["deleted"] += 1
#
#     except ClientError as e:
#         print(f"Error in deleting files: {e}")
#         stats["errors"] += 1
#
# def list_source_files(s3_bucket: str):
#     """Return existing files in S3"""
#
#     try:
#         response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=S3_PREFIX)
#
#         for prefix in response.get("Contents", []):
#             print(prefix["Key"])
#
#     except Exception as e:
#         print(f"Error listing s3 objects: {e}")
#
#
# def handler(even, context):
#     session = make_session()
#     import_to_s3(session, S3_BUCKET, S3_PREFIX)
#     # list_source_files(S3_BUCKET)
